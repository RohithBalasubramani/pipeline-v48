"""config/defs/windows.py — ATOMIC config declaration for the `windows` concern: the SINGLE source of its DB-backed
keys (key, default, data_type). The cfg() loader reads these from cmd_catalog.app_config; seed_app_config.py
upserts them from here. One concern per file. [atomic DB-config]"""
CONFIG = [
    {"key": 'windows.default_window', "default": 'today', "data_type": 'text'},
    {"key": 'windows.time_windows', "default": '{"today": {"lookback": "1 day", "bucket": "hour"}, "last-24h": {"lookback": "24 hours", "bucket": "hour"}, "last-7-days": {"lookback": "7 days", "bucket": "day"}, "shift-8h": {"lookback": "8 hours", "bucket": "15 min"}, "live": {"lookback": "30 min", "bucket": "minute"}}', "data_type": 'json'},
]
