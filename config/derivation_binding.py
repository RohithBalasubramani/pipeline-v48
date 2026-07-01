"""config/derivation_binding.py — thin reader over cmd_catalog.derivation_binding (recovery fn ↔ base columns).

For a derived metric: the registry fn that computes it, the real base columns it needs, and its fidelity. A fn is only
bindable when its base_columns ⊆ the columns actually present/fetched (the caller checks that); a 'nameplate:*' pseudo-
column means the base comes from asset_nameplate, not the meter frame. NO hardcoded fn/base map in logic code — READS
this table. [DID-02/05, DS-04(ieee519)]
"""
from data.db_client import q

_COLS = ["metric", "fn", "base_columns", "fidelity"]


def binding(metric):
    """{fn, base_columns:[...], fidelity} for a derived metric, or None if it isn't a registered derivation."""
    rows = q("cmd_catalog",
             "SELECT " + ",".join(_COLS) + f" FROM derivation_binding WHERE metric='{_esc(metric)}'")
    if not rows:
        return None
    _, fn, base, fidelity = rows[0]
    return {"fn": fn, "base_columns": _split(base), "fidelity": fidelity}


def base_columns(metric):
    """The real base columns a metric's fn needs → [...] ('nameplate:rated_kva' style pseudo-cols kept as-is)."""
    b = binding(metric)
    return b["base_columns"] if b else []


def bindable(metric, present_columns):
    """True iff every non-nameplate base column of `metric` is in `present_columns` (the endpoint's fetched set).
    nameplate:* pseudo-columns are satisfied by the nameplate table, so they don't gate on the frame."""
    b = binding(metric)
    if not b:
        return False
    present = set(present_columns or [])
    for col in b["base_columns"]:
        if col.startswith("nameplate:"):
            continue
        if col not in present:
            return False
    return True


def all_bindings():
    rows = q("cmd_catalog", "SELECT " + ",".join(_COLS) + " FROM derivation_binding ORDER BY metric")
    return [{"metric": r[0], "fn": r[1], "base_columns": _split(r[2]), "fidelity": r[3]} for r in rows]


def _split(base):
    return [c.strip() for c in (base or "").split(",") if c.strip()]


def _esc(s):
    return str(s).replace("'", "''")
