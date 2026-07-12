"""tests/test_agentb_fill_fixes.py — the fullsweep_20260706 AGENT-B fill/roster/events/windows/reasons fixes.

(1) ROSTER ENERGY pick_mover — the `delta` binding + the bucketed energy_delta fold pick the MOVING register
    (reversed-CT: import flat ~0, export carries the real kWh), the SAME selection panel_kwh applies — killing the
    cards-12/13 member-0.0-vs-panel-Σ self-contradiction and the card-16 UPS false-zero trend.
(2) EVENT REGISTERS — rising edges are counted on the RAW rows (neuract.edge_count / bucketed_edges), never on the
    hourly-AVG bucketed series that collapsed a flapping flag to ~1 edge/day (cards 18/20/22: 0 shown vs 100+ real).
(3) WINDOW HONORING — the consumer's declared range widens the read window (card 16 last-7-days on a 24h window);
    a recipe slot's own `range` is authoritative (card 14 Monthly == this-month).
(5) DERIVATION metric-wins — a derived field whose METRIC has its own curated binding row runs THAT fn (card 44:
    fn=nominalVoltageLN under metric=voltageSpread shipped the 240 V nominal as a spread); worst_phase_spread is a real
    windowed statistic.
(6) REASONS ALWAYS — every still-blank data leaf carries a per-leaf 'unbound_by_emit' record (cards 63/79/48).
All offline (neuract reads monkeypatched); no live DB required beyond the config fail-opens.
"""
from __future__ import annotations

import pytest

from ems_exec.executor import fill as F
from ems_exec.executor import members as M
# _export_col HOME moved to energy_registers (monoliths F7) — patch the defining module,
# not the members re-export (a re-exported NAME patch never reaches the callee's globals).
from ems_exec.executor import energy_registers as ER
from ems_exec.executor import roster as R


# ── helpers ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def _pairs_fixture(monkeypatch, tables, windows):
    """Monkeypatch neuract reads: `tables` = {table: {col: ...}} present columns; `windows` = {(table, col): (s, e)}."""
    monkeypatch.setattr(M._nx, "present_columns", lambda t: frozenset((tables.get(t) or {}).keys()))

    def _window(table, cols, start, end):
        first = {c: windows.get((table, c), (None, None))[0] for c in cols}
        last = {c: windows.get((table, c), (None, None))[1] for c in cols}
        return first, last

    monkeypatch.setattr(M._nx, "window", _window)


# ═══ (1) pick_mover unification ═══════════════════════════════════════════════════════════════════════════════════
def test_member_delta_picks_the_moving_register(monkeypatch):
    _IMP, _EXP = "active_energy_import_kwh", "active_energy_export_kwh"
    tables = {"ups": {_IMP: 1, _EXP: 1}, "bpdb": {_IMP: 1, _EXP: 1}}
    windows = {("ups", _IMP): (100.0, 100.0), ("ups", _EXP): (1000.0, 5691.0),
               ("bpdb", _IMP): (2647890.0, 2727560.0), ("bpdb", _EXP): (0.0, 0.0)}
    _pairs_fixture(monkeypatch, tables, windows)
    monkeypatch.setattr(ER, "_export_col", lambda: _EXP)
    ups = {"mfm_id": 1, "table": "ups", "role": "outgoing"}
    bpdb = {"mfm_id": 2, "table": "bpdb", "role": "outgoing"}
    # reversed-CT feeder: import delta 0, export moved 4691 → the member leaf reads 4691, never a false 0.0
    assert M.member_delta(ups, (None, None), _IMP) == 4691.0
    # forward feeder: import moved → import wins
    assert M.member_delta(bpdb, (None, None), _IMP) == 79670.0
    # the roster element Σ == panel_kwh (the 79670-vs-93771 self-contradiction is structurally dead)
    pairs = [(ups, {}), (bpdb, {})]
    total = sum(M.member_delta(m, (None, None), _IMP) for m, _r in pairs)
    assert total == M.panel_kwh(pairs, (None, None), _IMP) == 84361.0


def test_member_delta_unpaired_column_stays_legacy(monkeypatch):
    tables = {"a": {"some_counter": 1}}
    windows = {("a", "some_counter"): (10.0, 25.0)}
    _pairs_fixture(monkeypatch, tables, windows)
    assert M.member_delta({"mfm_id": 1, "table": "a", "role": "outgoing"}, (None, None), "some_counter") == 15.0


