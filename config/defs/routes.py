"""config/defs/routes.py — ATOMIC config declaration for the `routes` concern: the SINGLE source of its DB-backed
keys (key, default, data_type). The cfg() loader reads these from cmd_catalog.app_config; seed_app_config.py
upserts them from here. One concern per file. [atomic DB-config]"""
CONFIG = [
    {"key": 'routes.page_tail_alias', "default": '{"harmonics-pq": "power-quality", "overview-sld-3d": "overview"}', "data_type": 'json'},
    {"key": 'routes.retired_endpoints', "default": '["power-quality-history", "distortion-harmonics", "harmonics-pq", "power-quality"]', "data_type": 'json'},
    {"key": 'routes.source_backend', "default": 'ems_backend', "data_type": 'text'},
]
