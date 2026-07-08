"""R4 residual FALSE-BLANK fixes — the two MEASURABLE leaves R4 wrongly left blank now bind source:live to their real
column (stubbed neuract, no live DB):

  card 18 (roster)  — the worstVoltage/worstCurrent element keys vAvg/vMax/vMin/amps were declared {"b":"null"} with a
                      FALSE 'no such column' reason; the member gic_*_p1 tables DO carry voltage_avg/max/min + current_avg.
                      _rescue_false_nulls rebinds each to {"b":"col","c":<real column>} — ONLY when present+logged.
  card 40 (fields)  — the AI emitted NO field for the scalar leaves data.activePowerAvgKw / reactivePowerAvgKw, yet
                      active_power_total_kw / reactive_power_total_kvar exist live (the bars already bind them).
                      scalar_mean_fill fills each from the sibling column's window mean.

Both are OVER-REACH-SAFE: a genuinely-absent column keeps its honest blank (asserted below).
"""
from __future__ import annotations

import ems_exec.data.neuract as nx
from ems_exec.executor import measurable_resolve as MR
from ems_exec.executor import scalar_mean_fill as SMF
from ems_exec.executor import roster as R


# ── measurable_resolve: the pure key→column derivation (no DB) ────────────────────────────────────────────────────────
def test_candidate_columns_exact_no_substitute():
    assert MR.candidate_columns("vAvg") == ["voltage_avg"]
    assert MR.candidate_columns("vMax") == ["voltage_max"]
    assert MR.candidate_columns("vMin") == ["voltage_min"]
    assert MR.candidate_columns("amps") == ["current_avg"]
    # a bare quantity → the canonical _avg; an un-electrical leaf → nothing (never guessed)
    assert MR.candidate_columns("voltage") == ["voltage_avg"]
    assert MR.candidate_columns("cause") == []
    assert MR.candidate_columns("panel") == []


def test_resolve_column_present_logged_guard(monkeypatch):
    present = {"voltage_avg", "voltage_max", "current_avg"}                 # NOTE: no voltage_min
    monkeypatch.setattr(nx, "present_columns", lambda t: frozenset(present))
    monkeypatch.setattr(nx, "column_logged", lambda t, c: c in present)
    tabs = ["gic_x_p1"]
    assert MR.resolve_column("vAvg", tabs) == "voltage_avg"
    assert MR.resolve_column("vMax", tabs) == "voltage_max"
    assert MR.resolve_column("amps", tabs) == "current_avg"
    # NO OVER-REACH: voltage_min absent → None (honest blank), NEVER voltage_avg-as-min
    assert MR.resolve_column("vMin", tabs) is None
    # an all-null (present-but-not-logged) column also stays None
    monkeypatch.setattr(nx, "column_logged", lambda t, c: False)
    assert MR.resolve_column("vAvg", tabs) is None


# ── card 18: the roster false-null rescue ─────────────────────────────────────────────────────────────────────────────
def test_rescue_false_nulls_rebinds_only_real_columns(monkeypatch):
    logged = {"voltage_avg", "voltage_max", "voltage_min", "current_avg"}   # current tables carry all four
    monkeypatch.setattr(nx, "column_logged", lambda t, c: c in logged)
    roster = [{
        "mode": "aggregates", "slot": "strip.stats",
        "element": {
            "amps": {"b": "null", "why": "no aggregate current column bound for the worst-panel chip"},
            "vAvg": {"b": "null", "why": "no per-window vAvg column on gic_*"},
            "vMax": {"b": "null", "why": "no per-window vMax column on gic_*"},
            "vMin": {"b": "null", "why": "no per-window vMin column on gic_*"},
            "cause": {"b": "const", "v": ""},                              # a non-electrical null-ish is untouched
            "iUnbalance": {"b": "col", "c": "current_unbalance_pct", "r": 2},
        },
    }]
    R._rescue_false_nulls(roster, ["gic_01_n8_bpdb_01_p1", "gic_02_n2_bpdb_02_p1"])
    el = roster[0]["element"]
    assert el["vAvg"] == {"b": "col", "c": "voltage_avg", "r": 1}
    assert el["vMax"] == {"b": "col", "c": "voltage_max", "r": 1}
    assert el["vMin"] == {"b": "col", "c": "voltage_min", "r": 1}
    assert el["amps"] == {"b": "col", "c": "current_avg", "r": 1}
    assert el["cause"] == {"b": "const", "v": ""}                          # const untouched
    assert el["iUnbalance"] == {"b": "col", "c": "current_unbalance_pct", "r": 2}  # real col untouched


