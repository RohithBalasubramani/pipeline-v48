"""ems_exec executor — DETERMINISTIC POST-FILL FABRICATION GUARDS (slot-name-INDEPENDENT class killers).

Covers the three fabrication CLASSES the adversarial audit keeps re-finding on DIFFERENT slots each fire, GENERICALLY
(no card ids in the guard code) — driven straight from ems_exec/executor/fab_guards.py and through the real fill()
orchestrator (so the wiring is proven, not just the unit):

  CLASS 1  epoch-ms time-leak   — a NON-time-axis leaf holding epoch-ms magnitudes (maxLine.value / expectedMax ←
                                  [1783362600000,…]) blanks; a genuine time-axis leaf (…indexes / …timestamps / ts) and
                                  a real reading (238.6 V / 0.0 kW / 9.0 %) are NEVER touched.
  CLASS 2  null-column reading   — a written leaf whose bound column is 100% NULL (column_logged==False) blanks 0.0; a
                                  present-and-LOGGED column's real 0.0 stays.
  CLASS 3  no-source value       — a written numeric leaf whose field resolved NO column/fn/nameplate blanks (iThdPk=265);
                                  a const literal label (chrome) and a nameplate-sourced const stay.

Pure unit tests: neuract reads + nameplate + slot map are monkeypatched (no data DB, no LLM).
"""
from __future__ import annotations

import importlib

import pytest
from unittest.mock import patch

import ems_exec.data.neuract as nx
from ems_exec.executor import fab_guards as G
from ems_exec.executor import fill as F


@pytest.fixture(autouse=True)
def _pin_enforce_mode():
    """These guards' unit tests assert ENFORCE-mode blanking; pin fab_guards.mode='enforce' so the suite is isolated
    from the live app_config knob (an operator may leave mode='report' during a fleet audit — report mode never
    mutates, which would legitimately fail every blank assertion here). The report-mode contract is pinned separately
    in tests/test_fab_guards_rework.py."""
    A = importlib.import_module("ems_exec.executor.fab_guards.apply")
    with patch.object(A, "_mode", lambda: "enforce"):
        yield


# ── CLASS 1 — epoch-ms time-leak ────────────────────────────────────────────────────────────────────────────────────
def test_class1_epoch_scalar_and_array_blank_time_axis_exempt():
    # card-46 mode: maxLine.value / expectedMax mislabeled with epoch ms. A time-axis leaf (xLabelIndexes) is exempt;
    # a real reading (voltage 238.6, power 0.0) is never touched (no over-reach).
    out = {"data": {"maxLine": {"value": 1783362600000},
                    "expectedMax": [1783362600000, 1783362700000],
                    "xLabelIndexes": [1783193400000, 1783197000000],   # …indexes = time axis → exempt
                    "voltage": 238.6, "power": 0.0}}
    out, gaps = G.apply(out, [], frozenset(), "tbl")
    assert out["data"]["maxLine"]["value"] is None                 # epoch scalar → None
    assert out["data"]["expectedMax"] == []                        # all-epoch array → [] (type preserved)
    assert out["data"]["xLabelIndexes"] == [1783193400000, 1783197000000]  # time axis untouched
    assert out["data"]["voltage"] == 238.6 and out["data"]["power"] == 0.0  # real readings survive
    causes = {(g["slot"], g["cause"]) for g in gaps}
    assert ("data.maxLine.value", "epoch_ms_leak") in causes
    assert ("data.expectedMax", "epoch_ms_leak") in causes


def test_class1_epoch_in_series_object_value_key_blanks_time_key_exempt():
    # a per-point object {time, value}: an epoch mislabeled into `value` blanks; the point's own `time` axis is exempt.
    out = {"series": [{"time": 1783362600000, "value": 1783362600000},
                      {"time": 1783362700000, "value": 1783362700000}]}
    out, gaps = G.apply(out, [], frozenset(), "tbl")
    assert all(p["time"] >= 1e12 for p in out["series"])           # time key kept (real axis)
    assert all(p["value"] is None for p in out["series"])          # value key epoch → blanked


def test_class1_does_not_touch_real_readings():
    # every real EMS reading sits many orders below 1e12 → never mistaken for a timestamp.
    out = {"r": {"kw": 0.0, "v": 238.6, "pct": 9.0, "count": 12, "big": 999_999_999_999.0}}
    out, gaps = G.apply(out, [], frozenset(), "tbl")
    assert out["r"] == {"kw": 0.0, "v": 238.6, "pct": 9.0, "count": 12, "big": 999_999_999_999.0}
    assert not gaps


# ── CLASS 2 — null-column reading ───────────────────────────────────────────────────────────────────────────────────
def test_class2_all_null_column_blanks_logged_column_stays(monkeypatch):
    # card-47 mode: vThd bound to thd_compliance_v_avg (0/n non-null) shipped 0.0; iThd bound to a LOGGED column keeps
    # its real 0.0. Only the genuinely all-null column is blanked (no over-reach on a real 0.0).
    monkeypatch.setattr(nx, "column_logged", lambda t, c: c != "thd_compliance_v_avg")
    monkeypatch.setattr(nx, "latest_ts", lambda t: "2026-07-06T00:00:00")   # table reachable + has rows (gate open)
    G._ROWS_CACHE.clear()
    out = {"snapshot": {"vThd": {"valuePct": 0.0}, "iThd": {"valuePct": 0.0}}}
    fields = [{"slot": "snapshot.vThd.valuePct", "kind": "raw", "column": "thd_compliance_v_avg", "label": "V-THD"},
              {"slot": "snapshot.iThd.valuePct", "kind": "raw", "column": "thd_compliance_i_avg", "label": "I-THD"}]
    present = frozenset({"thd_compliance_v_avg", "thd_compliance_i_avg"})
    out, gaps = G.apply(out, fields, present, "tbl")
    assert out["snapshot"]["vThd"]["valuePct"] is None             # all-null column → not a reading → blank
    assert out["snapshot"]["iThd"]["valuePct"] == 0.0             # logged column's real 0.0 stays
    assert any(g["cause"] == "null_column_reading" and g["column"] == "thd_compliance_v_avg" for g in gaps)
    # the served SENTENCE names the real column, never the literal '{column}' placeholder [audit 11 F4]
    g2 = next(g for g in gaps if g["cause"] == "null_column_reading")
    assert "{column}" not in (g2.get("reason") or "")
    if "thd" in (g2.get("reason") or ""):                          # DB template reachable → real column rendered
        assert "thd_compliance_v_avg" in g2["reason"]


