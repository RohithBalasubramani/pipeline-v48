"""validate/render_verdict — the ONE post-fill verdict. Non-live.

Covers the three honest leaf sources that replaced the old tangle (_card_leaf_stats + roster fold-in + seed sentinel):
  1. DECLARED field leaves — resolved on the completed payload; non-blank ⟺ really filled (executor blanks unfillable).
  2. ROSTER telemetry     — the interpreter's recipe-driven real/data counts fold in.
  3. UNDECLARED numeric   — a leaf_classify data leaf that no field/roster bound (panel fields=[] 0.0 leftover /
                            surviving Storybook seed) is NEVER 'answered' → always BLANK. This is the R2 fake-full fix.
"""
from __future__ import annotations

from validate.render_verdict import compute, declared_stats, undeclared_blank_count
from ems_exec.executor import roster_stats as _rstats


def _v(payload, di=None, roster=None, **kw):
    kw.setdefault("has_payload", payload is not None)
    return compute(payload, di or {"fields": []}, roster, **kw)


# ── DECLARED-field real/blank (relocated F8 blind-leaves behaviour) ─────────────────────────────────────────────────
def test_filled_series_slot_contributes_real_leaves():
    di = {"fields": [{"slot": "history.series", "kind": "bucketed", "column": "active_power_total_kw"}]}
    payload = {"history": {"series": [{"time": 1, "value": 10.5}, {"time": 2, "value": 11.2}]}}
    v = _v(payload, di)
    assert v["n_real"] == 2 and v["n_data"] == 2 and v["verdict"] == "render" and v["answerability"] == "full"


def test_empty_series_slot_is_honest_blank_not_render():
    di = {"fields": [{"slot": "history.series", "kind": "bucketed", "column": "active_power_total_kw"}]}
    v = _v({"history": {"series": []}}, di)
    assert v["n_real"] == 0 and v["n_data"] >= 1 and v["verdict"] == "honest_blank" and v["answerability"] == "none"


def test_partial_series_is_partial():
    di = {"fields": [{"slot": "series", "kind": "bucketed", "column": "x"}]}
    v = _v({"series": [{"value": 10.5}, {"value": None}]}, di)
    assert v["n_real"] == 1 and v["n_data"] == 2 and v["verdict"] == "partial" and v["answerability"] == "partial"


def test_reading_object_slot_counts_only_the_value_leaf_not_chrome():
    di = {"fields": [{"slot": "data.readings.activePower", "kind": "raw", "column": "active_power_total_kw"}]}
    payload = {"data": {"readings": {"activePower": {
        "value": 426.75, "unit": "kW", "label": "Active Power", "displayValue": "426.8"}}}}
    v = _v(payload, di)
    assert v["n_real"] == 1 and v["n_data"] == 1 and v["verdict"] == "render"


def test_blanked_scalar_value_slot_is_honest_blank():
    di = {"fields": [{"slot": "data.readings.activePower.value", "kind": "raw", "column": "active_power_total_kw"}]}
    v = _v({"data": {"readings": {"activePower": {"value": "—", "unit": "kW"}}}}, di)
    assert v["n_real"] == 0 and v["verdict"] == "honest_blank"


def test_unresolvable_slot_counts_as_one_honest_blank():
    di = {"fields": [{"slot": "missing.path", "kind": "raw", "column": "x"}]}
    v = _v({"data": {"readings": {}}}, di)
    assert v["n_real"] == 0 and v["n_data"] == 1 and v["verdict"] == "honest_blank"


# ── R2 FAKE-FULL FIX: a fields=[] card with UNDECLARED 0.0 leaves is honest_blank, NOT full ─────────────────────────
def test_panel_fields_empty_with_undeclared_zeros_is_honest_blank_not_full():
    # the panel-aggregate bug: Layer 2 declared NO fields, but the payload carries data leaves stripped to 0.0 that
    # were never filled. The OLD verdict saw n_data==0 → render/full; the net counts them as undeclared-blank → none.
    payload = {"card": {"view": {"value": 0.0, "target": 0.0,
                                 "metrics": [{"value": 0.0, "label": "Active"}, {"value": 0.0, "label": "Reactive"}]}}}
    v = _v(payload, {"fields": []})
    assert v["n_real"] == 0 and v["n_data"] >= 3 and v["n_undeclared"] >= 3
    assert v["verdict"] == "honest_blank" and v["answerability"] == "none"   # NEVER 'full'


