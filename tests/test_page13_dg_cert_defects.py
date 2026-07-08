"""tests/test_page13_dg_cert_defects.py — the two page-13 (DG operations-runtime, asset dg_1_mfm) cert defects.

DEFECT A (Family G, card 72 fab-by-mislabel): the "Reactive Energy" cell (unit MVARh) was bound to windowEnergyKwh (an
ACTIVE-energy fn) and rendered the active 24h energy delta (100.2) labeled as reactive. dg_1_mfm has NO reactive-energy
register, so the reactive slot MUST honest-blank — never the active delta. The executor's energy-POLARITY guard
(verify._polarity_conflict, driven by the registry _QUANTITY table) refuses an active-energy fn bound to a reactive slot
and blanks it with an honest 'quantity_mismatch' reason.

DEFECT B (Family C, card 73 false-blank): the per-bucket power-trend was emitted as SOLO single-index scalar fields
`buckets[0].active/reactive/apparent/pf` (distinct keys, all at index 0). The old scalar loop crammed the WHOLE ordered
series into element[0] (or blanked it) even though the same columns produced a real axis max — a false-blank. fill() now
PROMOTES a solo single-index bucketed scalar-point field to the wildcard array-grow, so the array grows to the full
per-bucket series (point i ← bucket i). A same-key multi-index sparkline family is NOT promoted (still the indexed-fill).

All offline — neuract reads monkeypatched; no live DB required.
"""
from __future__ import annotations

from ems_exec.executor import fill as F
from ems_exec.executor import series_fill as SF
from ems_exec.executor import indexed_families as IF
from ems_exec.executor.gaps import GAPS_KEY
from ems_exec.executor.verify import _polarity_conflict, _polarity_of_token, _fn_output_polarity


# ── neuract patch: dg_1_mfm has the active-energy counter + the 4 power columns, NO reactive-energy register ──────────
_PRESENT = {"active_energy_import_kwh", "active_power_total_kw", "reactive_power_total_kvar",
            "apparent_power_total_kva", "power_factor_total"}
_BUCKETS = {
    "active_power_total_kw":     [10.0, 50.0, 104.9],
    "reactive_power_total_kvar": [2.0, 8.0, 16.6],
    "apparent_power_total_kva":  [11.0, 51.0, 107.3],
    "power_factor_total":        [0.10, 0.12, 0.13],
}


def _patch_neuract(monkeypatch):
    monkeypatch.setattr(F._nx, "present_columns", lambda t: frozenset(_PRESENT))
    monkeypatch.setattr(SF._nx, "present_columns", lambda t: frozenset(_PRESENT))
    monkeypatch.setattr(IF._nx, "present_columns", lambda t: frozenset(_PRESENT))

    def _bucketed(table, col, start, end, sampling="hourly"):
        vals = _BUCKETS.get(col)
        if not vals:
            return []
        return [{"t": f"2026-07-06T{i:02d}:00:00", "value": v} for i, v in enumerate(vals)]

    monkeypatch.setattr(SF._nx, "bucketed", _bucketed)
    monkeypatch.setattr(F._nx, "bucketed", _bucketed) if hasattr(F._nx, "bucketed") else None
    # the ACTIVE energy 24h delta = 27827.9 - 27727.7 = 100.2 (window endpoints)
    monkeypatch.setattr(F._nx, "window",
                        lambda t, cols, s, e: ({c: (27727.7 if c == "active_energy_import_kwh" else None) for c in cols},
                                               {c: (27827.9 if c == "active_energy_import_kwh" else None) for c in cols}))
    monkeypatch.setattr(F._nx, "latest", lambda t, cols: {})


# ═══ classifier unit tests ════════════════════════════════════════════════════════════════════════════════════════
def test_polarity_classifier():
    assert _polarity_of_token("MVARh", "Reactive") == "reactive"
    assert _polarity_of_token("MWh", "Active") == "active"
    assert _polarity_of_token("kVAh", "Apparent") == "apparent"
    assert _fn_output_polarity("windowEnergyKwh") == "active"
    assert _fn_output_polarity("reactiveEnergyMvarh") == "reactive"
    # a fn measuring active bound to a reactive slot is a conflict; same-polarity is not
    assert _polarity_conflict({"unit": "MVARh", "label": "Reactive"}, "windowEnergyKwh") is True
    assert _polarity_conflict({"unit": "MWh", "label": "Active"}, "windowEnergyKwh") is False
    assert _polarity_conflict({"unit": "MVARh", "label": "Reactive"}, "reactiveEnergyMvarh") is False
    # unknown polarity on either side never fabricates a blank
    assert _polarity_conflict({"unit": "V"}, "windowEnergyKwh") is False


