"""config/asset_granularity.py — the SINGLE DB-driven policy for which asset CLASSES use PANEL-AGGREGATE granularity
(the panel-overview shell + the member-feeder basket expansion) vs SINGLE-METER granularity.

Shared by BOTH the Layer-1a route reconcile (layer1a.parse.granularity_reconcile) and the Layer-1b basket
sibling-expansion (layer1b.basket.topology_siblings), so the two can never drift. THE DEFECT this centralises: those
two places each keyed on `has_feeders` alone, so a Transformer/DG/UPS that happens to feed downstream loads was treated
as a panel — forced onto the panel-overview shell AND given an 18-table member fan-out — and its own real meter data
then failed to bind (validation 'column absent', every card honest-blank). A single asset is a single meter.

Live value = cmd_catalog.app_config 'routes.panel_granularity_classes' (json list); code default ['Panel']."""
from config.app_config import cfg


def panel_classes():
    """The set of asset classes (lowercased) whose natural home is the panel-aggregate granularity."""
    v = cfg("routes.panel_granularity_classes", ["Panel"])
    return {str(x).lower() for x in (v if isinstance(v, list) and v else ["Panel"])}


def belongs_on_panel(has_feeders, asset_class):
    """Does this asset use PANEL-AGGREGATE granularity? CLASS is decisive — the panel-overview shell + member fan-out is
    a Panel-class home. A non-panel asset with downstream feeders (a Transformer feeding a PCC, a DG with loads) is a
    single asset: its OWN meter, no member aggregation. Falls back to the legacy has_feeders heuristic ONLY when the
    class is unknown (never regress a case where class wasn't resolved).

    LEAF-PANEL CARVE-OUT [#2, BPDB-01]: a panel-CLASS asset with NO feeders (has_feeders is decisively False — a board
    named like a panel but a single leaf meter, e.g. BPDB-01) is NOT an aggregate: the panel-overview shell would fan
    out to 0 members and honest-blank every card. It is a single meter → False. Only applies when has_feeders is
    DECISIVELY False; None (undecidable) still trusts the class so a real panel whose edges failed to load doesn't
    regress to single-meter."""
    if asset_class:
        if has_feeders is False:
            return False
        return str(asset_class).lower() in panel_classes()
    return bool(has_feeders)
