"""
alpaca_executor.py — v4: Live Alpaca paper trading.
New: short selling, inverse ETF hedging, trailing stop registration,
     daily loss kill switch integration, drawdown-aware sizing.
"""

import logging
import json
import os
from datetime import datetime, timezone

import config
import credential_manager as sec

log = logging.getLogger(__name__)
TRADE_LOG_FILE = os.path.join(os.path.dirname(__file__), "data", "trades.json")


def _client():
    from alpaca.trading.client import TradingClient
    return TradingClient(sec.alpaca_key(), sec.alpaca_secret(), paper=True)


def get_account_summary() -> dict:
    try:
        c         = _client()
        account   = c.get_account()
        positions = c.get_all_positions()
        trades    = _load_trades()
        closed    = [t for t in trades if t["action"] in ("SELL","SHORT_COVER") and "pnl" in t]
        wins      = [t for t in closed if t["pnl"] > 0]
        total_val = float(account.portfolio_value)
        start     = config.VIRTUAL_CASH

        pos_list = [{
            "symbol":         p.symbol,
            "shares":         float(p.qty),
            "side":           p.side.value if hasattr(p.side,"value") else str(p.side),
            "avg_price":      float(p.avg_entry_price),
            "current_price":  float(p.current_price),
            "market_value":   float(p.market_value),
            "unrealized_pnl": float(p.unrealized_pl),
            "unrealized_pct": float(p.unrealized_plpc) * 100,
        } for p in positions]

        return {
            "total_value":      round(total_val, 2),
            "cash":             round(float(account.cash), 2),
            "invested":         round(total_val - float(account.cash), 2),
            "total_return":     round(total_val - start, 2),
            "total_return_pct": round((total_val - start) / start * 100, 2),
            "open_positions":   len(positions),
            "total_trades":     len(trades),
            "win_rate":         round(len(wins)/len(closed)*100, 1) if closed else 0,
            "positions":        pos_list,
            "trades":           trades[-20:],
            "buying_power":     round(float(account.buying_power), 2),
        }
    except Exception as e:
        log.error(f"Account fetch failed: {e}")
        return {}


def execute_decision(decision: dict) -> dict | None:
    import market_filter as mf
    import risk_manager  as rm

    try:
        import alerts as _alerts
    except Exception:
        _alerts = None

    action = decision.get("action","HOLD")
    if action == "HOLD":
        return None

    # ── Kill switch ──
    if rm.is_trading_halted():
        log.warning(f"  🚨 {decision['symbol']}: trading halted (daily loss limit)")
        return None

    if decision.get("confidence", 0) < config.MIN_CONFIDENCE and action not in ("SHORT","BUY"):
        return None

    # ── Pre-trade filters (BUY and SHORT) ──
    if action in ("BUY","SHORT"):
        ok, reason = mf.should_trade(decision)
        if not ok:
            log.info(f"  🚫 {decision['symbol']}: {reason}")
            return None

    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums    import OrderSide, TimeInForce
    from alpaca.common.exceptions import APIError

    c      = _client()
    symbol = decision["symbol"].replace("/","")
    price  = decision.get("price") or 0

    try:
        account   = c.get_account()
        bp        = float(account.buying_power)
        port_val  = float(account.portfolio_value)

        # Drawdown-aware sizing
        dd_mult   = rm.drawdown_size_multiplier(port_val, config.VIRTUAL_CASH)

        # Regime sizing
        try:
            from regime import regime_multipliers, detect_regime
            reg, _  = detect_regime()
            r_mult  = regime_multipliers(reg).get("size_mult", 1.0)
        except Exception:
            r_mult  = 1.0

        record = None

        # ── BUY (long) ────────────────────────────────────────────────────────
        if action == "BUY":
            size_pct  = mf.position_size_pct(decision["confidence"]) * dd_mult * r_mult
            spend     = min(port_val * size_pct, bp * 0.95)
            # Alpaca minimums: $10 for crypto, $1 for stocks
            min_order = 1.0   # stocks only
            if spend < min_order:
                log.info(f"  💸 {symbol}: spend ${spend:.2f} below Alpaca minimum ${min_order}")
                return None

            positions = c.get_all_positions()
            if len(positions) >= config.MAX_OPEN_POSITIONS and \
               symbol not in [p.symbol for p in positions]:
                log.info(f"  🚫 {symbol}: max positions reached")
                return None

            order = c.submit_order(MarketOrderRequest(
                symbol=symbol, notional=round(spend,2),
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
            ))
            log.info(f"  ✅ BUY  {symbol} ${spend:.2f} ({size_pct:.1%}) | {order.id}")

            # Register trailing stop
            if price > 0:
                rm.register_trailing_stop(symbol, price)

            record = {
                "timestamp":  datetime.now(timezone.utc).isoformat(),
                "symbol":     symbol, "action": "BUY",
                "value":      round(spend,2), "price": price,
                "size_pct":   round(size_pct,4), "order_id": str(order.id),
                "confidence": decision["confidence"],
                "reasoning":  decision["reasoning"],
                "source":     decision.get("source","llm"),
            }
            mf.record_trade_time(symbol)
            _alerts.trade_executed(record)

        # ── SHORT ─────────────────────────────────────────────────────────────
        elif action == "SHORT":
            # Check we don't already have a long in this symbol
            positions = c.get_all_positions()
            held = {p.symbol: p for p in positions}
            if symbol in held and float(held[symbol].qty) > 0:
                log.info(f"  ⏭  {symbol}: have long position, skipping short")
                return None

            size_pct = mf.position_size_pct(decision["confidence"]) * dd_mult * r_mult * 0.8
            spend    = min(port_val * size_pct, bp * 0.90)
            if spend < 1.0:
                return None

            order = c.submit_order(MarketOrderRequest(
                symbol=symbol, notional=round(spend,2),
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
            ))
            log.info(f"  ✅ SHORT {symbol} ${spend:.2f} | {order.id}")

            record = {
                "timestamp":  datetime.now(timezone.utc).isoformat(),
                "symbol":     symbol, "action": "SHORT",
                "value":      round(spend,2), "price": price,
                "order_id":   str(order.id),
                "confidence": decision["confidence"],
                "reasoning":  decision["reasoning"],
                "source":     decision.get("source","llm"),
            }
            mf.record_trade_time(symbol)
            _alerts.trade_executed(record)

        # ── SELL (close long) ─────────────────────────────────────────────────
        elif action == "SELL":
            positions = c.get_all_positions()
            held = {p.symbol: p for p in positions}
            if symbol not in held:
                log.info(f"  📭 {symbol}: no position")
                return None

            pos      = held[symbol]
            proceeds = float(pos.market_value)
            pnl      = float(pos.unrealized_pl)
            pnl_pct  = float(pos.unrealized_plpc) * 100

            c.close_position(symbol)
            rm.remove_trailing_stop(symbol)
            rm.record_daily_pnl(pnl)
            log.info(f"  ✅ SELL {symbol} ${proceeds:.2f} P&L ${pnl:+.2f} ({pnl_pct:+.1f}%)")

            record = {
                "timestamp":  datetime.now(timezone.utc).isoformat(),
                "symbol":     symbol, "action": "SELL",
                "value":      round(proceeds,2), "price": price,
                "pnl":        round(pnl,2), "pnl_pct": round(pnl_pct,2),
                "confidence": decision["confidence"],
                "reasoning":  decision["reasoning"],
                "source":     decision.get("source","llm"),
            }
            mf.record_trade_time(symbol)
            _alerts.trade_executed(record)

        if record:
            trades = _load_trades()
            trades.append(record)
            _save_trades(trades)
        return record

    except APIError as e:
        log.error(f"  ❌ Alpaca API error {symbol}: {e}")
        try:
            import alerts; alerts.error_alert(f"API error {symbol}: {e}")
        except Exception:
            pass
        return None
    except Exception as e:
        log.error(f"  ❌ Order failed {symbol}: {e}")
        return None


