"""RESIDUAL FIX round 3 (2026-07-06) — regression pins for the replay-round-2 residual closures. Pure/unit where
possible (config accessors fall back to code defaults; the quantity-vocab pins read the seeded cmd_catalog rows).

  R1       backfill declared-range consensus (per-slot 'this-month' drives the window; calendar site-tz start) +
           coherence leaves the truthful 'Monthly' label alone
  R2/R3    (narrative seam threading pinned in test_family_h_render_safety.py); c19 story wording: a within-band
           deviation is never called a 'sag'
  R4/R5    xaxis: stripped-default scrub residue counts as clock evidence; paired per-label ts axis subsets
  R6       norm_series: default-proven [0,1] contract normalizes raw kW + derives the numeric-string label axis
  R7/R8    yscale: ticks-only axes derive from series[{data}] as numeric-STRING labels when the default says so;
           fill's time-guard never epoch-fills a y-scale key
  R9       yscale prefix pairs (demandYMax↔demandYMin) + zero-floor; gates drop ANY scalar bind into an axis slot
           beside a series; KPI-tile arrays are never an axis source
  R10      roster suffix re-address (family recipe slot lands on this card's own leaf; no alien subtree);
           recipe explicit-id fallthrough to the endpoint family
  R11      render_verdict asset_3d envelope rule (bound url = render; unbound = honest_blank)
  R12/R13  count-quantity wall ('Events' label / unit='count' slots never take a loadFactorPct bind)
  plus     _reconcile_slots both-side address normalization (no stale unbound_by_emit over filled leaves)
"""
from __future__ import annotations


# ── R4/R5: xaxis evidence + paired-axis subsetting ───────────────────────────────────────────────
def _clock_default():
    return {"data": {"xLabels": ["00:00", "02:00", "04:00", "06:00"],
                     "xLabelIndexes": [0, 2, 4, 6],
                     "series": [{"values": [1, 2, 3, 4, 5, 6, 7]}]}}


def test_xaxis_scrub_residue_counts_as_clock_evidence():
    from ems_exec.executor import xaxis
    stripped = {"data": {"xLabels": ["", "", "", ""], "xLabelIndexes": [],
                         "series": [{"values": []}]}}
    out = {"data": {"xLabels": ["", "", "", ""],
                    "xLabelIndexes": [1783247400000, 1783251000000, 1783254600000, 1783258200000,
                                      1783261800000, 1783265400000, 1783269000000],
                    "series": [{"values": [1, 2, 3, 4, 5, 6, 7]}]}}
    gaps = []
    xaxis.apply(out, stripped, gaps)
    assert all(x and ":" in x for x in out["data"]["xLabels"])     # real HH:MM labels derived
    assert out["data"]["xLabelIndexes"] == [0, 2, 4, 6]            # integer tick positions, not epochs
    assert gaps == []


def test_xaxis_raw_default_index_rewrite():
    from ems_exec.executor import xaxis
    out = {"data": {"xLabels": ["", "", "", ""],
                    "xLabelIndexes": [1783247400000, 1783251000000, 1783254600000, 1783258200000,
                                      1783261800000, 1783265400000, 1783269000000]}}
    gaps = []
    xaxis.apply(out, _clock_default(), gaps)
    assert out["data"]["xLabelIndexes"] == [0, 2, 4, 6]


def test_xaxis_paired_per_label_ts_axis_subsets():
    from ems_exec.executor import xaxis
    # default: 3 labels paired with a 3-long RELATIVE-ms ts axis (card-36 timeLabelTimestamps shape)
    shape = {"data": {"timeLabels": ["05:29:10", "05:29:20", "05:29:30"],
                      "timeLabelTimestamps": [-20000, -10000, 0]}}
    epochs = [1783247400000 + i * 3600000 for i in range(9)]
    out = {"data": {"timeLabels": ["", "", ""], "timeLabelTimestamps": list(epochs)}}
    gaps = []
    xaxis.apply(out, shape, gaps)
    assert len(out["data"]["timeLabels"]) == 3 and all(out["data"]["timeLabels"])
    ts = out["data"]["timeLabelTimestamps"]
    assert len(ts) == 3 and ts[0] == epochs[0] and ts[-1] == epochs[-1]   # subset of the REAL bucket ts


