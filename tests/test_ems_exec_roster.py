"""ems_exec GENERIC ROSTER INTERPRETER [generalization package §3] — pure unit tests (no DB, no LLM, no host).
The interpreter carries ZERO card knowledge: the closed binding/reducer/mode vocabularies are exercised here over
synthetic members/rows/specs; honest-null is asserted everywhere a value is missing (never a fabricated number)."""
from __future__ import annotations

import copy

from ems_exec.executor import bindings as B
from ems_exec.executor import recipe as RC
from ems_exec.executor import reducers as RD
from ems_exec.executor import roster as R


class _P(B.Policy):
    """A Policy with fixed knobs (no config/DB read)."""

    def __init__(self):
        self.pf_cols = ["kpi_true_pf", "power_factor_total"]
        self.power_col = "active_power_total_kw"
        self.status_synonyms = {"critical": ["critical", "danger"], "warning": ["warning"],
                                "normal": ["normal", "success"]}
        self.pf_good, self.pf_fair, self.flow_threshold_kw = 0.95, 0.90, 1.0


_M = {"mfm_id": 7, "name": "GIC-08-N10-AHU-1", "table": None, "role": "outgoing", "type": "lt_panel",
      "load_group": "GIC-08"}


# ── bindings: the closed op vocabulary ──────────────────────────────────────────────────────────────────────────────
def test_binding_ops_real_and_honest_null():
    p = _P()
    row = {"active_power_total_kw": -23.9, "kpi_true_pf": None, "power_factor_total": -0.891,
           "thd_current_r_pct": 2.0, "thd_current_y_pct": 4.0}
    # col: negative power → abs (dataset convention); keep_sign keeps the lead/lag sign
    assert B.evaluate({"b": "col", "c": "active_power_total_kw", "q": "power", "r": 2}, _M, row, None, p) == 23.9
    assert B.evaluate({"b": "col", "c": "active_power_total_kw", "keep_sign": True, "r": 2}, _M, row, None, p) == -23.9
    assert B.evaluate({"b": "col", "c": "absent_col"}, _M, row, None, p) is None
    # prefer_abs: unsigned preferred absent → abs(signed)
    assert B.evaluate({"b": "prefer_abs", "cs": ["kpi_true_pf", "power_factor_total"], "r": 3}, _M, row, None, p) == 0.891
    # phase_mean over present phases only
    assert B.evaluate({"b": "phase_mean", "cs": ["thd_current_r_pct", "thd_current_y_pct"], "r": 2}, _M, row, None, p) == 3.0
    # attr / slug / const / null / unknown-op
    assert B.evaluate({"b": "attr", "a": "load_group"}, _M, row, None, p) == "GIC-08"
    assert B.evaluate({"b": "slug", "a": "name"}, _M, row, None, p) == "gic-08-n10-ahu-1"
    assert B.evaluate({"b": "const", "v": 5}, _M, row, None, p) == 5
    assert B.evaluate({"b": "null", "why": "no such column"}, _M, row, None, p) is None
    assert B.evaluate({"b": "made_up_op"}, _M, row, None, p) is None
    # bare-string shorthand = col with NO declared quantity → sign passes through (the abs convention only applies
    # to a DECLARED power/energy quantity — the executor never guesses a quantity from a name)
    assert B.evaluate("active_power_total_kw", _M, row, None, p) == -23.9


def test_binding_status_and_energized():
    p = _P()
    vocab = ["success", "warning", "danger"]
    assert B.evaluate({"b": "status", "vocab": vocab}, _M, {"kpi_true_pf": 0.97}, None, p) == "success"
    assert B.evaluate({"b": "status", "vocab": vocab}, _M, {"kpi_true_pf": 0.91}, None, p) == "warning"
    assert B.evaluate({"b": "status", "vocab": vocab}, _M, {"kpi_true_pf": 0.5}, None, p) == "danger"
    # no PF: energized folds to vocab[0], dark folds to idle — NEVER a fabricated fault
    assert B.evaluate({"b": "status", "vocab": vocab}, _M, {"active_power_total_kw": 50}, None, p) == "success"
    assert B.evaluate({"b": "status", "vocab": vocab}, _M, {}, None, p) == "idle"
    assert B.evaluate({"b": "energized"}, _M, {"active_power_total_kw": -50}, None, p) is True
    assert B.evaluate({"b": "energized"}, _M, {}, None, p) is False


# ── reducers: the closed reducer vocabulary (honest-null on empty) ─────────────────────────────────────────────────
def test_reducers_vocabulary():
    els = [{"kw": -10, "iThd": 9.0, "status": "danger"}, {"kw": 20, "iThd": 3.0, "status": "success"},
           {"kw": None, "iThd": None, "status": "idle"}]
    assert RD.reduce({"agg": "sum_magnitude", "of": "kw"}, els) == 30
    assert RD.reduce({"agg": "mean", "of": "iThd"}, els) == 6.0
    assert RD.reduce({"agg": "argmax", "of": "iThd"}, els)["kw"] == -10
    assert RD.reduce({"agg": "count_breach", "of": "iThd", "floor": 8.0}, els) == 1
    assert RD.reduce({"agg": "count_breach", "of": "iThd", "floor": 8.0}, [{"iThd": None}]) is None  # blank ≠ 0-breach
    assert RD.reduce({"agg": "len"}, els) == 3
    assert RD.reduce({"agg": "first_nonnull", "of": "kw"}, els) == -10
    assert RD.reduce({"agg": "alias", "of": "a"}, [], computed={"a": 42}) == 42
    assert RD.reduce({"agg": "sum_of", "keys": ["a", "b"]}, [], computed={"a": 2, "b": None}) == 2
    assert RD.reduce({"agg": "const", "v": None}, els) is None
    assert RD.reduce({"agg": "made_up"}, els) is None
    # count_status discovers the status KEY from the element spec's binding metadata (no hardcoded key name)
    spec = {"status": {"b": "status", "vocab": ["success", "warning", "danger"]}}
    n = RD.reduce({"agg": "count_status", "status": "critical"}, els, element_spec=spec, policy=_P())
    assert n == 1                                              # 'danger' folds into critical via the synonym row


