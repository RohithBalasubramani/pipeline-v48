"""config/defs/card_grid_size.py — ATOMIC config declaration for the `card_grid_size` concern: the SINGLE source of its DB-backed
keys (key, default, data_type). The cfg() loader reads these from cmd_catalog.app_config; seed_app_config.py
upserts them from here. One concern per file. [atomic DB-config]"""
CONFIG = [
    {"key": 'card_grid_size.default_viewport', "default": '1920x1080', "data_type": 'text'},
]