def test_class2_db_outage_does_not_over_reach(monkeypatch):
    # CONCLUSIVENESS GATE: column_logged returns False on a DB OUTAGE too — but the table has NO rows (latest_ts None),
    # so the all-null verdict is inconclusive → a real reading must NOT be blanked (never over-reach on an outage).
    monkeypatch.setattr(nx, "column_logged", lambda t, c: False)   # everything reads unlogged (outage signature)
    monkeypatch.setattr(nx, "latest_ts", lambda t: None)           # table unreachable → gate CLOSED
    G._ROWS_CACHE.clear()
    out = {"snapshot": {"v": {"valuePct": 238.6}}}
    fields = [{"slot": "snapshot.v.valuePct", "kind": "raw", "column": "v_avg", "label": "V"}]
    out, gaps = G.apply(out, fields, frozenset({"v_avg"}), "tbl")
    assert out["snapshot"]["v"]["valuePct"] == 238.6              # inconclusive → honest reading survives
    assert not any(g["cause"] == "null_column_reading" for g in gaps)


# ── CLASS 3 — no-source value ───────────────────────────────────────────────────────────────────────────────────────
def test_class3_no_source_numeric_blanks(monkeypatch):
    # card-04 mode: iThdPk=265.0 filled with no source column (not present, no fn, no nameplate) → stray → blank.
    monkeypatch.setattr(nx, "column_logged", lambda t, c: True)
    out = {"snapshot": {"iThdPk": 265.0}}
    fields = [{"slot": "snapshot.iThdPk", "kind": "raw", "column": None, "label": "iThd Peak"}]
    out, gaps = G.apply(out, fields, frozenset(), "tbl")
    assert out["snapshot"]["iThdPk"] is None
    assert any(g["cause"] == "no_source_value" for g in gaps)


def test_class3_absent_column_numeric_blanks(monkeypatch):
    # the field names a column but the meter does NOT carry it (not present) → no resolved source → stray value blanks.
    monkeypatch.setattr(nx, "column_logged", lambda t, c: True)
    out = {"snapshot": {"iThdPk": 265.0}}
    fields = [{"slot": "snapshot.iThdPk", "kind": "raw", "column": "peak_thd_col", "label": "iThd Peak"}]
    out, gaps = G.apply(out, fields, frozenset({"other_col"}), "tbl")   # peak_thd_col absent
    assert out["snapshot"]["iThdPk"] is None


def test_class3_const_literal_label_preserved():
    # a const/text literal (axis chrome '-29d') is AI-authored chrome, not a measurement → never policed.
    out = {"axis": {"label": "-29d"}}
    fields = [{"slot": "axis.label", "kind": "const", "value": "-29d"}]
    out, gaps = G.apply(out, fields, frozenset(), "tbl")
    assert out["axis"]["label"] == "-29d"
    assert not gaps


def test_class3_nameplate_sourced_const_preserved(monkeypatch):
    # a const number that resolves a real nameplate rating HAS a source → not a stray → preserved.
    from config import nameplate_slot_map as sm
    monkeypatch.setattr(sm, "rating_key_for",
                        lambda s: "rated_kva" if s and "rated" in str(s).lower() else None)
    out = {"nameplate": {"ratedKva": 600.0}}
    fields = [{"slot": "nameplate.ratedKva", "kind": "const", "value": 600.0}]
    out, gaps = G.apply(out, fields, frozenset(), "tbl")
    assert out["nameplate"]["ratedKva"] == 600.0


def test_class3_field_with_present_column_not_blanked(monkeypatch):
    # a field binding a PRESENT column has a real source → its written value is a reading, never a CLASS-3 stray.
    monkeypatch.setattr(nx, "column_logged", lambda t, c: True)
    out = {"r": {"v": 238.6}}
    fields = [{"slot": "r.v", "kind": "raw", "column": "v_avg", "label": "V"}]
    out, gaps = G.apply(out, fields, frozenset({"v_avg"}), "tbl")
    assert out["r"]["v"] == 238.6
    assert not gaps


# ── end-to-end through the real fill() orchestrator (wiring proof) ──────────────────────────────────────────────────
def _stub_neuract(monkeypatch, present, buckets=(), latest=None, logged=True):
    monkeypatch.setattr(nx, "present_columns", lambda t: frozenset(present))
    monkeypatch.setattr(nx, "bucketed", lambda t, c, s, e, sampling="hourly": list(buckets))
    monkeypatch.setattr(nx, "latest", lambda t, cols: dict(latest or {}))
    monkeypatch.setattr(nx, "latest_ts", lambda t: "2026-07-06T00:00:00")   # table reachable (CLASS-2 gate open)
    monkeypatch.setattr(nx, "window", lambda t, cols, s, e: ({}, {}))
    monkeypatch.setattr(nx, "edge_count", lambda t, c, s, e: 0)
    monkeypatch.setattr(nx, "column_logged", lambda t, c: (logged(c) if callable(logged) else logged))
    monkeypatch.setattr(F._np, "derive_ratings_for", lambda t: {})
    monkeypatch.setattr(F._np, "get_nameplate", lambda t: {})
    G._ROWS_CACHE.clear()


def test_fill_wires_the_guard_class1_epoch_leak(monkeypatch):
    # a kind='time' field mis-declared onto a scale leaf could leak epoch ms; the guard blanks it AFTER the fill,
    # while the real bucketed series survives. Proves fab_guards.apply is wired into fill().
    _stub_neuract(monkeypatch, present={"i_avg"},
                  buckets=[{"t": "2026-01-01T00:00:00", "value": 100.0},
                           {"t": "2026-01-01T01:00:00", "value": 120.0}])
    payload = {"history": {"data": {"values": [0.0, 0.0],
                                    "expectedMax": 1783362600000,
                                    "maxLine": {"value": 1783362600000}}}}
    di = {"fields": [{"slot": "history.data.values", "kind": "bucketed", "column": "i_avg", "unit": "A"}]}
    out = F.fill(payload, di, {"asset_table": "tbl", "window": (None, None)})
    assert out["history"]["data"]["values"] == [100.0, 120.0]      # real series filled + kept
    assert out["history"]["data"]["expectedMax"] is None           # epoch scalar blanked by the guard
    assert out["history"]["data"]["maxLine"]["value"] is None      # epoch scalar blanked
    gaps = F.pop_gaps(out) or []
    assert any(g["cause"] == "epoch_ms_leak" for g in gaps)


