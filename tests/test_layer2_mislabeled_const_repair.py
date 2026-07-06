"""★ mislabeled-const repair — the thermal-legend payload_error root-cause fix (sweep 15 / card 76).

The AI sometimes stamps kind="const" on a field it ALSO marks source="live"/"frame" (a legend's latest-value KPI,
a series point) but leaves valueless — a MEASURED binding mis-tagged as a literal. A truly literal field is
source=="const" WITH a baked `value`. layer2.resolve.column_override.apply must RECLASSIFY the mislabelled field to
the FRAME honest-blank path (kind=raw, source=frame, column=None) so a missing column blanks THAT one leaf (per-leaf
degradation) instead of tripping the card-level `fields[i] kind=const without a value` gate → payload_error → the
whole card renders blank-with-error.

Non-live: pure in-memory data_instructions + a minimal basket; no LLM, no :5433.
"""
from layer2.resolve.column_override import apply as override
from layer2.gates import gate_data_instructions


def _basket():
    # a plain electrical basket that does NOT measure thermal quantities (hotspotC/oilC/…)
    return {"columns": [{"column": "active_power_total_kw", "metric": "active_power", "unit": "kW", "has_data": True}]}


def test_valueless_live_const_reclassified_to_frame():
    """kind=const + source=live + no value + metric=hotspotC (no basket column) → honest-blank frame leaf, not a const."""
    di = {"fields": [
        {"slot": "timeline.legend[0].value", "kind": "const", "source": "live",
         "metric": "hotspotC", "agg": "last", "label": "Hotspot", "unit": "°C"},
    ]}
    di, _issues = override(di, _basket())
    f = di["fields"][0]
    assert f["kind"] != "const", "a live/valueless const must be reclassified off the const path"
    assert f["source"] == "frame", "reclassified to the frame honest-blank path"
    assert f.get("column") is None, "no basket column measures the thermal quantity → honest-blank leaf"


def test_reclassified_field_passes_the_data_gate():
    """After the repair the whole card CONFORMS (no `kind=const without a value` gate hit → no payload_error)."""
    di = {"fields": [
        {"slot": "timeline.legend[0].value", "kind": "const", "source": "live", "metric": "hotspotC"},
        {"slot": "timeline.legend[1].value", "kind": "const", "source": "live", "metric": "oilC"},
    ]}
    di, _ = override(di, _basket())
    ok, issues = gate_data_instructions(di, _basket())
    assert ok, f"reclassified fields must pass the data gate cleanly: {issues}"
    assert not any("kind=const without a value" in i for i in issues)


def test_real_literal_const_is_untouched():
    """A TRUE literal (source=const OR a present value) is a baked threshold line — never reclassified."""
    di = {"fields": [
        {"slot": "timeline.hotspotWarnC", "kind": "const", "source": "const", "value": 120.0, "metric": "hotspotWarnC"},
        {"slot": "timeline.tempAxis.max", "kind": "const", "value": 100.0, "metric": "tempAxisMax"},
    ]}
    di, _ = override(di, _basket())
    for f in di["fields"]:
        assert f["kind"] == "const", "a real literal keeps kind=const"
        assert f.get("value") is not None