def test_bucketed_energy_delta_picks_mover_per_bucket(monkeypatch):
    _IMP, _EXP = "active_energy_import_kwh", "active_energy_export_kwh"
    monkeypatch.setattr(M._nx, "present_columns", lambda t: frozenset([_IMP, _EXP]))
    monkeypatch.setattr(ER, "_export_col", lambda: _EXP)
    series = {_IMP: [{"t": "2026-07-01", "value": 0.0}, {"t": "2026-07-02", "value": 0.0}],
              _EXP: [{"t": "2026-07-01", "value": 4691.0}, {"t": "2026-07-02", "value": 4703.0}]}
    monkeypatch.setattr(M._nx, "bucketed_delta", lambda t, c, s, e, sampling="day": list(series.get(c) or []))
    pts = M._bucketed_energy_delta("ups", _IMP, (None, None), "day")
    assert [p["value"] for p in pts] == [4691.0, 4703.0]          # the card-16 UPS trend false-zero is dead


# ═══ (2) raw-row rising edges ════════════════════════════════════════════════════════════════════════════════════
def test_member_event_count_uses_raw_row_edges(monkeypatch):
    calls = {}

    def _edge_count(table, col, start, end):
        calls["args"] = (table, col)
        return 102                                                # the real bpdb current_imbalance edge count

    monkeypatch.setattr(M._nx, "edge_count", _edge_count)
    n = M.member_event_count({"table": "bpdb"}, (None, None), "current_imbalance_event_active")
    assert n == 102 and calls["args"] == ("bpdb", "current_imbalance_event_active")


def test_fill_event_kind_uses_raw_row_edges(monkeypatch):
    monkeypatch.setattr(F._nx, "edge_count", lambda t, c, s, e: 32)
    assert F._event_count("bpdb", "current_imbalance_event_active", (None, None)) == 32


def test_bucketed_multi_event_kind_counts_edges_per_bucket(monkeypatch):
    monkeypatch.setattr(M._nx, "present_columns", lambda t: frozenset(["current_imbalance_event_active"]))
    monkeypatch.setattr(M._nx, "bucketed_edges",
                        lambda t, c, s, e, sampling="hourly": [{"t": "2026-07-05T00:00", "value": 25},
                                                               {"t": "2026-07-05T01:00", "value": 6}])
    pairs = [({"mfm_id": 1, "table": "bpdb", "role": "outgoing"}, {})]
    out = M.bucketed_multi(pairs, [{"key": "current", "kind": "event",
                                    "column": "current_imbalance_event_active"}], (None, None), sampling="hourly")
    assert [(p["t"], p["vals"]["current"]) for p in out] == [("2026-07-05T00:00", 25), ("2026-07-05T01:00", 6)]


def test_edge_count_none_on_absent_column(monkeypatch):
    from ems_exec.data import neuract as NX
    monkeypatch.setattr(NX, "present_columns", lambda t: frozenset())
    assert NX.edge_count("t", "nope", None, None) is None
    assert NX.bucketed_edges("t", "nope", None, None) == []


# ═══ (3) window honoring ═════════════════════════════════════════════════════════════════════════════════════════
def test_window_of_widens_to_declared_range():
    ctx = {"window": ("2026-07-05T04:00:00", "2026-07-06T04:00:00")}
    di = {"consumer": {"range": "last-7-days"}}
    s, e = F._window_of(ctx, di)
    assert s.startswith("2026-06-29") and e == "2026-07-06T04:00:00"


def test_window_of_never_shrinks_a_wider_window():
    ctx = {"window": ("2026-06-20T00:00:00", "2026-07-06T04:00:00")}
    s, _e = F._window_of(ctx, {"consumer": {"range": "last-7-days"}})
    assert s == "2026-06-20T00:00:00"                             # a user-picked longer window is never shrunk


def test_window_of_untouched_without_end_or_range():
    assert F._window_of({"window": (None, None)}, {"consumer": {"range": "last-7-days"}}) == (None, None)
    assert F._window_of({"window": ("a", "b")}, {"consumer": {}}) == ("a", "b")


def test_slot_range_is_authoritative():
    s, e = F._honor_range("2026-07-05T04:00:00", "2026-07-06T04:00:00", "this-month", authoritative=True)
    assert s.startswith("2026-07-01T00:00") and e == "2026-07-06T04:00:00"


def test_range_start_calendar_and_lookback():
    from datetime import datetime
    end = datetime.fromisoformat("2026-07-06T04:33:00")
    assert F._range_start("today", end).isoformat().startswith("2026-07-06T00:00")
    assert F._range_start("this-month", end).isoformat().startswith("2026-07-01T00:00")
    assert F._range_start("last-7-days", end).isoformat().startswith("2026-06-29")
    assert F._range_start("no-such-range", end) is None


# ═══ (5) derivation metric-wins ══════════════════════════════════════════════════════════════════════════════════
def test_derived_key_metric_wins_when_bound(monkeypatch):
    rows = {"voltageSpread": {"fn": "worstPhaseSpreadV", "base_columns": [], "fidelity": "real_exact",
                              "scope": "series"}}
    monkeypatch.setattr(F._deriv, "binding", lambda k: rows.get(k))
    f = {"kind": "derived", "fn": "nominalVoltageLN", "metric": "voltageSpread"}
    assert F._derived_key(f) == "voltageSpread"                   # the curated quantity row wins over the emit's guess
    f2 = {"kind": "derived", "fn": "nominalVoltageLN", "metric": "someUnknownMetric"}
    assert F._derived_key(f2) == "nominalVoltageLN"               # no curated row → the declared fn stands


