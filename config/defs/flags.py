"""config/defs/flags.py — ATOMIC config declaration for the `flags` concern: the SINGLE source of its DB-backed
keys (key, default, data_type). The cfg() loader reads these from cmd_catalog.app_config; seed_app_config.py
upserts them from here. One concern per file. [atomic DB-config]"""
CONFIG = [
    {"key": 'flags.ctx_source_form', "default": 'dotted', "data_type": 'text'},
    {"key": 'flags.page_wise_shared_detection', "default": False, "data_type": 'bool'},
    {"key": 'flags.require_live_sentinel', "default": True, "data_type": 'bool'},
]
