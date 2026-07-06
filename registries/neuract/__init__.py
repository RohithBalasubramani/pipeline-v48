"""registries/neuract/ — the NEURACT METADATA REGISTRY (READ-ONLY over target_version1.neuract, framework-light).

One atomic file per concern, all reading solely through config/neuract_dsn.py (DB-driven DSN, code-default fallback) via
the pooled read door _db.py. Honest-degrade everywhere: an unknown / empty / missing source → [] or None, never a
fabricated value.

The concerns:
    members    — a panel's member meters (THE aggregation source) from the lt_mfm_incoming/outgoing edge tables
    meters     — the lt_mfm 320-row meter registry: meter_by / table_for (→ the gic_* time-series table) / list_meters
    topology   — the directed edge list for SLD / topology cards
    nameplate  — rating / limit params per meter from lt_parameter + lt_config_field/value
    assets3d   — the 3D model registry + per-asset override→type-default resolution

Ground truth encoded here (introspected, not guessed): lt_mfm.panel_id and .role are EMPTY, so membership is edge-table
only; lt_mfm_outgoing = panel→downstream-member (incoming is its exact mirror); lt_parameter / lt_config_value /
asset_3d_model / lt_asset_3d are currently empty and honest-degrade.
"""
from __future__ import annotations

from registries.neuract.members import (
    members_of, incomers_of, outgoers_of, member_tables,
)
from registries.neuract.meters import (
    meter_by, table_for, name_for, type_of, list_meters,
)
from registries.neuract.topology import edges, neighbors
from registries.neuract.nameplate import params_for, param, rated_kva
from registries.neuract.assets3d import (
    model_for, model_for_asset, model_by_id, model_by_key, list_models,
)

__all__ = [
    # members (aggregation source)
    "members_of", "incomers_of", "outgoers_of", "member_tables",
    # meter registry
    "meter_by", "table_for", "name_for", "type_of", "list_meters",
    # topology
    "edges", "neighbors",
    # nameplate
    "params_for", "param", "rated_kva",
    # 3d
    "model_for", "model_for_asset", "model_by_id", "model_by_key", "list_models",
]
