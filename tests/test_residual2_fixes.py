"""RESIDUAL FIX round 2 (2026-07-06) — regression pins for the replay_round1 residual closures. Pure/unit (no LLM,
no neuract; cmd_catalog only via config accessors' code defaults where possible).

  R1/R2  roster gap channel (blank roster leaves reasoned; const-null why rides verbatim)
  R3/R5  narrative_ai zero-skeleton → nulled placeholders + host _emit_gaps merge (stale records dropped)
  R4     site-timezone calendar anchors ('today' at 00:03Z = IST midnight, never a 4-minute window)
  R6/R7  xaxis clock-label derivation + index-axis rewrite (+ per-leaf gap when underivable)
  R8     todaysEnergyTotalKwh = reversed-CT window deltas, active+reactive coherent
  R9     axis-coherence wall (percent fn never a kW axis floor)
  R10    topology-boundary wall (hv_input_kw never proxied by the meter's own power)
  R11    percent-vs-dimensional wall (raw kW never ships under unit '%')
  R12    view auto-select (empty default view → the data-bearing sibling)
  R13    sibling-unit slot classification (power fn never fills a '°C' KPI cell)
  R14    element_chrome_keys in leaf_classify (warn/trip/width survive the strip byte-identical)
"""
from __future__ import annotations

from datetime import datetime


# ── R4: site-tz calendar anchors ─────────────────────────────────────────────────────────────────
def test_today_range_anchors_at_site_midnight_not_utc():
    from ems_exec.executor.fill import _range_start
    end = datetime.fromisoformat("2026-07-06T00:03:51+00:00")     # 05:33 IST
    start = _range_start("today", end)
    assert str(start) == "2026-07-05 18:30:00+00:00"              # IST midnight, not a 4-minute UTC-midnight window


def test_naive_anchor_keeps_legacy_midnight():
    from ems_exec.executor.fill import _range_start
    start = _range_start("today", datetime.fromisoformat("2026-07-06T10:00:00"))
    assert str(start) == "2026-07-06 00:00:00"


def test_period_starts_month_in_site_tz():
    from ems_exec.executor.fill import _period_starts
    got = _period_starts(datetime.fromisoformat("2026-07-06T00:03:51+00:00"))
    assert str(got["this_month"]) == "2026-06-30 18:30:00+00:00"  # July 1 IST midnight, converted back to UTC


# ── R11: percent ↔ hard-dimensional wall ────────────────────────────────────────────────────────
def test_percent_slot_never_takes_a_power_column():
    from layer2.quantity_class import compatible
    assert compatible("percent", "power") is False                 # raw kW under unit '%' = fabrication (card 42)
    assert compatible("power", "percent") is False                 # mirrored
    assert compatible("percent", "load-factor") is True            # ratio-like stays compatible
    assert compatible("percent", "unbalance") is True
    assert compatible(None, "power") is True                       # unclassified never flags


# ── R9/R10/R13: the new emit walls ──────────────────────────────────────────────────────────────
_BASKET = {"columns": [{"column": "active_power_total_kw", "unit": "kW"},
                       {"column": "reactive_power_total_kvar", "unit": "kVAr"}]}


def _enforce(fields, em=None):
    from layer2.gates import enforce_honest_blank
    di = {"fields": fields}
    blanked = enforce_honest_blank(di, _BASKET, exact_metadata=em)
    return di["fields"], blanked


def test_axis_slot_percent_fn_dropped_under_kw_series():
    # ROUND-4 CONTRACT [wall precision rework]: beside a co-emitted series, an axis slot drops every cross-quantity
    # bind (the c40 percent-fn kW floor) and every SAMPLE read (yMax ← the instantaneous kW column — the degenerate
    # yMax=yMin=183 axis) — but a source whose OWN name IS the bound's direction (yMax ← fn worstPeakKw, a REAL
    # windowed peak of the series' quantity) KEEPS (corpus replay: the maxY←current_max/worstPeakKw FP family).
    kept, blanked = _enforce([
        {"slot": "data.bars[*].active", "kind": "bucketed", "column": "active_power_total_kw", "source": "$ctx"},
        {"slot": "data.yMin", "kind": "derived", "fn": "loadFactorWindowPct",
         "base_columns": ["active_power_total_kw"], "source": "$ctx"},
        {"slot": "data.yMax", "kind": "derived", "fn": "worstPeakKw",
         "base_columns": ["active_power_total_kw"], "source": "$ctx"},
        {"slot": "data.demandYMin", "kind": "raw", "column": "active_power_total_kw", "source": "$ctx"},
    ])
    slots = [f["slot"] for f in kept]
    assert "data.yMin" not in slots                                # percent fn under a kW series = cross-quantity
    assert "data.demandYMin" not in slots                          # instantaneous-sample read = degenerate axis
    assert "data.yMax" in slots                                    # a real windowed PEAK answers a max bound
    assert any("axis slot" in b for b in blanked)


