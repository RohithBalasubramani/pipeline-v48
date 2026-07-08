"""Narrative AI summary — the ask + window + leaf-bind fixes (r_5c6797f815 card-19 lineage). Non-live (no LLM/DB).

Covers the four generic fixes keyed on the narrative_ai handling class (never a card id):
  (A) the ASKED-ABOUT quantity threads into the story + leads the deterministic fallback.
  (B) _window_label is dict-aware and NEVER mislabels a latest-snapshot analysis as a windowed one (honest 'latest').
  (C) summary.period.label is always a real label (fixes the dangling FE prose 'Redistribution at ; …').
  (D) the builder's already-computed worst-V/I facts bind into the REAL payload leaves (no shape growth, no fabrication).
"""
from __future__ import annotations

from ems_exec.renderers._story import voltage_current as vc
from ems_exec.renderers import narrative_ai as na


# ── (A) asked-about → fallback ordering ──────────────────────────────────────────────────────────────────────────────
_VW = {"name": "GIC-01-N3-UPS-01 CL:600KVA", "mag": 2.47, "signed": -2.47, "kind": "deviation"}
_IW = {"name": "GIC-01-N8-BPDB-01", "mag": 12.29}


def test_voltage_question_fallback_leads_with_voltage():
    t = vc._fallback_text(0, 1, _VW, "normal", _IW, "critical", "drv", "voltage")
    assert t.startswith("Worst voltage")


def test_current_question_fallback_leads_with_current():
    t = vc._fallback_text(0, 1, _VW, "normal", _IW, "critical", "drv", "current")
    assert t.startswith("Worst current")


def test_no_ask_keeps_original_count_first_order():
    t = vc._fallback_text(0, 1, _VW, "normal", _IW, "critical", "drv", None)
    assert t.startswith("1 V/I band-crossing")


def test_asked_about_threads_into_story_generically():
    assert na._with_asked_about({"panel": "X"}, {"metric": "voltage"})["asked_about"] == "voltage"
    assert "asked_about" not in na._with_asked_about({"panel": "X"}, {})   # no metric → unchanged


# ── (B) window label is dict-aware and honest ('latest' over snapshot facts, never a false window claim) ──────────────
def test_window_label_dict_aware_but_honest_latest():
    assert vc._window_label({"range": "last-7-days", "start": "a", "end": "b", "sampling": "hourly"}) == "latest"
    assert vc._window_label(("a", "b")) == "latest"     # 2-tuple still honest
    assert vc._window_label(None) == "latest"


def test_norm_window_recognises_dict_and_tuple():
    assert vc._norm_window({"range": "last-7-days", "start": "a", "end": "b"}) == {"start": "a", "end": "b", "range": "last-7-days"}
    assert vc._norm_window(("a", "b")) == {"start": "a", "end": "b"}
    assert vc._norm_window({}) is None and vc._norm_window(None) is None


# ── (C) period label is always real → no dangling 'Redistribution at ; …' ────────────────────────────────────────────
def test_period_label_never_blank():
    assert vc._period_label({"start": "a", "end": "b"}) == "the latest reading"
    assert vc._period_label(None) == "the latest reading"
    prose = "Redistribution at " + vc._period_label(None) + "; inspect peak before clearing."
    assert "at ;" not in prose and "at  ;" not in prose


# ── (D) builder facts bind into REAL leaves — only what was computed, never grows the shape ──────────────────────────
def test_leaf_binds_only_present_facts():
    b = vc._leaf_binds(_VW, _IW, "the latest reading")
    assert b["summary.stats.worstVoltage.vDeviation"] == -2.47
    assert b["summary.stats.worstVoltage.panel"] == "GIC-01-N3-UPS-01 CL:600KVA"
    assert b["summary.stats.worstCurrent.iUnbalance"] == 12.29
    assert b["summary.period.label"] == "the latest reading"
    # a missing worst → its leaves are absent (honest-blank, never fabricated)
    b2 = vc._leaf_binds(None, _IW, "the latest reading")
    assert "summary.stats.worstVoltage.vDeviation" not in b2
    assert b2["summary.stats.worstCurrent.iUnbalance"] == 12.29


def test_bind_leaves_writes_existing_only_no_shape_growth():
    payload = {"summary": {"period": {"label": ""},
                           "stats": {"worstVoltage": {"vDeviation": None, "panel": "seed"}}}}
    out = na._bind_leaves(payload, {
        "summary.period.label": "the latest reading",
        "summary.stats.worstVoltage.vDeviation": -2.47,
        "summary.stats.worstVoltage.panel": "GIC-01-N3-UPS-01 CL:600KVA",
        "summary.stats.worstCurrent.iUnbalance": 12.29,   # leaf ABSENT → must not be created
        "summary.period.dropme": None,                    # None value → never written
    })
    assert out["summary"]["period"]["label"] == "the latest reading"
    assert out["summary"]["stats"]["worstVoltage"]["vDeviation"] == -2.47
    assert out["summary"]["stats"]["worstVoltage"]["panel"] == "GIC-01-N3-UPS-01 CL:600KVA"
    assert "worstCurrent" not in out["summary"]["stats"]        # no shape growth
    assert "dropme" not in out["summary"]["period"]


def test_bind_leaves_tolerates_data_nesting():
    p = {"data": {"summary": {"period": {"label": ""}}}}
    o = na._bind_leaves(p, {"summary.period.label": "the latest reading"})
    assert o["data"]["summary"]["period"]["label"] == "the latest reading"


def test_pop_binds_strips_private_key_from_narrated_story():
    s = {"panel": "X", "_leaf_binds": {"summary.period.label": "the latest reading"}}
    b = na._pop_binds(s)
    assert b == {"summary.period.label": "the latest reading"}
    assert "_leaf_binds" not in s                               # the narrator never sees the bind spec
