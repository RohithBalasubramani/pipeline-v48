"""ems_exec executor — POST-FILL RESCUE OVER-REACH GUARDS + seed-leak class (DEFECTS 56 / 71 / 73).

Every rescue (scalar_tile_fill / scalar_mean_fill / load_factor_fill) is now OVER-REACH-SAFE against three durable
class-level defects the adversarial audit found; a genuine fill on a sibling card is PRESERVED (no regression):

  DEFECT 56 (a) GENERAL honest-blank fence — a leaf the AI EXPLICITLY honest-blanked (di._honest_blanked / di._emit_gaps)
                is NEVER resurrected by a mechanical label/mean/load-factor rescue. Threaded from fill() via
                fill._honest_blank_paths (parses the 'slot:' prefix of each _honest_blanked string + each _emit_gaps.slot).
  DEFECT 56 (b) DEFENSE-IN-DEPTH source-role wall — measurable_resolve.resolve_column returns [] for a voltage/current
                label qualified by a NON-MEASURED SOURCE ROLE (bypass/input/mains/utility/grid/source/incoming/line-side);
                'Output Voltage'/'Output Current' still resolve (the meter's own measured point).
  DEFECT 71     load_factor_fill UNIT GATE — a load-factor (%) fills ONLY a PERCENT-LIKE target slot; a load-% under an
                HOURS ('h') / count / energy unit is refused (a run-hours slot honest-blanks).
  DEFECT 73     fab_guards CLASS 4 seed-leak — a leaf byte-identical to the card's DEFAULT payload at the same path AND
                never filled real → BLANK (unstripped seed); a filled-real leaf is protected by the written-path set.

Card 50 preservation: a HARD-blank {label:'Output Voltage', value:None} STILL fills (234V / 269A) — the honest-blank
fence never fires for a leaf the AI did NOT declare honest-blank, and the source-role wall passes 'Output ...'.

Pure unit tests — neuract reads monkeypatched (no live DB, no LLM).
"""
from __future__ import annotations

import importlib

import pytest
from unittest.mock import patch

import ems_exec.data.neuract as nx
from ems_exec.executor import fill as F
from ems_exec.executor import scalar_tile_fill as STF
from ems_exec.executor import scalar_mean_fill as SMF
from ems_exec.executor import load_factor_fill as LFF
from ems_exec.executor import measurable_resolve as MR
from ems_exec.executor import fab_guards as G


@pytest.fixture(autouse=True)
def _pin_enforce_mode():
    """Pin fab_guards.mode='enforce' so the CLASS-4 blank assertions here are isolated from the live app_config knob
    (an operator may leave mode='report' during a fleet audit — report mode never mutates)."""
    A = importlib.import_module("ems_exec.executor.fab_guards.apply")
    with patch.object(A, "_mode", lambda: "enforce"):
        yield


# ── fill._honest_blank_paths: parse the AI's declared honest-blank set ───────────────────────────────────────────────
def test_honest_blank_paths_parses_both_channels():
    di = {"_honest_blanked": ["metrics[1].value: slot names the bypass source role — leaf honest-blanks",
                              "data.foo.bar: reason with a stray : colon inside"],
          "_emit_gaps": [{"slot": "data.baz.qux", "cause": "unbound_by_emit"},
                         {"slot": "arr[*].k"}]}
    hb = F._honest_blank_paths(di)
    # slot prefix parsed before the FIRST ':' — reason colons never leak into the path
    assert ("metrics", "1", "value") in hb
    assert ("foo", "bar") in hb and ("data", "foo", "bar") in hb        # both address forms normalized
    assert ("baz", "qux") in hb and ("data", "baz", "qux") in hb
    assert ("arr", "*", "k") in hb                                      # wildcard segment kept raw


def test_honest_blank_paths_empty_when_absent():
    assert F._honest_blank_paths({}) == set()
    assert F._honest_blank_paths(None) == set()