def test_fill_wires_the_guard_class2_null_column(monkeypatch):
    # a raw field bound to an all-null column writes 0.0 from a stale placeholder chain; the guard blanks it (the col
    # is present so no earlier honest pass caught it). A logged column's real 0.0 survives.
    _stub_neuract(monkeypatch, present={"thd_v", "thd_i"},
                  latest={"thd_v": 0.0, "thd_i": 0.0},
                  logged=lambda c: c != "thd_v")
    payload = {"snap": {"vThd": 0.0, "iThd": 0.0}}
    di = {"fields": [{"slot": "snap.vThd", "kind": "raw", "column": "thd_v", "unit": "%"},
                     {"slot": "snap.iThd", "kind": "raw", "column": "thd_i", "unit": "%"}]}
    out = F.fill(payload, di, {"asset_table": "tbl", "window": (None, None)})
    assert out["snap"]["vThd"] is None                             # all-null column → blanked
    assert out["snap"]["iThd"] == 0.0                             # logged column's real 0.0 kept
    gaps = F.pop_gaps(out) or []
    assert any(g["cause"] == "null_column_reading" for g in gaps)


# ── CLASS 4 — unstripped seed-leak ──────────────────────────────────────────────────────────────────────────────────
def _card73_default():
    """The card-53/73 ScoreHistoryCard default: per-series legendValue 52/71/85/43 (the audit's fabricated legend
    readings) with empty values arrays + structural chrome (key/color/dashed) beside each."""
    return {"backupHistory": {"series": [
        {"key": "index",        "color": "#444443", "dashed": False, "label": "Autonomy index",     "legendValue": 52, "values": []},
        {"key": "runtimeScore", "color": "#86a86b", "dashed": False, "label": "Backup time score",  "legendValue": 71, "values": []},
        {"key": "loadPressure", "color": "#7e6ea1", "dashed": False, "label": "Load Pressure score", "legendValue": 85, "values": []},
        {"key": "headroom",     "color": "#9c8235", "dashed": True,  "label": "Load Headroom",       "legendValue": 43, "values": []},
    ]}}


def test_class4_card73_legendvalue_seed_blanks_real_series_survive():
    # card-73 mode: series VALUES filled real (written); the per-series legendValue survived byte-identical to the
    # card-53 default AND was never filled → an unstripped seed → BLANK (each legend reading → None). Real series live.
    default = _card73_default()
    out = {"backupHistory": {"series": [dict(s) for s in default["backupHistory"]["series"]]}}
    for i, vals in enumerate([[10.0, 11.0, 12.0], [5.0, 6.0, 7.0], [1.0, 2.0, 3.0], [9.0, 8.0, 7.0]]):
        out["backupHistory"]["series"][i]["values"] = vals
    written = [f"backupHistory.series[{i}].values" for i in range(4)]
    out, gaps = G.apply(out, [], frozenset(), "tbl", default_payload=default, written_paths=written)
    s = out["backupHistory"]["series"]
    assert [x["legendValue"] for x in s] == [None, None, None, None]          # the 4 seed legend readings blanked
    assert [x["values"] for x in s] == [[10.0, 11.0, 12.0], [5.0, 6.0, 7.0],
                                        [1.0, 2.0, 3.0], [9.0, 8.0, 7.0]]      # real series survive
    seed = {g["slot"] for g in gaps if g["cause"] == "unstripped_seed"}
    assert seed == {f"backupHistory.series[{i}].legendValue" for i in range(4)}


def test_class4_structural_chrome_never_blanked():
    # OVER-REACH GUARD: the series identity/style chrome (key/color/dashed/label) is byte-identical to the default BY
    # DESIGN (the harvested skeleton the byte-identity gate keeps) — CLASS 4 must NEVER blank it, or the component's
    # series mapping/legend colours break. Only the value-rendering legendValue is a seed here.
    default = _card73_default()
    out = {"backupHistory": {"series": [dict(s) for s in default["backupHistory"]["series"]]}}
    out["backupHistory"]["series"][0]["values"] = [10.0, 11.0]                # one real series → written
    out, gaps = G.apply(out, [], frozenset(), "tbl", default_payload=default,
                        written_paths=["backupHistory.series[0].values"])
    s = out["backupHistory"]["series"]
    assert [x["key"] for x in s] == ["index", "runtimeScore", "loadPressure", "headroom"]  # keys survive
    assert [x["color"] for x in s] == ["#444443", "#86a86b", "#7e6ea1", "#9c8235"]         # colours survive
    assert [x["dashed"] for x in s] == [False, False, False, True]                          # style flags survive
    assert [x["label"] for x in s] == ["Autonomy index", "Backup time score",
                                       "Load Pressure score", "Load Headroom"]               # series names survive
    assert not any(g["cause"] == "unstripped_seed" and g["slot"].endswith((".key", ".color", ".dashed", ".label"))
                   for g in gaps)


def test_class4_written_real_leaf_protected_even_if_equals_seed():
    # COINCIDENCE PROTECTION: a real reading that happens to equal the seed at the same path is PROTECTED because it was
    # filled real (its path is in written_paths) — never mistaken for a surviving seed.
    default = {"kpi": {"value": 42}}
    out, gaps = G.apply({"kpi": {"value": 42}}, [], frozenset(), "tbl",
                        default_payload=default, written_paths=["kpi.value"])
    assert out["kpi"]["value"] == 42                                          # coincidental-but-written reading kept
    assert not any(g["cause"] == "unstripped_seed" for g in gaps)


def test_class4_unwritten_nontrivial_seed_blanks_trivial_scalar_safe():
    # an UNWRITTEN non-trivial scalar byte-identical to its default is a surviving seed → blank; a trivial 0 (a legit
    # real/honest value) equal-to-default is NEVER blanked (no over-reach on a bare 0/None).
    out, gaps = G.apply({"a": {"score": 42}}, [], frozenset(), "tbl",
                        default_payload={"a": {"score": 42}}, written_paths=[])
    assert out["a"]["score"] is None
    assert any(g["cause"] == "unstripped_seed" for g in gaps)
    out2, gaps2 = G.apply({"b": {"n": 0}}, [], frozenset(), "tbl",
                          default_payload={"b": {"n": 0}}, written_paths=[])
    assert out2["b"]["n"] == 0                                                # trivial 0 never blanked
    assert not gaps2


def test_class4_narrative_seed_policed_but_series_name_exempt():
    # event NARRATIVE seeds (title/why/severity + a numeric value) byte-identical to their default are policed (blank),
    # while a SERIES display name (label/name) equal-to-default is exempt structural display chrome.
    default = {"chart": {"series": [{"key": "load", "label": "Load %", "values": []}],
                         "events": [{"title": "Exhaust over-temp", "why": "load 99%",
                                     "severity": "danger", "value": 656}]}}
    out = {"chart": {"series": [{"key": "load", "label": "Load %", "values": [1.0, 2.0]}],
                     "events": [{"title": "Exhaust over-temp", "why": "load 99%",
                                 "severity": "danger", "value": 656}]}}
    out, gaps = G.apply(out, [], frozenset(), "tbl", default_payload=default,
                        written_paths=["chart.series[0].values"])
    assert out["chart"]["series"][0]["label"] == "Load %"                     # series display name kept
    ev = out["chart"]["events"][0]
    assert ev["title"] is None and ev["why"] is None                          # narrative seeds blanked
    assert ev["severity"] is None and ev["value"] is None
    assert out["chart"]["series"][0]["values"] == [1.0, 2.0]                  # real series survives