def test_true_chrome_card_with_no_numeric_leaves_still_renders():
    # a genuine chrome-only card (nav/title — NO numeric data leaves at all) legitimately renders.
    v = _v({"title": "Overview", "subtitle": "PCC Panel 1"}, {"fields": []})
    assert v["n_data"] == 0 and v["n_undeclared"] == 0 and v["verdict"] == "render"


# ── SEED SUBSUMED: a real declared fill + an UNDECLARED surviving number demotes render → partial ───────────────────
def test_undeclared_seed_beside_a_real_fill_is_partial_not_render():
    di = {"fields": [{"slot": "card.view.value", "kind": "raw", "column": "active_power_total_kw"}]}
    payload = {"card": {"view": {"value": 426.7}}, "extra": {"seed": 2146.0}}   # seed leak in an undeclared leaf
    v = _v(payload, di)
    assert v["n_real"] == 1 and v["n_undeclared"] == 1 and v["verdict"] == "partial"


# ── ROSTER telemetry folds into the same arithmetic (no double-count of member leaves) ─────────────────────────────
def test_roster_real_leaves_fold_in_and_are_not_double_counted():
    di = {"fields": [], "roster": [{"mode": "elements", "slot": "consumer.rows[*]"}]}
    payload = {"consumer": {"rows": [{"value": 12.0}, {"value": 8.0}]}}        # member-filled real values
    v = _v(payload, di, roster={"real": 2, "data": 2})
    assert v["n_real"] == 2 and v["n_data"] == 2 and v["n_undeclared"] == 0 and v["verdict"] == "render"


# ── skeleton / broken-emit guards ──────────────────────────────────────────────────────────────────────────────────
def test_served_skeleton_is_always_honest_blank():
    payload = {"card": {"view": {"value": 0.0}}}
    v = _v(payload, {"fields": [{"slot": "card.view.value"}]}, skeleton_blank=True)
    assert v["verdict"] == "honest_blank"


def test_payload_error_with_zero_real_is_honest_blank():
    v = _v({"title": "x"}, {"fields": []}, payload_error="data_instructions.fields is empty")
    assert v["verdict"] == "honest_blank"


# ── the helper functions in isolation ──────────────────────────────────────────────────────────────────────────────
def test_declared_stats_resolves_data_and_stripped_aliases():
    di = {"fields": [{"slot": "readings.p.value"}]}
    n_real, n_blank, paths = declared_stats({"data": {"readings": {"p": {"value": 5.0}}}}, di)
    assert n_real == 1 and n_blank == 0 and any("readings.p.value" in p for p in paths)


def test_undeclared_blank_excludes_declared_and_roster_subtrees():
    payload = {"a": {"value": 1.0}, "rows": [{"value": 2.0}], "loose": 9.0}
    # 'a.value' declared, 'rows' under a roster base → only 'loose' is undeclared
    n = undeclared_blank_count(payload, {"a.value"}, ["rows"])
    assert n == 1


# ── A-1: chart SCAFFOLDING (time axis + y-scale) is NOT measured data ───────────────────────────────────────────────
def test_time_axis_field_is_not_counted_as_real():
    # a declared kind='time' axis (epoch-ms) must NOT inflate real — only the measured series values count.
    di = {"fields": [{"slot": "series.values", "kind": "bucketed", "column": "v"},
                     {"slot": "xLabelIndexes", "kind": "time"}]}
    pl = {"series": {"values": [10.0, 11.0]}, "xLabelIndexes": [1720000000000, 1720003600000, 1720007200000]}
    v = _v(pl, di)
    assert v["n_real"] == 2 and v["n_data"] == 2   # the 3 epoch-ms timestamps are excluded, not counted real


def test_undeclared_scale_scaffold_is_not_counted_as_blank():
    # maxY/minY/yTicks are y-scale chrome a chart derives from its own series — never measured data, never undeclared-blank.
    di = {"fields": [{"slot": "series.values", "kind": "bucketed"}]}
    pl = {"series": {"values": [5.0]}, "maxY": 131.0, "minY": 0.0, "yTicks": [0, 50, 100]}
    v = _v(pl, di)
    assert v["n_undeclared"] == 0 and v["verdict"] == "render"