# ═══ DEFECT A — card 72 reactive cell must honest-blank, active still fills ════════════════════════════════════════
def test_card72_reactive_slot_never_shows_active_delta(monkeypatch):
    _patch_neuract(monkeypatch)
    window = ("2026-07-05T18:00:00", "2026-07-06T18:00:00")
    payload = {"energyReliability": {"cells": [
        {"id": "active", "unit": "MWh", "label": "Active", "value": None},
        {"id": "reactive", "unit": "MVARh", "label": "Reactive", "value": None}],
        "reactiveMvarh": None, "activeMwh": None}}
    di = {"fields": [
        # the MIS-BINDING: reactive slots point at the active-energy fn
        {"slot": "energyReliability.cells[1].value", "kind": "derived", "fn": "windowEnergyKwh",
         "metric": "reactive", "unit": "MVARh", "label": "Reactive"},
        {"slot": "energyReliability.reactiveMvarh", "kind": "derived", "fn": "windowEnergyKwh",
         "metric": "reactiveMvarh", "unit": "MVARh"},
        # a CORRECT active binding must still fill the active delta
        {"slot": "energyReliability.cells[0].value", "kind": "derived", "fn": "windowEnergyKwh",
         "metric": "active", "unit": "MWh", "label": "Active"}]}
    out = F.fill(payload, di, {"asset_table": "dg_1_mfm", "window": window})
    er = out["energyReliability"]
    assert er["cells"][1]["value"] is None, "reactive cell must NOT render the active delta"
    assert er["reactiveMvarh"] is None, "reactiveMvarh must NOT render the active delta"
    assert er["cells"][0]["value"] == 100.2, "active cell still fills the real 24h delta"
    # honest reason: quantity_mismatch (not a misleading 'no valid reading' on a column that DID read)
    reasons = out.get(GAPS_KEY, [])
    assert any(g.get("cause") == "quantity_mismatch" for g in reasons), reasons


