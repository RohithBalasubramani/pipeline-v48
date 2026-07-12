"""registries/neuract/meters.py — the lt_mfm METER REGISTRY (the 320-row name/table/type/panel dictionary).

Single concern: resolve a meter (MFM) by id OR name, and hand back the neuract gic_* `table_name` that meter physically
logs its time-series to. lt_mfm is the join key for the whole registry — every edge/member row is an mfm id, and every
data read is against the table_name resolved here.

REAL SCHEMA (introspected, not guessed): lt_mfm(id, name, db_link, table_name, panel_id, mfm_type_id, load_group,
asset_3d_override_id, parent_series, rated_capacity_kva, role). NOTE the ground truth: panel_id is EMPTY ('') and role
is NULL for all 320 rows — so membership does NOT come from panel_id; it comes from the lt_mfm_incoming/outgoing edge
tables (see members.py / topology.py). mfm_type_id → lt_mfm_type(1=APFC, 2=LT Panel, 3=Transformer, 4=UPS).

Honest-degrade: an unknown id/name → None; a meter with no table_name → None (never a fabricated table). [atomic; cached]
"""
from __future__ import annotations

from registries.neuract import _db

# lt_mfm columns we surface (only ones that physically exist). type name is joined from lt_mfm_type.
_SELECT = (
    "SELECT m.id, m.name, m.table_name, m.mfm_type_id, m.panel_id, m.load_group, "
    "m.parent_series, m.rated_capacity_kva, m.role, m.asset_3d_override_id, "
    "t.name AS type_name, t.code AS type_code "
    "FROM lt_mfm m LEFT JOIN lt_mfm_type t ON t.id = m.mfm_type_id"
)

_BY_ID: dict = {}       # int id -> row dict
_BY_NAME: dict = {}     # lower(name) -> row dict
_ALL: list = []         # cached list_meters()
_LOADED = False


def _load():
    global _LOADED, _ALL
    if _LOADED:
        return
    rows = _db.dicts(_SELECT + " ORDER BY m.id")
    _ALL = rows
    for r in rows:
        _BY_ID[int(r["id"])] = r
        nm = (r.get("name") or "").strip().lower()
        if nm:
            _BY_NAME.setdefault(nm, r)
    _LOADED = True


def _as_int(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def meter_by(ref):
    """Resolve a meter by MFM id (int / numeric str) OR by exact name (case-insensitive) → the lt_mfm row dict, or None.

    Returns keys: id, name, table_name, mfm_type_id, type_name, type_code, panel_id, load_group, parent_series,
    rated_capacity_kva, role, asset_3d_override_id. None for an unknown id/name (honest-degrade — never invented)."""
    if ref is None:
        return None
    _load()
    iid = _as_int(ref)
    if iid is not None:
        return _BY_ID.get(iid)
    return _BY_NAME.get(str(ref).strip().lower())


def table_for(mfm):
    """The neuract gic_* `table_name` this meter logs to → str, or None. `mfm` may be an id, a name, or a row dict.

    This is the bridge from a metadata meter to its live time-series table (what ems_exec/data/neuract.py then reads)."""
    row = mfm if isinstance(mfm, dict) else meter_by(mfm)
    if not row:
        return None
    tbl = (row.get("table_name") or "").strip()
    return tbl or None


def name_for(mfm):
    """The display name for a meter → str or None."""
    row = mfm if isinstance(mfm, dict) else meter_by(mfm)
    return (row.get("name") if row else None) or None


def type_of(mfm):
    """(type_code, type_name) for a meter, e.g. ('transformer', 'Transformer') — (None, None) if unknown."""
    row = mfm if isinstance(mfm, dict) else meter_by(mfm)
    if not row:
        return None, None
    return row.get("type_code"), row.get("type_name")


def list_meters(type_code=None):
    """All meters as row dicts (optionally filtered to one lt_mfm_type code, e.g. 'lt_panel'/'transformer'). [] if none."""
    _load()
    if not type_code:
        return list(_ALL)
    tc = str(type_code).strip().lower()
    return [r for r in _ALL if (r.get("type_code") or "").lower() == tc]


