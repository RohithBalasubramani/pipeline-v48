"""NON-AI data+payload validation layer (validate/). Unit (deterministic) + live."""
import pandas as pd
import pytest

from validate.leaf_classify import classify
from validate.data_validate import validate_data
from validate.payload_validate import validate_one, _supply
from validate.schema import validate_validation_output


# ---------- leaf classification (type-based DATA vs METADATA) ----------
def test_leaf_classify_by_type():
    pl = {"variant": "x", "title": "Voltage", "unit": "V", "color": "#fff", "focused": True,
          "value": 415.0, "phases": [230.0, 231.0, 229.0],
          "history": [{"ts": 1, "v": 1.0}, {"ts": 2, "v": 2.0}]}
    c = classify(pl)
    assert c["demand"]["scalars"] == 1            # value
    assert c["demand"]["arrays"] == 1             # phases (small numeric array)
    assert c["demand"]["series"] == 1             # history (list of objects with numeric)
    assert c["metadata_leaves"] >= 4              # variant/title/unit/color/focused are metadata


def test_leaf_classify_pure_metadata():
    assert classify({"variant": "x", "title": "Hi", "ok": True})["demand"] == {"scalars": 0, "arrays": 0, "series": 0}


# ---------- data quality verdicts ----------
def test_data_validate_verdicts():
    df = pd.DataFrame({"ts": pd.date_range("2026-01-01", periods=20, freq="min")[::-1],
                       "good": [1.0] * 20, "half": [None] * 11 + [1.0] * 9, "empty": [None] * 20})
    rep = validate_data(df, [{"column": "good", "label": "g", "kind": "k", "unit": "u"},
                             {"column": "half", "label": "h", "kind": "k", "unit": "u"},
                             {"column": "empty", "label": "e", "kind": "k", "unit": "u"},
                             {"column": "absent", "label": "a", "kind": "k", "unit": "u"}])
    v = {c["column"]: c["verdict"] for c in rep["columns"]}
    assert v["good"] == "pass"
    assert v["half"] in ("warn", "fail")          # 55% null -> fail (> MAX_NULL_RATE 0.5)
    assert v["empty"] == "fail"
    assert v["absent"] == "fail"
    assert rep["summary"]["n_columns"] == 4


# ---------- payload feasibility (demand vs supply) ----------
def test_payload_feasibility_discriminates():
    pl = {"variant": "x", "series": [{"ts": 1, "v": 1.0}], "value": 42.0, "label": "V"}
    empty = {"numeric_ok": 0, "phase_cols": 0, "has_timeseries": False, "series_cols": 0}
    rich = {"numeric_ok": 40, "phase_cols": 12, "has_timeseries": True, "series_cols": 40}
    assert validate_one(pl, empty)["verdict"] == "fail"
    assert validate_one(pl, rich)["verdict"] == "pass"
    assert validate_one({"title": "x", "unit": "V"}, rich)["verdict"] == "warn"   # no data leaves


def test_supply_counts_only_usable_numeric():
    data_report = {"columns": [
        {"column": "current_r", "numeric": True, "series_capable": True, "verdict": "pass"},
        {"column": "v_avg", "numeric": True, "series_capable": True, "verdict": "warn"},
        {"column": "panel_name", "numeric": False, "series_capable": False, "verdict": "pass"},
        {"column": "dead", "numeric": True, "series_capable": False, "verdict": "fail"},
    ]}
    s = _supply(data_report)
    assert s["numeric_ok"] == 2                    # pass+warn numeric; fail excluded; non-numeric excluded
    assert s["phase_cols"] == 1 and s["has_timeseries"] is True


# ---------- live integration ----------
@pytest.mark.live
def test_validate_live_ahu5():
    from run.harness import run_pipeline
    from validate.build import run_validate
    out = run_pipeline("voltage and current health for AHU-5")          # GIC-03-N6-AHU-5 (neuract gic table)
    rep = run_validate(out["layer1a"], out["layer1b"])
    assert validate_validation_output(rep) == []                        # report is well-formed
    assert rep["verdict"] in ("pass", "warn", "fail")
    s = rep["data"]["summary"]
    assert s["n_columns"] > 0 and s["n_pass"] > 0                        # ran on REAL neuract columns (no empty basket)
    assert s["n_pass"] + s["n_warn"] + s["n_fail"] == s["n_columns"]     # coherent tally (per-column verdicts sum up)
    assert rep["payload"]["summary"]["n_fail"] == 0                      # payloads conform; data-tier nulls are annotate-only


@pytest.mark.live
def test_harness_includes_validation():
    from run.harness import run_pipeline
    out = run_pipeline("voltage and current health for AHU-5")
    assert "validation" in out and out["validation"]["verdict"] in ("pass", "warn", "fail")