def test_class4_no_default_payload_is_a_noop():
    # CLASS 4 needs the harvested default; without it (default_payload=None) the pass is a no-op (never fabricates a
    # blank from nothing) — the other three classes still run.
    out, gaps = G.apply({"kpi": {"value": 4242}}, [], frozenset(), "tbl", default_payload=None)
    assert out["kpi"]["value"] == 4242
    assert not any(g["cause"] == "unstripped_seed" for g in gaps)


def test_fill_wires_the_guard_class4_seed_leak(monkeypatch):
    # END-TO-END: the real fill() orchestrator passes default_payload + written_paths into fab_guards.apply, so an
    # unfilled legendValue seed blanks while the bucketed series it decorates fills real. Proves CLASS 4 is wired.
    _stub_neuract(monkeypatch, present={"i_avg"},
                  buckets=[{"t": "2026-01-01T00:00:00", "value": 100.0},
                           {"t": "2026-01-01T01:00:00", "value": 120.0}])
    default = {"backupHistory": {"series": [
        {"key": "index", "color": "#444443", "legendValue": 52, "values": []}]}}
    payload = {"backupHistory": {"series": [
        {"key": "index", "color": "#444443", "legendValue": 52, "values": []}]}}
    di = {"fields": [{"slot": "backupHistory.series[0].values", "kind": "bucketed", "column": "i_avg", "unit": "A"}]}
    # the harness passes the harvested default_payload into fill() (it wires exactly this into fab_guards.apply)
    out = F.fill(payload, di, {"asset_table": "tbl", "window": (None, None)}, default_payload=default)
    s = out["backupHistory"]["series"][0]
    assert s["values"] == [100.0, 120.0]                                      # real bucketed series filled + kept
    assert s["key"] == "index" and s["color"] == "#444443"                    # structural chrome survives
    assert s["legendValue"] is None                                          # unfilled seed legend reading blanked
    gaps = F.pop_gaps(out) or []
    assert any(g["cause"] == "unstripped_seed" for g in gaps)


# ── CLASS 4 — CHROME WALL [metadata-stripping root cause, run r_627ae7b326] ─────────────────────────────────────────
def test_class4_chrome_wall_title_unit_metricid_axiskey_raillabels_never_blanked():
    # run r_627ae7b326 (card 36): the metadata-only emit copies chrome VERBATIM from card_payloads, so every chrome
    # leaf equals the default AND is unwritten — the classic CLASS-4 trigger blanked data.title, readings.*.unit/
    # metricId, axisKey, railLabels.*, xAxisLabel (nameless, unitless cards). The chrome wall must keep ALL of it,
    # while an UNWRITTEN DATA value equal to its seed at the same depth still blanks (no over-block of the class).
    default = {"data": {"title": "Power & Energy", "axisKey": "fixed-clock:6:10000", "xAxisLabel": "Time",
                        "railLabels": {"dkwDt": "dKW/dt", "apparent": "Apparent"},
                        "readings": {"activePower": {"unit": "kW", "metricId": "activePower", "unitSuffix": "",
                                                     "label": "Active Power", "value": 325.9,
                                                     "displayValue": "325.9"}}}}
    import copy
    out = copy.deepcopy(default)
    out, gaps = G.apply(out, [], frozenset(), "tbl", default_payload=default, written_paths=[])
    d = out["data"]
    assert d["title"] == "Power & Energy"                         # card title chrome survives
    assert d["axisKey"] == "fixed-clock:6:10000"                  # renderer directive (…Key) survives
    assert d["xAxisLabel"] == "Time"                              # axis label survives
    assert d["railLabels"] == {"dkwDt": "dKW/dt", "apparent": "Apparent"}   # strings under a *Labels container survive
    ap = d["readings"]["activePower"]
    assert ap["unit"] == "kW" and ap["metricId"] == "activePower"  # unit + …Id chrome survive
    assert ap["label"] == "Active Power"                          # display label survives (structural exact key)
    assert ap["value"] is None                                    # the UNWRITTEN seed reading STILL blanks (325.9)
    assert ap["displayValue"] is None                             # …Value projection stays policed with it
    seeded = {g["slot"] for g in gaps if g["cause"] == "unstripped_seed"}
    assert "data.readings.activePower.value" in seeded
    assert not any(s.endswith((".title", ".unit", ".metricId", ".axisKey", ".xAxisLabel", ".dkwDt", ".apparent"))
                   for s in seeded)                               # no chrome leaf reported as a seed


def test_class4_axis_scale_arrays_yLabels_yTicks_timeLabels_never_blanked():
    # run r_627ae7b326: emptying yLabels sends CMD_V2 LinePath's y-domain degenerate (the 3.4e9 axis). An axis/scale
    # scalar ARRAY under a labels/ticks key equal to its default is chrome BY DESIGN — never a seed. A NUMERIC data
    # array under a non-chrome key at the same depth still blanks (the class keeps policing data).
    default = {"data": {"yLabels": ["380", "340", "300"], "yTicks": [1.0, 0.6, 0.2],
                        "timeLabels": ["22:00", "03:00"], "samples": [52.0, 71.0, 85.0, 43.0]}}
    import copy
    out = copy.deepcopy(default)
    out, gaps = G.apply(out, [], frozenset(), "tbl", default_payload=default, written_paths=[])
    d = out["data"]
    assert d["yLabels"] == ["380", "340", "300"]                  # label axis array survives
    assert d["yTicks"] == [1.0, 0.6, 0.2]                         # numeric tick scale survives
    assert d["timeLabels"] == ["22:00", "03:00"]                  # clock-label axis survives
    assert d["samples"] == []                                     # a real numeric DATA seed array still blanks
    seeded = {g["slot"] for g in gaps if g["cause"] == "unstripped_seed"}
    assert seeded == {"data.samples"}


