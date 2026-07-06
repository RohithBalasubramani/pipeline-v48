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