# ── DEFECT 56 (b): source-role wall in measurable_resolve ────────────────────────────────────────────────────────────
def test_source_role_wall_blocks_nonmeasured_rails_keeps_output():
    # the meter measures its OWN output — voltage_avg/current_avg IS that measured point
    assert MR.candidate_columns("Output Voltage") == ["voltage_avg"]
    assert MR.candidate_columns("Output Current") == ["current_avg"]
    # a DEDICATED-sensing rail (bypass/utility/grid/source/incoming/line-side) names a physically distinct sensing
    # point this OUTPUT-metering MFM has no column for → [] (honest blank). NOTE [DEFECT c59 inputVoltageV]: 'input'/
    # 'mains' are NOT dedicated rails — the meter's own voltage_avg IS the input/line/mains reading — so they RESOLVE
    # (they were once wrongly walled here, silently false-blanking every input* leaf; the vocab is dedicated-only now).
    for label in ("Average Bypass Voltage", "Bypass Voltage",
                  "Utility Voltage", "Grid Voltage", "Source Voltage", "Incoming Voltage",
                  "Line-side Voltage", "Line side Current"):
        assert MR.candidate_columns(label) == [], label
    # the NON-dedicated roles fill from the meter's own plain reading
    assert MR.candidate_columns("Input Voltage") == ["voltage_avg"]
    assert MR.candidate_columns("Mains Voltage") == ["voltage_avg"]


def test_source_role_wall_token_exact_no_substring_false_fire():
    # token-exact: 'sourced'/'grinder'/'inputted'/'outgoing' do NOT tokenize to the role token → still resolve
    assert MR.candidate_columns("grinder amps") == ["current_avg"]
    assert MR.candidate_columns("inputted voltage") == ["voltage_avg"]
    assert MR.candidate_columns("outgoing voltage") == ["voltage_avg"]


def test_resolve_column_source_role_returns_none(monkeypatch):
    monkeypatch.setattr(nx, "column_logged", lambda t, c: True)         # voltage_avg IS logged
    assert MR.resolve_column("Output Voltage", "tbl") == "voltage_avg"  # measured → binds
    assert MR.resolve_column("Bypass Voltage", "tbl") is None           # source-role wall → no candidate → honest blank


# ── DB-DRIVEN proof: every steering vocab is a cmd_catalog row (edit the row → behavior follows, no code change) ──────
# measurable_resolve reads each vocab via config.app_config.cfg with a code-default MIRROR. Patching cfg simulates a DB
# row edit; the wall/derivation must follow it — proving there is NO hardcoded label/quantity/class SET baked in code.
def _patch_cfg(monkeypatch, overrides):
    import config.app_config as ac
    orig = ac.cfg
    monkeypatch.setattr(ac, "cfg", lambda k, d=None: overrides[k] if k in overrides else orig(k, d))


def test_measured_source_roles_is_db_driven(monkeypatch):
    # THE consolidated role-vocab home [F10, 2026-07-12]: quantity.source_role_wall steers the wall — add 'bypass'
    # to its measured markers → the wall LIFTS for 'Bypass Voltage' (now a measured terminal). No code literal.
    _patch_cfg(monkeypatch, {"quantity.source_role_wall": {
        "measured": ["output", "bypass"],
        "dedicated": ["utility", "grid", "source", "incoming", "line side", "line-side", "lineside"],
        "nondedicated": ["input", "line", "mains"]}})
    assert MR.candidate_columns("Bypass Voltage") == ["voltage_avg"]    # DB row steers the wall, not a code literal
    assert MR.candidate_columns("Output Voltage") == ["voltage_avg"]


def test_legacy_measurable_alias_steers_when_new_row_absent(monkeypatch):
    # ALIAS CHAIN [F10]: with quantity.source_role_wall absent, the legacy measurable.* rows still steer (they are
    # documented aliases, not dead keys) — the same 'bypass becomes measured' edit through the OLD key.
    _patch_cfg(monkeypatch, {"quantity.source_role_wall": None,
                             "measurable.measured_source_roles": ["output", "bypass"]})
    assert MR.candidate_columns("Bypass Voltage") == ["voltage_avg"]
    assert MR.candidate_columns("Utility Voltage") == []                # dedicated rail still walls via the alias


def test_derived_quantity_classes_is_db_driven(monkeypatch):
    # drop '-thd' from measurable.derived_quantity_classes → iThdPk is no longer walled as a distortion quantity.
    _patch_cfg(monkeypatch, {"measurable.derived_quantity_classes": ["-harmonic"]})
    assert MR.candidate_columns("iThdPk") == ["current_avg"]            # distortion wall follows the DB set