def test_class4_chrome_wall_stops_at_list_elements_narrative_still_policed():
    # the wall NEVER covers a leaf inside a LIST ELEMENT: a per-record narrative title/why (events[i]) is on-screen
    # DATA, so a stale seed there still blanks — while the card-level data.title beside it survives.
    default = {"data": {"title": "Alarms",
                        "events": [{"title": "Exhaust over-temp", "why": "load 99%", "value": 656}]}}
    import copy
    out = copy.deepcopy(default)
    out, gaps = G.apply(out, [], frozenset(), "tbl", default_payload=default, written_paths=[])
    assert out["data"]["title"] == "Alarms"                       # card title survives (dict path)
    ev = out["data"]["events"][0]
    assert ev["title"] is None and ev["why"] is None and ev["value"] is None  # narrative seeds still blank


def test_class4_chrome_wall_card73_numeric_legendvalue_regression_still_blanks():
    # REGRESSION PIN [task requirement]: the card-73 numeric legendValue seed [52,71,85,43] must STILL blank — its
    # key's last word is 'value' (never chrome) and it is a numeric reading. Same fixture as the original defect.
    default = _card73_default()
    out = {"backupHistory": {"series": [dict(s) for s in default["backupHistory"]["series"]]}}
    out, gaps = G.apply(out, [], frozenset(), "tbl", default_payload=default, written_paths=[])
    assert [x["legendValue"] for x in out["backupHistory"]["series"]] == [None, None, None, None]
    assert [x["label"] for x in out["backupHistory"]["series"]] == [
        "Autonomy index", "Backup time score", "Load Pressure score", "Load Headroom"]  # display names survive


# ── CLASS 4 — RAW-vs-STRIPPED WALL [root-cause fix, run r_5c6797f815] ────────────────────────────────────────────────
# The AUTHORITATIVE data/metadata classification is the strip-builder's own raw-vs-stripped diff (card_payloads.payload
# vs payload_stripped, threaded into fab_guards as default_payload=STRIPPED + shape_ref=RAW). A leaf byte-identical
# between raw and stripped is METADATA (kept verbatim) → NEVER a seed candidate, whatever its key; a leaf the strip
# CHANGED is DATA → its seed test is byte-identity to the RAW default. This replaces the key-vocab chrome whack-a-mole.
def test_class4_metadata_leaf_raw_equals_stripped_is_kept_regardless_of_key():
    # ROOT-CAUSE FIX: the compound presentation/ordering keys the vocab wall kept missing (stackOrder / lineOrder /
    # columnOrder / titleConnector / leftAxisLabel) are METADATA — raw == stripped (the strip left them verbatim) — so
    # they must SURVIVE with ZERO new key vocab. This is the exact set the FE iterates to build series/columns.
    raw = {"trend": {"pres": {"stackOrder": ["sag", "swell", "current", "neutral"],
                              "lineOrder": ["vWorst", "iWorst"],
                              "titleConnector": " at ", "leftAxisLabel": "No. of Events"}},
           "table": {"pres": {"columnOrder": ["panel", "events", "voltage", "cause"]}}}
    stripped = {"trend": {"pres": {"stackOrder": ["sag", "swell", "current", "neutral"],
                                   "lineOrder": ["vWorst", "iWorst"],
                                   "titleConnector": " at ", "leftAxisLabel": "No. of Events"}},
                "table": {"pres": {"columnOrder": ["panel", "events", "voltage", "cause"]}}}
    out = {"trend": {"pres": {"stackOrder": ["sag", "swell", "current", "neutral"],
                             "lineOrder": ["vWorst", "iWorst"],
                             "titleConnector": " at ", "leftAxisLabel": "No. of Events"}},
           "table": {"pres": {"columnOrder": ["panel", "events", "voltage", "cause"]}}}
    out, gaps = G.apply(out, [], frozenset(), "tbl", default_payload=stripped, written_paths=[], shape_ref=raw)
    assert out["trend"]["pres"]["stackOrder"] == ["sag", "swell", "current", "neutral"]   # metadata order survives
    assert out["trend"]["pres"]["lineOrder"] == ["vWorst", "iWorst"]
    assert out["trend"]["pres"]["titleConnector"] == " at "
    assert out["trend"]["pres"]["leftAxisLabel"] == "No. of Events"
    assert out["table"]["pres"]["columnOrder"] == ["panel", "events", "voltage", "cause"]
    assert not any(g["cause"] == "unstripped_seed" for g in gaps)                        # ZERO over-blanks


def test_class4_data_leaf_equal_to_raw_default_still_blanks():
    # CHARTER PRESERVED: a DATA leaf (raw != stripped — the strip zeroed the seed to a placeholder) that survived byte-
    # identical to its RAW default and was never filled real IS an unstripped seed → blank. The metadata series identity
    # chrome (key/color, raw == stripped) survives; the data legendValue seed [52,71,85,43] blanks.
    raw = {"chart": {"series": [{"key": "index", "color": "#444443",
                                 "legendValue": [52, 71, 85, 43], "values": [1.0, 2.0, 3.0]}]}}
    stripped = {"chart": {"series": [{"key": "index", "color": "#444443",
                                      "legendValue": [], "values": []}]}}          # DATA → placeholders
    out = {"chart": {"series": [{"key": "index", "color": "#444443",
                                 "legendValue": [52, 71, 85, 43], "values": []}]}}  # seed leaked, values unfilled
    out, gaps = G.apply(out, [], frozenset(), "tbl", default_payload=stripped, written_paths=[], shape_ref=raw)
    s = out["chart"]["series"][0]
    assert s["legendValue"] == []                                                  # data seed == raw default → blanked
    assert s["key"] == "index" and s["color"] == "#444443"                         # metadata identity chrome survives
    assert any(g["cause"] == "unstripped_seed" and g["slot"].endswith(".legendValue") for g in gaps)


def test_class4_numeric_seed_kept_by_strip_raw_equals_stripped_still_blanks():
    # REAL-DB CHARTER (cards 51/53 backupHistory): the strip MISSED the per-series scalar legendValue (52/71/85/43) —
    # payload_stripped keeps each BYTE-IDENTICAL to payload, so raw == stripped (the metadata branch fires). A rendered
    # numeric legend READING under a non-chrome key ('value' last word) must STILL blank even in that branch (carve-out
    # b), or the fabricated seed leaks on-screen. This is the exact shape the fab-code verifier flagged; the fixture
    # mirrors the real DB (scalar legendValue per series, byte-identical raw==stripped) and is proven live on the DB.
    seeds = [52, 71, 85, 43]
    def _series(): return [{"key": f"s{i}", "color": "#444443", "legendValue": v, "values": []}
                           for i, v in enumerate(seeds)]
    raw = {"backupHistory": {"series": _series()}}
    stripped = {"backupHistory": {"series": _series()}}     # STRIP MISS: raw == stripped for every scalar legendValue
    out = {"backupHistory": {"series": _series()}}          # seeds leaked, never filled
    out, gaps = G.apply(out, [], frozenset(), "tbl", default_payload=stripped, written_paths=[], shape_ref=raw)
    assert [s["legendValue"] for s in out["backupHistory"]["series"]] == [None, None, None, None]  # all blanked
    assert [s["key"] for s in out["backupHistory"]["series"]] == ["s0", "s1", "s2", "s3"]          # chrome survives
    assert sum(1 for g in gaps if g["cause"] == "unstripped_seed" and g["slot"].endswith(".legendValue")) == 4


