"""config/windows.py — time-window presets (the worker binds :start/:end/:bucket from these). Add/remove here."""
from config.app_config import cfg

TIME_WINDOWS = cfg("windows.time_windows", {
    "today":       {"lookback": "1 day",  "bucket": "hour"},
    "last-24h":    {"lookback": "24 hours", "bucket": "hour"},
    "last-7-days": {"lookback": "7 days", "bucket": "day"},
    "shift-8h":    {"lookback": "8 hours", "bucket": "15 min"},
    "live":        {"lookback": "30 min", "bucket": "minute"},
})
DEFAULT_WINDOW = cfg("windows.default_window", "today")


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