def test_quantity_prefix_is_db_driven(monkeypatch):
    # remove the voltage prefix from measurable.quantity_prefix → a vAvg leaf no longer resolves (honest-blank).
    _patch_cfg(monkeypatch, {"measurable.quantity_prefix": {"current": "current", "amps": "current"}})
    assert MR.candidate_columns("vAvg") == []                          # voltage prefix gone via DB → no candidate
    assert MR.candidate_columns("amps") == ["current_avg"]             # current prefix still present


def test_stat_suffix_is_db_driven(monkeypatch):
    # remove 'max' from measurable.stat_suffix → vMax collapses to the canonical _avg headline (no _max composed).
    _patch_cfg(monkeypatch, {"measurable.stat_suffix": {"avg": "avg", "mean": "avg"}})
    assert MR.candidate_columns("vMax") == ["voltage_avg"]             # unknown stat → canonical _avg (DB-driven)


def test_shared_vocab_accessors_read_db_defaults():
    # the SHARED vocab both rescues read lives in ONE home (measurable_resolve) and is DB-backed with a code default.
    assert MR.unit_keys() == {"unit", "units", "suffix"}
    assert MR.scalar_quantity_words() == {"power", "energy", "demand", "load", "frequency"}


def test_unit_keys_is_db_driven_via_load_factor_gate(monkeypatch):
    # The unit-key vocab is SHARED (one home in measurable_resolve, read by both rescues). Proof via the load-factor
    # DEFECT-71 gate, where reading the unit CHANGES the outcome: rename the unit key to 'uom' via measurable.unit_keys
    # → the gate reads the HOURS unit from {uom:'h'} and REFUSES. With the default keys the 'uom' sibling is missed and
    # the load-% wrongly fills — a change in outcome proves the key set is DB-driven, not a code literal.
    monkeypatch.setattr(LFF, "_native_load_factor", lambda tbl, col, w: 91.1)
    monkeypatch.setattr(LFF, "_load_factor_field",
                        lambda f: "active_power_total_kw" if f.get("kind") == "derived" else None)
    fields = [{"slot": "slot.value", "kind": "derived", "fn": "loadFactorPct", "metric": "loadFactorPct"}]
    # DEFAULT keys ('unit'/'units'/'suffix'): 'uom' is NOT a unit key → unit=None → id/label fallback ('x' not non-%) → FILLS
    out = {"data": {"slot": {"id": "x", "uom": "h", "value": None}}}
    assert LFF.apply(out, fields, "dg_1_mfm", (None, None)) and out["data"]["slot"]["value"] == 91.1
    # DB rename to ['uom']: the HOURS unit is now read → the load-% is refused (honest-blank)
    out2 = {"data": {"slot": {"id": "x", "uom": "h", "value": None}}}
    _patch_cfg(monkeypatch, {"measurable.unit_keys": ["uom"]})
    assert not LFF.apply(out2, fields, "dg_1_mfm", (None, None)) and out2["data"]["slot"]["value"] is None


# ── DEFECT 56 (a): scalar_tile_fill honors the honest-blank fence + card-50 preservation ─────────────────────────────
def _stub_bucketed(monkeypatch, value):
    monkeypatch.setattr(nx, "bucketed", lambda t, c, s, e, sampling="hourly": [{"t": "T", "value": value}])
    monkeypatch.setattr(nx, "column_logged", lambda t, c: True)
    monkeypatch.setattr(nx, "present_columns", lambda t: frozenset({"voltage_avg", "current_avg"}))


