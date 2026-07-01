"""grounding/metric_class.py — the CLASS-vs-PAGE feasibility gate: does the resolved meter expose the column CLASS the
requested page actually needs?

THE PROBLEM (DS-07, class-vs-page, SCADA-pin): a page requires a metric class — energy-power needs power+energy,
power-quality needs thd, voltage-current needs voltage+current, overview-sld-3d needs breaker. If a card resolves a
meter whose schema simply has no column of that class (a feedbacks_35 SCADA table pinned to an energy page; a tm_ups
table on a THD page; an ng_se_jk transformer on a harmonics page), the page can never render real values — it must
honest-degrade BEFORE routing, not blank later.

THE FIX (deterministic, no AI): read the page's required classes from cmd_catalog.metric_class (config.metric_class),
read the meter's present quantities from its schema fingerprint (grounding.schema_route → schema_slot_map), and check
coverage. NO hardcoded page→class map and NO hardcoded class→column map here — the page requirements and the physical
quantities are both EDITABLE DB rows; only the generic class↔quantity relationship (a required class is satisfied by any
present quantity carrying that class token, so `power` is met by active_/apparent_/reactive_power) lives here.

Covers: DS-07, class-vs-page, SCADA-pin.
"""
from __future__ import annotations

from config import metric_class as cfg
from grounding import schema_route as sr


def _quantity_satisfies(required_class, quantity):
    """A page's required CLASS is satisfied by a present QUANTITY when they name the same physical thing.

    Direct hit ('energy'=='energy', 'thd'=='thd', 'voltage'=='voltage', 'breaker'=='breaker') OR the quantity carries
    the class as a token, so the broad class 'power' is met by 'active_power'/'apparent_power'/'reactive_power'. This is
    a generic string-relationship over the two DB vocabularies — not a hardcoded per-class mapping table.
    """
    if not required_class or not quantity:
        return False
    rc, qn = required_class.lower(), quantity.lower()
    if rc == qn:
        return True
    # token match: the quantity's underscore-separated tokens include the class (active_power ⊇ power).
    return rc in qn.split("_")


def _present_quantities(table):
    """The SET of quantity classes physically present on `table` (from its fingerprint's routed slot map)."""
    fp_map = sr.routed_map(table)
    return {v.get("quantity") for v in fp_map.values() if v.get("quantity")}


def _covers(table, required_class):
    """True if `table` exposes at least one present column satisfying `required_class`."""
    quantities = _present_quantities(table)
    return any(_quantity_satisfies(required_class, qn) for qn in quantities)


def missing_classes(table, page_key):
    """The required classes for `page_key` that `table`'s schema does NOT expose (empty ⇒ the page is renderable here).

    An unconstrained page (no metric_class rows) returns [] — every meter can render it.
    """
    required = cfg.required_classes(page_key)
    if not required:
        return []
    return [rc for rc in required if not _covers(table, rc)]


def has_class(asset, page_key):
    """Does the resolved `asset` (dict with a `table`) expose ALL column classes `page_key` requires?

    True ⇒ the page is class-feasible on this meter. False ⇒ honest-degrade the card (wrong-class / SCADA pin) with the
    machine reason from missing_classes(). An asset with no table (aggregate panel resolved via feeders) defers to the
    representative feeder table under its `table` key; if none is present, returns False (no own class evidence).
    """
    table = _asset_table(asset)
    if not table:
        return False
    return not missing_classes(table, page_key)


def class_gate(asset, page_key):
    """The full gate verdict for the fact-sheet: {ok, missing, required, cause}.

    cause='no_class' (a seeded reason_template) when a required class is absent — the caller fills the human sentence
    via config.reason_templates.reason('no_class', page=page_key, missing=...).
    """
    table = _asset_table(asset)
    required = cfg.required_classes(page_key)
    if not table:
        return {"ok": False, "missing": list(required), "required": list(required),
                "cause": "no_class"}
    missing = missing_classes(table, page_key)
    return {"ok": not missing, "missing": missing, "required": list(required),
            "cause": ("no_class" if missing else None)}


def _asset_table(asset):
    """The neuract table for an asset dict/str — tolerates the asset_candidates.as_asset() shape and a bare table name."""
    if isinstance(asset, str):
        return asset or None
    if isinstance(asset, dict):
        return asset.get("table") or asset.get("table_name") or None
    return None
