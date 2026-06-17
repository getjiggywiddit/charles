"""
macro_calendar.py — No-trade windows around major economic events.
Keeps the bot quiet 2 hours before and after Fed meetings, CPI prints,
NFP reports, and other high-impact scheduled events.
All free — uses a hardcoded 2025/2026 calendar + scrapes FedSpeak dates.
"""

import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta

import requests

log = logging.getLogger(__name__)

DATA_DIR    = os.path.join(os.path.dirname(__file__), "data")
EVENTS_FILE = os.path.join(DATA_DIR, "macro_events.json")

# How many hours before/after a high-impact event to avoid trading
BLACKOUT_HOURS_BEFORE = 2
BLACKOUT_HOURS_AFTER  = 2

# Cache so we don't re-fetch every cycle
_cache: dict = {"ts": 0, "events": []}
CACHE_TTL = 3600 * 6   # refresh every 6 hours


# ── Hardcoded 2025/2026 high-impact events (UTC times) ───────────────────────
# Fed decisions: 2 PM ET = 19:00 UTC
# CPI/NFP:       8:30 AM ET = 13:30 UTC

HARDCODED_EVENTS = [
    # Fed FOMC decisions 2025/2026
    {"name": "FOMC Rate Decision", "dt": "2025-09-17T19:00:00Z"},
    {"name": "FOMC Rate Decision", "dt": "2025-11-07T19:00:00Z"},
    {"name": "FOMC Rate Decision", "dt": "2025-12-17T19:00:00Z"},
    {"name": "FOMC Rate Decision", "dt": "2026-01-29T19:00:00Z"},
    {"name": "FOMC Rate Decision", "dt": "2026-03-18T19:00:00Z"},
    {"name": "FOMC Rate Decision", "dt": "2026-04-29T19:00:00Z"},
    {"name": "FOMC Rate Decision", "dt": "2026-06-17T19:00:00Z"},
    {"name": "FOMC Rate Decision", "dt": "2026-07-29T19:00:00Z"},
    {"name": "FOMC Rate Decision", "dt": "2026-09-16T19:00:00Z"},
    {"name": "FOMC Rate Decision", "dt": "2026-11-04T19:00:00Z"},
    {"name": "FOMC Rate Decision", "dt": "2026-12-16T19:00:00Z"},
    # CPI 2026 (approximate — 2nd or 3rd Wed of month)
    {"name": "CPI Report",         "dt": "2026-01-14T13:30:00Z"},
    {"name": "CPI Report",         "dt": "2026-02-11T13:30:00Z"},
    {"name": "CPI Report",         "dt": "2026-03-11T13:30:00Z"},
    {"name": "CPI Report",         "dt": "2026-04-10T13:30:00Z"},
    {"name": "CPI Report",         "dt": "2026-05-13T13:30:00Z"},
    {"name": "CPI Report",         "dt": "2026-06-10T13:30:00Z"},
    {"name": "CPI Report",         "dt": "2026-07-15T13:30:00Z"},
    {"name": "CPI Report",         "dt": "2026-08-12T13:30:00Z"},
    {"name": "CPI Report",         "dt": "2026-09-09T13:30:00Z"},
    {"name": "CPI Report",         "dt": "2026-10-14T13:30:00Z"},
    {"name": "CPI Report",         "dt": "2026-11-12T13:30:00Z"},
    {"name": "CPI Report",         "dt": "2026-12-09T13:30:00Z"},
    # Non-Farm Payrolls — first Friday of each month
    {"name": "NFP Jobs Report",    "dt": "2026-01-09T13:30:00Z"},
    {"name": "NFP Jobs Report",    "dt": "2026-02-06T13:30:00Z"},
    {"name": "NFP Jobs Report",    "dt": "2026-03-06T13:30:00Z"},
    {"name": "NFP Jobs Report",    "dt": "2026-04-03T13:30:00Z"},
    {"name": "NFP Jobs Report",    "dt": "2026-05-01T13:30:00Z"},
    {"name": "NFP Jobs Report",    "dt": "2026-06-05T13:30:00Z"},
    {"name": "NFP Jobs Report",    "dt": "2026-07-10T13:30:00Z"},
    {"name": "NFP Jobs Report",    "dt": "2026-08-07T13:30:00Z"},
    {"name": "NFP Jobs Report",    "dt": "2026-09-04T13:30:00Z"},
    {"name": "NFP Jobs Report",    "dt": "2026-10-02T13:30:00Z"},
    {"name": "NFP Jobs Report",    "dt": "2026-11-06T13:30:00Z"},
    {"name": "NFP Jobs Report",    "dt": "2026-12-04T13:30:00Z"},
]


def _parse_events() -> list[dict]:
    events = []
    for e in HARDCODED_EVENTS:
        try:
            dt = datetime.fromisoformat(e["dt"].replace("Z", "+00:00"))
            events.append({"name": e["name"], "dt": dt})
        except Exception:
            pass
    return events


def in_macro_blackout() -> tuple[bool, str]:
    """
    Returns (is_blackout, event_name_if_blackout).
    True if within BLACKOUT_HOURS of a high-impact event.
    """
    now    = datetime.now(timezone.utc)
    events = _parse_events()

    for e in events:
        delta_hours = (e["dt"] - now).total_seconds() / 3600
        if -BLACKOUT_HOURS_AFTER <= delta_hours <= BLACKOUT_HOURS_BEFORE:
            direction = "in" if delta_hours > 0 else "after"
            hours_abs = abs(delta_hours)
            msg = f"{e['name']} ({hours_abs:.1f}h {direction})"
            log.info(f"  📅 Macro blackout: {msg}")
            return True, msg

    return False, ""


def next_event() -> dict | None:
    """Returns the next upcoming macro event."""
    now    = datetime.now(timezone.utc)
    events = sorted(
        [e for e in _parse_events() if e["dt"] > now],
        key=lambda x: x["dt"]
    )
    if events:
        e = events[0]
        hours_away = (e["dt"] - now).total_seconds() / 3600
        return {
            "name":       e["name"],
            "dt":         e["dt"].isoformat(),
            "hours_away": round(hours_away, 1),
        }
    return None


def get_upcoming_events(days: int = 7) -> list[dict]:
    """Return all events in the next N days."""
    now    = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=days)
    events = []
    for e in _parse_events():
        if now < e["dt"] < cutoff:
            events.append({
                "name":       e["name"],
                "dt":         e["dt"].strftime("%b %d %H:%M UTC"),
                "hours_away": round((e["dt"] - now).total_seconds() / 3600, 1),
            })
    return sorted(events, key=lambda x: x["hours_away"])