# ═══ DEFECT A2 — card 72 energy cells emitted with fn=null + snake_case metric ALIAS must resolve (not derivation_unbound)
# The live cert emitted {slot:'energyReliability.cells[0].value', kind:'derived', metric:'active_mwh', base_columns:
# ['active_energy_import_kwh'], fn:null}. With fn=null and NO derivation_binding row for 'active_mwh', the executor logged
# 'derivation_unbound' and the Active cell FALSE-BLANKED even though active_energy_import_kwh has 17k+ live rows. The FIX
# adds derivation_binding rows (db/seed_card72_energy_reliability_metrics.sql) mapping each energy-family alias to the
# EXISTING registry fn (active_mwh→activeEnergyMvah, reactive_mvarh→reactiveEnergyMvarh, apparent_mvah→cumulativeApparent-
# Mvah), so a fn=null derived field with a known energy metric resolves deterministically from its base register.
#
# DEFINITIVE ENERGY-REGISTER RULE [2026-07-07]: the Active cell fills its REAL cumulative register; the Reactive and
# Apparent cells HONEST-BLANK on dg_1_mfm because that meter has NO reactive/apparent ENERGY register. There is NO
# ∫reactive-power→reactive-ENERGY recovery (that was fabrication-by-substitution): a live reactive-POWER series must NOT
# manufacture a reactive/apparent ENERGY reading for a register the meter never carried.
def test_card72_energy_alias_fn_null_resolves_active_reactive_apparent_honest_blank(monkeypatch):
    from ems_exec.executor import derived as D
    from ems_exec.executor.gaps import GAPS_KEY
    # dg_1_mfm: cumulative active register present (27827.9 kWh = 27.83 MWh); NO reactive-ENERGY register, but a LIVE
    # reactive-POWER column (reactive_power_total_kvar). The reactive/apparent ENERGY cells must STILL honest-blank —
    # a reactive-POWER series never synthesizes reactive/apparent ENERGY.
    monkeypatch.setattr(D._nx, "present_columns", lambda t: frozenset(_PRESENT))
    monkeypatch.setattr(F._nx, "present_columns", lambda t: frozenset(_PRESENT))
    monkeypatch.setattr(D._nx, "latest",
                        lambda t, cols: {c: (27827.9 if c == "active_energy_import_kwh" else None) for c in cols})
    monkeypatch.setattr(F._nx, "latest",
                        lambda t, cols: {c: (27827.9 if c == "active_energy_import_kwh" else None) for c in cols})
    monkeypatch.setattr(F._nx, "window", lambda t, cols, s, e: ({}, {}))
    monkeypatch.setattr(D._nx, "window", lambda t, cols, s, e: ({}, {}))
    monkeypatch.setattr(F._nx, "column_logged", lambda t, c: c in _PRESENT)

    # a live 3-point reactive-power series over 2h is available — but it MUST NOT be integrated into reactive ENERGY.
    from datetime import datetime
    _ser = [{"ts": datetime(2026, 7, 6, h, 0, 0), "reactive_power_total_kvar": v, "active_power_total_kw": 0.0}
            for h, v in ((0, 2.0), (1, 8.0), (2, 16.6))]
    monkeypatch.setattr(D._nx, "series", lambda t, cols, s, e, **k: list(_ser))

    # the derivation lookup KEY for each fn=null/alias field is the metric alias (the binding row exists → metric wins)
    for alias, fn in (("active_mwh", "activeEnergyMvah"), ("reactive_mvarh", "reactiveEnergyMvarh"),
                      ("apparent_mvah", "cumulativeApparentMvah")):
        field = {"slot": "s", "kind": "derived", "metric": alias, "fn": None}
        assert D._derived_key(field) == alias, f"{alias} must be the derivation key (binding row exists)"
        from config import derivation_binding as _db
        assert (_db.binding(alias) or {}).get("fn") == fn, f"{alias} → {fn}"

    payload = {"energyReliability": {"cells": [
        {"id": "active", "unit": "MWh", "label": "Active", "value": None},
        {"id": "reactive", "unit": "MVARh", "label": "Reactive", "value": None},
        {"id": "apparent", "unit": "MVAh", "label": "Apparent", "value": None}]}}
    di = {"fields": [
        {"slot": "energyReliability.cells[0].value", "kind": "derived", "metric": "active_mwh",
         "base_columns": ["active_energy_import_kwh"], "fn": None, "unit": "MWh", "label": "Active"},
        {"slot": "energyReliability.cells[1].value", "kind": "derived", "metric": "reactive_mvarh",
         "base_columns": ["reactive_energy_import_kvarh"], "fn": None, "unit": "MVARh", "label": "Reactive"},
        {"slot": "energyReliability.cells[2].value", "kind": "derived", "metric": "apparent_mvah",
         "base_columns": ["active_energy_import_kwh", "reactive_energy_import_kvarh"], "fn": None,
         "unit": "MVAh", "label": "Apparent"}]}
    out = F.fill(payload, di, {"asset_table": "dg_1_mfm", "window": ("2026-07-05T18:00:00", "2026-07-06T18:00:00")})
    er = out["energyReliability"]
    assert er["cells"][0]["value"] == 27.83, "Active cell fills the real cumulative MWh (~27.8), no derivation_unbound"
    # DEFINITIVE FIX: reactive/apparent ENERGY honest-blank — NO ∫power synthesis for an absent energy register.
    assert er["cells"][1]["value"] is None, "Reactive honest-blanks: no reactive-ENERGY register (∫power never synthesizes)"
    assert er["cells"][2]["value"] is None, "Apparent honest-blanks: no reactive leg (never active MWh relabeled Apparent)"
    reasons = out.get(GAPS_KEY, [])
    assert any(g.get("cause") == "column_absent" and "reactive_energy_import_kvarh" in str(g.get("metric"))
               for g in reasons), reasons