def test_scalar_tile_fill_card50_output_tiles_still_fill(monkeypatch):
    # CARD 50 PRESERVATION: a HARD-blank {label:'Output Voltage', value:None} fills 234.1; 'Output Current' fills 268.7.
    def _bkt(t, c, s, e, sampling="hourly"):
        return [{"t": "T", "value": 234.1}] if c == "voltage_avg" else [{"t": "T", "value": 268.7}]
    monkeypatch.setattr(nx, "bucketed", _bkt)
    monkeypatch.setattr(nx, "column_logged", lambda t, c: True)
    out = {"data": {"metrics": [{"label": "Temperature", "unit": "°C", "value": None},
                                {"label": "Output Voltage", "unit": "V", "value": None},
                                {"label": "Output Current", "unit": "A", "value": None}]}}
    filled = STF.apply(out, "gic_01_n3_ups_01_p1", (None, None), written_value_paths=set(),
                       honest_blank_paths=set())
    m = out["data"]["metrics"]
    assert m[1]["value"] == 234.1 and m[2]["value"] == 268.7            # Output V/A fill (card-50 fix preserved)
    assert m[0]["value"] is None                                       # Temperature (no v/i column) honest-blanks
    assert "data.metrics[1].value" in filled


def test_scalar_tile_fill_skips_ai_honest_blank(monkeypatch):
    # DEFECT 56: the AI honest-blanked metrics[1].value ('Average Bypass Voltage') — the rescue must NOT resurrect it,
    # even though a matching column exists; a sibling 'Output Voltage' tile still fills.
    def _bkt(t, c, s, e, sampling="hourly"):
        return [{"t": "T", "value": 234.1}]
    monkeypatch.setattr(nx, "bucketed", _bkt)
    monkeypatch.setattr(nx, "column_logged", lambda t, c: True)
    out = {"data": {"metrics": [{"label": "Output Voltage", "unit": "V", "value": None},
                                {"label": "Average Bypass Voltage", "unit": "V", "value": None}]}}
    hb = {("data", "metrics", "1", "value")}
    filled = STF.apply(out, "tbl", (None, None), written_value_paths=set(), honest_blank_paths=hb)
    assert out["data"]["metrics"][0]["value"] == 234.1                 # Output Voltage still fills
    assert out["data"]["metrics"][1]["value"] is None                 # explicit honest-blank NOT resurrected
    assert "data.metrics[1].value" not in filled


def test_scalar_tile_fill_source_role_label_honest_blanks(monkeypatch):
    # DEFENSE-IN-DEPTH: even with NO honest-blank fence, a 'Bypass Voltage' label resolves to no column → stays blank.
    _stub_bucketed(monkeypatch, 234.1)
    out = {"data": {"metrics": [{"label": "Bypass Voltage", "unit": "V", "value": None}]}}
    filled = STF.apply(out, "tbl", (None, None), written_value_paths=set(), honest_blank_paths=set())
    assert out["data"]["metrics"][0]["value"] is None
    assert not filled


# ── DEFECT 56 (a): scalar_mean_fill honors the fence ─────────────────────────────────────────────────────────────────
def test_scalar_mean_fill_skips_ai_honest_blank(monkeypatch):
    monkeypatch.setattr(nx, "column_logged", lambda t, c: True)
    monkeypatch.setattr(nx, "bucketed", lambda t, c, s, e, sampling="hourly": [{"t": "T", "value": 190.0}])
    fields = [{"slot": "data.bars[*].active", "kind": "bucketed", "column": "active_power_total_kw",
               "label": "Active Power", "unit": "kW"}]
    out = {"data": {"activePowerAvgKw": None}}
    hb = {("data", "activePowerAvgKw"), ("activePowerAvgKw",)}
    filled = SMF.apply(out, fields, "tbl", (None, None), honest_blank_paths=hb)
    assert out["data"]["activePowerAvgKw"] is None                     # AI honest-blank respected
    assert not filled
    # without the fence it fills (proves the fence is the ONLY thing holding it)
    filled2 = SMF.apply(out, fields, "tbl", (None, None), honest_blank_paths=set())
    assert out["data"]["activePowerAvgKw"] == 190.0 and "data.activePowerAvgKw" in filled2


# ── DEFECT 71: load_factor_fill UNIT GATE ────────────────────────────────────────────────────────────────────────────
def _lf_fields():
    return [{"slot": "avgLoadPct", "kind": "derived", "fn": "loadFactorPct", "metric": "loadFactorPct"}]


def _stub_lf(monkeypatch, deriv_col="active_power_total_kw"):
    monkeypatch.setattr(LFF, "_native_load_factor", lambda tbl, col, w: 91.1)

    def _lf_field(f):
        return deriv_col if (f.get("kind") == "derived") else None
    monkeypatch.setattr(LFF, "_load_factor_field", _lf_field)