def check_stops():
    """
    Check all open positions:
      1. Trailing stop triggered?
      2. Fixed stop-loss / take-profit?
    """
    import risk_manager as rm
    try:
        import alerts as _alerts
    except Exception:
        _alerts = None

    try:
        c         = _client()
        positions = c.get_all_positions()
        if not positions:
            return

        current_prices = {p.symbol: float(p.current_price) for p in positions}

        # 1. Trailing stops
        stopped = rm.update_trailing_stops(current_prices)
        for symbol in stopped:
            try:
                c.close_position(symbol)
                pos = next((p for p in positions if p.symbol == symbol), None)
                if pos:
                    pnl = float(pos.unrealized_pl)
                    rm.record_daily_pnl(pnl)
                    _log_close(symbol, pos, "trailing_stop")
                    if _alerts:
                        _alerts.stop_loss_hit(symbol, float(pos.unrealized_plpc)*100)
                log.info(f"  🛑 Trailing stop closed: {symbol}")
            except Exception as e:
                log.error(f"  ❌ Trailing stop close failed {symbol}: {e}")

        # 2. Fixed stop-loss / take-profit
        for p in positions:
            pct = float(p.unrealized_plpc) * 100
            if pct <= -(config.STOP_LOSS_PCT * 100):
                log.info(f"  🛑 Fixed stop-loss: {p.symbol} at {pct:.1f}%")
                c.close_position(p.symbol)
                rm.remove_trailing_stop(p.symbol)
                rm.record_daily_pnl(float(p.unrealized_pl))
                _log_close(p.symbol, p, "stop_loss")
                _alerts.stop_loss_hit(p.symbol, pct)

            elif pct >= (config.TAKE_PROFIT_PCT * 100):
                log.info(f"  🎯 Take profit: {p.symbol} at {pct:.1f}%")
                c.close_position(p.symbol)
                rm.remove_trailing_stop(p.symbol)
                rm.record_daily_pnl(float(p.unrealized_pl))
                _log_close(p.symbol, p, "take_profit")
                _alerts.take_profit_hit(p.symbol, pct)

    except Exception as e:
        log.error(f"Stop check failed: {e}")


def _log_close(symbol: str, p, reason: str):
    trades = _load_trades()
    trades.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol":    symbol, "action": "SELL",
        "value":     round(float(p.market_value),2),
        "price":     round(float(p.current_price),4),
        "pnl":       round(float(p.unrealized_pl),2),
        "pnl_pct":   round(float(p.unrealized_plpc)*100,2),
        "reason":    reason, "source": "risk_management",
        "confidence":1.0, "reasoning": f"Auto-closed: {reason.replace('_',' ')}",
    })
    _save_trades(trades)


def _load_trades() -> list:
    if os.path.exists(TRADE_LOG_FILE):
        with open(TRADE_LOG_FILE) as f:
            return json.load(f)
    return []

def _save_trades(trades):
    os.makedirs(os.path.dirname(TRADE_LOG_FILE), exist_ok=True)
    with open(TRADE_LOG_FILE,"w") as f:
        json.dump(trades, f, indent=2)
