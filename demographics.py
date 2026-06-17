"""
demographics.py — Portfolio demographics and analytics engine.
Generates charts and CSVs showing portfolio performance breakdowns
by symbol, time period, trade type, win/loss, and market conditions.
All charts exportable as CSV for Excel graphing.
"""

import csv
import io
import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone, timedelta

log = logging.getLogger(__name__)

DATA_DIR    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")


def _load_trades() -> list:
    p = os.path.join(DATA_DIR, "trades.json")
    if not os.path.exists(p): return []
    with open(p) as f: return json.load(f)


def _load_equity() -> list:
    p = os.path.join(DATA_DIR, "equity_curve.json")
    if not os.path.exists(p): return []
    with open(p) as f: return json.load(f)


def _parse_dt(ts: str) -> datetime:
    return datetime.fromisoformat(ts[:19]).replace(tzinfo=timezone.utc)


def _filter_period(trades: list, equity: list,
                   period: str, start: str = None, end: str = None):
    """Filter data to a date range."""
    now = datetime.now(timezone.utc)

    if period == "all":
        start_dt, end_dt = datetime(2020, 1, 1, tzinfo=timezone.utc), now
    elif period == "weekly":
        start_dt = now - timedelta(days=7)
        end_dt   = now
    elif period == "monthly":
        start_dt = now.replace(day=1, hour=0, minute=0, second=0)
        end_dt   = now
    elif period == "yearly":
        start_dt = now.replace(month=1, day=1, hour=0, minute=0, second=0)
        end_dt   = now
    elif period == "custom" and start and end:
        start_dt = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
        end_dt   = datetime.fromisoformat(end).replace(tzinfo=timezone.utc)
    else:
        start_dt, end_dt = datetime(2020, 1, 1, tzinfo=timezone.utc), now

    t = [x for x in trades if start_dt <= _parse_dt(x["timestamp"]) <= end_dt]
    e = [x for x in equity if start_dt <= _parse_dt(x["ts"]) <= end_dt]
    return t, e, start_dt, end_dt


# ── Chart data generators ─────────────────────────────────────────────────────

def pnl_by_symbol(trades: list) -> dict:
    """P&L breakdown by stock symbol."""
    data = defaultdict(lambda: {"pnl": 0, "trades": 0, "wins": 0, "losses": 0})
    for t in trades:
        if t["action"] != "SELL" or "pnl" not in t:
            continue
        sym = t["symbol"]
        pnl = float(t.get("pnl", 0) or 0)
        data[sym]["pnl"]    += pnl
        data[sym]["trades"] += 1
        if pnl > 0: data[sym]["wins"]   += 1
        else:       data[sym]["losses"] += 1

    return {
        "symbols":  list(data.keys()),
        "pnl":      [round(v["pnl"], 2)    for v in data.values()],
        "trades":   [v["trades"]            for v in data.values()],
        "win_rate": [round(v["wins"] / v["trades"] * 100, 1) if v["trades"] else 0
                     for v in data.values()],
    }


def pnl_over_time(equity: list, granularity: str = "daily") -> dict:
    """Portfolio value over time — daily, weekly, or monthly."""
    if not equity:
        return {"dates": [], "values": [], "returns": []}

    # Group by granularity
    groups = defaultdict(list)
    for e in equity:
        dt = _parse_dt(e["ts"])
        if granularity == "daily":
            key = dt.strftime("%Y-%m-%d")
        elif granularity == "weekly":
            key = f"{dt.isocalendar()[0]}-W{dt.isocalendar()[1]:02d}"
        else:
            key = dt.strftime("%Y-%m")
        groups[key].append(float(e["value"]))

    dates  = sorted(groups.keys())
    values = [round(groups[d][-1], 2) for d in dates]  # end-of-period value

    start = values[0] if values else 1000
    returns = [round((v - start) / start * 100, 2) for v in values]

    return {"dates": dates, "values": values, "returns": returns}


def trade_distribution(trades: list) -> dict:
    """Distribution of trade outcomes."""
    sells = [t for t in trades if t["action"] == "SELL" and "pnl" in t]
    if not sells:
        return {"buckets": [], "counts": []}

    pnls = [float(t["pnl"]) for t in sells]
    mn, mx = min(pnls), max(pnls)

    # Create 10 buckets
    step = (mx - mn) / 10 if mx != mn else 1
    buckets = []
    counts  = []
    for i in range(10):
        lo = mn + i * step
        hi = lo + step
        label  = f"${lo:+.1f} to ${hi:+.1f}"
        count  = sum(1 for p in pnls if lo <= p < hi)
        buckets.append(label)
        counts.append(count)

    return {"buckets": buckets, "counts": counts}


def win_loss_streak(trades: list) -> dict:
    """Win/loss streak analysis."""
    sells = [t for t in trades if t["action"] == "SELL" and "pnl" in t]
    if not sells:
        return {"dates": [], "cumulative_pnl": [], "win_streak": 0, "loss_streak": 0}

    cum_pnl = []
    running = 0
    dates   = []
    cur_win_streak = cur_loss_streak = 0
    max_win = max_loss = 0

    for t in sorted(sells, key=lambda x: x["timestamp"]):
        pnl     = float(t["pnl"])
        running += pnl
        cum_pnl.append(round(running, 2))
        dates.append(t["timestamp"][:10])
        if pnl > 0:
            cur_win_streak  += 1
            cur_loss_streak  = 0
            max_win = max(max_win, cur_win_streak)
        else:
            cur_loss_streak += 1
            cur_win_streak   = 0
            max_loss = max(max_loss, cur_loss_streak)

    return {
        "dates":        dates,
        "cumulative_pnl": cum_pnl,
        "max_win_streak":  max_win,
        "max_loss_streak": max_loss,
    }