def test_load_factor_fill_refuses_hours_unit_slot(monkeypatch):
    # DEFECT 71: a load-% must NOT fill a run-hours slot {unit:'h', label:'Average load'} → stays honest-blank.
    _stub_lf(monkeypatch)
    out = {"data": {"total-run-hours": {"id": "total-run-hours", "unit": "h", "label": "Average load",
                                        "value": None}}}
    fields = [{"slot": "total-run-hours.value", "kind": "derived", "fn": "loadFactorPct", "metric": "loadFactorPct"}]
    filled = LFF.apply(out, fields, "dg_1_mfm", (None, None))
    assert out["data"]["total-run-hours"]["value"] is None            # hours unit → refused
    assert not filled


def test_load_factor_fill_fills_percent_unit_slot(monkeypatch):
    # a genuine load-factor-% slot ('%' unit) still fills 91.1 (no regression).
    _stub_lf(monkeypatch)
    out = {"data": {"avgLoad": {"id": "avg-load-pct", "unit": "%", "label": "Average load", "value": None}}}
    fields = [{"slot": "avgLoad.value", "kind": "derived", "fn": "loadFactorPct", "metric": "loadFactorPct"}]
    filled = LFF.apply(out, fields, "dg_1_mfm", (None, None))
    assert out["data"]["avgLoad"]["value"] == 91.1
    assert "avgLoad.value" in filled


def test_load_factor_fill_bare_percent_key_fills(monkeypatch):
    # a scalar KPI leaf with NO unit sibling but a percent-like id/label → treated as percent-like → fills.
    _stub_lf(monkeypatch)
    out = {"data": {"avgLoadPct": None}}
    fields = [{"slot": "avgLoadPct", "kind": "derived", "fn": "loadFactorPct", "metric": "loadFactorPct"}]
    filled = LFF.apply(out, fields, "dg_1_mfm", (None, None))
    assert out["data"]["avgLoadPct"] == 91.1

def test_load_factor_unit_predicate():
    assert LFF._unit_is_percent_like("%") is True
    assert LFF._unit_is_percent_like("pct") is True
    assert LFF._unit_is_percent_like("percent") is True
    assert LFF._unit_is_percent_like("") is True
    assert LFF._unit_is_percent_like(None) is True
    assert LFF._unit_is_percent_like("h") is False
    assert LFF._unit_is_percent_like("hr") is False
    assert LFF._unit_is_percent_like("hours") is False
    assert LFF._unit_is_percent_like("kWh") is False
    assert LFF._unit_is_percent_like("count") is False


def test_load_factor_fill_honors_honest_blank_fence(monkeypatch):
    _stub_lf(monkeypatch)
    out = {"data": {"avgLoad": {"unit": "%", "value": None}}}
    fields = [{"slot": "avgLoad.value", "kind": "derived", "fn": "loadFactorPct", "metric": "loadFactorPct"}]
    hb = {("data", "avgLoad", "value"), ("avgLoad", "value")}
    filled = LFF.apply(out, fields, "dg_1_mfm", (None, None), honest_blank_paths=hb)
    assert out["data"]["avgLoad"]["value"] is None                    # AI honest-blank respected
    assert not filled


# ── DEFECT 73: fab_guards CLASS 4 seed-leak ──────────────────────────────────────────────────────────────────────────
def test_class4_seed_leak_blanks_unwritten_default_array():
    # card 73: backupHistory.series[0].legendValue byte-identical to the DEFAULT + never written → unstripped seed.
    out = {"data": {"backupHistory": {"series": [{"legendValue": [52, 71, 85, 43],
                                                  "values": [10.0, 20.0, 30.0]}]}}}
    default = {"data": {"backupHistory": {"series": [{"legendValue": [52, 71, 85, 43],
                                                     "values": [0.0, 0.0, 0.0]}]}}}
    written = {"data.backupHistory.series[0].values"}                 # values were filled real; legendValue was not
    out2, gaps = G.apply(out, [], frozenset(), "tbl", default_payload=default, written_paths=written)
    assert out2["data"]["backupHistory"]["series"][0]["legendValue"] == []   # seed leaked → blanked
    assert out2["data"]["backupHistory"]["series"][0]["values"] == [10.0, 20.0, 30.0]  # real values kept
    assert any(g["cause"] == "unstripped_seed" for g in gaps)


