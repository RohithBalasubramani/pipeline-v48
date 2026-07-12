"""grounding/schema_route.py — the ROUTED column map for a live table: which real physical column fills each logical
SLOT, given the table's schema fingerprint.

THE PROBLEM (DS-03, DS-07): a card asks for a logical slot ('active_power_total_kw', 'voltage_r', 'energy_import_kwh').
On a p1_72 meter that column is literally named that; on a tm_ups_56 UPS it is `output_active_power_total_kw`; on a
feedbacks_35 SCADA table it does not exist at all. Feeding a tm/feedbacks table through the p1 map returns all-None.

THE FIX (deterministic, no AI): fingerprint the table (grounding.schema_fingerprint), then read the slot→column routing
from cmd_catalog.schema_slot_map (via config.schema_map — the EDITABLE table). A slot absent for that fingerprint
returns None → the caller honest-degrades that ONE slot with a reason, never force-fits a wrong column. ZERO hardcoded
column names here — every mapping is a DB row.

Covers: DS-03, DS-07. Feeds meaningful / metric_class / the POST value-fetch.
"""
from __future__ import annotations

from config import schema_map as sm
from grounding.schema_fingerprint import fingerprint, is_known


def route(table, slot):
    """The real physical column that fills logical `slot` on `table`, or None if that slot is absent for this schema.

    None when: the table is a sch_stub/feedbacks shape that lacks the slot, OR the slot simply is not mapped for the
    fingerprint. A None means honest-degrade that slot — the caller must NOT substitute a different column.
    """
    fp = fingerprint(table)
    if not is_known(fp):
        return None                                   # sch_stub → nothing routes; every slot honest-blanks
    return sm.column_for(fp, slot)


def routed_map(table):
    """{slot: {column_name, unit, quantity}} — every PRESENT slot for this table's fingerprint (absent slots omitted).

    The card's fact-sheet uses this to know exactly which slots are fillable on this meter and which honest-degrade.
    """
    fp = fingerprint(table)
    if not is_known(fp):
        return {}
    return sm.slot_map(fp)


def columns_for_quantity(table, quantity):
    """The real columns of a quantity class ('voltage','current','energy','thd',...) present on `table` →
    [{slot, column_name, unit}]. Empty when the table's fingerprint exposes no column of that class."""
    fp = fingerprint(table)
    if not is_known(fp):
        return []
    return sm.slots_for_quantity(fp, quantity)


def has_quantity(table, quantity):
    """Does `table` (by fingerprint) expose ANY present column of `quantity`? The building block of the class gate."""
    fp = fingerprint(table)
    if not is_known(fp):
        return False
    return sm.has_quantity(fp, quantity)