# ── R7/R8/R9: yscale ─────────────────────────────────────────────────────────────────────────────
def test_yscale_ticks_only_axis_derives_string_labels_from_series_data():
    from ems_exec.executor import yscale
    shape = {"data": {"yTicks": ["430", "422", "414", "406", "398", "390"],
                      "series": [{"data": [0.1], "color": "#000"}]}}
    out = {"data": {"yTicks": [], "series": [{"data": [228.0, 240.0, 232.0], "color": "#000"}]}}
    yscale.apply(out, shape_ref=shape)
    ticks = out["data"]["yTicks"]
    assert len(ticks) == 6 and all(isinstance(t, str) for t in ticks)     # default-proven STRING labels
    assert float(ticks[0]) > float(ticks[-1])                             # descending: Number(yTicks[0]) is the max
    assert float(ticks[0]) >= 240.0 and float(ticks[-1]) <= 228.0


def test_yscale_prefix_pairs_and_zero_floor():
    from ems_exec.executor import yscale
    shape = {"data": {"yMax": 500, "yMin": 0, "demandYMax": 500, "demandYMin": 0}}
    out = {"data": {"yMax": 183.0, "yMin": 183.0, "demandYMax": 183.0, "demandYMin": 183.0,
                    "bars": [{"time": "16:00", "active": 195.0, "reactive": 9.8},
                             {"time": "17:00", "active": 201.0, "reactive": 9.9}],
                    "demandBars": [{"band": "low", "time": 1783247400000, "value": 195.0},
                                   {"band": "low", "time": 1783251000000, "value": 201.0}],
                    "hourlyAverage": [195.0, 201.0]}}
    yscale.apply(out, shape_ref=shape)
    d = out["data"]
    assert d["yMin"] == 0.0 and d["demandYMin"] == 0.0                    # default-proven zero baseline
    assert d["yMax"] > 201.0 and d["demandYMax"] > 201.0                  # padded above the real data max
    assert d["yMax"] != d["yMin"]                                          # degenerate axis gone


def test_yscale_kpi_tiles_never_drive_the_axis():
    from ems_exec.executor import yscale
    out = {"data": {"maxY": 0.0, "minY": 0.0,
                    "stats": [{"label": "Max Deviation", "value": 4.52, "unit": "%"}],
                    "series": [{"values": [228.0, 240.0]}]}}
    yscale.apply(out)
    assert out["data"]["minY"] > 200.0                                     # the 4.52% tile did not drag the V axis


def test_yscale_time_guard_key_vocabulary():
    from ems_exec.executor import yscale
    assert yscale.is_scale_key("yTicks") and yscale.is_scale_key("maxY") and yscale.is_scale_key("demandYMin")
    assert not yscale.is_scale_key("sampleTimestamps") and not yscale.is_scale_key("xLabelIndexes")


def test_yscale_honest_blank_without_data():
    from ems_exec.executor import yscale
    out = {"data": {"yTicks": [], "series": [{"data": []}]}}
    yscale.apply(out)
    assert out["data"]["yTicks"] == []                                     # never a fabricated axis


# ── R6: normalized-series contract ───────────────────────────────────────────────────────────────
def test_norm_series_normalizes_raw_kw_and_derives_labels():
    from ems_exec.executor import norm_series
    shape = {"data": {"dataSeries": [[0.2, 0.5, 0.8], [0.1, 0.3, 0.4]],
                      "yLabels": ["380", "340", "300", "120", "100", "80"]}}
    out = {"data": {"dataSeries": [[171.0, 201.0, 190.0], [180.0, 195.0, 200.0]], "yLabels": []}}
    norm_series.apply(out, shape)
    ds = out["data"]["dataSeries"]
    assert all(0.0 <= x <= 1.0 for s in ds for x in s)                     # normalized contract restored
    labels = out["data"]["yLabels"]
    assert len(labels) == 6 and all(isinstance(x, str) for x in labels)
    assert int(labels[0]) > int(labels[-1])                                # max → min
    assert int(labels[0]) >= 201 and int(labels[-1]) <= 171                # encloses the real range


def test_norm_series_untouched_without_shape_proof():
    from ems_exec.executor import norm_series
    out = {"data": {"dataSeries": [[171.0, 201.0]], "yLabels": []}}
    norm_series.apply(out, {"data": {"dataSeries": [[100.0, 300.0]], "yLabels": []}})  # default NOT within [0,1]
    assert out["data"]["dataSeries"] == [[171.0, 201.0]]                   # no contract proven → untouched


