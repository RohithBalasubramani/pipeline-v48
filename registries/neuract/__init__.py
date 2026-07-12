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

# Re-exports are LAZY (PEP-562, same pattern as config/): the eager `from registries.neuract.members import …` block
# made this __init__ + all five submodules ONE import SCC — each submodule's `from registries.neuract import _db`
# re-entered a partially-initialized package, and it worked only by import-order luck. Now importing the package
# executes nothing; `from registries.neuract import member_tables` resolves through __getattr__ on first use.
# [cycle-kill 2026-07-12]

# public name → owning submodule (the ONE dispatch table; extend it when a concern gains a public name)
_EXPORTS = {
    # members (aggregation source)
    "members_of": "members", "incomers_of": "members", "outgoers_of": "members", "member_tables": "members",
    # meter registry
    "meter_by": "meters", "table_for": "meters", "name_for": "meters", "type_of": "meters", "list_meters": "meters",
    # topology
    "edges": "topology", "neighbors": "topology",
    # nameplate
    "params_for": "nameplate", "param": "nameplate", "rated_kva": "nameplate",
    # 3d
    "model_for": "assets3d", "model_for_asset": "assets3d", "model_by_id": "assets3d",
    "model_by_key": "assets3d", "list_models": "assets3d",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name):
    mod = _EXPORTS.get(name)
    if mod is None:
        raise AttributeError(f"module 'registries.neuract' has no attribute {name!r}")
    from importlib import import_module
    return getattr(import_module(f"registries.neuract.{mod}"), name)


def __dir__():
    return sorted(set(globals()) | set(_EXPORTS))