def test_class4_written_real_leaf_protected_even_if_equals_seed():
    # a FILLED-real leaf coincidentally equal to its seed is protected by the written-path set — never blanked.
    out = {"data": {"kpi": [1.0, 2.0, 3.0]}}
    default = {"data": {"kpi": [1.0, 2.0, 3.0]}}
    written = {"data.kpi"}
    out2, gaps = G.apply(out, [], frozenset(), "tbl", default_payload=default, written_paths=written)
    assert out2["data"]["kpi"] == [1.0, 2.0, 3.0]                     # written → protected
    assert not any(g["cause"] == "unstripped_seed" for g in gaps)


def test_class4_over_reach_safe_trivial_scalars_and_zero_none():
    # a bare 0 / None / '' / single digit equal-to-default is NOT blanked (a real fill or honest blank produces these).
    out = {"data": {"z": 0, "n": None, "s": "", "one": 5, "flag": True, "big": 4200.0}}
    default = {"data": {"z": 0, "n": None, "s": "", "one": 5, "flag": True, "big": 4200.0}}
    out2, gaps = G.apply(out, [], frozenset(), "tbl", default_payload=default, written_paths=set())
    # trivial values survive; a NON-trivial unwritten scalar (4200.0) equal to its seed IS a leak → blanked
    assert out2["data"]["z"] == 0 and out2["data"]["n"] is None and out2["data"]["s"] == ""
    assert out2["data"]["one"] == 5 and out2["data"]["flag"] is True
    assert out2["data"]["big"] is None                               # non-trivial unwritten seed scalar → blanked
    assert any(g["slot"] == "data.big" for g in gaps)


def test_class4_differing_value_not_blanked():
    # a leaf whose final value DIFFERS from the default is real (filled or honest) — never blanked as a seed.
    out = {"data": {"series": [{"legendValue": [1, 2, 3]}]}}
    default = {"data": {"series": [{"legendValue": [52, 71, 85, 43]}]}}
    out2, gaps = G.apply(out, [], frozenset(), "tbl", default_payload=default, written_paths=set())
    assert out2["data"]["series"][0]["legendValue"] == [1, 2, 3]     # differs from seed → kept
    assert not gaps


def test_class4_no_default_no_op():
    out = {"data": {"x": [1, 2, 3]}}
    out2, gaps = G.apply(out, [], frozenset(), "tbl")                # no default_payload → CLASS 4 no-op
    assert out2["data"]["x"] == [1, 2, 3] and not gaps


# ── end-to-end through fill() (wiring proof) ─────────────────────────────────────────────────────────────────────────
def _stub_fill_neuract(monkeypatch, present, bkt_by_col=None, latest=None):
    monkeypatch.setattr(nx, "present_columns", lambda t: frozenset(present))
    monkeypatch.setattr(nx, "latest", lambda t, cols: dict(latest or {}))
    monkeypatch.setattr(nx, "window", lambda t, cols, s, e: ({}, {}))
    monkeypatch.setattr(nx, "latest_ts", lambda t: "2026-07-06T00:00:00")
    monkeypatch.setattr(nx, "column_logged", lambda t, c: c in present)

    def _bkt(t, c, s, e, sampling="hourly"):
        return list((bkt_by_col or {}).get(c, []))
    monkeypatch.setattr(nx, "bucketed", _bkt)
    monkeypatch.setattr(F._np, "derive_ratings_for", lambda t: {})
    monkeypatch.setattr(F._np, "get_nameplate", lambda t: {})
    G._ROWS_CACHE.clear()


