"""
portfolio.py — Paper trading engine.
Tracks virtual positions, executes simulated orders, calculates P&L.
Persists state to data/portfolio.json so it survives restarts.
"""

import json
import logging
import os
from datetime import datetime, timezone

import config

log = logging.getLogger(__name__)

PORTFOLIO_FILE = os.path.join(os.path.dirname(__file__), "data", "portfolio.json")
TRADE_LOG_FILE = os.path.join(os.path.dirname(__file__), "data", "trades.json")


# ── Persistence ───────────────────────────────────────────────────────────────

def _load_portfolio() -> dict:
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE) as f:
            return json.load(f)
    return {
        "cash":      config.VIRTUAL_CASH,
        "positions": {},   # symbol → {shares, avg_price, cost_basis}
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _save_portfolio(portfolio: dict):
    os.makedirs(os.path.dirname(PORTFOLIO_FILE), exist_ok=True)
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(portfolio, f, indent=2)


def _load_trades() -> list:
    if os.path.exists(TRADE_LOG_FILE):
        with open(TRADE_LOG_FILE) as f:
            return json.load(f)
    return []


def _save_trades(trades: list):
    os.makedirs(os.path.dirname(TRADE_LOG_FILE), exist_ok=True)
    with open(TRADE_LOG_FILE, "w") as f:
        json.dump(trades, f, indent=2)


# ── Order execution ───────────────────────────────────────────────────────────

def execute_decision(decision: dict) -> dict | None:
    """
    Given a decision dict from brain.py, execute a paper trade if conditions met.
    Returns a trade record dict, or None if no trade was placed.
    """
    if decision["confidence"] < config.MIN_CONFIDENCE:
        log.info(f"  ⏭  {decision['symbol']}: confidence {decision['confidence']:.0%} below threshold — skipping")
        return None

    action = decision["action"]
    if action == "HOLD":
        log.info(f"  ⏸  {decision['symbol']}: HOLD")
        return None

    portfolio = _load_portfolio()
    symbol    = decision["symbol"]
    price     = decision["price"]

    if price is None or price <= 0:
        log.warning(f"  ❌ {symbol}: invalid price {price}")
        return None

    trade = None

    if action == "BUY":
        trade = _execute_buy(portfolio, symbol, price, decision)
    elif action == "SELL":
        trade = _execute_sell(portfolio, symbol, price, decision)

    if trade:
        _save_portfolio(portfolio)
        trades = _load_trades()
        trades.append(trade)
        _save_trades(trades)
        log.info(f"  ✅ {action} {symbol} @ ${price:.2f} | {trade.get('shares', 0):.4f} shares")

    return trade


def _execute_buy(portfolio: dict, symbol: str, price: float, decision: dict) -> dict | None:
    """Buy up to MAX_POSITION_SIZE_PCT of portfolio value."""
    total_value  = _portfolio_value(portfolio)
    max_spend    = total_value * config.MAX_POSITION_SIZE_PCT
    cash         = portfolio["cash"]

    # Don't exceed cash or position limit
    spend        = min(max_spend, cash * 0.95)
    if spend < 1.0:
        log.info(f"  💸 {symbol}: insufficient cash (${cash:.2f})")
        return None

    # Check open position count
    if len(portfolio["positions"]) >= config.MAX_OPEN_POSITIONS and symbol not in portfolio["positions"]:
        log.info(f"  🚫 {symbol}: max open positions reached")
        return None

    shares = spend / price
    portfolio["cash"] -= spend

    pos = portfolio["positions"].get(symbol, {"shares": 0, "avg_price": 0, "cost_basis": 0})
    total_shares     = pos["shares"] + shares
    total_cost       = pos["cost_basis"] + spend
    pos["shares"]    = total_shares
    pos["avg_price"] = total_cost / total_shares
    pos["cost_basis"]= total_cost
    portfolio["positions"][symbol] = pos

    return {
        "timestamp":  datetime.now(timezone.utc).isoformat(),
        "symbol":     symbol,
        "action":     "BUY",
        "shares":     round(shares, 6),
        "price":      price,
        "value":      round(spend, 2),
        "confidence": decision["confidence"],
        "reasoning":  decision["reasoning"],
        "source":     decision.get("source", "llm"),
    }


def _execute_sell(portfolio: dict, symbol: str, price: float, decision: dict) -> dict | None:
    """Sell entire position in symbol."""
    pos = portfolio["positions"].get(symbol)
    if not pos or pos["shares"] <= 0:
        log.info(f"  📭 {symbol}: no position to sell")
        return None

    shares   = pos["shares"]
    proceeds = shares * price
    pnl      = proceeds - pos["cost_basis"]
    pnl_pct  = (pnl / pos["cost_basis"] * 100) if pos["cost_basis"] else 0

    portfolio["cash"] += proceeds
    del portfolio["positions"][symbol]

    return {
        "timestamp":  datetime.now(timezone.utc).isoformat(),
        "symbol":     symbol,
        "action":     "SELL",
        "shares":     round(shares, 6),
        "price":      price,
        "value":      round(proceeds, 2),
        "pnl":        round(pnl, 2),
        "pnl_pct":    round(pnl_pct, 2),
        "confidence": decision["confidence"],
        "reasoning":  decision["reasoning"],
        "source":     decision.get("source", "llm"),
    }


# ── Portfolio stats ───────────────────────────────────────────────────────────

def _portfolio_value(portfolio: dict, current_prices: dict | None = None) -> float:
    """Total portfolio value = cash + market value of all positions."""
    total = portfolio["cash"]
    for sym, pos in portfolio["positions"].items():
        price = (current_prices or {}).get(sym, pos["avg_price"])
        total += pos["shares"] * price
    return total


def get_summary(current_prices: dict | None = None) -> dict:
    """Return a human-readable portfolio summary dict."""
    portfolio   = _load_portfolio()
    trades      = _load_trades()
    total_value = _portfolio_value(portfolio, current_prices)
    start_value = config.VIRTUAL_CASH

    closed = [t for t in trades if t["action"] == "SELL" and "pnl" in t]
    wins   = [t for t in closed if t["pnl"] > 0]

    positions_detail = []
    for sym, pos in portfolio["positions"].items():
        cur_price    = (current_prices or {}).get(sym, pos["avg_price"])
        market_val   = pos["shares"] * cur_price
        unrealized   = market_val - pos["cost_basis"]
        unreal_pct   = (unrealized / pos["cost_basis"] * 100) if pos["cost_basis"] else 0
        positions_detail.append({
            "symbol":        sym,
            "shares":        round(pos["shares"], 6),
            "avg_price":     round(pos["avg_price"], 4),
            "current_price": round(cur_price, 4),
            "market_value":  round(market_val, 2),
            "unrealized_pnl":round(unrealized, 2),
            "unrealized_pct":round(unreal_pct, 2),
        })

    return {
        "total_value":    round(total_value, 2),
        "cash":           round(portfolio["cash"], 2),
        "invested":       round(total_value - portfolio["cash"], 2),
        "total_return":   round(total_value - start_value, 2),
        "total_return_pct": round((total_value - start_value) / start_value * 100, 2),
        "open_positions": len(portfolio["positions"]),
        "total_trades":   len(trades),
        "win_rate":       round(len(wins) / len(closed) * 100, 1) if closed else 0,
        "positions":      positions_detail,
        "trades":         trades[-20:],   # last 20 trades
    }