def test_card72_reactive_apparent_honest_blank_when_no_reactive_channel_at_all(monkeypatch):
    """A meter with NO reactive-energy register (and here no reactive-power column either) honest-blanks reactive +
    apparent (column_absent). Under the DEFINITIVE rule the absence of the reactive-ENERGY register alone is sufficient
    to honest-blank — a reactive-power series would not change the result (∫power never synthesizes reactive ENERGY).
    Only the ACTIVE cell (real register) fills."""
    from ems_exec.executor import derived as D
    from ems_exec.executor.gaps import GAPS_KEY
    present = {"active_energy_import_kwh", "active_power_total_kw", "power_factor_total"}  # NO reactive channel of any kind
    monkeypatch.setattr(D._nx, "present_columns", lambda t: frozenset(present))
    monkeypatch.setattr(F._nx, "present_columns", lambda t: frozenset(present))
    monkeypatch.setattr(D._nx, "latest",
                        lambda t, cols: {c: (27827.9 if c == "active_energy_import_kwh" else None) for c in cols})
    monkeypatch.setattr(F._nx, "latest",
                        lambda t, cols: {c: (27827.9 if c == "active_energy_import_kwh" else None) for c in cols})
    monkeypatch.setattr(F._nx, "window", lambda t, cols, s, e: ({}, {}))
    monkeypatch.setattr(D._nx, "window", lambda t, cols, s, e: ({}, {}))
    monkeypatch.setattr(F._nx, "column_logged", lambda t, c: c in present)
    # series carries NO reactive_power (the column is absent) → nothing to integrate → reactive leg stays None
    monkeypatch.setattr(D._nx, "series", lambda t, cols, s, e, **k: [])

    payload = {"energyReliability": {"cells": [
        {"id": "active", "unit": "MWh", "label": "Active", "value": None},
        {"id": "reactive", "unit": "MVARh", "label": "Reactive", "value": None},
        {"id": "apparent", "unit": "MVAh", "label": "Apparent", "value": None}]}}
    di = {"fields": [
        {"slot": "energyReliability.cells[0].value", "kind": "derived", "metric": "active_mwh", "fn": None,
         "unit": "MWh", "label": "Active"},
        {"slot": "energyReliability.cells[1].value", "kind": "derived", "metric": "reactive_mvarh", "fn": None,
         "unit": "MVARh", "label": "Reactive"},
        {"slot": "energyReliability.cells[2].value", "kind": "derived", "metric": "apparent_mvah", "fn": None,
         "unit": "MVAh", "label": "Apparent"}]}
    out = F.fill(payload, di, {"asset_table": "no_reactive_mfm", "window": ("2026-07-05T18:00:00", "2026-07-06T18:00:00")})
    er = out["energyReliability"]
    assert er["cells"][0]["value"] == 27.83, "Active still fills from its real register"
    assert er["cells"][1]["value"] is None, "Reactive honest-blanks: no reactive-energy register AND no reactive-power to ∫"
    assert er["cells"][2]["value"] is None, "Apparent honest-blanks: no reactive basis (never the active magnitude relabeled)"
    reasons = out.get(GAPS_KEY, [])
    assert any(g.get("cause") == "column_absent" and "reactive_energy_import_kvarh" in str(g.get("metric"))
               for g in reasons), reasons


def test_cumulative_apparent_requires_both_legs_no_over_block():
    """apparent = √(active² + reactive²): a MISSING reactive leg (None — no register) → honest None (never |active|); a
    reactive leg that is a REAL 0.0 (register present, reads zero) still computes apparent = |active| (a true quadrature
    with a zero reactive term, not a fabricated one). This is the no-over-block guard: a meter that DOES log reactive
    energy at 0 still fills apparent."""
    from ems_exec.derivations import energy as E
    # reactive register ABSENT (row has no reactive_energy_import_kvarh) → apparent honest-blanks
    assert E.cumulative_apparent_mvah({"row": {"active_energy_import_kwh": 27827.9}}) is None
    # reactive register PRESENT and a real 0.0 → apparent = |active| MVAh (no over-block)
    assert E.cumulative_apparent_mvah(
        {"row": {"active_energy_import_kwh": 27827.9, "reactive_energy_import_kvarh": 0.0}}) == 27.83
    # both legs real → the quadrature sum
    v = E.cumulative_apparent_mvah(
        {"row": {"active_energy_import_kwh": 27827.9, "reactive_energy_import_kvarh": 6330.0}})
    assert v is not None and v > 27.83, "quadrature adds the reactive leg"
    # no active leg at all → None (unchanged)
    assert E.cumulative_apparent_mvah({"row": {"reactive_energy_import_kvarh": 6330.0}}) is None


def test_mvah_reactive_fills_only_from_real_register_never_from_power():
    """DEFINITIVE [card-72 fab-by-substitution]: reactive MVArh fills ONLY from a real reactive-ENERGY register. A live
    reactive-POWER series must NEVER be integrated into a reactive-ENERGY reading (that was fabrication-by-substitution:
    reporting reactive ENERGY for a meter that carries NO reactive-ENERGY register). Register absent → honest None,
    whether or not a reactive-power series exists. (∫power recovery stays legitimate only for a POWER quantity.)"""
    from datetime import datetime
    from ems_exec.derivations import energy as E
    # register PRESENT → real_exact counter path (the ONLY source)
    assert E.mvah_reactive({"row": {"reactive_energy_import_kvarh": 6330.0}}) == 6.33
    # register PRESENT and a real 0.0 → fills 0.0 (honest zero on a present register, not a blank)
    assert E.mvah_reactive({"row": {"reactive_energy_import_kvarh": 0.0}}) == 0.0
    # register ABSENT + a live reactive-power series → STILL None (NO ∫power synthesis of reactive ENERGY)
    ser = [{"ts": datetime(2026, 7, 6, h), "reactive_power_total_kvar": v} for h, v in ((0, 2.0), (1, 8.0), (2, 16.6))]
    assert E.mvah_reactive({"row": {}, "series": ser}) is None, "reactive ENERGY never synthesized from ∫power"
    # register ABSENT + NO series (dark reactive channel) → honest None
    assert E.mvah_reactive({"row": {}}) is None
    assert E.mvah_reactive({"row": {}, "series": []}) is None
    # apparent HONEST-BLANKS on a meter with no reactive-energy register even when a reactive-power series exists
    apx = E.cumulative_apparent_mvah({"row": {"active_energy_import_kwh": 27827.9}, "series": ser})
    assert apx is None, "apparent honest-blanks: reactive ENERGY leg absent (never active MWh relabeled Apparent)"
    # the disabled ∫reactive-power→reactive-ENERGY recovery always returns None now
    assert E.reactive_energy_from_power_kvarh({"series": ser}) is None


