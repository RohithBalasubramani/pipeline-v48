"""Layer 1 routing+asset hardening — the adversarial-batch fixes:
  · granularity reconcile: a single-meter asset routed to a panel-aggregate shell (or vice versa) is re-routed to the
    correct-granularity MIRROR page (layer1a.parse.granularity_reconcile + layer1a.route.route_to).
  · no_data is NOT a dead end: a resolved-but-empty asset carries onward-pick ALTERNATIVES (layer1b.resolve.no_data_gate).
  · no_data does NOT skip Layer 2: the harness still emits the per-leaf-null skeleton (run/harness asset gate).
Unit-first (deterministic, no live LLM) where the seam allows; the harness end-to-end is marked live."""
import pytest

from layer1a.parse.granularity_reconcile import mirror_page_key, target_shell
from layer1a.db_reads.page_specs import read_page_specs
from config.available_pages import filter_to_available
from layer1a.route import route_to
from layer1b.resolve.no_data_gate import no_data_outcome, _alternatives
from layer1b.resolve.asset_candidates import asset_candidates


# ── granularity reconcile ───────────────────────────────────────────────────────────────────────────────────────────
def _specs():
    return filter_to_available(read_page_specs("cmd_catalog"))


def test_target_shell_flips_to_correct_granularity():
    # panel shell + no feeders (single meter) → the METER group is correct, and it IS a mismatch
    assert target_shell("Panel overview shell", False) == ("meter", True)
    # panel shell + has feeders (aggregate) → PANEL is correct, no mismatch
    assert target_shell("Panel overview shell", True) == ("panel", False)
    # meter shell + has feeders (aggregate panel) → PANEL is correct, mismatch
    assert target_shell("Individual feeder / meter shell", True) == ("panel", True)
    # meter shell + no feeders (single meter) → METER is correct, no mismatch
    assert target_shell("Individual feeder / meter shell", False) == ("meter", False)
    # an unknown (non-granularity) shell → nothing to reconcile
    assert target_shell("UPS asset dashboard", False) == (None, False)


def test_mirror_single_meter_off_panel_shell():
    specs = _specs()
    # the batch-3 defect: a single-meter UPS routed to panel-overview RTM must mirror to the feeder-meter RTM
    m = mirror_page_key("panel-overview-shell/real-time-monitoring", "Panel overview shell", False, specs)
    assert m == "individual-feeder-meter-shell/real-time-monitoring"


def test_mirror_uses_tail_alias():
    specs = _specs()
    # harmonics-pq (panel) ≡ power-quality (feeder) via the EXISTING routes.page_tail_alias row
    m = mirror_page_key("panel-overview-shell/harmonics-pq", "Panel overview shell", False, specs)
    assert m == "individual-feeder-meter-shell/power-quality"


def test_mirror_aggregate_panel_off_meter_shell():
    specs = _specs()
    m = mirror_page_key("individual-feeder-meter-shell/voltage-current", "Individual feeder / meter shell", True, specs)
    assert m == "panel-overview-shell/voltage-current"


def test_no_reconcile_when_granularity_matches():
    specs = _specs()
    # panel shell + aggregate panel = correct → no mirror
    assert mirror_page_key("panel-overview-shell/real-time-monitoring", "Panel overview shell", True, specs) is None
    # meter shell + single meter = correct → no mirror
    assert mirror_page_key("individual-feeder-meter-shell/voltage-current",
                           "Individual feeder / meter shell", False, specs) is None


def test_no_reconcile_when_has_feeders_undecidable_or_non_granularity_shell():
    specs = _specs()
    assert mirror_page_key("panel-overview-shell/real-time-monitoring", "Panel overview shell", None, specs) is None
    assert mirror_page_key("ups-asset-dashboard/battery-autonomy", "UPS asset dashboard", False, specs) is None