# ── B: roster_stats counts a series_split slot (was blind → card rendered real member series but scored honest_blank) ─
def test_roster_stats_series_split_counts_member_keys_not_the_time_label():
    spec = {"mode": "series_split", "slot": "demand.view.points",
            "series": [{"key": "ups"}, {"key": "bpdp"}, {"key": "hhf"}]}
    payload = {"demand": {"view": {"points": [
        {"label": "23:00", "ups": 613.4, "bpdp": 335.6, "hhf": None},   # ups+bpdp real, hhf honest-null
        {"label": "00:00", "ups": 590.0, "bpdp": 300.0, "hhf": None}]}}}
    real, data = _rstats.stats(payload, {"roster": [spec]})
    assert real == 4 and data == 6          # 2 real keys × 2 points = 4 real; hhf nulls counted as data (blank), label ignored


# ── NARRATIVE REAL LEAF [F5]: a grounded ai_summary sentence must count as >=1 real leaf, never honest_blank ──────────
def test_populated_narrative_is_real_not_honest_blank():
    # A narrative_ai card (fields=[]) whose real content is a grounded SENTENCE (backendHeadline + ai_summary.text)
    # plus builder-bound worst-V/I stats — was verdicted honest_blank (real=0) because the scan is string-blind.
    payload = {"summary": {
        "stats": {"worstVoltage": {"vDeviation": -2.47, "panel": "GIC-01-N3-UPS-01 CL:600KVA"},
                  "worstCurrent": {"iUnbalance": 12.29, "panel": "GIC-01-N8-BPDB-01"}},
        "period": {"label": "the latest reading"},
        "pres": {"backendHeadline": "Voltage steady; critical 12.3% current unbalance at BPDB-01."}},
        "ai_summary": {"badge": "review", "text": "Voltage steady; critical 12.3% current unbalance at BPDB-01."}}
    v = _v(payload, {"fields": []})
    assert v["n_real"] >= 1
    assert v["verdict"] != "honest_blank" and v["answerability"] != "none"


def test_narrative_with_unbound_roster_is_partial():
    # narrative sentence real (+2 bound numeric stats) but the per-member roster is unbound → PARTIAL, answerable.
    payload = {"summary": {"stats": {"worstVoltage": {"vDeviation": -2.47}, "worstCurrent": {"iUnbalance": 12.29}}},
               "ai_summary": {"text": "one grounded factual sentence."}}
    v = _v(payload, {"fields": []})
    assert v["n_real"] == 1 and v["verdict"] == "partial" and v["answerability"] == "partial"


def test_skeleton_blank_narrative_gets_no_credit():
    # a served skeleton (L2 skipped) carries no real sentence → honest_blank, never a false narrative credit.
    payload = {"summary": {}, "ai_summary": {"text": ""}}
    v = _v(payload, {"fields": []}, skeleton_blank=True)
    assert v["verdict"] == "honest_blank"


def test_degraded_narrative_stays_honest_blank_over_empty_panel():
    # HONEST-BLANK PROTECTION: an EMPTY panel's narrative_ai card emits the honest 'no metered data resolved' sentence,
    # marked degraded (narrative_ai._is_degraded). It must NOT flip honest_blank → partial (a false 'answered') — even
    # though narrative_ai threads that same degradation text into the backendHeadline seam. The degraded flag vetoes.
    from validate.render_verdict import _narrative_real
    text = "AI summary unavailable for PCC-Panel-4 — no metered data resolved."
    # faithful empty-panel shape: honest-blanked declared stat leaf (n_data>0, n_real=0) + the degradation narrative.
    degraded = {"summary": {"stats": {"worstVoltage": {"vDeviation": None}},
                            "pres": {"backendHeadline": text}},
                "widgets": {"ai_summary": {"badge": "accounting", "text": text, "degraded": True}},
                "ai_summary": {"badge": "accounting", "text": text, "degraded": True}}
    assert _narrative_real(degraded) is False                    # degradation sentence → NOT real content
    di = {"fields": [{"slot": "summary.stats.worstVoltage.vDeviation", "kind": "raw"}]}
    v = _v(degraded, di)
    assert v["n_real"] == 0 and v["verdict"] == "honest_blank" and v["answerability"] == "none"


def test_non_narrative_payload_gets_no_narrative_credit():
    from validate.render_verdict import _narrative_real
    assert _narrative_real({"data": {"readings": {"activePower": {"value": None, "unit": "kW"}}}}) is False
    di = {"fields": [{"slot": "data.readings.activePower.value", "kind": "raw"}]}
    v = _v({"data": {"readings": {"activePower": {"value": "—", "unit": "kW"}}}}, di)
    assert v["n_real"] == 0 and v["verdict"] == "honest_blank"   # unchanged: no narrative present
