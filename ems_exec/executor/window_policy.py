"""ems_exec/executor/window_policy.py — window / declared-range honoring: the range vocabulary (calendar anchors,
config lookbacks, 'last-N' spellings), the widen-only reconcile and the ctx window resolver. One concern; fill.py
re-exports byte-compatibly. [atomic]
"""
from __future__ import annotations

import re

from ems_exec.executor.derived import _site_calendar_start


def _range_start(range_key, end_dt):
    """The START instant a declared range names, anchored at `end_dt` (the window's real end — never wall-clock).
    Vocabulary (all config-extendable, code defaults):
      · calendar anchors: today → midnight(end); this-week → Monday midnight; this-month → the 1st midnight.
      · config lookbacks: config.windows.TIME_WINDOWS[key].lookback ('7 days' / '24 hours' / '30 min' …).
      · generic 'last-N-days/hours/min(utes)' spelling.
    None when the range is unknown / unparsable (honest — the caller keeps its window untouched)."""
    from datetime import timedelta
    key = str(range_key or "").strip().lower().replace("_", "-")
    if not key or end_dt is None:
        return None
    # calendar anchors are SITE-timezone starts (window.site_tz): a UTC-midnight 'today' at 05:30 IST is a
    # ~0-minute window that under-counts every windowed read (the card-18 '3 events vs 124 DB edges' defect).
    if key in ("today", "day"):
        return _site_calendar_start(end_dt, "day")
    if key in ("this-week", "week"):
        return _site_calendar_start(end_dt, "week")
    if key in ("this-month", "month", "monthly"):
        return _site_calendar_start(end_dt, "month")
    lookback = None
    try:
        from config.windows import TIME_WINDOWS
        lookback = ((TIME_WINDOWS or {}).get(key) or {}).get("lookback")
    except Exception:
        lookback = None
    m = re.match(r"^\s*(\d+)\s*(day|hour|min)", str(lookback or "").strip().lower()) \
        or re.match(r"^last-(\d+)-?(day|hour|min|h|d)", key)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    if unit in ("day", "d"):
        return end_dt - timedelta(days=n)
    if unit in ("hour", "h"):
        return end_dt - timedelta(hours=n)
    return end_dt - timedelta(minutes=n)


def _honor_range(start, end, range_key, authoritative=False):
    """Reconcile a (start, end) window with a DECLARED range so the values a card renders MATCH the range it claims
    (card 16: consumer range='last-7-days' but the caller handed a 24h window → 2 of 7 daily buckets rendered; card 14:
    a 'Monthly' KPI filled from a 24h delta). Default = WIDEN-ONLY: the range start replaces `start` only when `start`
    is missing or NARROWER (a user-picked longer window is never shrunk). `authoritative=True` (a recipe slot's own
    declared range) sets the start outright. Anchored at the window's real end — no end → nothing to anchor, window
    untouched (honest). Valve: app_config window.honor_declared_range ('on' unless 'off')."""
    if not range_key or not end:
        return start, end
    try:
        from config.app_config import cfg
        if str(cfg("window.honor_declared_range", "on")).strip().lower() == "off":
            return start, end
    except Exception:
        pass
    from datetime import datetime
    try:
        end_dt = end if isinstance(end, datetime) else datetime.fromisoformat(str(end))
    except (TypeError, ValueError):
        return start, end
    req = _range_start(range_key, end_dt)
    if req is None:
        return start, end
    if not authoritative and start:
        try:
            cur = start if isinstance(start, datetime) else datetime.fromisoformat(str(start))
            if cur <= req:
                return start, end                              # the given window already covers the declared range
        except (TypeError, ValueError):
            pass
    return req.isoformat(), end


def _window_of(ctx, data_instructions):
    w = (ctx or {}).get("window")
    start, end = None, None
    if isinstance(w, (list, tuple)) and len(w) == 2:
        start, end = w[0], w[1]
    elif isinstance(w, dict):
        start, end = w.get("start"), w.get("end")
    else:
        dw = (data_instructions or {}).get("window") or {}
        if isinstance(dw, dict) and (dw.get("start") or dw.get("end")):
            start, end = dw.get("start"), dw.get("end")
    # DECLARED-RANGE HONORING: the consumer's own `range` is the card's window CONTRACT — the reads must span it.
    rng = ((data_instructions or {}).get("consumer") or {}).get("range")
    return _honor_range(start, end, rng)