def test_fill_card56_bypass_tile_honest_blanks_output_tile_fills(monkeypatch):
    # DEFECT 56 end-to-end: 'Average Bypass Voltage' is BOTH in di._honest_blanked (fence a) AND source-role-walled
    # (fence b) → honest blank; the sibling 'Output Voltage' tile fills 234.1 through the same rescue.
    _stub_fill_neuract(monkeypatch, present={"voltage_avg"},
                       bkt_by_col={"voltage_avg": [{"t": "T", "value": 234.1}]})
    payload = {"data": {"metrics": [{"label": "Output Voltage", "unit": "V", "value": None},
                                    {"label": "Average Bypass Voltage", "unit": "V", "value": None}]}}
    di = {"fields": [],
          "_honest_blanked": ["data.metrics[1].value: slot names the bypass source role — this meter has no bypass "
                              "column; leaf honest-blanks"],
          "_emit_gaps": [{"slot": "data.metrics[1].value", "cause": "unbound_by_emit"}]}
    out = F.fill(payload, di, {"asset_table": "gic_01_n3_ups_01_p1", "window": (None, None)})
    m = out["data"]["metrics"]
    assert m[0]["value"] == 234.1                                     # genuine Output Voltage still fills
    assert m[1]["value"] is None                                     # avg-bypass-v NEVER resurrected


def test_fill_card50_output_tiles_still_fill(monkeypatch):
    # CARD 50 through fill(): no honest-blank declared for these leaves → Output V/A fill 234.1 / 268.7.
    _stub_fill_neuract(monkeypatch, present={"voltage_avg", "current_avg"},
                       bkt_by_col={"voltage_avg": [{"t": "T", "value": 234.1}],
                                   "current_avg": [{"t": "T", "value": 268.7}]})
    payload = {"data": {"metrics": [{"label": "Output Voltage", "unit": "V", "value": None},
                                    {"label": "Output Current", "unit": "A", "value": None}]}}
    out = F.fill(payload, {"fields": []}, {"asset_table": "gic_01_n3_ups_01_p1", "window": (None, None)})
    m = out["data"]["metrics"]
    assert m[0]["value"] == 234.1 and m[1]["value"] == 268.7          # the card-50 hard-blank fill preserved


def test_fill_wires_class4_seed_leak(monkeypatch):
    # DEFECT 73 through fill(): a legendValue array that leaked its DATA seed byte-identical and was never filled →
    # blanked by CLASS 4; the sibling series values fill real from a bucketed column and survive. Proves fab_guards
    # receives BOTH the STRIPPED default (default_payload) AND the RAW default (shape_ref) + the written set.
    #
    # REALISTIC raw-vs-stripped defaults [fab_guards root-cause wall]: the strip zeroes DATA leaves to typed
    # placeholders and keeps METADATA verbatim, so for a data leaf like legendValue the STRIPPED default ([]) DIFFERS
    # from the RAW default ([52,71,85,43]) — that raw≠stripped diff is exactly how CLASS 4 knows legendValue is DATA
    # (not chrome). fill() is always called with these two DISTINCT defaults; passing shape_ref==default_payload would
    # be a degenerate fixture (raw==stripped) that mis-reads every data leaf as metadata and never fires the wall.
    _stub_fill_neuract(monkeypatch, present={"p_kw"},
                       bkt_by_col={"p_kw": [{"t": "T0", "value": 10.0}, {"t": "T1", "value": 20.0}]})
    payload  = {"data": {"chart": {"series": [{"legendValue": [52, 71, 85, 43], "values": [0.0, 0.0]}]}}}
    stripped = {"data": {"chart": {"series": [{"legendValue": [],            "values": [0.0, 0.0]}]}}}  # DATA zeroed
    raw      = {"data": {"chart": {"series": [{"legendValue": [52, 71, 85, 43], "values": [0.0, 0.0]}]}}}  # seed kept
    di = {"fields": [{"slot": "chart.series[0].values", "kind": "bucketed", "column": "p_kw", "unit": "kW"}]}
    out = F.fill(payload, di, {"asset_table": "tbl", "window": (None, None)},
                 default_payload=stripped, shape_ref=raw)
    s0 = out["data"]["chart"]["series"][0]
    assert s0["values"] == [10.0, 20.0]                              # real filled series survives
    assert s0["legendValue"] == []                                  # unstripped DATA seed → blanked
    gaps = F.pop_gaps(out) or []
    assert any(g.get("cause") == "unstripped_seed" for g in gaps)
