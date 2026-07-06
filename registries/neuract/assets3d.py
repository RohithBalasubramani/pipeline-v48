"""registries/neuract/assets3d.py — the 3D MODEL registry (asset_3d_model / lt_asset_3d) + the per-asset resolution chain.

Single concern: resolve the glTF/GLB 3D model a viewer should mount for an asset — by a direct model key, by an
asset_type, or by an MFM/asset row via its override→type-default chain.

REAL SCHEMA (introspected): both asset_3d_model and lt_asset_3d are (id, key, name, category, file, description). Both
are currently EMPTY (0 rows), and every *_asset_3d_id FK (lt_mfm.asset_3d_override_id, lt_mfm_type.default_asset_3d_id,
asset.asset_3d_override_id, asset_type.default_asset_3d_id) is NULL in the ground truth — so every accessor here
honest-degrades to None today, but the FULL resolution wiring is in place so a model resolves the instant rows land.

Resolution order for a meter/asset (model_for):
    1. the row's asset_3d_override_id  (a per-instance override)
    2. its type's default_asset_3d_id  (lt_mfm_type / asset_type default)
    3. → None (no fabricated model, no default file path)
Both model tables are consulted by id (lt_asset_3d first, then asset_3d_model) so whichever holds the row wins.
[atomic; DB-driven; honest-degrade → None]
"""
from __future__ import annotations

from registries.neuract import _db
from registries.neuract import meters as _meters

# the two 3D model tables, in lookup order (both share the same shape). First one that has the id/key wins.
_MODEL_TABLES = ("lt_asset_3d", "asset_3d_model")


def _model_row(where_sql, params):
    """First matching model row across the model tables → dict, or None. Skips tables that don't exist."""
    for tbl in _MODEL_TABLES:
        if not _db.table_exists(tbl):
            continue
        got = _db.dicts(
            f"SELECT id, key, name, category, file, description FROM {tbl} {where_sql} LIMIT 1",
            params,
        )
        if got:
            row = got[0]
            row["_table"] = tbl
            return row
    return None


def model_by_id(model_id):
    """A 3D model by its id → {id, key, name, category, file, description}, or None (honest-degrade)."""
    if model_id is None:
        return None
    return _model_row("WHERE id = %s", (model_id,))


def model_by_key(key):
    """A 3D model by its `key` (e.g. 'transformer', 'ups') → model dict, or None (honest-degrade)."""
    if not key:
        return None
    return _model_row("WHERE lower(key) = lower(%s)", (str(key),))


def _type_default_model_id(mfm_type_id):
    """lt_mfm_type.default_asset_3d_id for a type id → id or None."""
    if mfm_type_id is None:
        return None
    r = _db.one("SELECT default_asset_3d_id FROM lt_mfm_type WHERE id = %s", (mfm_type_id,))
    return (r or {}).get("default_asset_3d_id")


def _asset_type_default_model_id(asset_type_id):
    """asset_type.default_asset_3d_id for an asset_type id → id or None."""
    if asset_type_id is None:
        return None
    r = _db.one("SELECT default_asset_3d_id FROM asset_type WHERE id = %s", (asset_type_id,))
    return (r or {}).get("default_asset_3d_id")


def model_for(ref):
    """The 3D model to mount for an asset → model dict, or None. `ref` may be:

      - a str model key            → model_by_key (a 3d-model key or an lt_mfm_type code like 'transformer')
      - an MFM id / name / row      → override_id → its type's default_asset_3d_id → None

    Resolution never fabricates: with the tables empty / FKs NULL (the current ground truth) this returns None, but the
    override→type-default chain resolves automatically once models + FKs exist."""
    # explicit model key (string, not a numeric id)
    if isinstance(ref, str) and not ref.isdigit():
        by_key = model_by_key(ref)
        if by_key:
            return by_key
        # a bare type code (e.g. 'transformer') → that type's default model
        trow = _db.one("SELECT default_asset_3d_id FROM lt_mfm_type WHERE lower(code) = lower(%s)", (ref,))
        if trow and trow.get("default_asset_3d_id") is not None:
            return model_by_id(trow["default_asset_3d_id"])
        arow = _db.one("SELECT default_asset_3d_id FROM asset_type WHERE lower(code) = lower(%s)", (ref,))
        if arow and arow.get("default_asset_3d_id") is not None:
            return model_by_id(arow["default_asset_3d_id"])
        return None

    # a meter row / id / name: per-instance override → type default
    row = ref if isinstance(ref, dict) else _meters.meter_by(ref)
    if not row:
        return None
    override = row.get("asset_3d_override_id")
    if override is not None:
        m = model_by_id(override)
        if m:
            return m
    return model_by_id(_type_default_model_id(row.get("mfm_type_id")))


def model_for_asset(asset_ref):
    """The 3D model for an `asset` table row (id/name) via asset.asset_3d_override_id → asset_type default → None."""
    if asset_ref is None:
        return None
    if isinstance(asset_ref, str) and not asset_ref.isdigit():
        row = _db.one("SELECT id, asset_type_id, asset_3d_override_id FROM asset WHERE lower(name) = lower(%s)",
                      (asset_ref,))
    else:
        row = _db.one("SELECT id, asset_type_id, asset_3d_override_id FROM asset WHERE id = %s", (asset_ref,))
    if not row:
        return None
    override = row.get("asset_3d_override_id")
    if override is not None:
        m = model_by_id(override)
        if m:
            return m
    return model_by_id(_asset_type_default_model_id(row.get("asset_type_id")))


def list_models():
    """Every 3D model across both tables → [model dict]. [] if none (the current ground truth)."""
    out = []
    for tbl in _MODEL_TABLES:
        if not _db.table_exists(tbl):
            continue
        out.extend(_db.dicts(f"SELECT id, key, name, category, file, description FROM {tbl} ORDER BY id"))
    return out
