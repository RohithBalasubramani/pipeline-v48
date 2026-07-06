"""registries/neuract/nameplate.py — a meter's NAMEPLATE / rating / limit params from lt_parameter + lt_config_field/value.

Single concern: for a given MFM (or its type), assemble the rated-capacity / limit / threshold params the plant defines
for it, honest-degrading around the parts that are empty.

REAL SCHEMA (introspected) + ground-truth population:
  - lt_parameter(name, column_name, kind, unit, spec, mfm_type_id): metric DICTIONARY per type. Currently EMPTY (0 rows)
    → params_for degrades gracefully (returns whatever config fields resolve).
  - lt_config_field(key, label, data_type, unit, default_value, mfm_type_id, section, display_order): 14 rows — the
    nameplate FIELD definitions per mfm_type (rated_kva, rated_kw, event_sag_pct_of_nominal, …), with a default_value.
  - lt_config_value(value, field_id, mfm_id): the PER-METER override of a field. Currently EMPTY (0 rows) → each field
    honest-degrades to its lt_config_field.default_value (a plant-declared default, NOT a fabricated number).
  - lt_mfm.rated_capacity_kva: a direct per-meter rating column (surfaced as a first-class param when present).

Resolution per field: lt_config_value(field, this mfm) → else lt_config_field.default_value → else None. `source` on each
returned param records which one won ('meter' | 'type_default' | 'mfm_column' | 'parameter_spec') so callers know
whether a value is real-per-meter or a declared default. Honest-degrade: unknown meter / no fields → {} or []. [atomic]
"""
from __future__ import annotations

from registries.neuract import _db
from registries.neuract import meters as _meters


def _num(x):
    if x in (None, "", "NULL"):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return x


def _mfm_row(mfm):
    return mfm if isinstance(mfm, dict) else _meters.meter_by(mfm)


def _config_fields(mfm_type_id):
    """The lt_config_field definitions for a type → [row dicts] (empty list if none / no type)."""
    if mfm_type_id is None:
        return []
    return _db.dicts(
        "SELECT id, key, label, data_type, unit, default_value, section, display_order "
        "FROM lt_config_field WHERE mfm_type_id = %s ORDER BY display_order, id",
        (mfm_type_id,),
    )


def _config_values(mfm_id):
    """The per-meter lt_config_value overrides → {field_id: value} (empty if none — currently the ground-truth case)."""
    got = _db.rows(
        "SELECT field_id, value FROM lt_config_value WHERE mfm_id = %s",
        (mfm_id,),
    )
    return {r[0]: r[1] for r in got if r and r[0] is not None}


def _parameter_specs(mfm_type_id):
    """The lt_parameter metric dictionary for a type → [row dicts] (currently EMPTY → []). Adds spec/unit per metric."""
    if mfm_type_id is None or not _db.table_exists("lt_parameter"):
        return []
    return _db.dicts(
        "SELECT name, column_name, kind, unit, spec, description "
        "FROM lt_parameter WHERE mfm_type_id = %s ORDER BY id",
        (mfm_type_id,),
    )


def params_for(mfm):
    """Every nameplate / rating / limit param defined for a meter → [ {key, label, value, unit, source, section} ].

    `mfm` = an MFM id, name, or row dict. Value resolution per lt_config field: the per-meter lt_config_value → else the
    lt_config_field.default_value (source='type_default') → else None. lt_mfm.rated_capacity_kva is surfaced as its own
    param (key='rated_capacity_kva', source='mfm_column') when present. lt_parameter specs (metric dictionary) are
    appended as value-less entries (source='parameter_spec') so a card knows the unit/spec even before a value exists.
    [] for an unknown meter. Honest-degrade: never invents a value — a declared default is tagged as such."""
    row = _mfm_row(mfm)
    if not row:
        return []
    try:
        mfm_id = int(row["id"])
    except (KeyError, TypeError, ValueError):
        return []
    type_id = row.get("mfm_type_id")
    out = []

    # 1) the direct per-meter rating column on lt_mfm (real per-meter value when set)
    rc = _num(row.get("rated_capacity_kva"))
    if rc is not None:
        out.append({"key": "rated_capacity_kva", "label": "Rated Capacity",
                    "value": rc, "unit": "kVA", "source": "mfm_column", "section": "Rating & Identity"})

    # 2) the configurable nameplate fields for this meter's type, resolved per-meter → else declared default
    overrides = _config_values(mfm_id)
    for f in _config_fields(type_id):
        fid = f.get("id")
        if fid in overrides:
            raw, src = overrides[fid], "meter"
        else:
            raw, src = f.get("default_value"), "type_default"
        raw = raw if raw not in ("",) else None            # empty declared default = no value (honest-degrade)
        out.append({
            "key": f.get("key"), "label": f.get("label"),
            "value": _num(raw), "unit": f.get("unit"),
            "source": (src if raw is not None else "absent"),
            "section": f.get("section"),
        })

    # 3) the lt_parameter metric dictionary (unit/spec only — currently empty, so usually a no-op)
    for p in _parameter_specs(type_id):
        out.append({
            "key": p.get("column_name") or p.get("name"), "label": p.get("name"),
            "value": None, "unit": p.get("unit"),
            "source": "parameter_spec", "section": p.get("kind"),
        })
    return out


def param(mfm, key):
    """One nameplate param by key → its param dict, or None (honest-degrade for an unknown meter/key)."""
    k = str(key).strip().lower()
    for p in params_for(mfm):
        if (p.get("key") or "").strip().lower() == k:
            return p
    return None


def rated_kva(mfm):
    """The rated kVA for a meter → float or None. Prefers the direct lt_mfm column, else the rated_kva config field."""
    p = param(mfm, "rated_capacity_kva") or param(mfm, "rated_kva")
    v = p.get("value") if p else None
    return v if isinstance(v, (int, float)) else None