def trades_by_hour(trades: list) -> dict:
    """Which hours of the day produce the best trades."""
    hours   = list(range(9, 17))
    pnl_by  = defaultdict(list)
    count_by= defaultdict(int)

    for t in trades:
        if t["action"] != "SELL" or "pnl" not in t:
            continue
        hour = _parse_dt(t["timestamp"]).hour
        pnl_by[hour].append(float(t["pnl"]))
        count_by[hour] += 1

    avg_pnl = {h: round(sum(v)/len(v), 2) if v else 0 for h, v in pnl_by.items()}

    return {
        "hours":    [f"{h:02d}:00" for h in hours],
        "avg_pnl":  [avg_pnl.get(h, 0) for h in hours],
        "count":    [count_by.get(h, 0) for h in hours],
    }


def confidence_vs_outcome(trades: list) -> dict:
    """Does higher AI confidence correlate with better outcomes?"""
    sells = [t for t in trades if t["action"] == "SELL" and "pnl" in t
             and "confidence" in t]
    if not sells:
        return {"confidence": [], "pnl": [], "symbols": []}

    return {
        "confidence": [round(float(t.get("confidence", 0)) * 100, 1) for t in sells],
        "pnl":        [round(float(t["pnl"]), 2)    for t in sells],
        "symbols":    [t["symbol"]                   for t in sells],
    }


def monthly_summary(trades: list, equity: list) -> dict:
    """Month-by-month performance summary."""
    months = defaultdict(lambda: {"pnl": 0, "trades": 0, "wins": 0})

    for t in trades:
        if t["action"] != "SELL" or "pnl" not in t:
            continue
        key = _parse_dt(t["timestamp"]).strftime("%Y-%m")
        pnl = float(t["pnl"])
        months[key]["pnl"]    += pnl
        months[key]["trades"] += 1
        if pnl > 0: months[key]["wins"] += 1

    sorted_months = sorted(months.keys())
    return {
        "months":   sorted_months,
        "pnl":      [round(months[m]["pnl"], 2)    for m in sorted_months],
        "trades":   [months[m]["trades"]            for m in sorted_months],
        "win_rate": [round(months[m]["wins"] / months[m]["trades"] * 100, 1)
                     if months[m]["trades"] else 0 for m in sorted_months],
    }


# ── CSV exporters ─────────────────────────────────────────────────────────────

def export_demographics_csv(trades: list, equity: list,
                             period_label: str = "All Time") -> dict:
    """
    Export all demographic data as CSV strings.
    Returns dict of {chart_name: csv_string} for download buttons.
    """
    os.makedirs(REPORTS_DIR, exist_ok=True)
    csvs = {}

    def make_csv(headers: list, rows: list) -> str:
        out = io.StringIO()
        w   = csv.writer(out)
        w.writerow(headers)
        w.writerows(rows)
        return out.getvalue()

    # P&L by symbol
    sym = pnl_by_symbol(trades)
    if sym["symbols"]:
        csvs["pnl_by_symbol"] = make_csv(
            ["Symbol", "Total P&L ($)", "Trades", "Win Rate (%)"],
            zip(sym["symbols"], sym["pnl"], sym["trades"], sym["win_rate"])
        )

    # P&L over time
    daily = pnl_over_time(equity, "daily")
    if daily["dates"]:
        csvs["portfolio_over_time"] = make_csv(
            ["Date", "Portfolio Value ($)", "Return (%)"],
            zip(daily["dates"], daily["values"], daily["returns"])
        )

    # Monthly summary
    ms = monthly_summary(trades, equity)
    if ms["months"]:
        csvs["monthly_summary"] = make_csv(
            ["Month", "P&L ($)", "Trades", "Win Rate (%)"],
            zip(ms["months"], ms["pnl"], ms["trades"], ms["win_rate"])
        )

    # Trades by hour
    th = trades_by_hour(trades)
    csvs["trades_by_hour"] = make_csv(
        ["Hour (ET)", "Avg P&L ($)", "Trade Count"],
        zip(th["hours"], th["avg_pnl"], th["count"])
    )

    # Confidence vs outcome
    co = confidence_vs_outcome(trades)
    if co["confidence"]:
        csvs["confidence_vs_outcome"] = make_csv(
            ["Symbol", "AI Confidence (%)", "P&L ($)"],
            zip(co["symbols"], co["confidence"], co["pnl"])
        )

    # Win/loss streak
    wl = win_loss_streak(trades)
    if wl["dates"]:
        csvs["cumulative_pnl"] = make_csv(
            ["Date", "Cumulative P&L ($)"],
            zip(wl["dates"], wl["cumulative_pnl"])
        )

    # Save all to disk
    safe_label = period_label.replace(" ", "_").replace("/", "-")
    for name, csv_data in csvs.items():
        path = os.path.join(REPORTS_DIR, f"demographics_{safe_label}_{name}.csv")
        with open(path, "w") as f:
            f.write(csv_data)

    log.info(f"📊 Demographics CSVs exported: {list(csvs.keys())}")
    return csvs
