"""
backtest.py — Run the bot's strategy against historical data.
Uses only yfinance (free). No API costs.
Run directly: python backtest.py
Results saved to data/backtest_results.json and printed to console.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone, timedelta

import pandas as pd
import yfinance as yf

sys.path.insert(0, os.path.dirname(__file__))
import config
from collector import _calc_rsi, _calc_macd

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


# ── Historical data fetch ─────────────────────────────────────────────────────

def fetch_history(symbol: str, years: int) -> pd.DataFrame | None:
    """Fetch N years of daily OHLCV for a stock symbol."""
    try:
        end   = datetime.now()
        start = end - timedelta(days=years * 365)
        hist  = yf.Ticker(symbol).history(start=start, end=end, interval="1d")
        if hist.empty:
            return None
        if isinstance(hist.columns, pd.MultiIndex):
            hist.columns = hist.columns.get_level_values(0)
        hist = hist.dropna(subset=["Close"])
        return hist
    except Exception as e:
        log.warning(f"History fetch failed {symbol}: {e}")
        return None


# ── Signal generation (mirrors brain.py logic, no LLM needed) ────────────────

def generate_signals(closes: list[float]) -> list[str]:
    """
    Generate BUY/SELL/HOLD signal for each day using RSI + MACD.
    Returns a list of signals, same length as closes.
    """
    signals = ["HOLD"] * len(closes)
    for i in range(50, len(closes)):
        window = closes[:i+1]
        rsi    = _calc_rsi(window)
        macd, sig = _calc_macd(window)

        ma50      = sum(closes[i-50:i]) / 50
        ma50_prev = sum(closes[i-51:i-1]) / 50 if i >= 51 else ma50
        crossed_up  = closes[i] > ma50 and closes[i-1] <= ma50_prev
        continuation = closes[i] > ma50 and closes[i] <= ma50 * 1.03 and 52 <= rsi <= 65
        breakout    = (crossed_up or continuation) and macd > sig
        dip        = rsi < config.RSI_OVERSOLD
        if dip and breakout:
            signals[i] = "STRONG_BUY"
        elif dip or breakout:
            signals[i] = "BUY"
        elif rsi > config.RSI_OVERBOUGHT and macd < sig:
            signals[i] = "SELL"

    return signals


# ── Single-symbol backtest ────────────────────────────────────────────────────

def backtest_symbol(symbol: str, years: int = 2, capital: float = 10_000.0) -> dict:
    """
    Backtest one symbol. Returns performance metrics dict.
    """
    hist = fetch_history(symbol, years)
    if hist is None:
        return {"symbol": symbol, "error": "no data"}

    closes  = hist["Close"].tolist()
    dates   = [str(d.date()) for d in hist.index]
    signals = generate_signals(closes)

    cash     = capital
    shares     = 0.0
    peak_price = 0.0
    hold_days  = 0
    trades   = []
    equity   = []

    for i, (date, price, signal) in enumerate(zip(dates, closes, signals)):
        # SPY-style trend filter: only buy above 20-day MA
        if i >= 20:
            ma20    = sum(closes[i-20:i]) / 20
            bullish = closes[i] > ma20
        else:
            bullish = True

        if shares > 0 and price > peak_price:
            peak_price = price
        if shares > 0:
            hold_days += 1
        trailing_stop_hit = shares > 0 and peak_price > 0 and price <= peak_price * 0.85 and hold_days >= 5
        size_pct = config.MAX_POSITION_SIZE_PCT * 1.5 if signal == "STRONG_BUY" else config.MAX_POSITION_SIZE_PCT
        size_pct = min(size_pct, 1.0)
        if signal in ("BUY", "STRONG_BUY") and shares == 0 and cash > 0:
            shares = (cash * size_pct) / price
            cost   = shares * price
            cash  -= cost
            peak_price = price
            trades.append({
                "date": date, "action": "BUY",
                "price": round(price, 4), "shares": round(shares, 6),
                "value": round(cost, 2),
            })

        elif (signal == "SELL" or trailing_stop_hit) and shares > 0:
            proceeds = shares * price
            pnl      = proceeds - trades[-1]["value"] if trades else 0
            cash    += proceeds
            trades.append({
                "date": date, "action": "SELL",
                "price": round(price, 4), "shares": round(shares, 6),
                "value": round(proceeds, 2),
                "pnl":   round(pnl, 2),
                "pnl_pct": round(pnl / trades[-1]["value"] * 100, 2) if trades else 0,
            })
            shares = 0.0

        equity.append(round(cash + shares * price, 2))

    # Close any open position at end
    if shares > 0:
        final_price = closes[-1]
        proceeds    = shares * final_price
        pnl         = proceeds - trades[-1]["value"] if trades else 0
        cash       += proceeds
        trades.append({
            "date": dates[-1], "action": "SELL (end)",
            "price": round(final_price, 4), "shares": round(shares, 6),
            "value": round(proceeds, 2),
            "pnl":   round(pnl, 2),
        })
        shares = 0.0

    # Metrics
    sells      = [t for t in trades if "SELL" in t["action"] and "pnl" in t]
    wins       = [t for t in sells if t["pnl"] > 0]
    total_ret  = cash - capital
    total_pct  = total_ret / capital * 100

    # Buy & hold comparison
    bh_return  = (closes[-1] - closes[0]) / closes[0] * 100 if closes else 0

    # Max drawdown
    peak = capital
    max_dd = 0.0
    for e in equity:
        if e > peak:
            peak = e
        dd = (peak - e) / peak * 100
        if dd > max_dd:
            max_dd = dd

    # Sharpe (simplified, daily returns)
    if len(equity) > 1:
        daily_rets = [(equity[i] - equity[i-1]) / equity[i-1] for i in range(1, len(equity))]
        avg_ret  = sum(daily_rets) / len(daily_rets)
        variance = sum((r - avg_ret)**2 for r in daily_rets) / len(daily_rets)
        std_ret  = variance ** 0.5
        sharpe   = (avg_ret / std_ret * (252 ** 0.5)) if std_ret > 0 else 0
    else:
        sharpe = 0

    return {
        "symbol":          symbol,
        "years":           years,
        "start_capital":   capital,
        "end_capital":     round(cash, 2),
        "total_return":    round(total_ret, 2),
        "total_return_pct":round(total_pct, 2),
        "buy_hold_pct":    round(bh_return, 2),
        "alpha":           round(total_pct - bh_return, 2),
        "max_drawdown_pct":round(max_dd, 2),
        "sharpe_ratio":    round(sharpe, 3),
        "total_trades":    len(trades),
        "closed_trades":   len(sells),
        "win_rate":        round(len(wins) / len(sells) * 100, 1) if sells else 0,
        "avg_win":         round(sum(t["pnl"] for t in wins) / len(wins), 2) if wins else 0,
        "avg_loss":        round(sum(t["pnl"] for t in [t for t in sells if t["pnl"] <= 0])
                                 / max(len([t for t in sells if t["pnl"] <= 0]), 1), 2),
        "equity_curve":    equity[::5],   # every 5th point to keep file small
        "trades":          trades,
    }


# ── Full backtest across watchlist ────────────────────────────────────────────

def run_full_backtest() -> list[dict]:
    """Backtest all symbols in the watchlist. Saves results to data/."""
    symbols = config.STOCK_WATCHLIST   # backtest stocks only (crypto history is shorter)
    years   = config.BACKTEST_YEARS
    capital = config.BACKTEST_CAPITAL / len(symbols) if symbols else config.BACKTEST_CAPITAL

    log.info(f"📊 Starting backtest: {len(symbols)} symbols, {years} years, "
             f"${capital:,.0f} each")
    log.info("=" * 55)

    results = []
    for sym in symbols:
        log.info(f"  Testing {sym}...")
        r = backtest_symbol(sym, years, capital)
        results.append(r)
        if "error" not in r:
            alpha_str = f"{r['alpha']:+.1f}% vs B&H"
            log.info(f"    Return: {r['total_return_pct']:+.1f}%  |  "
                     f"Sharpe: {r['sharpe_ratio']:.2f}  |  "
                     f"Win: {r['win_rate']:.0f}%  |  {alpha_str}")

    # Portfolio-level summary
    valid = [r for r in results if "error" not in r]
    if valid:
        total_invested = sum(r["start_capital"] for r in valid)
        total_end      = sum(r["end_capital"] for r in valid)
        port_return    = (total_end - total_invested) / total_invested * 100

        log.info("=" * 55)
        log.info(f"📈 PORTFOLIO BACKTEST SUMMARY")
        log.info(f"   Start capital:  ${total_invested:>12,.2f}")
        log.info(f"   End capital:    ${total_end:>12,.2f}")
        log.info(f"   Total return:   {port_return:>+.2f}%")
        log.info(f"   Avg Sharpe:     {sum(r['sharpe_ratio'] for r in valid)/len(valid):.3f}")
        log.info(f"   Avg win rate:   {sum(r['win_rate'] for r in valid)/len(valid):.1f}%")
        log.info(f"   Avg max DD:     {sum(r['max_drawdown_pct'] for r in valid)/len(valid):.1f}%")
        log.info("=" * 55)

    # Save results
    os.makedirs(DATA_DIR, exist_ok=True)
    out = {
        "run_at":  datetime.now(timezone.utc).isoformat(),
        "symbols": symbols,
        "years":   years,
        "results": results,
    }
    path = os.path.join(DATA_DIR, "backtest_results.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    log.info(f"✅ Results saved → {path}")

    return results


# ── Run directly ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run_full_backtest()
