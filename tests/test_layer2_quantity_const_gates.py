"""EMIT PROPER — the QUANTITY WALL (rule iii) + CONST-SOURCE guard (rule iv) in layer2/gates.enforce_honest_blank,
vocabulary/resolution in layer2/quantity_class (DB rows quantity.* / consts.*, code-default mirrors).

Pins the sweep-#3 defect classes:
  · power bound into a temperature slot (card 76: active_power_total_kw → timeline.points[*].hotspotC),
  · a current-THD column into a voltage-harmonic cell (card 47: thd_current_r_pct → snapshot.h5.valuePct),
  · deviation/spread re-purposed as flicker/crest-factor (card 47),
  · power/energy dressed as readiness/backup-time (cards 52/59),
  · a fabricated numeric const with no real DB source (card 69: 131 A rated line; card 75: 1000 kVA derated),
and the non-negotiable negatives: a SAME-quantity bind, an unclassified slot/column, a $ctx group atom, and a
DB-sourced const (nameplate rating slot-map / app_config consts.* row) are NEVER touched. All non-live, deterministic.
"""
import pytest

from layer2 import quantity_class as qc
from layer2.gates import enforce_honest_blank, gate_data_instructions


@pytest.fixture(autouse=True)
def _pinned_vocab(monkeypatch):
    """Hermetic: pin the vocab + consts rows to the CODE DEFAULTS + a known consts table, so the tests never depend on
    a live cmd_catalog (the DB rows are seeded as exact mirrors of these defaults by db/seed_quantity_class.sql)."""
    monkeypatch.setattr(qc, "_unit_map", lambda: {k.replace(" ", "").lower(): v
                                                  for k, v in qc._UNIT_CLASSES_DEFAULT.items()})
    monkeypatch.setattr(qc, "_name_map", lambda: {k.replace(" ", "").lower(): v
                                                  for k, v in qc._NAME_CLASSES_DEFAULT.items()})
    monkeypatch.setattr(qc, "_weak", lambda: set(qc._WEAK_CLASSES_DEFAULT))
    monkeypatch.setattr(qc, "_const_rows", lambda: {"stressborderpct": ("consts.stress_border_pct", 100.0),
                                                    "hotspotwarnc": ("consts.hotspot_warn_c", 120.0)})
    yield


# ── rule (iii): the QUANTITY WALL ────────────────────────────────────────────────────────────────────────────────────

def test_power_into_hotspot_temperature_slot_is_blanked():
    """Card-76 class: active_power_total_kw bucketed into timeline.points[*].hotspotC — power is NOT a temperature.
    Blanked with the 'X not measured by this meter (no X column)' reason."""
    basket = {"columns": [{"column": "active_power_total_kw", "unit": "kW"}]}
    di = {"fields": [{"slot": "timeline.points[*].hotspotC", "kind": "bucketed",
                      "column": "active_power_total_kw", "metric": "hotspotC", "source": "live"}]}
    blanked = enforce_honest_blank(di, basket)
    assert di["fields"] == []
    assert len(blanked) == 1
    assert "temperature not measured by this meter (no temperature column)" in blanked[0]


def test_thd_current_into_h5_voltage_harmonic_slot_is_blanked():
    """Card-47 class: thd_current_r_pct into snapshot.h5.valuePct — a current-THD column is NOT a voltage-harmonic
    value (sharing '%' does not make them the same quantity: class vocab says h5/h7=voltage-harmonic vs current-thd)."""
    basket = {"columns": [{"column": "thd_current_r_pct", "unit": "%"}]}
    di = {"fields": [{"slot": "snapshot.h5.valuePct", "kind": "raw",
                      "column": "thd_current_r_pct", "metric": "h5.valuePct", "source": "live"}]}
    blanked = enforce_honest_blank(di, basket)
    assert di["fields"] == []
    assert len(blanked) == 1
    assert "voltage-harmonic not measured by this meter" in blanked[0]
    assert "current-thd" in blanked[0]


def test_deviation_spread_never_repurposed_as_flicker_or_crest():
    """Card-47 class: kpi_voltage_deviation_pct → flickerPst and current_max_spread → crestFactor both blank — a
    deviation/spread column is a different physical quantity from waveform flicker/crest."""
    basket = {"columns": [{"column": "kpi_voltage_deviation_pct", "unit": "%"},
                          {"column": "current_max_spread", "unit": "A"}]}
    di = {"fields": [
        {"slot": "snapshot.flickerPst.value", "kind": "raw", "column": "kpi_voltage_deviation_pct", "source": "live"},
        {"slot": "snapshot.crestFactor.value", "kind": "raw", "column": "current_max_spread", "source": "live"},
    ]}
    blanked = enforce_honest_blank(di, basket)
    assert di["fields"] == []
    assert any("flicker not measured" in b for b in blanked)
    assert any("crest-factor not measured" in b for b in blanked)


