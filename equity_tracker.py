"""
equity_tracker.py — Records portfolio value snapshots over time.
Called after every trade cycle to build the equity curve shown in the dashboard.
Data saved to data/equity_curve.json — survives restarts.
"""

import json
import logging
import os
from datetime import datetime, timezone

log = logging.getLogger(__name__)

DATA_DIR    = os.path.join(os.path.dirname(__file__), "data")
EQUITY_FILE = os.path.join(DATA_DIR, "equity_curve.json")

import config
START_VALUE = config.VIRTUAL_CASH


def record_snapshot(total_value: float):
    """Append a timestamped portfolio value to the equity curve."""
    os.makedirs(DATA_DIR, exist_ok=True)
    curve = _load()
    curve.append({
        "ts":    datetime.now(timezone.utc).isoformat(),
        "value": round(total_value, 2),
        "pnl":   round(total_value - START_VALUE, 2),
        "pct":   round((total_value - START_VALUE) / START_VALUE * 100, 4),
    })
    # Keep last 10,000 points (~3 months at 30-min intervals)
    curve = curve[-10_000:]
    with open(EQUITY_FILE, "w") as f:
        json.dump(curve, f)


def load_curve() -> list[dict]:
    return _load()


def _load() -> list:
    if os.path.exists(EQUITY_FILE):
        try:
            with open(EQUITY_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return []
