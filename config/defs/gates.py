"""config/defs/gates.py — ATOMIC config declaration for the `gates` concern: the SINGLE source of its DB-backed
keys (key, default, data_type). The cfg() loader reads these from cmd_catalog.app_config; seed_app_config.py
upserts them from here. One concern per file. [atomic DB-config]"""
CONFIG = [
    {"key": 'gates.chrome_markers', "default": '["=>", "function(", "function (", "React.", "onClick", "px solid", "rgba("]', "data_type": 'json'},
]
