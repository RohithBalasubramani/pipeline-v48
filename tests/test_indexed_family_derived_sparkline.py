"""ems_exec executor — the per-INDEX DERIVED sparkline family (card 58 UPS-Load historical-load).

The card-58 defect: 30 `load.sparkline[i].loadPct` fields emit as kind='derived' (a scope='row' derivation over
|kW|÷rated_kw), NOT kind='bucketed'. A literal kind=='bucketed' routing gate excluded them, so all 30 fell to the
scalar loop which computed ONE window loadFactor and BROADCAST it (every bar 33.4 flat) while the REAL per-day loadPct
varies 33.8-36.2% (DB: avg(abs(active_power_total_kw))/rated_kw*100 GROUP BY day).

These are UNIT tests over indexed_families (no data DB, no LLM): neuract reads + nameplate + derivation binding are
monkeypatched. They assert (1) the routing predicate classifies a derived series point as family-fillable, (2) the
granularity chooser resolves at the series' OWN resolution (the finest ladder step that fits the slot budget — DAY, not
hourly), reusing the SAME rated_kw divisor as the scalar KPI, (3) each bar gets its OWN per-bucket value (not a
broadcast), a no-reading bucket blanks end-aligned, and (4) the fit-slots knob is DB-driven with a code default.
"""
from __future__ import annotations

import ems_exec.data.neuract as nx
from ems_exec.executor import indexed_families as IF


# a day-granularity power series (12 daily buckets), signed like a real UPS (all negative → abs recovers the magnitude)
_DAY_KW = [-185.3, -183.9, -187.7, -192.9, -182.5, -189.3, -186.2, -182.9, -188.4, -194.8, -195.5, -191.1]
# the SAME meter at HOURLY would yield far more buckets than 30 slots (over-refined) — the chooser must NOT pick this
_HOURLY_KW = [-180.0 - (i % 20) for i in range(248)]
# the DB-truth per-day loadPct (rated_kw=540): round(abs(kw)/540*100, 1)
_DB_LOADPCT = [34.3, 34.1, 34.8, 35.7, 33.8, 35.1, 34.5, 33.9, 34.9, 36.1, 36.2, 35.4]


def _rows(kw_list):
    return [{"ts": f"2026-06-{25 + i:02d}T00:00:00" if i < 6 else f"2026-07-{i - 5:02d}T00:00:00",
             "active_power_total_kw": kw} for i, kw in enumerate(kw_list)]


def _stub(monkeypatch, present=("active_power_total_kw",), per_gran=None):
    """Stub neuract so `series(sampling=g)` returns the g-specific rows (granularity-aware), and the binding/nameplate
    resolve to the SAME kpiKwLoadPctOfRated (|kW|÷rated_kw=540) the scalar KPI uses. per_gran maps gran→kw_list."""
    per_gran = per_gran or {"day": _DAY_KW, "hourly": _HOURLY_KW}
    monkeypatch.setattr(nx, "present_columns", lambda t: frozenset(present))
    monkeypatch.setattr(nx, "bucketed", lambda t, c, s, e, sampling="hourly": [])
    monkeypatch.setattr(nx, "series",
                        lambda t, cols, s, e, sampling="hourly": list(_rows(per_gran.get((sampling or "").lower(), []))))
    monkeypatch.setattr(IF._np, "get_nameplate", lambda t: {"rated_kva": 600.0})
    monkeypatch.setattr(IF._np, "derive_ratings_for", lambda t: {"rated_kw": 540})
    monkeypatch.setattr(IF._deriv, "binding", lambda m: (
        {"fn": "kpiKwLoadPctOfRated", "base_columns": ["active_power_total_kw", "nameplate:rated_kva"],
         "fidelity": "real_exact", "scope": "series"} if m in ("loadPct", "kpiKwLoadPctOfRated") else None))


def _derived_loadpct_fields(n=30):
    """The card-58 emission shape: n per-index loadPct points, kind='derived', column-less (metric+fn+base only)."""
    return [{"slot": f"load.sparkline[{i}].loadPct", "kind": "derived", "role": "series", "metric": "loadPct",
             "fn": "loadFactorPct", "base_columns": ["active_power_total_kw"], "target_column": "loadPct",
             "agg": "derived", "source": "live", "scope": "row"} for i in range(n)]


