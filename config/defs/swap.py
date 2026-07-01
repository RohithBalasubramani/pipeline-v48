"""config/defs/swap.py — ATOMIC config declaration for the `swap` concern: the SINGLE source of its DB-backed
keys (key, default, data_type). The cfg() loader reads these from cmd_catalog.app_config; seed_app_config.py
upserts them from here. One concern per file. [atomic DB-config]"""
CONFIG = [
    {"key": 'swap.min_confidence', "default": 0.9, "data_type": 'number'},
    {"key": 'swap.size_tolerance', "default": 0.15, "data_type": 'number'},
    {"key": 'swap.swap_pool_max', "default": 6, "data_type": 'int'},
    {"key": 'swap.vague_criteria', "default": '["better", "more relevant", "relevant", "nicer", "good fit", "best fit", "improved", "cleaner", "clearer", "more suitable", "suitable", "fits better", "more appropriate", "appropriate", "nice", "good", "great", "preferred", "stronger", "richer"]', "data_type": 'json'},
]
