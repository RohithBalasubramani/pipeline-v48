"""Validation-streamline (2026-07-04): synthetic dense/sparse/dead/panel frames through the consolidated pre-L2 pass,
the F1 verdict rollup, the folded basket verdicts Layer 2 consumes, the canonical class resolution, and the narrowed
event/numeric patterns. NON-LIVE — no tunnel, no LLM."""
import pandas as pd

from validate.data_validate import validate_data
from validate.report import assemble, _roll
from validate.schema import validate_validation_output
from validate.build import _fold_into_basket
from validate.leaf_classify import _num_str
from layer2.gates import gate_data_instructions, _bindable
from layer1b.resolve.asset_candidates import _name_class, _class_of
from layer1b.basket.describe import describe


def _basket_cols(*names):
    return [{"column": n, "label": n, "kind": "raw", "unit": ""} for n in names]


def _frame(n=50, **cols):
    return pd.DataFrame({"timestamp_utc": pd.date_range("2026-07-01", periods=n, freq="min", tz="UTC")[::-1], **cols})


# ---------- synthetic frames: dense / sparse-but-live / dead / panel ----------
def test_dense_meter_passes():
    df = _frame(50, kw=[400.0] * 50, amps=[30.0] * 50)
    rep = validate_data(df, _basket_cols("kw", "amps"))
    assert rep["summary"] == {"n_columns": 2, "n_pass": 2, "n_warn": 0, "n_fail": 0}
    assert all(c["series_capable"] for c in rep["columns"])


def test_sparse_but_live_meter_validates_pass():
    """An intermittent meter (some nulls, latest row live) must NOT fail — sparse ≠ dead."""
    kw = [410.0 if i % 4 else None for i in range(50)]   # 25% null, newest row (i=1..) live
    kw[0] = 415.0
    rep = validate_data(_frame(50, kw=kw), _basket_cols("kw"))
    c = rep["columns"][0]
    assert c["verdict"] in ("pass", "warn")
    assert _roll(rep["summary"]) in ("pass", "warn")


def test_dead_meter_honest_blanks_with_reason():
    rep = validate_data(_frame(30, dead=[None] * 30), _basket_cols("dead"))
    c = rep["columns"][0]
    assert c["verdict"] == "fail" and c["reasons"]        # machine reason, never a silent blank
    assert _roll(rep["summary"]) == "fail"                # zero usable columns → genuine can't-render


def test_live_meter_with_dead_registers_is_not_page_fail():
    """F1: a live meter with dead/spare registers must NOT roll the page to 'fail' (10/25 audit prompts)."""
    df = _frame(40, kw=[400.0] * 40, thd=[None] * 40, spare=[None] * 40)
    rep = validate_data(df, _basket_cols("kw", "thd", "spare"))
    assert rep["summary"]["n_fail"] == 2 and rep["summary"]["n_pass"] == 1
    assert _roll(rep["summary"]) == "pass_with_gaps"      # dead columns are telemetry, not the page verdict


def test_unordered_read_makes_no_latest_claim():
    """A table with no time column loads unordered — latest_ok must be None (unknown), not a fabricated claim."""
    df = pd.DataFrame({"kw": [None] + [400.0] * 19})      # row 0 null; heap order
    rep = validate_data(df, _basket_cols("kw"), ordered=False)
    c = rep["columns"][0]
    assert c["latest_ok"] is None
    assert "no value in latest row" not in (c["reasons"] or [])


def test_panel_representative_feeder_frame():
    """Aggregate panel: validation runs on the representative FEEDER table's frame — same verdict machinery."""
    df = _frame(30, active_power_total_kw=[52.0] * 30, current_avg=[12.0] * 30)
    cols = _basket_cols("active_power_total_kw", "current_avg")
    rep = validate_data(df, cols)
    _fold_into_basket(cols, rep)
    assert all(c["usable"] for c in cols)                 # folded verdicts ride the basket into Layer 2


# ---------- report assembly: rollup + expected gaps + schema ----------
def _rep(n_pass, n_warn, n_fail):
    n = n_pass + n_warn + n_fail
    return {"rows": 1, "span": None, "columns": [],
            "summary": {"n_columns": n, "n_pass": n_pass, "n_warn": n_warn, "n_fail": n_fail}}


