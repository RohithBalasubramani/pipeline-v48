"""ems_exec executor — per-INDEX series-family fill + fill-completion placeholder-null (cards 58/59 families).

Covers the three Agent-C fill defects, GENERICALLY (no card ids in the code paths under test):
  1. `<array>[i].<key>` bucketed slots (one field per POINT — the 30-bar sparkline emission) fill from ONE shared real
     series, END-aligned; a column-less family resolves through its METRIC's derivation_binding row; a const STRING
     label ('-29d') passes through instead of being nulled by the numeric _verify gate.
  2. An UNTOUCHED scalar data leaf (undeclared, no binding) is NULLED at fill completion — the numeric 0.0 build
     placeholder never ships as a measured zero (c59 bypassVoltageV) — while a REAL measured 0.0 the executor wrote
     stays 0.0, and chrome stays byte-identical.
  3. role_scrub: 'mode' is an ACTIVE-STATE value key (points[].mode='normal' / summary.mode='sag') — blanked in the
     stripped skeleton; a mode OPTION-SET under a *Vocab dictionary subtree stays.

Pure unit tests: neuract reads + nameplate + derivation binding are monkeypatched (no data DB, no LLM).
"""
from __future__ import annotations

import ems_exec.data.neuract as nx
from ems_exec.executor import fill as F


def _stub_neuract(monkeypatch, buckets, present=("p_kw",), latest=None, series_rows=None):
    monkeypatch.setattr(nx, "bucketed", lambda t, c, s, e, sampling="hourly": list(buckets))
    monkeypatch.setattr(nx, "present_columns", lambda t: frozenset(present))
    monkeypatch.setattr(nx, "latest", lambda t, cols: dict(latest or {}))
    monkeypatch.setattr(nx, "window", lambda t, cols, s, e: ({}, {}))
    monkeypatch.setattr(nx, "series", lambda t, cols, s, e, sampling="hourly": list(series_rows or []))
    monkeypatch.setattr(nx, "column_logged", lambda t, c: True)
    monkeypatch.setattr(F._np, "derive_ratings_for", lambda t: {"rated_kw": 540})
    monkeypatch.setattr(F._np, "get_nameplate", lambda t: {"rated_kva": 600.0})


_BUCKETS = [
    {"t": "2026-01-01T00:00:00", "value": 10.0},
    {"t": "2026-01-01T01:00:00", "value": 20.0},
    {"t": "2026-01-01T02:00:00", "value": 30.0},
]


def _sparkline_payload(n=4):
    return {"load": {"title": "UPS Load",
                     "sparkline": [{"label": "", "loadPct": 0.0} for _ in range(n)]}}


def _sparkline_fields(n=4, **extra):
    fields = []
    for i in range(n):
        fields.append({"slot": f"load.sparkline[{i}].label", "kind": "const", "value": f"-{n - 1 - i}h"})
        fields.append({"slot": f"load.sparkline[{i}].loadPct", "kind": "bucketed", "metric": "loadPct",
                       "unit": "%", "sampling": "hourly", **extra})
    return fields


def test_per_index_family_fills_real_points_end_aligned(monkeypatch):
    # 4 point slots, 3 real buckets → END-aligned: oldest slot honest-None, 'now' slot = newest bucket. Never [].
    _stub_neuract(monkeypatch, _BUCKETS)
    out = F.fill(_sparkline_payload(), {"fields": _sparkline_fields(column="p_kw")},
                 {"asset_table": "tbl", "window": (None, None)})
    pts = [p["loadPct"] for p in out["load"]["sparkline"]]
    assert pts == [None, 10.0, 20.0, 30.0]
    assert all(not isinstance(p, list) for p in pts)            # point slots are SCALARS, never a whole-series array


def test_const_string_labels_pass_through_not_nulled(monkeypatch):
    _stub_neuract(monkeypatch, _BUCKETS)
    out = F.fill(_sparkline_payload(), {"fields": _sparkline_fields(column="p_kw")},
                 {"asset_table": "tbl", "window": (None, None)})
    assert [p["label"] for p in out["load"]["sparkline"]] == ["-3h", "-2h", "-1h", "-0h"]


def test_column_less_family_resolves_through_metric_binding(monkeypatch):
    # column=null, metric='loadPct' → derivation_binding row → per-bucket derived (|kW| ÷ rated_kw × 100). [card 58]
    _stub_neuract(monkeypatch, [], present=("active_power_total_kw",),
                  series_rows=[{"ts": "2026-01-01T00:00:00", "active_power_total_kw": -270.0},
                               {"ts": "2026-01-01T01:00:00", "active_power_total_kw": -135.0}])
    monkeypatch.setattr(F._deriv, "binding", lambda m: (
        {"fn": "kpiKwLoadPctOfRated", "base_columns": ["active_power_total_kw", "nameplate:rated_kva"],
         "fidelity": "real_exact", "scope": "series"} if m == "loadPct" else None))
    out = F.fill(_sparkline_payload(2), {"fields": _sparkline_fields(2)},
                 {"asset_table": "tbl", "window": (None, None)})
    pts = [p["loadPct"] for p in out["load"]["sparkline"]]
    assert pts == [50.0, 25.0]                                  # abs(-270)/540*100, abs(-135)/540*100 — real, not raw kW