def test_card72_energy_alias_polarity_families_classified():
    """The snake_case aliases carry the correct energy POLARITY family in registry._QUANTITY so verify._polarity_conflict
    (which receives the _derived_key = the alias) never false-flags a correct cell, yet still catches a genuine cross-
    polarity mis-bind (an active fn dropped onto a reactive slot)."""
    from ems_exec.executor.verify import _polarity_conflict, _fn_output_polarity
    assert _fn_output_polarity("active_mwh") == "active"
    assert _fn_output_polarity("reactive_mvarh") == "reactive"
    assert _fn_output_polarity("apparent_mvah") == "apparent"
    # correct cells: slot polarity == fn polarity → no conflict (the cell keeps its real value)
    assert _polarity_conflict({"unit": "MWh", "label": "Active", "metric": "active_mwh"}, "active_mwh") is False
    assert _polarity_conflict({"unit": "MVARh", "label": "Reactive", "metric": "reactive_mvarh"}, "reactive_mvarh") is False
    assert _polarity_conflict({"unit": "MVAh", "label": "Apparent", "metric": "apparent_mvah"}, "apparent_mvah") is False
    # a genuine mis-bind (active fn → reactive slot) is STILL refused
    assert _polarity_conflict({"unit": "MVARh", "label": "Reactive"}, "active_mwh") is True


# ═══ DEFECT 1 — a fn=null derived KPI whose metric HAS a binding resolves deterministically (not derivation_unbound) ══
# The final Layer-2 emit shipped kind=derived LIVE-DATA KPIs (totalKwh / avgLoad) with fn=null — the AI named the
# QUANTITY via `metric` but omitted the recovery fn. With a derivation_binding row now mapping each metric → its fn
# (db/seed_derivation_binding_fnless_metrics.sql), executor._derived_key's metric-wins path resolves the fn WITHOUT the
# AI supplying it, so the KPI fills from real data instead of logging 'derivation_unbound' and false-blanking.
def test_defect1_fnnull_metric_resolves_from_binding_totalkwh_avgload():
    from ems_exec.executor.derived import _derived_key
    from config import derivation_binding as _db
    # the binding maps each fn-less metric → its computing fn (the deterministic route _derived_key/_run_derived take)
    for metric, fn in (("totalKwh", "todaysEnergyTotalKwh"), ("avgLoad", "loadFactorPct")):
        field = {"slot": "s", "kind": "derived", "fn": None, "metric": metric}
        assert _derived_key(field) == metric, f"{metric} must be the derivation key when fn is null (binding exists)"
        assert (_db.binding(metric) or {}).get("fn") == fn, f"{metric} → {fn} (deterministic fn from the binding)"