# ── (1) routing predicate ─────────────────────────────────────────────────────────────────────────────────────────
def test_predicate_classifies_derived_series_point_as_family_fillable():
    f = _derived_loadpct_fields(1)[0]
    assert IF.is_series_family_field(f) is True                        # the card-58 derived loadPct point
    assert IF.is_series_family_field({"kind": "bucketed", "column": "p_kw"}) is True
    assert IF.is_series_family_field({"kind": "const", "value": "-3h"}) is False   # a label chrome const
    assert IF.is_series_family_field({"kind": "time"}) is False                    # a time axis point
    assert IF.is_series_family_field({"kind": "event", "column": "flag"}) is False
    assert IF.is_series_family_field(None) is False


# ── (2) resolution chooser: series' OWN resolution (day fits 30 slots; hourly over-refines) ────────────────────────
def test_choose_granularity_picks_finest_that_fits_slot_budget(monkeypatch):
    _stub(monkeypatch)
    binding = IF._deriv.binding("loadPct")
    gran, vals = IF._choose_granularity(None, binding, "tbl", ("2026-06-08", "2026-07-07"),
                                        30, "power", {"rated_kw": 540}, declared="")
    assert gran == "day"                                               # NOT 'hourly' (248 buckets > 30 slots)
    assert [round(v, 1) for v in vals] == _DB_LOADPCT                  # real per-day loadPct via the SAME divisor


# ── (3) the family fill: per-bucket bars, end-aligned, no-data buckets blank — NOT a broadcast ─────────────────────
def test_derived_family_fills_per_bucket_not_broadcast(monkeypatch):
    _stub(monkeypatch)
    payload = {"load": {"title": "UPS Load", "sparkline": [{"label": "", "loadPct": 0.0} for _ in range(30)]}}
    group = [(f, i) for i, f in enumerate(_derived_loadpct_fields(30))]
    gaps, written = [], set()
    consumed = IF._fill_indexed_families(payload, payload, {("load.sparkline", "loadPct"): group},
                                         "tbl", frozenset(("active_power_total_kw",)),
                                         ("2026-06-08", "2026-07-07"), gaps,
                                         ratings={"rated_kw": 540}, asset_name="UPS-1", written_paths=written)
    bars = [p["loadPct"] for p in payload["load"]["sparkline"]]
    real = [round(v, 1) for v in bars if v is not None]
    assert real == _DB_LOADPCT                                         # each bar its OWN per-day value (33.8-36.2)
    assert len(set(real)) > 1                                          # NOT a flat broadcast
    assert bars[:18] == [None] * 18                                    # 18 pre-data buckets blank (end-aligned)
    assert all(b != 0.0 for b in bars if b is not None)               # a no-reading bucket blanks — never a fake 0
    assert len(consumed) == 30 and not gaps                           # all 30 consumed, no false gap on a filled family


# ── (4) honest-blank when nothing resolves + the DB-driven fit knob ────────────────────────────────────────────────
def test_unresolvable_derived_family_blanks_all_with_one_gap(monkeypatch):
    _stub(monkeypatch, present=())                                    # no column, and…
    monkeypatch.setattr(IF._deriv, "binding", lambda m: None)         # …no binding → nothing resolves
    payload = {"load": {"sparkline": [{"loadPct": 0.0} for _ in range(4)]}}
    group = [(f, i) for i, f in enumerate(_derived_loadpct_fields(4))]
    gaps = []
    IF._fill_indexed_families(payload, payload, {("load.sparkline", "loadPct"): group},
                              "tbl", frozenset(), (None, None), gaps, ratings={}, asset_name="UPS-1")
    assert [p["loadPct"] for p in payload["load"]["sparkline"]] == [None, None, None, None]
    assert gaps                                                       # ONE explained gap, not a silent all-empty card


def test_fit_slots_knob_is_db_driven_with_code_default():
    from config.app_config import cfg
    # code default is 'on' (finest-that-fits); the accessor returns it unchanged when the row is absent
    assert str(cfg("layer2.sparkline_fit_slots", "on")).lower() == "on"
