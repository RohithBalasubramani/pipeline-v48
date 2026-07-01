"""config/defs/cards_intent.py — ATOMIC config declaration for the `cards_intent` concern: the SINGLE source of its DB-backed
keys (key, default, data_type). The cfg() loader reads these from cmd_catalog.app_config; seed_app_config.py
upserts them from here. One concern per file. [atomic DB-config]"""
CONFIG = [
    {"key": 'cards_intent.card_status', "default": 'live', "data_type": 'text'},
    {"key": 'cards_intent.default_db', "default": 'cmd_catalog', "data_type": 'text'},
    {"key": 'cards_intent.grid_viewport', "default": '1920x1080', "data_type": 'text'},
]
