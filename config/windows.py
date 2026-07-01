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