def test_class4_numeric_config_kept_by_strip_survives_only_value_word_policed():
    # OVER-REACH GUARD for carve-out (b): the metadata-branch strip-miss carve-out must fire ONLY on a data-VALUE-word
    # key (value/val), NEVER on presentation/layout/scale CONFIG the strip legitimately keeps byte-identical under a
    # NON-value key. This fixture mirrors the real catalog leaves the over-reach scan surfaced (curveSag/rowHeight/
    # dimOpacity.line/bandThresholds.divisors.kw/minWidth — all raw==stripped, numeric, non-trivial, unwritten): a broad
    # "any numeric non-chrome metadata leaf" carve-out would blank them and break the cards. Only legendValue blanks.
    cfg = {"table": {"pres": {"minWidth": 1240, "layout": {"rowHeight": 20, "headerHeight": 28}}},
           "trend": {"pres": {"dimOpacity": {"line": 0.4, "stack": 0.35}}},
           "heatmap": {"bandThresholds": {"divisors": {"kw": 250, "current": 400, "voltageNominal": 415}}},
           "flow": {"vm": {"sankey": {"links": [{"curveSag": 120, "value": []}]}}},
           "chart": {"series": [{"key": "s0", "legendValue": 87, "values": []}]}}   # the lone strip-missed reading
    import copy
    out = copy.deepcopy(cfg)
    out, gaps = G.apply(out, [], frozenset(), "tbl",
                        default_payload=copy.deepcopy(cfg), written_paths=[], shape_ref=copy.deepcopy(cfg))
    # every non-value CONFIG leaf survives verbatim (never blanked)
    assert out["table"]["pres"]["minWidth"] == 1240
    assert out["table"]["pres"]["layout"] == {"rowHeight": 20, "headerHeight": 28}
    assert out["trend"]["pres"]["dimOpacity"] == {"line": 0.4, "stack": 0.35}
    assert out["heatmap"]["bandThresholds"]["divisors"] == {"kw": 250, "current": 400, "voltageNominal": 415}
    assert out["flow"]["vm"]["sankey"]["links"][0]["curveSag"] == 120
    # only the data-VALUE-word reading blanks
    assert out["chart"]["series"][0]["legendValue"] is None
    seeded = {g["slot"] for g in gaps if g["cause"] == "unstripped_seed"}
    assert seeded == {"chart.series[0].legendValue"}                                # exactly one, the legend reading


def test_class4_data_leaf_real_value_differing_from_raw_seed_is_kept():
    # the seed test is byte-identity to the RAW default (never the stripped placeholder): a DATA leaf the executor filled
    # to a REAL value that differs from the raw seed is kept — only the fabricated seed value blanks, never a reading.
    raw = {"kpi": {"score": 999}}                                                  # raw seed 999
    stripped = {"kpi": {"score": 0.0}}                                             # numeric DATA → 0.0 placeholder
    out = {"kpi": {"score": 234}}                                                  # real filled value, != the seed
    out, gaps = G.apply(out, [], frozenset(), "tbl", default_payload=stripped, written_paths=[], shape_ref=raw)
    assert out["kpi"]["score"] == 234                                              # genuine reading kept
    assert not any(g["cause"] == "unstripped_seed" for g in gaps)


def test_class4_magnitude_label_metadata_still_neutralised():
    # CARVE-OUT PRESERVED (card 69): a chrome LABEL that bakes a stale data magnitude ('Rated: 131A') is METADATA
    # (raw == stripped — a string label the strip keeps verbatim), yet it carries a fabricated reading → the number is
    # stripped to '—', the label chrome kept — regardless of the leaf key.
    raw = {"nameplate": {"caption": "Rated: 131A"}}
    stripped = {"nameplate": {"caption": "Rated: 131A"}}
    out = {"nameplate": {"caption": "Rated: 131A"}}
    out, gaps = G.apply(out, [], frozenset(), "tbl", default_payload=stripped, written_paths=[], shape_ref=raw)
    assert out["nameplate"]["caption"] == "Rated: —"                               # magnitude stripped, chrome kept
    assert any(g["cause"] == "unstripped_seed" for g in gaps)


def test_fill_threads_shape_ref_into_fab_guards_apply(monkeypatch):
    # WIRING (fill.py:592): fill() must pass its RAW default (shape_ref) into fab_guards.apply so CLASS 4 gets the raw-
    # vs-stripped classification. Capture the kwarg without depending on any downstream fill pass mutating data.
    from ems_exec.executor import fab_guards as _G
    seen = {}
    real = _G.apply

    def _spy(out, fields, present, table, **kw):
        seen.update(kw)
        return real(out, fields, present, table, **kw)

    monkeypatch.setattr(_G, "apply", _spy)
    raw = {"kpi": {"value": 4242}}
    F.fill({"kpi": {"value": 4242}}, {"fields": []}, {"asset_table": "tbl", "window": (None, None)},
           default_payload={"kpi": {"value": 0.0}}, shape_ref=raw)
    assert seen.get("shape_ref") == raw                                            # the RAW default reached CLASS 4


# ── CHROME-SELECTOR RESTORE (family H render-safety: enum/selector/scale keys) ───────────────────────────────────────
def test_chrome_selector_keys_exempt_from_class4_seed_leak():
    # OVER-REACH GUARD (root cause): the presentation-config SELECTOR/enum/scale keys (view/preset/resample/dir/
    # scaleMaxPct/tone) are byte-identical to their default BY DESIGN (they are the design's own switch/scale config, not
    # a data seed) — CLASS 4 must NEVER blank them, or the CMD_V2 component crashes (RT_DIR_PRESETS[null], rangeForPreset
    # (null)) or empties (views[null]). Each here is UNWRITTEN + equal-to-default (the classic seed-leak trigger).
    default = {"loadImpact": {"view": "pf-health"},
               "strip": {"filterSelection": {"preset": "today", "resample": "hourly"}},
               "trend": {"bottomStats": [{"trend": {"dir": "flat", "glyphColor": "#237492"}}]},
               "snapshot": {"h5": {"scaleMaxPct": 16}, "ieeeBadge": {"tone": "alarm"}}}
    out = {"loadImpact": {"view": "pf-health"},
           "strip": {"filterSelection": {"preset": "today", "resample": "hourly"}},
           "trend": {"bottomStats": [{"trend": {"dir": "flat", "glyphColor": "#237492"}}]},
           "snapshot": {"h5": {"scaleMaxPct": 16}, "ieeeBadge": {"tone": "alarm"}}}
    out, gaps = G.apply(out, [], frozenset(), "tbl", default_payload=default, written_paths=[])
    assert out["loadImpact"]["view"] == "pf-health"                 # selector never seed-blanked
    assert out["strip"]["filterSelection"]["preset"] == "today"
    assert out["trend"]["bottomStats"][0]["trend"]["dir"] == "flat"
    assert out["snapshot"]["h5"]["scaleMaxPct"] == 16
    assert out["snapshot"]["ieeeBadge"]["tone"] == "alarm"
    assert not any(g["cause"] == "unstripped_seed" for g in gaps)   # none of the chrome keys reported as a seed


