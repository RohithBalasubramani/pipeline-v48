"""config/schema_map.py — thin reader over cmd_catalog.schema_slot_map (seeded by db/seed_schema_and_endpoints.py).

The routed column map: for a schema FINGERPRINT (p1_72 / tm_ups_56 / feedbacks_35 / ng_se_jk_70), which real physical
column fills each logical SLOT. A slot whose column_name is '' is NOT present in that fingerprint → the routed mapper
honest-degrades that slot (DS-03/07). NO hardcoded column names in logic code — they READ this table.
"""
from data.db_client import q

_COLS = ["fingerprint", "slot", "column_name", "unit", "quantity"]


def slot_map(fingerprint):
    """{slot: {column_name, unit, quantity}} for a fingerprint (only PRESENT slots, column_name != '')."""
    rows = q("cmd_catalog",
             "SELECT slot, column_name, unit, quantity FROM schema_slot_map "
             f"WHERE fingerprint='{_esc(fingerprint)}' AND column_name<>'' ORDER BY slot")
    return {r[0]: {"column_name": r[1], "unit": r[2], "quantity": r[3]} for r in rows}


def column_for(fingerprint, slot):
    """The real physical column that fills `slot` in `fingerprint`, or None if the slot is absent there."""
    rows = q("cmd_catalog",
             "SELECT column_name FROM schema_slot_map "
             f"WHERE fingerprint='{_esc(fingerprint)}' AND slot='{_esc(slot)}'")
    if not rows or not rows[0][0]:
        return None
    return rows[0][0]


def slots_for_quantity(fingerprint, quantity):
    """All present slots of a given quantity class (e.g. 'voltage') for a fingerprint → [{slot,column_name,unit}]."""
    rows = q("cmd_catalog",
             "SELECT slot, column_name, unit FROM schema_slot_map "
             f"WHERE fingerprint='{_esc(fingerprint)}' AND quantity='{_esc(quantity)}' AND column_name<>'' ORDER BY slot")
    return [{"slot": r[0], "column_name": r[1], "unit": r[2]} for r in rows]


def has_quantity(fingerprint, quantity):
    """Does this fingerprint expose ANY present column of a quantity class? (feeds the metric-class feasibility gate)."""
    rows = q("cmd_catalog",
             "SELECT 1 FROM schema_slot_map "
             f"WHERE fingerprint='{_esc(fingerprint)}' AND quantity='{_esc(quantity)}' AND column_name<>'' LIMIT 1")
    return bool(rows)


def fingerprints():
    """All known fingerprint keys."""
    rows = q("cmd_catalog", "SELECT DISTINCT fingerprint FROM schema_slot_map ORDER BY 1")
    return [r[0] for r in rows]


def _esc(s):
    return str(s).replace("'", "''")
