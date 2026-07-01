"""config/defs/intents.py — ATOMIC config declaration for the `intents` concern: the SINGLE source of its DB-backed
keys (key, default, data_type). The cfg() loader reads these from cmd_catalog.app_config; seed_app_config.py
upserts them from here. One concern per file. [atomic DB-config]"""
CONFIG = [
    {"key": 'intents.default', "default": 'trend', "data_type": 'text'},
    {"key": 'intents.vocab', "default": '["trend", "distribution", "snapshot", "table", "events"]', "data_type": 'json'},
]