def test_topology_boundary_slot_never_proxied():
    kept, blanked = _enforce([{"slot": "data.hvInputKw", "kind": "raw", "metric": "hvInputKw",
                               "column": "active_power_total_kw", "source": "$ctx"}])
    assert kept == [] and any("topology boundary" in b for b in blanked)


def test_expectation_slot_refuses_direct_column_read():
    kept, blanked = _enforce([{"slot": "data.expectedLoad[*].value", "kind": "bucketed",
                               "column": "active_power_total_kw", "source": "$ctx"}])
    assert kept == []                                              # (percent wall or expectation wall — either drops it)
    kept2, blanked2 = _enforce([{"slot": "data.forecastKw", "kind": "raw",
                                 "column": "active_power_total_kw", "source": "$ctx"}])
    assert kept2 == [] and any("expected/forecast" in b for b in blanked2)


def test_sibling_unit_classifies_the_slot():
    em = {"chart": {"kpis": [{"unit": "°C", "label": "Peak Exhaust", "value": 0.0}]}}
    kept, blanked = _enforce([{"slot": "chart.kpis[0].value", "kind": "derived", "fn": "worstPeakKw",
                               "base_columns": ["active_power_total_kw"], "source": "$ctx"}], em=em)
    assert kept == [] and any("temperature" in b for b in blanked)  # °C cell never takes a power fn (card 61)


# ── R12: view auto-select ───────────────────────────────────────────────────────────────────────
def test_view_selector_moves_to_data_bearing_view():
    from ems_exec.executor import view_select
    p = {"vm": {"view": "v-thd", "views": {"v-thd": {"series": []},
                                           "i-thd": {"series": [{"values": [4.2, 8.6]}]}}}}
    view_select.apply(p)
    assert p["vm"]["view"] == "i-thd"


def test_view_selector_stays_when_current_has_data():
    from ems_exec.executor import view_select
    p = {"vm": {"view": "a", "views": {"a": {"series": [{"values": [1.0]}]}, "b": {"series": []}}}}
    view_select.apply(p)
    assert p["vm"]["view"] == "a"


# ── R6/R7: xaxis label derivation ───────────────────────────────────────────────────────────────
def test_xaxis_derives_clock_labels_and_index_positions():
    from ems_exec.executor import xaxis
    ts = [1783207800000 + i * 3600000 for i in range(25)]
    out = {"data": {"xLabels": [""] * 10, "xLabelIndexes": ts, "series": [{"values": [1.0] * 25}]}}
    dflt = {"data": {"xLabels": ["00:00", "02:00", "04:00", "08:00", "10:00",
                                 "12:00", "14:00", "16:00", "18:00", "22:00"],
                     "xLabelIndexes": [0, 4, 8, 12, 16, 20, 24, 28, 32, 35],
                     "series": [{"values": [0.0] * 36}]}}
    gaps = []
    xaxis.apply(out, dflt, gaps)
    labels = out["data"]["xLabels"]
    assert len(labels) == 10 and all(isinstance(x, str) and ":" in x for x in labels)   # real HH:MM labels
    idx = out["data"]["xLabelIndexes"]
    assert idx[0] == 0 and idx[-1] == 24 and all(isinstance(i, int) for i in idx)       # FE index contract
    assert gaps == []


def test_xaxis_underivable_labels_get_a_reason():
    from ems_exec.executor import xaxis
    out = {"data": {"xLabels": [""] * 4}}
    dflt = {"data": {"xLabels": ["00:00", "06:00", "12:00", "18:00"]}}
    gaps = []
    xaxis.apply(out, dflt, gaps)
    assert out["data"]["xLabels"] == [""] * 4                      # nothing to derive from → stays blank
    assert gaps and gaps[0]["slot"] == "data.xLabels" and gaps[0]["reason"]