def test_defect1_fnnull_kpi_fills_real_value(monkeypatch):
    """The full executor path: a fn=null derived field (metric=totalKwh) fills the real windowed active-energy delta
    instead of derivation_unbound. Offline — neuract window/series monkeypatched (active delta 27827.9-27727.7 = 100.2)."""
    from ems_exec.executor import derived as D
    from ems_exec.executor.gaps import GAPS_KEY
    present = {"active_energy_import_kwh", "active_power_total_kw"}
    monkeypatch.setattr(D._nx, "present_columns", lambda t: frozenset(present))
    monkeypatch.setattr(F._nx, "present_columns", lambda t: frozenset(present))
    monkeypatch.setattr(F._nx, "column_logged", lambda t, c: c in present)
    monkeypatch.setattr(D._nx, "latest", lambda t, cols: {})
    monkeypatch.setattr(F._nx, "latest", lambda t, cols: {})
    # the active-energy window delta = end(27827.9) - start(27727.7) = 100.2 (todaysEnergyTotalKwh's active leg)
    def _win(t, cols, s, e):
        return ({c: (27727.7 if c == "active_energy_import_kwh" else None) for c in cols},
                {c: (27827.9 if c == "active_energy_import_kwh" else None) for c in cols})
    monkeypatch.setattr(D._nx, "window", _win)
    monkeypatch.setattr(F._nx, "window", _win)
    monkeypatch.setattr(D._nx, "series", lambda t, cols, s, e, **k: [])

    payload = {"stats": {"totalKwh": None}}
    di = {"fields": [{"slot": "stats.totalKwh", "kind": "derived", "fn": None, "metric": "totalKwh",
                      "unit": "kWh", "label": "Total Energy"}]}
    out = F.fill(payload, di, {"asset_table": "dg_1_mfm", "window": ("2026-07-05T18:00:00", "2026-07-06T18:00:00")})
    assert out["stats"]["totalKwh"] == 100.2, "totalKwh fills the real windowed active-energy delta (no derivation_unbound)"
    reasons = out.get(GAPS_KEY, [])
    assert not any(g.get("cause") == "derivation_unbound" for g in reasons), reasons


# ═══ DEFECT B — card 73 solo single-index buckets grow to the full per-bucket series ══════════════════════════════
def test_card73_buckets_grow_to_full_series(monkeypatch):
    _patch_neuract(monkeypatch)
    window = ("2026-07-06T00:00:00", "2026-07-06T18:00:00")
    payload = {"buckets": [{"label": "", "active": 0.0, "reactive": 0.0, "apparent": 0.0, "pf": 0.0}]}
    di = {"fields": [
        {"slot": "buckets[0].active", "kind": "bucketed", "column": "active_power_total_kw", "unit": "kW"},
        {"slot": "buckets[0].reactive", "kind": "bucketed", "column": "reactive_power_total_kvar", "unit": "kvar"},
        {"slot": "buckets[0].apparent", "kind": "bucketed", "column": "apparent_power_total_kva", "unit": "kva"},
        {"slot": "buckets[0].pf", "kind": "bucketed", "column": "power_factor_total", "unit": ""}]}
    out = F.fill(payload, di, {"asset_table": "dg_1_mfm", "window": window})
    b = out["buckets"]
    assert len(b) == 3, "buckets grown to the full 3-bucket series (not left at 1, not crammed)"
    # every element carries SCALAR per-bucket values (never a whole series crammed into element[0])
    assert all(not isinstance(x["active"], list) for x in b), "no series crammed into one element"
    assert [x["active"] for x in b] == [10.0, 50.0, 104.9], "active series fills from the same frame as the axis"
    assert [x["reactive"] for x in b] == [2.0, 8.0, 16.6]
    assert [x["apparent"] for x in b] == [11.0, 51.0, 107.3]
    assert [round(x["pf"], 2) for x in b] == [0.10, 0.12, 0.13]


def test_card73_sparkline_same_key_family_not_promoted(monkeypatch):
    """A SAME-key multi-index family (sparkline[0..2].loadPct) must still fill via the indexed-family path (point i ←
    bucket i), NOT be grown by the solo-promotion — the fix must not over-fire."""
    _patch_neuract(monkeypatch)
    window = ("2026-07-06T00:00:00", "2026-07-06T18:00:00")
    payload = {"load": {"sparkline": [{"loadPct": 0.0}, {"loadPct": 0.0}, {"loadPct": 0.0}]}}
    di = {"fields": [
        {"slot": f"load.sparkline[{i}].loadPct", "kind": "bucketed", "column": "active_power_total_kw", "unit": "kW"}
        for i in range(3)]}
    out = F.fill(payload, di, {"asset_table": "dg_1_mfm", "window": window})
    sp = out["load"]["sparkline"]
    assert len(sp) == 3, "sparkline stays a 3-point family (not grown into a bucket array)"
    assert all(not isinstance(x["loadPct"], list) for x in sp), "each point is a scalar"
    # point i ← bucket i (end-aligned): the 3 real buckets land on the 3 slots
    assert [x["loadPct"] for x in sp] == [10.0, 50.0, 104.9]


