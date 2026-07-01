"""config/nameplates.py — thin reader over cmd_catalog.asset_nameplate (seeded by manage.py seed_nameplates).

THE nameplate source for V48 (rated/contract/nominal/role/section/category per neuract asset table). NO hardcoded
rating anywhere — every number is an editable row. A missing/unknown rating returns None so the caller honest-degrades
the loading% slot (never fabricates a denominator). [RN-01/02/05/07, DS-10, DID-03, VC-05]
"""
from data.db_client import q

_COLS = ["asset_table", "mfm_name", "rated_kva", "contracted_kva",
         "nominal_voltage_ll", "role", "section", "asset_category", "source"]


def _num(x):
    return None if x in (None, "", "NULL") else float(x)


def get_nameplate(asset_table):
    """The full nameplate row for a neuract table_name → dict (rated_kva/contracted_kva/nominal_voltage_ll numeric,
    others text) or None if the asset has no nameplate row at all."""
    rows = q("cmd_catalog",
             "SELECT " + ",".join(_COLS) + " FROM asset_nameplate "
             f"WHERE asset_table='{_esc(asset_table)}'")
    if not rows:
        return None
    r = rows[0]
    d = dict(zip(_COLS, r))
    for k in ("rated_kva", "contracted_kva", "nominal_voltage_ll"):
        d[k] = _num(d[k])
    return d


def rated_kva(asset_table):
    """Just the nameplate rated kVA (the loading% denominator), or None → honest-degrade."""
    np = get_nameplate(asset_table)
    return np["rated_kva"] if np else None


def nominal_voltage_ll(asset_table):
    np = get_nameplate(asset_table)
    return np["nominal_voltage_ll"] if np else None


def role_section(asset_table):
    """(role, section) for heatmap sectioning / limit lookup, or (None, None)."""
    np = get_nameplate(asset_table)
    return (np["role"], np["section"]) if np else (None, None)


def asset_category(asset_table):
    np = get_nameplate(asset_table)
    return np["asset_category"] if np else None


def all_nameplates():
    """Every row (for a build-time audit / bulk resolve)."""
    rows = q("cmd_catalog", "SELECT " + ",".join(_COLS) + " FROM asset_nameplate ORDER BY asset_table")
    out = []
    for r in rows:
        d = dict(zip(_COLS, r))
        for k in ("rated_kva", "contracted_kva", "nominal_voltage_ll"):
            d[k] = _num(d[k])
        out.append(d)
    return out


def _esc(s):
    return str(s).replace("'", "''")