# ── R14: chrome element keys survive classify/strip ─────────────────────────────────────────────
def test_warn_trip_width_are_chrome_not_data():
    from validate.leaf_classify import classify
    got = classify({"series": [{"key": "oilPressure", "trip": 140, "warn": 200, "width": 2.2, "name": "Oil P"}]})
    assert got["data_leaves"] == []                                # config array: no data leaf → strip keeps 140/200


def test_strip_preserves_design_thresholds():
    from grounding.default_assemble import strip_to_placeholders
    out = strip_to_placeholders({"chart": {"series": [
        {"key": "oilPressure", "trip": 140, "warn": 200, "width": 2.2, "values": [3.0, 4.0]}]}})
    el = out["chart"]["series"][0]
    assert el["trip"] == 140 and el["warn"] == 200 and el["width"] == 2.2   # chrome byte-identical
    assert el["values"] in ([], [0.0, 0.0])                        # the data leaf still strips


# ── R8: todaysEnergyTotalKwh reversed-CT window coherence ──────────────────────────────────────
def test_todays_energy_total_uses_the_moving_register_per_leg():
    from ems_exec.derivations.energy import todays_energy_total_kwh
    ctx = {"start_row": {"active_energy_import_kwh": 0.0, "active_energy_export_kwh": 328161.0,
                         "reactive_energy_import_kvarh": 22039.0, "reactive_energy_export_kvarh": 0.0},
           "end_row": {"active_energy_import_kwh": 0.0, "active_energy_export_kwh": 332835.0,
                       "reactive_energy_import_kvarh": 22270.0, "reactive_energy_export_kvarh": 0.0}}
    assert todays_energy_total_kwh(ctx) == 4905.0                  # 4674 export-kWh + 231 import-kvarh, never 231-as-total


# ── R1/R2: roster gap channel ───────────────────────────────────────────────────────────────────
def test_roster_gaps_reason_every_blank_leaf_and_carry_the_recipe_why():
    from ems_exec.executor import roster_gaps
    state = {"roster": [{"mode": "aggregates", "slot": "rail.vm", "agg": {
        "allTotalKw": {"agg": "alias", "of": "totalSuppliedKw"},
        "allUtilizationPct": {"agg": "const", "v": None, "why": "no panel rated capacity on gic_*"},
    }}]}
    payload = {"rail": {"vm": {"allTotalKw": None, "allUtilizationPct": None}}}
    gaps = roster_gaps.collect(payload, state)
    by_slot = {g["slot"]: g for g in gaps}
    assert "rail.vm.allTotalKw" in by_slot                         # blank reducer leaf reasoned
    assert by_slot["rail.vm.allUtilizationPct"]["reason"] == "no panel rated capacity on gic_*"


def test_roster_gaps_skip_filled_leaves():
    from ems_exec.executor import roster_gaps
    state = {"roster": [{"mode": "aggregates", "slot": "vm", "agg": {"totalKw": {"agg": "sum_magnitude", "of": "kw"}}}]}
    assert roster_gaps.collect({"vm": {"totalKw": 911.3}}, state) == []


# ── R3/R5: narrative zero-skeleton + host merge ────────────────────────────────────────────────
def test_narrative_skeleton_nulls_placeholder_zeros():
    from ems_exec.renderers.narrative_ai import _honest_skeleton
    out = _honest_skeleton({"exact_metadata": {"summary": {"stats": {"iThd": 0.0, "total": 0.0},
                                                           "pres": {"cardTitle": "AI Summary"}}}})
    assert out["summary"]["stats"]["iThd"] is None                 # zero-skeleton never renders a false '0 issues'
    assert out["summary"]["stats"]["total"] is None
    assert out["summary"]["pres"]["cardTitle"] == "AI Summary"     # chrome untouched


def test_host_merges_emit_gaps_and_drops_stale_ones():
    from host.server import _merge_emit_gaps
    payload = {"summary": {"stats": {"iThd": None}, "pres": {"cardTitle": "AI Summary"}}}
    emit_gaps = [
        {"slot": "summary.stats.iThd", "cause": "unbound_by_emit", "metric": "iThd", "reason": "r1"},
        {"slot": "summary.pres.cardTitle", "cause": "unbound_by_emit", "metric": "t", "reason": "r2"},
    ]
    merged = _merge_emit_gaps(None, emit_gaps, payload)
    slots = [g["slot"] for g in merged]
    assert "summary.stats.iThd" in slots                           # blank leaf keeps its reason
    assert "summary.pres.cardTitle" not in slots                   # filled-real leaf never carries a stale reason