# ── DEFECT B (card 73) second manifestation: source=$ctx on a STANDALONE card ────────────────────────────────────────
# The live re-fire showed card 73 (standalone, $ctx=None) systematically binding its 4 power-trend series with
# source=$ctx to REAL basket columns (active_power_total_kw …). $ctx cannot fill server-side on a standalone card, so
# the measurable series false-blanked. column_override reclassifies $ctx→live on a standalone card when the field names
# a real basket column (→ the series fills); a $ctx field naming no real column drops to frame/honest-blank; a real
# GROUP card keeps $ctx untouched.
def test_card73_ctx_on_standalone_reclassified_to_live():
    from layer2.resolve.column_override import apply as override
    basket = {"columns": [{"column": "active_power_total_kw", "unit": "kW"},
                          {"column": "reactive_power_total_kvar", "unit": "kVAr"}]}
    di = {"fields": [
        {"slot": "backupHistory.series[0].values", "kind": "bucketed", "column": "active_power_total_kw", "source": "$ctx"},
        {"slot": "backupHistory.series[1].values", "kind": "bucketed", "column": "reactive_power_total_kvar", "source": "$ctx"},
        {"slot": "backupHistory.series[9].values", "kind": "bucketed", "column": "not_a_real_col", "source": "$ctx"},
    ]}
    out, notes = override(di, basket, is_group_card=False)
    assert out["fields"][0]["source"] == "live" and out["fields"][0]["column"] == "active_power_total_kw"
    assert out["fields"][1]["source"] == "live"
    assert out["fields"][2]["source"] == "frame" and out["fields"][2]["column"] is None  # no real col → honest-blank
    assert any("reclassified to live" in n for n in notes)


# card 49 (pg09 power-quality, LoadImpactChart pf-angle) re-fired the c73 mode with a TWIST: the $ctx field omitted the
# redundant `column` but its own `metric` NAMED a real basket column (metric='phase_angle_deg' == the column). The direct-
# column check missed it, so the measurable pf-angle series+stat dropped to frame/honest-blank while phase_angle_deg had
# 61k live rows. column_override now resolves the column from the field's metric (unit-guarded) and reclassifies $ctx→live
# so the leaf fills; a metric that names NO real+compatible basket column still honest-blanks (never over-reach).
def test_card49_ctx_no_column_resolves_via_metric_to_live():
    from layer2.resolve.column_override import apply as override
    basket = {"columns": [{"column": "phase_angle_deg", "unit": "°"},
                          {"column": "power_factor_total", "unit": ""}]}
    di = {"fields": [
        {"slot": "loadImpact.views.pf-angle.series[0].values", "kind": "bucketed", "column": None,
         "metric": "phase_angle_deg", "unit": "°", "source": "$ctx"},
        {"slot": "loadImpact.views.pf-angle.stats[1].value", "kind": "raw", "column": None,
         "metric": "phase_angle_deg", "unit": "°", "source": "$ctx"},
        # a genuinely-unmeasurable $ctx leaf (metric names no basket column) must STAY honest-blank — no over-reach
        {"slot": "loadImpact.views.flicker.series[0].values", "kind": "bucketed", "column": None,
         "metric": "flicker_pst", "unit": "", "source": "$ctx"},
    ]}
    out, notes = override(di, basket, is_group_card=False)
    assert out["fields"][0]["source"] == "live" and out["fields"][0]["column"] == "phase_angle_deg"
    assert out["fields"][1]["source"] == "live" and out["fields"][1]["column"] == "phase_angle_deg"
    assert out["fields"][2]["source"] == "frame" and out["fields"][2]["column"] is None  # unmeasurable → honest-blank
    assert any("resolved to live via its metric" in n for n in notes)


def test_card73_group_card_keeps_ctx():
    """A genuine GROUP card ($ctx legal — reads the page shared buffer) must NOT be reclassified."""
    from layer2.resolve.column_override import apply as override
    basket = {"columns": [{"column": "active_power_total_kw", "unit": "kW"}]}
    di = {"fields": [{"slot": "s.series[0].values", "kind": "bucketed", "column": "active_power_total_kw", "source": "$ctx"}]}
    out, _ = override(di, basket, is_group_card=True)
    assert out["fields"][0]["source"] == "$ctx"


