"""config/defs/payload_shapes.py — ATOMIC config declaration for the `payload_shapes` concern: the SINGLE source of its DB-backed
keys (key, default, data_type). The cfg() loader reads these from cmd_catalog.app_config; seed_app_config.py
upserts them from here. One concern per file. [atomic DB-config]"""
CONFIG = [
    {"key": 'payload_shapes.canonical', "default": '["TextPayload", "TilePayload", "ProgressPayload", "SeriesPayload", "TablePayload", "RadarPayload", "SankeyPayload", "HeatmapPayload", "PqDiagnosisPayload", "PqEventStatsPayload"]', "data_type": 'json'},
    {"key": 'payload_shapes.shape_map', "default": '{"composite": null, "sld": "topology"}', "data_type": 'json'},
]