def test_rescue_false_nulls_keeps_honest_blank_when_column_absent(monkeypatch):
    monkeypatch.setattr(nx, "column_logged", lambda t, c: False)           # nothing logged → nothing rebinds
    roster = [{"mode": "aggregates", "slot": "s",
               "element": {"vAvg": {"b": "null", "why": "x"}, "amps": {"b": "null", "why": "y"}}}]
    R._rescue_false_nulls(roster, ["gic_dark_p1"])
    assert roster[0]["element"]["vAvg"] == {"b": "null", "why": "x"}       # honest null stands
    assert roster[0]["element"]["amps"] == {"b": "null", "why": "y"}


# ── card 40: the unbound scalar-average sibling fill ──────────────────────────────────────────────────────────────────
_FIELDS = [
    {"slot": "data.bars[*].active", "kind": "bucketed", "metric": "active_power_total_kw",
     "column": "active_power_total_kw", "label": "Active Power", "unit": "kW", "agg": "avg"},
    {"slot": "data.bars[*].reactive", "kind": "bucketed", "metric": "reactive_power_total_kvar",
     "column": "reactive_power_total_kvar", "label": "Reactive Power", "unit": "kVAr", "agg": "avg"},
    {"slot": "data.ratedKw", "kind": "const", "metric": "rated", "column": None},
]


def test_sibling_column_for_scalar_matches_quantity():
    col, q = MR.sibling_column_for_scalar("activePowerAvgKw", _FIELDS)
    assert col == "active_power_total_kw" and q == "power"                 # quantity=power → _verify abs's negative power
    col, q = MR.sibling_column_for_scalar("reactivePowerAvgKw", _FIELDS)
    assert col == "reactive_power_total_kvar" and q == "power"
    # a chrome/nameplate key (no stat) has no sibling scalar-mean intent → the walk predicate skips it
    assert SMF._has_stat_and_quantity("ratedKw") is False
    assert SMF._has_stat_and_quantity("activePowerAvgKw") is True


def test_scalar_mean_fill_fills_from_sibling_column(monkeypatch):
    monkeypatch.setattr(nx, "column_logged", lambda t, c: c in ("active_power_total_kw", "reactive_power_total_kvar"))
    # the sibling column's window series (negative active power — reversed CT — must abs to positive, matching the bars)
    def _bucketed(table, col, s, e, sampling="hourly"):
        if col == "active_power_total_kw":
            return [{"t": "T", "value": -180.0}, {"t": "T", "value": -200.0}]
        if col == "reactive_power_total_kvar":
            return [{"t": "T", "value": -9.0}, {"t": "T", "value": -11.0}]
        return []
    monkeypatch.setattr(nx, "bucketed", _bucketed)
    out = {"data": {"activePowerAvgKw": "—", "reactivePowerAvgKw": None, "ratedKw": "—",
                    "bars": [{"time": "15:00", "active": 190.0, "reactive": 9.0}]}}
    filled = SMF.apply(out, _FIELDS, "gic_01_n3_ups_01_p1", (None, None))
    assert out["data"]["activePowerAvgKw"] == 190.0                        # mean(180,200) abs'd
    assert out["data"]["reactivePowerAvgKw"] == 10.0                       # mean(9,11) abs'd
    assert out["data"]["ratedKw"] == "—"                                   # a const leaf (no stat) untouched — honest
    assert "data.activePowerAvgKw" in filled and "data.reactivePowerAvgKw" in filled


def test_scalar_mean_fill_over_reach_safe(monkeypatch):
    # the sibling column is NOT logged → the leaf keeps its honest blank (no fabrication)
    monkeypatch.setattr(nx, "column_logged", lambda t, c: False)
    monkeypatch.setattr(nx, "bucketed", lambda *a, **k: [])
    out = {"data": {"activePowerAvgKw": "—"}}
    filled = SMF.apply(out, _FIELDS, "gic_dark_p1", (None, None))
    assert out["data"]["activePowerAvgKw"] == "—"
    assert not filled
    # a leaf with NO matching sibling field also stays blank
    out2 = {"data": {"voltageAvgV": "—"}}                                  # no voltage sibling in _FIELDS
    monkeypatch.setattr(nx, "column_logged", lambda t, c: True)
    monkeypatch.setattr(nx, "bucketed", lambda *a, **k: [{"t": "T", "value": 230.0}])
    assert not SMF.apply(out2, _FIELDS, "gic_x_p1", (None, None))
    assert out2["data"]["voltageAvgV"] == "—"