def test_assemble_pass_with_gaps_and_expected_gaps():
    gaps = [{"card_id": 7, "title": "t", "cause": "topology_infeasible", "reason": "no feeders"}]
    out = assemble({"mfm_id": 1, "name": "A", "table": "t"}, "pg", "AI", _rep(5, 0, 2),
                   {"cards": [], "summary": {"n_cards": 0, "n_pass": 0, "n_warn": 0, "n_fail": 0}},
                   expected_gaps=gaps, n_cards=4, policy="annotate")
    assert out["verdict"] == "pass_with_gaps"
    assert out["expected_gap_frac"] == 0.25 and out["expected_gaps"] == gaps
    assert validate_validation_output(out) == []          # pass_with_gaps is a legal verdict


def test_assemble_fail_only_when_zero_usable():
    ok = {"cards": [], "summary": {"n_cards": 0, "n_pass": 0, "n_warn": 0, "n_fail": 0}}
    a = assemble({"mfm_id": 1}, "pg", "AI", _rep(0, 0, 4), ok, policy="annotate")
    assert a["verdict"] == "fail"
    b = assemble(None, "pg", "ambiguous", _rep(0, 0, 0), ok, policy="annotate")
    assert b["verdict"] == "asset_pending"


# ---------- Layer 2 consumes the folded verdicts ----------
def test_gate_treats_validate_fail_column_as_unbindable():
    basket = {"columns": [
        {"column": "kw", "verdict": "pass", "usable": True},
        {"column": "dead_kwh", "verdict": "fail", "usable": False, "validate_reasons": ["null_rate 1.00 > 0.5"]},
    ]}
    real, failed = _bindable(basket)
    assert real == {"kw"} and "dead_kwh" in failed
    di = {"fields": [{"slot": "a", "kind": "raw", "source": "live", "column": "dead_kwh"}]}
    ok, issues = gate_data_instructions(di, basket)
    assert not ok and any("failed pre-L2 data validation" in i for i in issues)
    di2 = {"fields": [{"slot": "a", "kind": "raw", "source": "live", "column": "kw"}]}
    ok2, issues2 = gate_data_instructions(di2, basket)
    assert ok2 and not issues2


def test_gate_unvalidated_basket_binds_as_before():
    basket = {"columns": [{"column": "kw"}]}              # no verdict keys (validation never ran) → no regression
    ok, issues = gate_data_instructions({"fields": [{"slot": "a", "kind": "raw", "source": "live", "column": "kw"}]},
                                        basket)
    assert ok and not issues


# ---------- canonical class resolution (asset_candidates, no DB) ----------
def test_class_authoritative_order():
    # asset_type wins over mfm_type and name
    assert _class_of({"asset_type_code": "dg", "mfm_type_code": "lt_panel", "table": "x_incomer"}) == "DG"
    # trusted mfm_type codes
    assert _class_of({"asset_type_code": None, "mfm_type_code": "apfc", "table": "x"}) == "APFCR"
    # lt_panel is UNTRUSTED → falls through to the name vocabulary
    assert _class_of({"asset_type_code": None, "mfm_type_code": "lt_panel", "table": "gic_03_n6_ahu_5_p1"}) == "AHU"


def test_name_class_port():
    assert _name_class("gic_30_n2_11kv_ht_dg_incomer_se") == "Incomer"     # Incomer BEFORE DG (order matters)
    assert _name_class("gic_01_n3_ups_01_p1") == "UPS"
    assert _name_class("pcc_panel_1_feedbacks") == "Panel"
    assert _name_class("dg_1_mfm") == "DG"
    assert _name_class("gic_09_n4_cwp_1_p1") == "Load"                     # no vocab hit → honest Load


# ---------- narrowed patterns ----------
def test_event_pattern_excludes_continuous_compliance_averages():
    assert describe("thd_compliance_i_avg")[1] != "event"                  # continuous % average — a real metric
    assert describe("thd_compliance_i_avg")[2] == "%"
    assert describe("thd_compliance_ieee519")[1] == "event"                # the genuine 0/1 flag
    assert describe("sag_event_active")[1] == "event"


def test_numeric_string_full_match():
    assert _num_str(".5") and _num_str("446.25") and _num_str("-3.2e4") and _num_str("98 %") and _num_str("42 kW")
    assert not _num_str("24x7")                                            # digit-leading text is NOT a KPI value
    assert not _num_str("Apr 15")
