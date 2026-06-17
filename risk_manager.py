"""
risk_manager.py — Advanced risk controls.
  1. Trailing stops — moves stop up as price rises, locking in gains
  2. ATR-based stop sizing — volatility-proportional stops
  3. Daily max loss kill switch — halts trading if daily loss exceeds limit
  4. Drawdown guard — reduces position sizes after significant drawdown
"""

import json
import logging
import os
from datetime import datetime, date, timezone

import yfinance as yf

import config

log = logging.getLogger(__name__)

DATA_DIR        = os.path.join(os.path.dirname(__file__), "data")
TRAILING_FILE   = os.path.join(DATA_DIR, "trailing_stops.json")
DAILY_LOSS_FILE = os.path.join(DATA_DIR, "daily_loss.json")


# ── 1. ATR calculation (pure Python) ─────────────────────────────────────────

def calc_atr(symbol: str, period: int = 14) -> float:
    """Fetch recent OHLC and compute ATR. Returns ATR in price units."""
    try:
        hist = yf.Ticker(symbol).history(period=f"{period + 5}d", interval="1d")
        if hist.empty or len(hist) < period:
            return 0.0
        highs  = hist["High"].tolist()
        lows   = hist["Low"].tolist()
        closes = hist["Close"].tolist()
        trs = []
        for i in range(1, len(closes)):
            trs.append(max(
                highs[i]  - lows[i],
                abs(highs[i]  - closes[i-1]),
                abs(lows[i]   - closes[i-1]),
            ))
        return sum(trs[-period:]) / period
    except Exception as e:
        log.debug(f"ATR calc failed for {symbol}: {e}")
        return 0.0


def atr_stop_distance(symbol: str, multiplier: float = 2.0) -> float:
    """
    Returns the stop-loss distance in price units based on ATR.
    Default: 2x ATR — wide enough to not get stopped by noise,
    tight enough to limit losses on a real move against you.
    """
    atr = calc_atr(symbol)
    return atr * multiplier


# ── 2. Trailing stop manager ──────────────────────────────────────────────────

def _load_trailing() -> dict:
    if os.path.exists(TRAILING_FILE):
        try:
            with open(TRAILING_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}   # symbol → {"entry": price, "highest": price, "stop": price}


def _save_trailing(data: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(TRAILING_FILE, "w") as f:
        json.dump(data, f, indent=2)


def register_trailing_stop(symbol: str, entry_price: float):
    """Call when a BUY is placed. Initialises the trailing stop."""
    atr  = calc_atr(symbol)
    dist = atr * config.TRAILING_STOP_ATR_MULT if atr > 0 else entry_price * config.STOP_LOSS_PCT
    stop = entry_price - dist

    data = _load_trailing()
    data[symbol] = {
        "entry":   round(entry_price, 4),
        "highest": round(entry_price, 4),
        "stop":    round(stop, 4),
        "atr":     round(atr, 4),
        "dist":    round(dist, 4),
    }
    _save_trailing(data)
    log.info(f"  🎯 Trailing stop set: {symbol} entry=${entry_price:.2f} "
             f"stop=${stop:.2f} (ATR×{config.TRAILING_STOP_ATR_MULT}={dist:.2f})")


def update_trailing_stops(current_prices: dict) -> list[str]:
    """
    Update trailing stops for all tracked positions.
    Returns list of symbols that have been stopped out.
    """
    data      = _load_trailing()
    stopped   = []
    changed   = False

    for symbol, ts in list(data.items()):
        price = current_prices.get(symbol) or current_prices.get(symbol.replace("/",""))
        if not price:
            continue

        new_high = max(ts["highest"], price)
        new_stop = new_high - ts["dist"]

        if new_high > ts["highest"]:
            old_stop = data[symbol]["stop"]
            log.info(f"  📈 Trailing stop raised: {symbol} "
                     f"high=${new_high:.2f} → stop=${new_stop:.2f}")
            data[symbol]["highest"] = round(new_high, 4)
            data[symbol]["stop"]    = round(new_stop, 4)
            changed = True
            try:
                import alerts
                alerts.trailing_stop_raised(symbol, old_stop, new_stop, new_high)
            except Exception:
                pass

        # Check if stopped out
        if price <= data[symbol]["stop"]:
            log.info(f"  🛑 Trailing stop triggered: {symbol} "
                     f"price=${price:.2f} ≤ stop=${data[symbol]['stop']:.2f}")
            stopped.append(symbol)
            del data[symbol]
            changed = True

    if changed:
        _save_trailing(data)

    return stopped


def remove_trailing_stop(symbol: str):
    """Remove trailing stop when position is closed."""
    data = _load_trailing()
    if symbol in data:
        del data[symbol]
        _save_trailing(data)


def get_trailing_stops() -> dict:
    return _load_trailing()


# ── 3. Daily max loss kill switch ─────────────────────────────────────────────

def _load_daily_loss() -> dict:
    if os.path.exists(DAILY_LOSS_FILE):
        try:
            with open(DAILY_LOSS_FILE) as f:
                data = json.load(f)
            # Reset if it's a new day
            if data.get("date") != str(date.today()):
                return {"date": str(date.today()), "loss": 0.0, "halted": False}
            return data
        except Exception:
            pass
    return {"date": str(date.today()), "loss": 0.0, "halted": False}


def _save_daily_loss(data: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DAILY_LOSS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def record_daily_pnl(pnl: float):
    """Call after every closed trade. Tracks today's cumulative P&L."""
    data = _load_daily_loss()
    data["loss"] = round(data["loss"] + pnl, 2)

    if not data["halted"] and data["loss"] <= -abs(config.MAX_DAILY_LOSS):
        data["halted"] = True
        log.warning(f"🚨 DAILY LOSS LIMIT HIT: ${data['loss']:.2f} — "
                    f"trading halted for today")
        try:
            import alerts
            alerts.daily_loss_halted(data["loss"], config.MAX_DAILY_LOSS)
        except Exception:
            pass

    _save_daily_loss(data)


def is_trading_halted() -> bool:
    """Returns True if the daily loss kill switch has fired."""
    return _load_daily_loss().get("halted", False)


def get_daily_stats() -> dict:
    return _load_daily_loss()


# ── 4. Drawdown guard ─────────────────────────────────────────────────────────

def drawdown_size_multiplier(current_value: float, start_value: float = None) -> float:
    """
    Reduce position sizes proportionally during significant drawdowns.
    >5% drawdown  → 80% of normal size
    >10% drawdown → 60% of normal size
    >15% drawdown → 40% of normal size
    >20% drawdown → 20% of normal size (near-defensive mode)
    """
    if start_value is None:
        start_value = config.VIRTUAL_CASH

    drawdown_pct = (start_value - current_value) / start_value * 100
    if drawdown_pct <= 5:
        return 1.0
    elif drawdown_pct <= 10:
        return 0.8
    elif drawdown_pct <= 15:
        return 0.6
    elif drawdown_pct <= 20:
        return 0.4
    else:
        return 0.2