# ── recipe: $same_as_slot expansion + the AI-emission fold (recipe wins; honest-null uncolonizable) ────────────────
_SPEC = {"slots": [
    {"slot": "a[]", "mode": "elements", "role_filter": "load", "cap": 10,
     "element": {"kw": {"b": "col", "c": "active_power_total_kw"},
                 "u": {"b": "null", "why": "absent on gic_*"}}},
    {"slot": "b[]", "mode": "elements", "role_filter": "supply", "element": {"$same_as_slot": "a[]"}},
]}


def test_recipe_expand_and_fold():
    spec = RC._expand(copy.deepcopy(_SPEC))
    assert spec["slots"][1]["element"]["kw"]["c"] == "active_power_total_kw"
    ai = {"slot": "a[]", "cap": 99,
          "element": {"kw": "active_power_r_kw",             # column swap (bare-string shorthand) — allowed
                      "u": {"b": "col", "c": "sneaky"},      # honest-null colonization — REJECTED
                      "invented": {"b": "col", "c": "x"}}}   # invented key — dropped
    out = RC._fold(ai, spec["slots"][0])
    assert out["element"]["kw"]["c"] == "active_power_r_kw"
    assert out["element"]["u"]["b"] == "null"
    assert "invented" not in out["element"]
    assert out["cap"] == 10                                   # cap may only shrink


# ── roster path walker: [] target, [*] repeat, dict-spine creation ─────────────────────────────────────────────────
def test_targets_walk_and_repeat():
    payload = {"timeline": {"periods": [{"label": "P1", "panels": None}, {"label": "P2", "panels": None}]}}
    tgts = R._targets(payload, None, "timeline.periods[*].panels[]")
    assert len(tgts) == 2
    for c, k, m in tgts:
        c[k] = [1]
    assert payload["timeline"]["periods"][0]["panels"] == [1]
    # dict spine creation for an envelope slot
    p2 = {}
    tg = R._targets(p2, None, "widgets.sld.incoming[]")
    assert len(tg) == 1
    tg[0][0][tg[0][1]] = []
    assert p2["widgets"]["sld"]["incoming"] == []
    # data.<slot> addressing follows fill's convention
    p3 = {"data": {"strip": {"stats": {}}}}
    tg3 = R._targets(p3, None, "strip.stats")
    assert tg3[0][0] is p3["data"]["strip"]


# ── series mode: member-rolled bucketed array (honest [] when no member reports) ──────────────────────────────────
def test_series_mode_member_rolled(monkeypatch):
    from ems_exec.executor import members as M

    tables = {
        "t_a": [{"t": "2026-07-03T08:00", "value": 10.0}, {"t": "2026-07-03T09:00", "value": -20.0}],
        "t_b": [{"t": "2026-07-03T08:00", "value": 5.0}],
    }
    monkeypatch.setattr(M._nx, "present_columns", lambda tbl: {"active_power_total_kw"} if tbl in tables else set())
    monkeypatch.setattr(M._nx, "bucketed",
                        lambda tbl, col, s, e, sampling="hourly": tables.get(tbl, []))
    pairs = [
        ({"mfm_id": 1, "name": "A", "table": "t_a", "role": "outgoing"}, {}),
        ({"mfm_id": 2, "name": "B", "table": "t_b", "role": "outgoing"}, {}),
        ({"mfm_id": 3, "name": "INC", "table": "t_a", "role": "incoming"}, {}),   # supply side — excluded (double-count)
        ({"mfm_id": 4, "name": "DARK", "table": None, "role": "outgoing"}, {}),   # dark member — skipped, never fabricated
    ]
    rolled = M.bucketed_rolled(pairs, "active_power_total_kw", (None, None))
    # per-bucket Σ|value| across LOAD members only: 08:00 → 10+5, 09:00 → |−20|
    assert [pt["value"] for pt in rolled] == [15.0, 20.0]
    assert M.bucketed_rolled(pairs, "absent_col", (None, None)) == []             # honest [] — no fabricated curve
    assert M.bucketed_rolled(pairs, None, (None, None)) == []

    # the roster slot writes the ORDERED value array wholesale at the slot path
    state = {"pairs": pairs, "window": (None, None)}
    payload = {"railVM": {"trend": {"series": [1, 2, 3]}}}
    R._series_slot(payload, {"mode": "series", "slot": "railVM.trend.series",
                             "column": "active_power_total_kw", "reduce": "sum_magnitude"}, state, None)
    assert payload["railVM"]["trend"]["series"] == [15.0, 20.0]