# ── DEFECT B (card 73) THIRD root cause: is_group_card wrongly derived from a mere COUPLING ───────────────────────────
# card 73 sits in a time-bucket-COUPLED group (cards 71,73). build_card_input set is_group_card=(group is not None), so
# a DATE-SYNC coupling made it a shared-context group card that emits src=$ctx — but shared_context (Approach-B) is
# DEFERRED (the fan-out passes shared_ctx_ref=None), so the $ctx series had no buffer and false-blanked measurable
# columns. is_group_card now requires a REAL shared buffer (shared_ctx_ref); a coupled card with no buffer is STANDALONE
# and fills its own data (src=live). Uses cmd_catalog (:5432) for the catalog row; no neuract needed.
def test_card73_coupling_without_buffer_is_standalone():
    from layer2.card_input import build_card_input
    l1a = {"page_key": "diesel-generator-asset-dashboard/operations-runtime", "metric": "power", "intent": "snapshot",
           "story": "s",
           "cards": [{"card_id": 71, "title": "t", "analytical_story": "a", "role_in_story": "r"},
                     {"card_id": 73, "title": "Power Energy Analysis", "analytical_story": "a", "role_in_story": "r"}],
           "interdependency_groups": [{"group_id": "g0", "card_ids": [71, 73], "coupling": ["time-bucket"]}]}
    l1b = {"asset": {"table": "dg_1_mfm", "name": "DG-1 MFM"},
           "column_basket": {"tables": ["dg_1_mfm"], "columns": []}}
    # DEFERRED shared_context (the live path): a coupled card with NO buffer is standalone → fills its own data.
    noctx = build_card_input("t", 73, l1a, l1b, shared_ctx_ref=None)
    assert noctx["is_group_card"] is False and noctx["group_id"] is None
    # When Approach-B builds a real buffer, the SAME coupled card IS a group card.
    withctx = build_card_input("t", 73, l1a, l1b, shared_ctx_ref={"$id": "g0"})
    assert withctx["is_group_card"] is True and withctx["group_id"] == "g0"


# ═══ DEFECT 1 (pg12 card 64) — the DERIVED-KEY emit form + avgLoad's full-value fill ══════════════════════════════════
# The card-64 stats KPIs ship kind=derived with fn=null. The AI names the QUANTITY two ways: the fn-name form
# (metric='totalKwh'/'avgLoad', covered above) AND the canonical derived-KEY / quantity form
# (metric='active-energy-kwh'/'load-factor-percent' — db/seed_card64_derivedkey_bindings.sql). BOTH must resolve their
# recovery fn from the binding row via _derived_key's metric-wins path — a null fn on the field is not a blank when the
# metric names a bound quantity. Regression guard: the executor MUST fall back to binding.fn, not to the (null) field fn.
def test_defect1_derived_key_emit_form_resolves_from_binding():
    from ems_exec.executor.derived import _derived_key
    from config import derivation_binding as _db
    # the derived-KEY / quantity emit form (the shape the live card-64 emit actually ships) → its computing fn
    for metric, fn in (("active-energy-kwh", "windowEnergyKwh"), ("load-factor-percent", "loadFactorPct")):
        field = {"slot": "s", "kind": "derived", "fn": None, "metric": metric}
        assert _derived_key(field) == metric, f"{metric} must be the derivation key when fn is null (binding exists)"
        assert (_db.binding(metric) or {}).get("fn") == fn, f"{metric} → {fn} (deterministic fn from the binding)"


def test_defect1_avgload_fills_load_factor_pct_via_native_rescue(monkeypatch):
    """The full executor path for stats.avgLoad: a fn=null derived field (metric=avgLoad → loadFactorPct) fills the real
    energized load factor (%), NOT derivation_unbound / false-blank. dg_1_mfm is a standby genset whose HOURLY-bucketed
    power collapses below the energized-degeneracy floor, so the derivation honest-blanks at bucket resolution — but the
    NATIVE-resolution load-factor rescue (load_factor_fill) recomputes the real mean/peak from the raw column (91.1 %).
    Offline: the rescue's native SQL aggregate is monkeypatched to the true energized load factor; the point is that a
    fn=null avgLoad ROUTES to the rescue and fills real, and the leaf carries no derivation_unbound gap."""
    from ems_exec.executor import load_factor_fill as LFF
    _patch_neuract(monkeypatch)
    monkeypatch.setattr(LFF._nx, "column_logged", lambda t, c: c == "active_power_total_kw")
    # native-resolution energized load factor over active_power_total_kw (mean 787 / peak 864 ≈ 91.1 %)
    monkeypatch.setattr(LFF, "_native_load_factor", lambda table, col, window:
                        91.1 if col == "active_power_total_kw" else None)
    window = ("2026-07-01T00:00:00", "2026-07-06T18:00:00")
    payload = {"stats": {"avgLoad": None}}
    di = {"fields": [{"slot": "stats.avgLoad", "kind": "derived", "fn": None, "metric": "avgLoad",
                      "unit": "%", "label": "Average Load"}]}
    out = F.fill(payload, di, {"asset_table": "dg_1_mfm", "window": window})
    assert out["stats"]["avgLoad"] == 91.1, "avgLoad fills the real energized load factor % (no false-blank)"
    reasons = out.get(GAPS_KEY, [])
    assert not any(g.get("cause") == "derivation_unbound" for g in reasons if g.get("slot", "").endswith("avgLoad")), reasons