def test_unfillable_family_stays_honest_null_with_gap(monkeypatch):
    _stub_neuract(monkeypatch, [], present=())
    monkeypatch.setattr(F._deriv, "binding", lambda m: None)
    out = F.fill(_sparkline_payload(2), {"fields": _sparkline_fields(2)},
                 {"asset_table": "tbl", "window": (None, None)})
    assert [p["loadPct"] for p in out["load"]["sparkline"]] == [None, None]
    gaps = F.pop_gaps(out)
    assert gaps and any(g.get("cause") for g in gaps)           # ONE explained gap, not a silent all-empty card


def test_multi_series_values_arrays_are_not_grouped(monkeypatch):
    # `chart.series[0].values` + `[1].values` are per-slot ORDERED-ARRAY fills (array-target leaves) — the family
    # grouping must leave them to the scalar loop's bucketed-array path, not write one scalar over each values array.
    _stub_neuract(monkeypatch, _BUCKETS, present=("p_kw", "q_kvar"))
    payload = {"chart": {"series": [{"name": "P", "values": [0.0]}, {"name": "Q", "values": [0.0]}]}}
    fields = [{"slot": "chart.series[0].values", "kind": "bucketed", "column": "p_kw", "sampling": "hourly"},
              {"slot": "chart.series[1].values", "kind": "bucketed", "column": "q_kvar", "sampling": "hourly"}]
    out = F.fill(payload, {"fields": fields}, {"asset_table": "tbl", "window": (None, None)})
    assert out["chart"]["series"][0]["values"] == [10.0, 20.0, 30.0]
    assert out["chart"]["series"][1]["values"] == [10.0, 20.0, 30.0]


def test_untouched_scalar_placeholder_nulls_and_real_zero_stays(monkeypatch):
    # bypassVoltageV: NO field declares it → its 0.0 build placeholder must ship as None (display '—'), never a
    # measured zero. measuredKw: declared + fills a REAL 0.0 reading → stays 0.0. Chrome strings untouched. [card 59]
    _stub_neuract(monkeypatch, [], latest={"p_kw": 0.0})
    payload = {"panel": {"label": "Bypass", "bypassVoltageV": 0.0, "measuredKw": 0.0}}
    fields = [{"slot": "panel.measuredKw", "kind": "raw", "column": "p_kw", "unit": "kW"}]
    out = F.fill(payload, {"fields": fields}, {"asset_table": "tbl", "window": (None, None)})
    assert out["panel"]["measuredKw"] == 0.0                    # real measured zero SURVIVES (written leaf)
    assert out["panel"]["bypassVoltageV"] is None               # untouched placeholder NULLED (honest '—')
    assert out["panel"]["label"] == "Bypass"                    # chrome byte-identical


def test_untouched_placeholder_inside_series_of_objects_nulls(monkeypatch):
    # classify() lists a series-of-objects as ONE leaf — the element walk must still null the untouched per-element
    # numeric placeholder (kpiCells[1].value=0.0 shipped as a measured average) while a WRITTEN element value stays.
    _stub_neuract(monkeypatch, [], latest={"v_avg": 231.5})
    payload = {"kpiCells": [{"id": "a", "label": "In", "value": 0.0},
                            {"id": "b", "label": "Bypass", "value": 0.0}]}
    fields = [{"slot": "kpiCells[0].value", "kind": "raw", "column": "v_avg", "unit": "V"}]
    _stub_neuract(monkeypatch, [], present=("v_avg",), latest={"v_avg": 231.5})
    out = F.fill(payload, {"fields": fields}, {"asset_table": "tbl", "window": (None, None)})
    assert out["kpiCells"][0]["value"] == 231.5                 # declared + written
    assert out["kpiCells"][1]["value"] is None                  # untouched placeholder → honest null


def test_wildcard_grown_elements_null_undeclared_scalars(monkeypatch):
    # a [*]-grown element clones the skeleton: declared member keys fill; an UNDECLARED scalar data key must be None
    # (its 0.0 placeholder would read as measured); string chrome (mode:'' post-scrub) is preserved. [card 59]
    _stub_neuract(monkeypatch, _BUCKETS[:2])
    default = {"composite": {"points": [{"label": "", "mode": "", "v1": 0.0, "bypassVoltageV": 0.0}]}}
    payload = {"composite": {"points": []}}
    fields = [{"slot": "composite.points[*].v1", "kind": "bucketed", "column": "p_kw", "sampling": "hourly"}]
    out = F.fill(payload, {"fields": fields}, {"asset_table": "tbl", "window": (None, None)},
                 default_payload=default)
    pts = out["composite"]["points"]
    assert [p["v1"] for p in pts] == [10.0, 20.0]               # declared member key filled with real buckets
    assert all(p["bypassVoltageV"] is None for p in pts)        # undeclared scalar → honest null, never 0.0
    assert all(p["mode"] == "" for p in pts)                    # string chrome preserved (skeleton, post-scrub)


def test_role_scrub_blanks_mode_keeps_mode_vocab():
    from grounding.role_scrub import scrub_active_string_leaves
    tree = {"composite": {"points": [{"mode": "normal", "label": "00:00"}]},
            "summary": {"mode": "sag"},
            "modeVocab": {"normal": "Normal", "bypass": "On Bypass"}}
    scrub_active_string_leaves(tree, "")
    assert tree["composite"]["points"][0]["mode"] == ""         # ACTIVE operating-mode verdict → blanked
    assert tree["summary"]["mode"] == ""                        # event-mode verdict → blanked
    assert tree["modeVocab"] == {"normal": "Normal", "bypass": "On Bypass"}   # option-set dictionary KEPT