def test_power_into_readiness_series_is_blanked():
    """Card-59 class: active_power_total_kw bucketed into composite.points[*].readiness — a load series dressed as a
    readiness score."""
    basket = {"columns": [{"column": "active_power_total_kw", "unit": "kW"}]}
    di = {"fields": [{"slot": "composite.points[*].readiness", "kind": "bucketed",
                      "column": "active_power_total_kw", "source": "live"}]}
    blanked = enforce_honest_blank(di, basket)
    assert di["fields"] == [] and "readiness not measured" in blanked[0]


def test_derived_fn_of_wrong_quantity_is_blanked():
    """Card-52 class: fn loadFactorPct into backupReadiness.score / fn todaysEnergyTotalKwh into a backup-time cell —
    a derived fn's quantity must match the slot's too."""
    basket = {"columns": [{"column": "active_power_total_kw", "unit": "kW"},
                          {"column": "active_energy_import_kwh", "unit": "kWh"}]}
    di = {"fields": [
        {"slot": "backupReadiness.score", "kind": "derived", "fn": "loadFactorPct",
         "base_columns": ["active_power_total_kw"], "metric": "score", "source": "live"},
        {"slot": "duty.points[*].runHours", "kind": "derived", "fn": "todaysEnergyTotalKwh",
         "base_columns": ["active_energy_import_kwh"], "metric": "run_hours", "source": "live"},
    ]}
    blanked = enforce_honest_blank(di, basket)
    assert di["fields"] == []
    assert any("readiness not measured" in b for b in blanked)
    assert any("duration not measured" in b for b in blanked)


def test_matching_quantity_bind_is_untouched():
    """voltage_avg into a voltage slot (same quantity) survives — never a false positive."""
    basket = {"columns": [{"column": "voltage_avg", "unit": "V"}]}
    di = {"fields": [{"slot": "voltage.phases[0].value", "kind": "raw",
                      "column": "voltage_avg", "metric": "voltage", "source": "live"}]}
    assert enforce_honest_blank(di, basket) == []
    assert [f["slot"] for f in di["fields"]] == ["voltage.phases[0].value"]


def test_unclassified_slot_or_column_never_flags():
    """A generic container slot (chart.series[0].values) and an unclassifiable column never flag — None on either
    side means 'don't know', not 'mismatch'. A load/score container word is deliberately NOT in the vocab
    (load.scoreCells[2].value ← power_factor_total is a legitimate PF cell)."""
    basket = {"columns": [{"column": "active_power_total_kw", "unit": "kW"},
                          {"column": "power_factor_total", "unit": ""}]}
    di = {"fields": [
        {"slot": "chart.series[0].values", "kind": "bucketed", "column": "active_power_total_kw", "source": "live"},
        {"slot": "load.scoreCells[2].value", "kind": "raw", "column": "power_factor_total", "source": "live"},
    ]}
    assert enforce_honest_blank(di, basket) == []
    assert len(di["fields"]) == 2


def test_weak_percent_class_never_blanks_on_dimension_alone():
    """A column classified only by its '%' unit (name tokens unknown) is dimension-only ('percent' = weak class) —
    cautious keep even under a classified slot."""
    basket = {"columns": [{"column": "kpi_neutral_to_phase_ratio_pct", "unit": "%"}]}
    di = {"fields": [{"slot": "current.unbalancePct", "kind": "raw",
                      "column": "kpi_neutral_to_phase_ratio_pct", "source": "live"}]}
    assert enforce_honest_blank(di, basket) == []


def test_group_ctx_atom_no_longer_bypasses_quantity_wall():
    """DEFECT G closure [pages 15/16/17]: a $ctx atom binding a POWER buffer key into a temperature slot is just as
    fabricated as a live bind — the wall now flags it on group cards too. A structural $ctx atom with no quantity
    class on either side (a group-context projection / time atom) stays exempt by construction."""
    di = {"fields": [{"slot": "timeline.points[*].hotspotC", "kind": "bucketed",
                      "column": "kw", "source": "$ctx"}]}
    blanked = enforce_honest_blank(di, {"columns": []}, is_group_card=True)
    assert di["fields"] == []
    assert len(blanked) == 1 and "temperature not measured by this meter" in blanked[0]
    # structural $ctx uses keep working: kind=time atoms and unclassified buffer projections never flag
    di2 = {"fields": [
        {"slot": "chart.xLabelIndexes", "kind": "time", "source": "live", "role": "series"},
        {"slot": "rail.items[0].value", "kind": "raw", "column": "kw", "metric": "kw", "source": "$ctx"},
    ]}
    assert enforce_honest_blank(di2, {"columns": []}, is_group_card=True) == []
    assert len(di2["fields"]) == 2


# ── rule (iv): the CONST-SOURCE guard ────────────────────────────────────────────────────────────────────────────────