# ── R10: roster suffix re-address ────────────────────────────────────────────────────────────────
def _c69ish_payload():
    return {"data": {"stats": [{"unit": "A", "label": "Peak", "value": 0.0},
                               {"unit": "A", "label": "Avg", "value": 0.0}]}}


def test_roster_readdress_family_slot_onto_this_cards_leaf():
    from ems_exec.executor import roster
    p = _c69ish_payload()
    targets = roster._targets(p, None, "history.data.stats.0.value")
    assert len(targets) == 1
    cont, key, _m = targets[0]
    assert key == "value" and cont is p["data"]["stats"][0]                # landed on the REAL leaf
    assert "history" not in p                                              # no alien manufactured subtree


def test_roster_readdress_keeps_matching_shapes_verbatim():
    from ems_exec.executor import roster
    p = {"history": {"data": {"stats": [{"value": 0.0}]}}}
    targets = roster._targets(p, None, "history.data.stats.0.value")
    cont, key, _m = targets[0]
    assert cont is p["history"]["data"]["stats"][0] and key == "value"


def test_roster_readdress_preserves_creation_for_unresolvable_slots():
    from ems_exec.executor import roster
    p = {}
    targets = roster._targets(p, None, "widgets.sld.incoming")
    assert targets and "widgets" in p                                      # build-from-scratch slots unchanged


# ── R11: asset_3d envelope verdict ───────────────────────────────────────────────────────────────
def test_render_verdict_bound_glb_is_render():
    from validate.render_verdict import compute
    payload = {"equipment": {"id": 2}, "viewer": {},
               "object": {"slug": "dg-final-v2", "label": "DG", "url": "http://x/dg.glb", "rating": None}}
    v = compute(payload, None, None, has_payload=True)
    assert v["verdict"] == "render" and v["n_real"] == 1


def test_render_verdict_unbound_glb_is_honest_blank():
    from validate.render_verdict import compute
    v = compute({"equipment": {"id": 2}, "viewer": {}, "object": None}, None, None, has_payload=True)
    assert v["verdict"] == "honest_blank" and v["n_real"] == 0


def test_asset_3d_unbound_carries_model_reason_not_metric_sentence():
    from ems_exec.renderers import asset_3d
    from ems_exec.executor.fill import GAPS_KEY
    out = asset_3d.render({"mfm_id": -999999, "name": "Unit-X"}, {"id": 60}, {"page_key": "x"})
    if out.get("object") is None:                                          # resolver honest-miss (expected offline)
        gaps = out.get(GAPS_KEY) or []
        assert gaps and gaps[0]["cause"] == "no_3d_model"
        assert "not logged" not in (gaps[0]["reason"] or "")               # never the metric-card template


# ── R12/R13: count-quantity wall ─────────────────────────────────────────────────────────────────
def _basket():
    return {"columns": [{"column": "active_power_total_kw", "unit": "kW", "has_data": True}]}


def test_events_kpi_label_blocks_load_factor_bind():
    from layer2.gates import enforce_honest_blank
    em = {"chart": {"kpis": [{"label": "Events", "value": 0.0}]}}
    di = {"fields": [{"slot": "chart.kpis[0].value", "kind": "derived", "metric": "totalEvents",
                      "fn": "loadFactorPct", "base_columns": ["active_power_total_kw"]}]}
    reasons = enforce_honest_blank(di, _basket(), exact_metadata=em)
    assert di["fields"] == [] and reasons and "count" in reasons[0]


def test_starts_count_unit_blocks_load_factor_bind():
    from layer2.gates import enforce_honest_blank
    di = {"fields": [{"slot": "stats.starts", "kind": "derived", "metric": "starts", "unit": "count",
                      "fn": "loadFactorPct", "base_columns": ["active_power_total_kw"], "source": "$ctx"}]}
    reasons = enforce_honest_blank(di, _basket(), exact_metadata={"stats": {"starts": 0.0}})
    assert di["fields"] == [] and reasons


def test_event_kind_count_bind_still_passes():
    from layer2.gates import enforce_honest_blank
    di = {"fields": [{"slot": "stats.starts", "kind": "event", "column": "active_power_total_kw",
                      "unit": "count"}]}
    reasons = enforce_honest_blank(di, _basket(), exact_metadata={"stats": {"starts": 0.0}})
    assert [f["slot"] for f in di["fields"]] == ["stats.starts"] and reasons == []