def test_restore_chrome_restores_stripped_selector_enum_scale_from_default():
    # the emit / honest-blank stripped every chrome discriminant to null/0/'': restore each from the default so the
    # component has a real switch/scale/enum value again. Covers view / preset / dir / glyphColor / scaleMaxPct / tone.
    default = {"loadImpact": {"view": "pf-health"},
               "strip": {"filterSelection": {"preset": "today", "resample": "hourly"}},
               "trend": {"bottomStats": [{"trend": {"dir": "flat", "glyph": "", "glyphColor": "#237492"}}]},
               "snapshot": {"h5": {"limitPct": 8, "scaleMaxPct": 16}, "ieeeBadge": {"tone": "alarm"}}}
    out = {"loadImpact": {"view": None},                            # selector stripped to null
           "strip": {"filterSelection": {"preset": None, "resample": None}},
           "trend": {"bottomStats": [{"trend": {"dir": None, "glyph": "→", "glyphColor": None}}]},
           "snapshot": {"h5": {"limitPct": 0.0, "scaleMaxPct": 0.0}, "ieeeBadge": {"tone": ""}}}
    restored = G.restore_chrome(out, default, written=[])
    assert out["loadImpact"]["view"] == "pf-health"                 # active-view selector restored
    assert out["strip"]["filterSelection"]["preset"] == "today"     # filter preset selector restored
    assert out["strip"]["filterSelection"]["resample"] == "hourly"
    assert out["trend"]["bottomStats"][0]["trend"]["dir"] == "flat"          # enum direction restored
    assert out["trend"]["bottomStats"][0]["trend"]["glyphColor"] == "#237492"
    assert out["trend"]["bottomStats"][0]["trend"]["glyph"] == "→"      # a LIVE chrome value is never overwritten
    assert out["snapshot"]["h5"]["scaleMaxPct"] == 16 and out["snapshot"]["h5"]["limitPct"] == 8  # gauge scale restored
    assert out["snapshot"]["ieeeBadge"]["tone"] == "alarm"          # tone/badge enum restored
    keys = {t[-1] for t in restored}
    assert {"view", "preset", "resample", "dir", "glyphColor", "scaleMaxPct", "limitPct", "tone"} <= keys


def test_restore_chrome_never_overwrites_a_written_selector_or_fabricates_over_null_default():
    # (a) a WRITTEN selector (the fill set it real) wins over the default — the restore leaves it. (b) a default that is
    # ITSELF blank never fabricates a value over a null (no restore from nothing).
    default = {"a": {"view": "pf-health"}, "b": {"preset": None}}
    out = {"a": {"view": "k-stress"}, "b": {"preset": None}}
    G.restore_chrome(out, default, written=["a.view"])
    assert out["a"]["view"] == "k-stress"                          # written live selector preserved (not clobbered)
    assert out["b"]["preset"] is None                             # null default → nothing to restore (no fabrication)


def test_restore_chrome_never_touches_a_data_leaf_no_over_block():
    # NO OVER-BLOCK: a genuine DATA leaf that is honest-blank (value / valuePct / kw) is NOT a chrome-selector key, so
    # the restore leaves it blank — only presentation config is preserved, never a measurement.
    default = {"snapshot": {"h5": {"valuePct": 10.4, "scaleMaxPct": 16}}, "kpi": {"value": 3228.0}}
    out = {"snapshot": {"h5": {"valuePct": None, "scaleMaxPct": 0.0}}, "kpi": {"value": None}}
    G.restore_chrome(out, default, written=[])
    assert out["snapshot"]["h5"]["valuePct"] is None              # DATA reading stays honest-blank
    assert out["kpi"]["value"] is None                           # DATA reading stays honest-blank
    assert out["snapshot"]["h5"]["scaleMaxPct"] == 16            # only the SCALE chrome restored


def test_fill_wires_chrome_restore_view_selector(monkeypatch):
    # END-TO-END through fill(): a multi-view chart whose `view` selector was stripped to null is restored from the
    # default BEFORE view_select runs, so the card opens on a real data-bearing view (never the empty views[null]).
    _stub_neuract(monkeypatch, present={"i_avg"},
                  buckets=[{"t": "2026-01-01T00:00:00", "value": 1.0},
                           {"t": "2026-01-01T01:00:00", "value": 2.0}])
    default = {"loadImpact": {"view": "pf-health",
                              "views": {"pf-health": {"series": []}}}}
    payload = {"loadImpact": {"view": None,                       # selector stripped by the emit
                              "views": {"pf-health": {"series": [0.0, 0.0]}}}}
    di = {"fields": [{"slot": "loadImpact.views.pf-health.series", "kind": "bucketed",
                      "column": "i_avg", "unit": "A"}]}
    out = F.fill(payload, di, {"asset_table": "tbl", "window": (None, None)}, default_payload=default)
    assert out["loadImpact"]["view"] == "pf-health"              # selector restored → chart is not empty
    assert out["loadImpact"]["views"]["pf-health"]["series"] == [1.0, 2.0]   # real series fills beneath it


# ── DB-DRIVEN KNOBS (every threshold / vocab token is a cmd_catalog row WITH a code-default mirror) ──────────────────
# Each guard reads its vocab/threshold via config.app_config.cfg with the code default; editing the DB row changes the
# guard's behavior with NO code change. These tests prove (1) the code default holds on a DB miss and (2) a row value
# actually STEERS the guard (the DB is the source of truth, not a hardcoded literal). cfg is imported at CALL time inside
# each accessor, so monkeypatching config.app_config.cfg reaches every one.
def _cfg_stub(mapping):
    """A cfg(key, default) that returns mapping[key] when present, else the passed default (the DB-miss path)."""
    def _c(key, default=None):
        return mapping[key] if key in mapping else default
    return _c


