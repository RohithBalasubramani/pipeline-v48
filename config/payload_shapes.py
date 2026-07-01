"""config/payload_shapes.py — the canonical normalized payload shapes. Add/remove here. [contract 5]"""
from config.app_config import cfg

PAYLOAD_SHAPES = cfg("payload_shapes.canonical", [
    "TextPayload", "TilePayload", "ProgressPayload", "SeriesPayload", "TablePayload",
    "RadarPayload", "SankeyPayload", "HeatmapPayload", "PqDiagnosisPayload", "PqEventStatsPayload",
])

# Live cmd_catalog payload_shape values that need mapping (REVIEW G10):
PAYLOAD_SHAPE_MAP = cfg("payload_shapes.shape_map", {
    "composite": None,   # -> a combo GROUP; do NOT collapse to one shape (open_items/composite_sld_payload_shape.md)
    "sld": "topology",   # -> topology path
})
