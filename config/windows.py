"""config/windows.py — time-window presets (the worker binds :start/:end/:bucket from these). Add/remove here.

TIME_WINDOWS / DEFAULT_WINDOW / MIN_SPAN_DAYS are LAZY module attributes (PEP 562): each access re-reads cfg(), so a
DB row edit + app_config.reload() (or a boot during a DB outage that later heals) reaches every consumer — the old
import-time binding pinned whatever cfg() returned at first import for the process life."""
from config.app_config import cfg

_TIME_WINDOWS_DEFAULT = {
    "today":       {"lookback": "1 day",  "bucket": "hour"},
    "last-24h":    {"lookback": "24 hours", "bucket": "hour"},
    "last-7-days": {"lookback": "7 days", "bucket": "day"},
    "shift-8h":    {"lookback": "8 hours", "bucket": "15 min"},
    "live":        {"lookback": "30 min", "bucket": "minute"},
}

_LAZY = {
    "TIME_WINDOWS":   lambda: cfg("windows.time_windows", _TIME_WINDOWS_DEFAULT),
    "DEFAULT_WINDOW": lambda: cfg("windows.default_window", "today"),
    "MIN_SPAN_DAYS":  lambda: cfg("windows.min_span_days", 1),
}


def __getattr__(name):
    if name in _LAZY:
        return _LAZY[name]()
    raise AttributeError(f"module 'config.windows' has no attribute {name!r}")


def site_tz():
    """The SITE's display timezone (zoneinfo) — the calendar day a card's 'today'/'this-month' range means, and the
    wall-clock a derived time-axis label renders. DB row app_config `window.site_tz` (IANA name), code default
    Asia/Kolkata (the plant's IST wall clock — a UTC-midnight 'today' at 05:30 IST is a ~0-minute window, the
    2026-07-06 card-18 event-count defect). Falls back to UTC on a bad row (never raises)."""
    name = cfg("window.site_tz", "Asia/Kolkata")
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(str(name))
    except Exception:
        from datetime import timezone
        return timezone.utc


# MIN_SPAN_DAYS (lazy attr above): the exclusive-end minimum span a resolved DATA window must cover — a counter-delta
# read is (end − start), so a degenerate window whose end <= start folds EVERY member/bucket to a false 0.0 (card-12
# 'today' custom-range resolved start==end==YYYY-MM-DD → member_delta over [today,today] == 0.0 while today genuinely
# carries kWh; the real delta needs [today, today+1)). Code default 1 day; DB-tunable via windows.min_span_days.


def _parse_dt(v):
    """(datetime, was_bare_date) from a window bound — a bare 'YYYY-MM-DD' calendar date (custom-range start/end) OR a
    full ISO datetime. None when unparseable / empty. `was_bare_date` marks a date-only token so ensure_nonzero_span
    can extend by whole calendar days (a 'today' custom-range is a CALENDAR day, not a rolling instant)."""
    from datetime import datetime, date
    if v in (None, ""):
        return None, False
    if isinstance(v, datetime):
        return v, False
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day), True
    s = str(v).strip()
    try:
        return datetime.fromisoformat(s), (len(s) == 10 and s.count("-") == 2)   # bare YYYY-MM-DD
    except (TypeError, ValueError):
        return None, False


def ensure_nonzero_span(start, end):
    """(start, end) guaranteeing a NON-ZERO exclusive span — the degenerate-window guard for every window-resolution
    path (custom-range promotion, AI-authored bounds, calendar/lookback backfill). A counter-delta read is (end −
    start): when the resolved end <= start (a same-day custom-range, a single calendar day, or any end that folds to
    or below the start), a 'today' delta comes back 0.0 for every member though today carries real kWh (card-12
    energy-distribution false-zero). Extend the END to a minimum span so the read spans the full period:
      • both bounds present and end <= start → end = start + MIN_SPAN_DAYS (the next-midnight for a bare calendar day,
        so a same-day 'today' custom-range spans [day 00:00, day+1 00:00));
      • only start present → end = start + MIN_SPAN_DAYS (a lone anchor is a single day, not a zero-width instant).
    A NORMAL window (end strictly after start, or nothing resolvable) is returned UNCHANGED — this only rescues the
    degenerate case, never shrinks or shifts a real multi-day/rolling window. Preserves each bound's original spelling
    (a bare date stays a bare date, an ISO datetime stays ISO). Never raises."""
    try:
        from datetime import timedelta
        span = timedelta(days=max(1, int(cfg("windows.min_span_days", 1) or 1)))
        s_dt, s_bare = _parse_dt(start)
        e_dt, _e_bare = _parse_dt(end)
        if s_dt is None:
            return start, end                                  # no start to anchor — leave the window untouched (honest)
        if e_dt is not None and e_dt > s_dt:
            return start, end                                  # a real forward span — never touched
        new_end = s_dt + span
        return start, (new_end.date().isoformat() if s_bare else new_end.isoformat())
    except Exception:
        return start, end
