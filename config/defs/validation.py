"""config/defs/validation.py — ATOMIC config declaration for the `validation` concern: the SINGLE source of its DB-backed
keys (key, default, data_type). The cfg() loader reads these from cmd_catalog.app_config; seed_app_config.py
upserts them from here. One concern per file. [atomic DB-config]"""
CONFIG = [
    {"key": 'validation.failure_policy', "default": 'annotate', "data_type": 'text'},
    {"key": 'validation.max_null_rate', "default": 0.5, "data_type": 'number'},
    {"key": 'validation.min_rows_series', "default": 12, "data_type": 'int'},
    {"key": 'validation.phase_suffixes', "default": '["_r", "_y", "_b", "_n", "_ry", "_yb", "_br", "_r_n", "_y_n", "_b_n", "_neutral"]', "data_type": 'json'},
    {"key": 'validation.probe_rows', "default": 500, "data_type": 'int'},
    {"key": 'validation.small_array_max', "default": 8, "data_type": 'int'},
    {"key": 'validation.warn_null_rate', "default": 0.1, "data_type": 'number'},
]