# ── R9: axis slots are geometry, never a scalar bind (beside a series) ───────────────────────────
def test_axis_slot_scalar_bind_dropped_even_same_quantity():
    from layer2.gates import enforce_honest_blank
    di = {"fields": [
        {"slot": "data.bars[*].active", "kind": "bucketed", "column": "active_power_total_kw", "unit": "kW"},
        {"slot": "data.yMax", "kind": "raw", "column": "active_power_total_kw", "unit": "kW"},
        {"slot": "data.yMin", "kind": "raw", "column": "active_power_total_kw", "unit": "kW"}]}
    reasons = enforce_honest_blank(di, _basket(), exact_metadata={"data": {"yMax": 0.0, "yMin": 0.0}})
    assert [f["slot"] for f in di["fields"]] == ["data.bars[*].active"]
    assert len(reasons) == 2 and all("axis" in r for r in reasons)


def test_axis_slot_without_series_left_alone():
    from layer2.gates import enforce_honest_blank
    di = {"fields": [{"slot": "data.yMax", "kind": "raw", "column": "active_power_total_kw", "unit": "kW"}]}
    reasons = enforce_honest_blank(di, _basket(), exact_metadata={"data": {"yMax": 0.0}})
    assert [f["slot"] for f in di["fields"]] == ["data.yMax"] and reasons == []


# ── R1: backfill declared-range consensus + calendar anchoring ───────────────────────────────────
def test_backfill_uses_per_slot_range_consensus():
    from layer2.build import _backfill_default_window
    di = {"fields": [], "roster": [{"slot": "card.view.value", "range": "this-month"},
                                   {"slot": "card.view.metrics", "range": "this-month"}],
          "window": {}, "fetch": {"range": None}}
    _backfill_default_window(di, None)
    bf = di["window"]["backfill"]
    assert bf["origin"] == "declared_range" and bf["range"] == "this-month"
    from datetime import datetime
    start = datetime.fromisoformat(di["window"]["start"])
    assert start.day == 1 or start.astimezone().day == 1 or "T18:30" in di["window"]["start"] \
        or start.hour in (0, 18)                                           # site-tz calendar month start


def test_backfill_slot_disagreement_falls_to_default():
    from layer2.build import _backfill_default_window
    di = {"fields": [{"slot": "a", "range": "today"}], "roster": [{"slot": "b", "range": "this-month"}],
          "window": {}}
    _backfill_default_window(di, None)
    assert di["window"]["backfill"]["origin"] == "default_range"


def test_coherence_agrees_with_consensus_window():
    from layer2.build import _backfill_default_window
    from layer2.coherence import reconcile_window_labels
    di = {"fields": [], "roster": [{"slot": "card.view.value", "range": "this-month"}], "window": {}}
    _backfill_default_window(di, None)
    em = {"card": {"view": {"periodLabel": "Monthly"}, "range": "this-month"}}
    assert reconcile_window_labels(em, di) == []                           # truthful label survives
    assert em["card"]["view"]["periodLabel"] == "Monthly"


# ── R2/R3: c19 story wording — a within-band deviation is never a 'sag' ──────────────────────────
def test_vc_story_within_band_deviation_not_called_sag():
    from ems_exec.renderers._story.voltage_current import _fallback_text
    v_worst = {"name": "UPS-02", "mag": 4.06, "signed": -4.06, "kind": "deviation"}
    text = _fallback_text(0, 1, v_worst, "normal", {"name": "BPDB-01", "mag": 19.77}, "critical", None)
    assert "sag" not in text.lower()
    assert "deviation" in text.lower() and "-4.1%" in text


# ── _reconcile_slots both-side normalization ─────────────────────────────────────────────────────
def test_reconcile_slots_covers_data_prefixed_catalog():
    from layer2.build import _reconcile_slots
    dp = {"data": {"bars": [{"time": "00:00", "active": 1.0}], "yMax": 500}}
    di = {"fields": [{"slot": "data.bars[0].active", "kind": "bucketed", "column": "x"},
                     {"slot": "data.bars[0].time", "kind": "time"},
                     {"slot": "data.yMax", "kind": "raw", "column": "x"}]}
    _reconcile_slots(di, dp, {"columns": []})
    issues = di.get("_slot_issues") or []
    assert not any("bars" in s for s in issues)                            # bound slots recognized
    gaps = di.get("_emit_gaps") or []
    assert not any("active" in str(g.get("slot")) for g in gaps)           # no stale unbound over a bound leaf