def test_const_131_with_no_real_source_is_blanked():
    """Card-69 class: const 131 stamped metric=I_RATED (not a nameplate slot-map name, no consts.* row) — a guessed
    rated current with the asset nameplate unknown/None. Blanked; same for the derated 1000 kVA and the 131-tick axis."""
    basket = {"columns": [{"column": "current_avg", "unit": "A"}]}
    di = {"fields": [
        {"slot": "data.maxLine.value", "kind": "const", "value": 131, "metric": "I_RATED", "source": "const"},
        {"slot": "lifeCapacity.deratedKva", "kind": "const", "value": 1000.0, "metric": "deratedKva", "source": "const"},
        {"slot": "data.yTicks", "kind": "const", "value": [0, 30, 60, 90, 120, 131], "metric": None, "source": "const"},
    ]}
    blanked = enforce_honest_blank(di, basket)
    assert di["fields"] == []
    assert len(blanked) == 3
    assert all("no real DB source" in b for b in blanked)


def test_const_from_real_app_config_row_is_kept():
    """A const citing a consts.* row by metric WITH the row's own value passes (stress_border_pct=100,
    hotspot_warn_c=120 — camelCase metric spelling normalizes to the row name)."""
    basket = {"columns": [{"column": "active_power_total_kw", "unit": "kW"}]}
    di = {"fields": [
        {"slot": "thermalLife.stressBorderPct", "kind": "const", "value": 100, "metric": "stress_border_pct",
         "source": "const"},
        {"slot": "timeline.hotspotWarnC", "kind": "const", "value": 120.0, "metric": "hotspotWarnC", "source": "const"},
    ]}
    assert enforce_honest_blank(di, basket) == []
    assert len(di["fields"]) == 2


def test_const_citing_row_with_wrong_value_is_blanked():
    """Citing a real row but shipping a DIFFERENT number is not sourcing — the value must BE the row's."""
    di = {"fields": [{"slot": "thermalLife.stressBorderPct", "kind": "const", "value": 95,
                      "metric": "stress_border_pct", "source": "const"}]}
    blanked = enforce_honest_blank(di, {"columns": []})
    assert di["fields"] == [] and "no real DB source" in blanked[0]


def test_const_nameplate_rating_kept_unless_rating_known_empty():
    """A const whose metric IS a nameplate slot-map rating name rides the executor's real-nameplate substitution
    (kept — the baked value is only a shape placeholder), UNLESS the basket says the rating is KNOWN-empty for this
    asset (rated_present=False) → blanked now ('const 131 with nameplate None')."""
    fld = {"slot": "data.maxLine.value", "kind": "const", "value": 131, "metric": "rated_current_a",
           "source": "const"}
    cols = [{"column": "current_avg", "unit": "A"}]
    kept = {"columns": cols, "nameplate": {"rated_present": True}}
    assert enforce_honest_blank({"fields": [dict(fld)]}, kept) == []
    unknown = {"columns": cols}                                   # no nameplate info → executor substitutes/blanks
    assert enforce_honest_blank({"fields": [dict(fld)]}, unknown) == []
    empty = {"columns": cols, "nameplate": {"rated_present": False}}
    di = {"fields": [dict(fld)]}
    blanked = enforce_honest_blank(di, empty)
    assert di["fields"] == [] and "nameplate rating is empty" in blanked[0]


def test_non_numeric_and_valueless_consts_left_to_other_gates():
    """A string const (status text) and a valueless const are NOT this guard's business (text chrome / the existing
    'const without a value' gate)."""
    basket = {"columns": []}
    di = {"fields": [
        {"slot": "status.text", "kind": "const", "value": "Live Health", "source": "const"},
        {"slot": "broken.const", "kind": "const", "value": None, "source": "const"},
    ]}
    assert enforce_honest_blank(di, basket) == []
    assert len(di["fields"]) == 2
    ok, issues = gate_data_instructions(di, basket)
    assert not ok and any("const without a value" in i for i in issues)


# ── wired path: telemetry, never a card-blocking gate ────────────────────────────────────────────────────────────────

def test_wired_gate_self_heals_quantity_and_const_as_telemetry():
    """gate_data_instructions runs both new rules in the honest-blank pre-pass: the cross-quantity bind and the
    sourceless const are dropped IN PLACE (per-leaf degradation, telemetry via return), the matching-quantity field
    survives, and the card does NOT fail the gate."""
    basket = {"columns": [{"column": "active_power_total_kw", "unit": "kW"},
                          {"column": "voltage_avg", "unit": "V"}]}
    di = {"fields": [
        {"slot": "timeline.points[*].hotspotC", "kind": "bucketed", "column": "active_power_total_kw",
         "metric": "hotspotC", "source": "live"},
        {"slot": "data.maxLine.value", "kind": "const", "value": 131, "metric": "I_RATED", "source": "const"},
        {"slot": "voltage.phases[0].value", "kind": "raw", "column": "voltage_avg", "metric": "v", "source": "live"},
    ]}
    ok, issues = gate_data_instructions(di, basket)
    assert ok and not issues
    assert [f["slot"] for f in di["fields"]] == ["voltage.phases[0].value"]
    hb = di.get("_honest_blanked") or []
    assert len(hb) == 2
    assert any("temperature not measured" in b for b in hb)
    assert any("no real DB source" in b for b in hb)