def test_knob_time_axis_suffixes_db_driven_with_code_default(monkeypatch):
    # code default: '…indexes' is a time axis (exempt); a bare value key holding epoch ms blanks. Then a DB row that
    # DROPS 'indexes' from the suffix vocab makes the SAME …Indexes leaf policed (no longer a time axis) — proving the
    # exemption is DB-driven, not a hardcoded suffix list.
    import config.app_config as ac
    ms = [1783362600000, 1783362700000]
    def _run():
        out = {"data": {"xLabelIndexes": list(ms), "expectedMax": list(ms)}}
        return G.apply(out, [], frozenset(), "tbl")[0]["data"]
    monkeypatch.setattr(ac, "cfg", _cfg_stub({}))                             # DB miss → code default
    d = _run()
    assert d["xLabelIndexes"] == ms and d["expectedMax"] == []               # …Indexes exempt, value key blanked
    monkeypatch.setattr(ac, "cfg", _cfg_stub({"fab_guards.time_axis_suffixes": ["ticks"]}))  # row drops 'indexes'
    d = _run()
    assert d["xLabelIndexes"] == [] and d["expectedMax"] == []               # now …Indexes is policed too (DB steers)


def test_knob_trivial_int_magnitude_db_driven(monkeypatch):
    # code default 10: a 2-digit unwritten seed (42) blanks, a 1-digit (7) is trivial and survives. A DB row lowering the
    # floor to 5 makes 7 non-trivial → it blanks too. Proves the trivial-scalar floor is a DB knob, not a baked 10.
    import config.app_config as ac
    def _score(n):
        return G.apply({"a": {"s": n}}, [], frozenset(), "tbl",
                       default_payload={"a": {"s": n}}, written_paths=[])[0]["a"]["s"]
    monkeypatch.setattr(ac, "cfg", _cfg_stub({}))                             # code default 10
    assert _score(42) is None and _score(7) == 7                             # 42 blanks, single-digit 7 is trivial
    monkeypatch.setattr(ac, "cfg", _cfg_stub({"fab_guards.trivial_int_magnitude": 5}))
    assert _score(7) is None                                                 # floor lowered → 7 now policed (DB steers)


def test_knob_magnitude_units_db_driven_seeded(monkeypatch):
    # the magnitude-label carve-out reads its unit vocab from fab_guards.magnitude_units (now seeded). Code default
    # strips 'Rated: 131A' → 'Rated: —'. A DB row WITHOUT 'A' leaves the same label untouched (no unit match → pure
    # chrome). Proves the unit set is DB-driven. NB: the regex is now a vocab-keyed per-call cache (no module-level
    # _MAGNITUDE_RE anymore); the reload is kept only to isolate this test's cfg stub from module state.
    import importlib
    import config.app_config as ac
    monkeypatch.setattr(ac, "cfg", _cfg_stub({"fab_guards.magnitude_units": ["kWh", "kW"]}))  # no bare 'A'
    G2 = importlib.reload(G)
    try:
        raw = {"n": {"caption": "Rated: 131A"}}
        out = G2.apply({"n": {"caption": "Rated: 131A"}}, [], frozenset(), "tbl",
                       default_payload=raw, written_paths=[], shape_ref=raw)[0]
        assert out["n"]["caption"] == "Rated: 131A"                          # 'A' not in the vocab → label untouched
    finally:
        monkeypatch.setattr(ac, "cfg", _cfg_stub({}))
        importlib.reload(G)                                                  # restore module-level regex from defaults


def test_knob_scale_selector_keys_db_driven(monkeypatch):
    # restore_chrome treats a 0 as blank ONLY for scale-selector keys. Code default includes scaleMaxPct → a 0 restores
    # to the default 16. A DB row that DROPS scaleMaxPct makes the 0 a live value (a string-style selector) → NOT restored.
    import config.app_config as ac
    monkeypatch.setattr(ac, "cfg", _cfg_stub({}))                            # code default (scaleMaxPct is a scale key)
    out = {"h5": {"scaleMaxPct": 0.0}}
    G.restore_chrome(out, {"h5": {"scaleMaxPct": 16}}, written=[])
    assert out["h5"]["scaleMaxPct"] == 16                                    # 0 == blank for a scale key → restored
    monkeypatch.setattr(ac, "cfg", _cfg_stub({"fab_guards.scale_selector_keys": ["limitpct"]}))
    out2 = {"h5": {"scaleMaxPct": 0.0}}
    G.restore_chrome(out2, {"h5": {"scaleMaxPct": 16}}, written=[])
    assert out2["h5"]["scaleMaxPct"] == 0.0                                  # no longer a scale key → 0 not treated blank


def test_class23_roster_slot_exemption(monkeypatch):
    """[fab_guards.exempt_roster_slots, card-15 defect] a ROSTER-written member-rolled value inside a recipe slot
    survives CLASS 3 even though the AI's FIELD for that leaf declared an absent control-table column; a stray OUTSIDE
    the roster slots is still blanked; flag off = today's blanking (byte-identical)."""
    import importlib
    FA = importlib.import_module("ems_exec.executor.fab_guards.apply")
    monkeypatch.setattr(nx, "column_logged", lambda t, c: True)
    fields = [{"slot": "card.view.value", "kind": "raw", "column": "apparent_power_total_kva", "label": "Live kVA"},
              {"slot": "stray.leaf", "kind": "raw", "column": None, "label": "stray"}]

    def _payload():
        return {"card": {"view": {"value": 3270.0, "metrics": [{"id": "active", "value": 3037.3}]}},
                "stray": {"leaf": 265.0}}

    # flag ON + the recipe's slot list → the roster-written subtree survives; the stray still blanks
    monkeypatch.setattr(FA, "_roster_exempt_on", lambda: True)
    out, gaps = G.apply(_payload(), fields, frozenset(), "tbl",
                        roster_slot_prefixes=["card.view.value", "card.view.metrics"])
    assert out["card"]["view"]["value"] == 3270.0                       # roster value survives the mis-declared field
    assert out["card"]["view"]["metrics"][0]["value"] == 3037.3
    assert out["stray"]["leaf"] is None                                 # non-roster stray still killed

    # flag OFF = byte-identical legacy: the mis-declared field blanks the roster's value too
    monkeypatch.setattr(FA, "_roster_exempt_on", lambda: False)
    out2, _ = G.apply(_payload(), fields, frozenset(), "tbl",
                      roster_slot_prefixes=["card.view.value", "card.view.metrics"])
    assert out2["card"]["view"]["value"] is None