def test_route_to_builds_valid_target_route():
    rr = route_to("individual-feeder-meter-shell/real-time-monitoring", "power", "snapshot", "cmd_catalog",
                  reason="test")
    assert rr["page_key"] == "individual-feeder-meter-shell/real-time-monitoring"
    assert rr["metric"] == "power" and rr["intent"] == "snapshot"
    assert rr["routing"]["page_key_how"] == "granularity_reconcile"
    assert rr["page_spec"]["shell"] == "Individual feeder / meter shell"


def test_route_to_rejects_unknown_page():
    with pytest.raises(RuntimeError):
        route_to("nope/not-a-page", "power", "snapshot", "cmd_catalog")


# ── no_data alternatives (not a dead end) ───────────────────────────────────────────────────────────────────────────
def test_no_data_outcome_without_cands_is_empty():
    asset = {"mfm_id": 999, "name": "Dark", "class": "Panel", "has_data": False}
    o = no_data_outcome(asset)
    assert o and o["how"] == "no_data" and o["candidates"] == []


def test_no_data_outcome_carries_alternatives():
    cands = asset_candidates()
    # a fabricated dark PANEL asset — alternatives must be REAL data-bearing rows, none of them the dark asset
    dark = {"mfm_id": 10 ** 9, "name": "Dark-Panel", "class": "Panel", "has_data": False}
    o = no_data_outcome(dark, cands)
    assert o["how"] == "no_data"
    assert o["candidates"], "no_data must offer onward-pick alternatives (not a dead-end picker)"
    assert all(c["mfm_id"] != dark["mfm_id"] for c in o["candidates"])
    assert all(c["has_data"] for c in o["candidates"])          # every alternative is renderable


def test_no_data_alternatives_prefer_same_class_first():
    cands = asset_candidates()
    dark = {"mfm_id": 10 ** 9, "name": "Dark-UPS", "class": "UPS", "has_data": False}
    alts = _alternatives(dark, cands)
    classes = [a["class"] for a in alts]
    if "UPS" in classes:                                        # if any data-bearing UPS exists, it must lead
        first_ups = classes.index("UPS")
        first_other = next((i for i, c in enumerate(classes) if c != "UPS"), len(classes))
        assert first_ups < first_other


def test_has_data_asset_is_not_no_data():
    assert no_data_outcome({"mfm_id": 1, "name": "Live", "has_data": True}, asset_candidates()) is None


# ── harness: no_data runs Layer 2 (structure-preserving) ────────────────────────────────────────────────────────────
@pytest.mark.live
def test_harness_no_data_runs_layer2_skeleton():
    """A no_data page must NOT skip Layer 2: every card gets a structure-preserving metadata payload (not None), so the
    FE mounts its real component with per-leaf-null leaves instead of a generic placeholder."""
    from run.harness import run_pipeline
    out = run_pipeline("harmonics and power quality for PCC Panel 4")
    assert out.get("asset_no_data") is True                     # telemetry preserved (FE greys the dark asset)
    l2 = out.get("layer2")
    assert l2, "Layer 2 must run for a no_data asset (skeleton), not be skipped"
    assert all(o.get("payload") is not None for o in l2.values()), "every card gets a structure-preserving payload"
    # onward-pick alternatives ride the candidate_list so the picker is never a dead end
    assert (out.get("layer1b") or {}).get("candidate_list")


@pytest.mark.live
def test_harness_reconciles_single_meter_off_panel_shell():
    """A single-meter UPS whose prompt routes to a panel-overview shell is reconciled to the feeder-meter shell."""
    from run.harness import run_pipeline
    import os
    os.environ["V48_SKIP_LAYER2"] = "1"
    try:
        out = run_pipeline("real time monitoring for GIC-01-N3-UPS-01")
    finally:
        os.environ.pop("V48_SKIP_LAYER2", None)
    l1a = out.get("layer1a") or {}
    asset = (out.get("layer1b") or {}).get("asset") or {}
    if asset.get("has_feeders") is False:                       # the UPS is a single meter
        assert l1a.get("shell") == "Individual feeder / meter shell"
        assert "individual-feeder-meter-shell" in l1a.get("page_key", "")
