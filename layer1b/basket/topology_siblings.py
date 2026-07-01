"""layer1b/basket/topology_siblings.py — expand the L1b basket across an aggregate panel's MEMBER feeder tables. [spec §2 L1b; TOPO-01..07, DS-08]

column_basket picks ONE representative feeder table for schema (every neuract meter shares the 72-col schema, so one is
enough to NAME the columns). But an AGGREGATE card (panel total, Sankey, section heatmap) must SUM over EVERY populated
member feeder — so this unit attaches the full member set + a coverage count (N of M reporting) to the basket.

SINGLE SOURCE OF TRUTH: member resolution is delegated ENTIRELY to data.lt_panels.panel_members — the one function that
owns the topology gotchas (FROM-side-only fan-out, recurse through empty aggregates, has_data filter, dedup on
to_mfm_id, orphan detection). This file only PROJECTS that result into the basket shape + a partial flag; it does not
re-walk the graph, so coverage/degrade behaviour stays uniform with every other aggregate consumer. [TOPO-07]

The partial threshold is read from the editable cmd_catalog.data_quality_policy (feeder_coverage_partial_pct) — no
magic % in logic. Members are value-aware (meaningful=True): a member only 'reports' if its table carries usable data.
"""
from config.quality_policy import num as _policy_num
from data.lt_panels.panel_members import panel_members


def panel_member_tables(mfm_id):
    """Ordered list of the panel's POPULATED (reporting) member feeder tables — the tables an aggregate worker sums.
    Delegates to panel_members (value-aware). Empty/non-reporting members are excluded here (they are still counted in
    the coverage denominator by expand_basket_with_siblings). [] for a leaf/orphan."""
    res = panel_members(mfm_id, meaningful=True)
    return [m["table"] for m in res.get("members", []) if m.get("reporting") and m.get("table")]


def expand_basket_with_siblings(basket, asset):
    """Add topology-sibling member tables + coverage metadata to a card-agnostic basket, IN PLACE (and returned).
    Only fires for an aggregate panel (asset.has_feeders); a leaf/real meter is returned unchanged. The column set is
    left as-is (single representative schema); `member_tables` is the full populated fan-out the aggregate worker sums,
    and `coverage` carries reporting/expected + a partial flag driven by the editable coverage policy. [DS-08, TOPO-04]"""
    if not asset or not asset.get("has_feeders") or not asset.get("mfm_id"):
        return basket

    res = panel_members(asset["mfm_id"], meaningful=True)     # THE member-resolution single source of truth
    members = [m["table"] for m in res.get("members", []) if m.get("reporting") and m.get("table")]
    reporting = res.get("reporting_count", len(members))
    expected = res.get("expected_count", 0)
    orphaned = bool(res.get("orphaned"))

    partial_pct = _policy_num("feeder_coverage_partial_pct", 50.0)
    pct = (100.0 * reporting / expected) if expected else (100.0 if reporting else 0.0)

    basket["member_tables"] = members
    basket["coverage"] = {
        "reporting_count": reporting,
        "expected_count": expected,
        "reporting_pct": round(pct, 1),
        "partial": bool(expected) and pct < partial_pct,     # < policy % feeders reporting → honest-partial aggregate
        "no_members": reporting == 0,                        # no populated feeder → honest-blank the aggregate
        "orphaned": orphaned,                                # no topology at all → 'no topology mapped' degrade [TOPO-01]
    }
    # union member tables into the basket's table list (schema is shared; the worker needs the full member set)
    tabs = list(basket.get("tables") or [])
    for t in members:
        if t not in tabs:
            tabs.append(t)
    basket["tables"] = tabs
    return basket