def test_worst_phase_spread_is_a_window_statistic():
    from ems_exec.derivations import voltage as V
    ctx = {"series": [{"voltage_r_n": 237.0, "voltage_y_n": 236.0, "voltage_b_n": 240.0},
                      {"voltage_r_n": 230.0, "voltage_y_n": 234.15, "voltage_b_n": 233.0}]}
    assert V.worst_phase_spread(ctx) == 4.15                      # max per-sample phase gap — never the ~240 V nominal
    assert V.worst_phase_spread({"series": [{"voltage_r_n": 237.0}]}) is None   # one phase → no spread (honest)


# ═══ (6) reasons always ══════════════════════════════════════════════════════════════════════════════════════════
def test_every_unbound_blank_leaf_carries_a_reason(monkeypatch):
    monkeypatch.setattr(F, "_gap_sentence", lambda cause, params: f"{params.get('metric')} — {cause}")
    payload = {"tank": {"levelPct": 0.0}, "stats": [{"label": "Fuel Level", "value": 0.0, "unit": "%"}]}
    out = F.fill(payload, {"fields": []}, {"asset_table": None})
    gaps = out.get(F.GAPS_KEY) or []
    slots = {g["slot"] for g in gaps}
    assert {"tank.levelPct", "stats[0].value"} <= slots
    assert all(g["cause"] == "unbound_by_emit" and g["reason"] for g in gaps)


def test_explained_leaves_are_not_double_reported(monkeypatch):
    monkeypatch.setattr(F, "_gap_sentence", lambda cause, params: "x")
    out = {"tank": {"levelPct": None}}
    gaps = [{"slot": "tank.levelPct", "cause": "column_absent", "metric": "fuel_level_pct", "reason": "x"}]
    F._attach_unbound_gaps(out, ({"tank": {"levelPct": 0.0}},), gaps)
    assert len(gaps) == 1                                         # the declared-field record already explains it


# ═══ roster: 'self' roster of one + stats_only ═══════════════════════════════════════════════════════════════════
def test_series_stats_only_self_roster(monkeypatch):
    rolled = {"current_max": [{"t": "t1", "value": 290.0}, {"t": "t2", "value": 299.4}],
              "current_neutral": [{"t": "t1", "value": 18.34}, {"t": "t2", "value": 12.0}]}
    monkeypatch.setattr(M, "bucketed_rolled_members",
                        lambda pairs, col, w, sampling="hourly", reduce="mean": list(rolled.get(col) or []))
    state = {"pairs": [], "self_pair": ({"mfm_id": 11, "table": "ups", "role": "self"}, {}),
             "window": (None, None)}
    payload = {"history": {"data": {"stats": [{"label": "Peak Current", "value": 250.0},
                                              {"label": "Neutral Peak", "value": 250.0}]}}}
    spec = {"mode": "series", "slot": "history.data.stats", "stats_only": True, "role_filter": "self",
            "column": "current_max", "reduce": "mean", "sampling": "hourly",
            "stats": [{"op": "maximum", "r": 1, "slot": "history.data.stats.0.value"},
                      {"op": "maximum", "r": 2, "column": "current_neutral",
                       "slot": "history.data.stats.1.value"}]}
    R._series_slot(payload, spec, state, None)
    stats = payload["history"]["data"]["stats"]
    assert stats[0]["value"] == 299.4                             # window max, not the live snapshot
    assert stats[1]["value"] == 18.34                             # neutral peak from current_neutral, never a phase A
    assert isinstance(stats, list) and len(stats) == 2            # stats_only: the array itself is never overwritten


def test_self_select_honest_empty_without_table():
    assert R._select({"role_filter": "self"}, {"pairs": [], "self_pair": None}) == []


def test_agg_row_not_injected_for_an_empty_rollup(monkeypatch):
    monkeypatch.setattr(M, "resolve", lambda mid: ([{"mfm_id": 317, "name": "P", "table": None,
                                                     "role": "incoming", "type": None, "load_group": None}],
                                                   {"reporting": 0, "expected": 1, "verdict": "honest_blank"}))
    monkeypatch.setattr(M, "rows", lambda mem, cols, ts_col=None: [(m, {}) for m in mem])
    monkeypatch.setattr(R._recipe, "roster_for", lambda di, cid: [{"mode": "const", "slot": "x", "v": None}])
    ctx = {"mfm_id": 11, "asset_table": "ups_table", "card_id": 46}
    monkeypatch.setattr(R, "_valve", lambda: "on")
    R.prepare_ctx({}, ctx)
    assert "_agg_row" not in ctx                                  # a leaf meter keeps its single-meter raw reads
    assert ctx.get("_roster_state") is not None
