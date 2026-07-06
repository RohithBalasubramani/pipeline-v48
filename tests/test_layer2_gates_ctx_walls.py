"""GATES BYPASS CLOSURE [DEFECT G — fullsweep_20260706_004334]: the quantity-mismatch (iii), const-source (iv) and
reuse/smear (ii) walls no longer skip fields with source='$ctx', and enforce_honest_blank no longer short-circuits on
is_group_card — 19 G-family cards fabricated through those doors (power as °C/years/aging/readiness/scores, PF as
K-factor, register as Level/Rate/Temp, negative power as battery scores).

Every case below is the EXACT field shape served in the evidence bundle
(outputs/fullsweep_20260706_004334/pages/v18_15b|16|17.json + v18_08), replayed through the extended gate:
cross-quantity binds BLANK, legit binds KEEP, structural $ctx uses (time atoms, unclassified buffer projections)
stay untouched. Hermetic (vocab pinned to the code defaults — the DB rows are seeded as exact mirrors by
db/seed_quantity_class.sql). All non-live, deterministic."""
import pytest

from layer2 import quantity_class as qc
from layer2.gates import enforce_honest_blank


@pytest.fixture(autouse=True)
def _pinned_vocab(monkeypatch):
    monkeypatch.setattr(qc, "_unit_map", lambda: {k.replace(" ", "").lower(): v
                                                  for k, v in qc._UNIT_CLASSES_DEFAULT.items()})
    monkeypatch.setattr(qc, "_name_map", lambda: {k.replace(" ", "").lower(): v
                                                  for k, v in qc._NAME_CLASSES_DEFAULT.items()})
    monkeypatch.setattr(qc, "_weak", lambda: set(qc._WEAK_CLASSES_DEFAULT))
    monkeypatch.setattr(qc, "_const_rows", lambda: {})
    yield


_UPS_BASKET = {"columns": [{"column": "active_power_total_kw", "unit": "kW"},
                           {"column": "apparent_power_total_kva", "unit": "kVA"},
                           {"column": "voltage_avg", "unit": "V"},
                           {"column": "current_avg", "unit": "A"},
                           {"column": "frequency_hz", "unit": "Hz"},
                           {"column": "power_factor_total", "unit": ""}]}


# ── page 15 (v18_15b) — transformer thermal life, all 4 cards were $ctx-doored fabrications ─────────────────────────

def test_c75_life_years_from_load_factor_blank_but_derated_kva_keeps():
    """c75: lifeRemainingYears/lifeFillPct ← fn loadFactorPct ('95 YEARS remaining') blank via the quantity wall;
    the REAL deratedLoadKva ← apparent_power_total_kva (worklog: '974.25 real') KEEPS."""
    di = {"fields": [
        {"slot": "lifeCapacity.deratedLoadKva", "kind": "raw", "source": "$ctx",
         "column": "apparent_power_total_kva", "metric": "deratedLoadKva", "unit": "kVA"},
        {"slot": "lifeCapacity.lifeFillPct", "kind": "derived", "source": "$ctx", "fn": "loadFactorPct",
         "metric": "lifeFillPct", "unit": "%"},
        {"slot": "lifeCapacity.lifeRemainingYears", "kind": "derived", "source": "$ctx", "fn": "loadFactorPct",
         "metric": "lifeRemainingYears", "unit": "years"},
    ]}
    blanked = enforce_honest_blank(di, _UPS_BASKET, is_group_card=True)
    assert [f["slot"] for f in di["fields"]] == ["lifeCapacity.deratedLoadKva"]
    assert any("lifetime not measured" in b for b in blanked)


def test_c75_const_life_base_years_without_db_source_blanks():
    """c75: lifeBaseYears const 20.0 (unit years) — a numeric literal with NO nameplate slot / consts.* row is the
    131A/1000kVA class, now policed on group cards too."""
    di = {"fields": [{"slot": "lifeCapacity.lifeBaseYears", "kind": "const", "source": "const",
                      "metric": "lifeBaseYears", "unit": "years", "value": 20.0}]}
    blanked = enforce_honest_blank(di, _UPS_BASKET, is_group_card=True)
    assert di["fields"] == [] and "no real DB source" in blanked[0]


def test_c76_negative_power_dumped_into_loadpct_efficiency_and_time_slot_blanks():
    """c76: raw NEGATIVE active_power_total_kw bucketed into points[*].loadPct / efficiencyPct / slot (the time
    label) — all three now blank (loadpct→load-factor, efficiency, slot→timestamp vocab), the $ctx door closed."""
    di = {"fields": [
        {"slot": "timeline.points[*].slot", "kind": "bucketed", "source": "$ctx",
         "column": "active_power_total_kw", "metric": "slot", "unit": ""},
        {"slot": "timeline.points[*].loadPct", "kind": "bucketed", "source": "$ctx",
         "column": "active_power_total_kw", "metric": "loadPct", "unit": "%"},
        {"slot": "timeline.points[*].efficiencyPct", "kind": "bucketed", "source": "$ctx",
         "column": "active_power_total_kw", "metric": "efficiencyPct", "unit": "%"},
    ]}
    blanked = enforce_honest_blank(di, _UPS_BASKET, is_group_card=True)
    assert di["fields"] == []
    assert len(blanked) == 3


def test_c77_aging_factor_smear_blanks_but_time_atom_and_unclassified_fn_keep():
    """c77: agingFactor/deltaLolPct/legend ← fn loadFactorPct ('aging ×' = 95) blank (aging-factor ≠ load-factor);
    the kind=time label atom and the UNCLASSIFIED progressActivePct binds keep (structural / unknown = compatible)."""
    di = {"fields": [
        {"slot": "aging.points[*].label", "kind": "time", "source": "live", "role": "series"},
        {"slot": "aging.kpis.lifeUsedPct", "kind": "derived", "fn": "progressActivePct",
         "base_columns": ["active_power_total_kw"], "metric": "lifeUsedPct", "source": "live"},
        {"slot": "aging.kpis.agingFactor", "kind": "derived", "fn": "loadFactorPct",
         "base_columns": ["active_power_total_kw"], "metric": "agingFactor", "source": "live"},
        {"slot": "aging.points[*].faa", "kind": "bucketed", "source": "live",
         "column": "active_power_total_kw", "metric": "active_power_total_kw", "unit": "x"},
    ]}
    blanked = enforce_honest_blank(di, _UPS_BASKET, is_group_card=True)
    kept = [f["slot"] for f in di["fields"]]
    assert "aging.points[*].label" in kept                     # time atom untouched
    assert "aging.kpis.lifeUsedPct" in kept                    # unclassified fn → compatible (no false positive)
    assert "aging.kpis.agingFactor" not in kept                # aging-factor ← load-factor fn = fabrication
    assert "aging.points[*].faa" not in kept                   # aging-factor ← raw power = fabrication
    assert any("aging-factor not measured" in b for b in blanked)


# ── page 16 (v18_16) — UPS battery: raw power/voltage as 'score' series (unit fallback) ────────────────────────────

def test_c51_c53_power_as_battery_scores_blank_via_unit_fallback():
    """c51/c53: batteryHistory/backupHistory series with unit='score' bound to raw active_power_total_kw /
    voltage_avg — the slot path is unclassified, so the field's OWN declared unit ('score' → score-index)
    establishes the wall; every power/voltage-as-score bind blanks, the time atom keeps."""
    di = {"fields": [
        {"slot": "batteryHistory.series[0].values", "kind": "bucketed", "source": "live",
         "column": "active_power_total_kw", "metric": "overall", "unit": "score"},
        {"slot": "batteryHistory.series[2].values", "kind": "bucketed", "source": "live",
         "column": "voltage_avg", "metric": "busScore", "unit": "score"},
        {"slot": "batteryHistory.maxY", "kind": "raw", "source": "live",
         "column": "active_power_total_kw", "metric": "maxY", "unit": "score"},
        {"slot": "backupHistory.series[0].values", "kind": "bucketed", "source": "live",
         "column": "active_power_total_kw", "metric": "backup-readiness-score", "unit": "score"},
        {"slot": "backupHistory.xLabelIndexes", "kind": "time", "source": "live", "role": "series"},
    ]}
    blanked = enforce_honest_blank(di, _UPS_BASKET)
    assert [f["slot"] for f in di["fields"]] == ["backupHistory.xLabelIndexes"]
    assert len(blanked) == 4
    assert all("score-index not measured" in b for b in blanked)


def test_c50_real_voltage_current_cells_keep():
    """c50 negatives: the REAL Output Voltage/Current cells (worklog: '238.56V + 245A REAL') keep; the frame-sourced
    socPct projection (no column) keeps for the executor's own honest-degrade."""
    di = {"fields": [
        {"slot": "batteryHealth.socPct", "kind": "raw", "source": "frame", "metric": "socPct", "unit": "%"},
        {"slot": "batteryHealth.metrics[1].value", "kind": "raw", "source": "live",
         "column": "voltage_avg", "metric": "voltage", "unit": "V"},
        {"slot": "batteryHealth.metrics[2].value", "kind": "raw", "source": "live",
         "column": "current_avg", "metric": "current", "unit": "A"},
    ]}
    assert enforce_honest_blank(di, _UPS_BASKET) == []
    assert len(di["fields"]) == 3


# ── page 17 (v18_17) — UPS output/load: score smears blank, real kW/PF/load-factor keep ─────────────────────────────

def test_c57_score_cell_smear_blanks():
    """c57: KVA/KW score BOTH ← kpiKwLoadPctOfRated, Current score + capacityHeadroom BOTH ← loadFactorPct — the
    reuse wall + the score-index//100 unit + the headroom vocab blank all four ($ctx door closed)."""
    di = {"fields": [
        {"slot": "capacity.scoreCells[0].value", "kind": "derived", "source": "$ctx", "fn": "kpiKwLoadPctOfRated",
         "metric": "ups_capacity_kva_score", "unit": "/100"},
        {"slot": "capacity.scoreCells[1].value", "kind": "derived", "source": "$ctx", "fn": "kpiKwLoadPctOfRated",
         "metric": "ups_capacity_kw_score", "unit": "/100"},
        {"slot": "capacity.scoreCells[2].value", "kind": "derived", "source": "$ctx", "fn": "loadFactorPct",
         "metric": "ups_capacity_current_score", "unit": "/100"},
        {"slot": "capacity.capacityHeadroom", "kind": "derived", "source": "$ctx", "fn": "loadFactorPct",
         "metric": "ups_capacity_headroom_score", "unit": "%"},
    ]}
    blanked = enforce_honest_blank(di, _UPS_BASKET, is_group_card=True)
    assert di["fields"] == []
    assert len(blanked) == 4


def test_c58_neg_power_sparkline_blanks_but_real_kw_pf_and_loadfactor_keep():
    """c58: the sparkline loadPct ← RAW active_power_total_kw (-195..-198 as 'load %') blanks; the REAL Load kW cell,
    the REAL PF cell (power_factor_total) and the LEGIT averageLoadPct ← loadFactorPct (same quantity) all keep."""
    di = {"fields": [
        {"slot": "load.sparkline[*].loadPct", "kind": "bucketed", "source": "$ctx",
         "column": "active_power_total_kw", "metric": "loadPct", "unit": "%"},
        {"slot": "load.scoreCells[0].value", "kind": "raw", "source": "$ctx",
         "column": "active_power_total_kw", "metric": "active_power_total_kw", "unit": "kW"},
        {"slot": "load.scoreCells[2].value", "kind": "raw", "source": "$ctx",
         "column": "power_factor_total", "metric": "power_factor_total", "unit": ""},
        {"slot": "load.averageLoadPct", "kind": "derived", "source": "$ctx", "fn": "loadFactorPct",
         "metric": "loadPct"},
    ]}
    blanked = enforce_honest_blank(di, _UPS_BASKET, is_group_card=True)
    kept = [f["slot"] for f in di["fields"]]
    assert kept == ["load.scoreCells[0].value", "load.scoreCells[2].value", "load.averageLoadPct"]
    assert len(blanked) == 1 and "load-factor not measured" in blanked[0]


def test_c59_input_series_kpi_and_time_atom_keep():
    """c59 POSITIVES: the meter's REAL input/line readings keep — inputCurrentA ← current_avg, inputVoltageV ←
    voltage_avg (input is a NON-dedicated role: the plain meter reading legitimately fills an input* slot), the
    kpi ← voltage_avg, the frame-ts label (no column) and the kind=time axis atom. Nothing here is a role smear."""
    di = {"fields": [
        {"slot": "composite.points[*].label", "kind": "bucketed", "source": "frame", "metric": "ts", "unit": ""},
        {"slot": "composite.points[*].inputCurrentA", "kind": "bucketed", "source": "live",
         "column": "current_avg", "metric": "current_avg", "unit": "A"},
        {"slot": "composite.points[*].inputVoltageV", "kind": "bucketed", "source": "live",
         "column": "voltage_avg", "metric": "voltage_avg", "unit": "V"},
        {"slot": "composite.points[*].inputFrequencyHz", "kind": "bucketed", "source": "live",
         "column": "frequency_hz", "metric": "frequency_hz", "unit": "Hz"},
        {"slot": "composite.kpiCells[0].value", "kind": "raw", "source": "live",
         "column": "voltage_avg", "metric": "voltage_avg", "unit": "V"},
        {"slot": "composite.leftAxis.ticks", "kind": "time", "source": "live", "role": "series"},
    ]}
    assert enforce_honest_blank(di, _UPS_BASKET) == []
    assert len(di["fields"]) == 6


def test_c59_bypass_role_smear_and_power_time_label_blank():
    """c59 DEFECT (Family G same-quantity, different-role): bypassVoltageV ← voltage_avg and bypassFrequencyHz ←
    frequency_hz present the INPUT/line reading AS the bypass reading — the gic_* UPS meter has NO bypass column
    (verified against information_schema), so both HONEST-BLANK via the source-role wall while the same-column
    inputVoltageV KEEPS. Secondary: composite.points[*].label ← active_power_total_kw (negative kW rendered as
    x-axis TIME labels) blanks via the time-axis-label wall — a series time label fills from bucket timestamps."""
    di = {"fields": [
        {"slot": "composite.points[*].label", "kind": "bucketed", "source": "live",
         "column": "active_power_total_kw", "metric": "active_power_total_kw", "unit": "kW"},
        {"slot": "composite.points[*].inputVoltageV", "kind": "bucketed", "source": "live",
         "column": "voltage_avg", "metric": "voltage_avg", "unit": "V"},
        {"slot": "composite.points[*].bypassVoltageV", "kind": "bucketed", "source": "live",
         "column": "voltage_avg", "metric": "voltage_avg", "unit": "V"},
        {"slot": "composite.points[*].bypassFrequencyHz", "kind": "bucketed", "source": "live",
         "column": "frequency_hz", "metric": "frequency_hz", "unit": "Hz"},
    ]}
    blanked = enforce_honest_blank(di, _UPS_BASKET)
    kept = [f["slot"] for f in di["fields"]]
    assert kept == ["composite.points[*].inputVoltageV"]        # the real input reading KEEPS
    assert any("bypassVoltageV" in b and "bypass source role" in b for b in blanked)
    assert any("bypassFrequencyHz" in b and "bypass source role" in b for b in blanked)
    assert any("points[*].label" in b and "time-axis label" in b for b in blanked)
    assert len(blanked) == 3


# ── page 08 (v18_08, DEFECT D/G) — % fn shipped as kW tiles on a $ctx group page ────────────────────────────────────

def test_c40_load_factor_fn_as_kw_tiles_blanks_on_group_page():
    """c40: activePowerAvgKw AND reactivePowerAvgKw ← fn loadFactorPct (a PERCENT shipped as kW tiles, real avgs
    ≈195/9.6) — the worklog's own replay note ('gate rule (iii) replay flags exactly this — bypassed') now holds in
    the wired gate: $ctx + group no longer bypass."""
    di = {"fields": [
        {"slot": "power.activePowerAvgKw", "kind": "derived", "source": "$ctx", "fn": "loadFactorPct",
         "metric": "activePowerAvgKw", "unit": "kW"},
        {"slot": "power.reactivePowerAvgKw", "kind": "derived", "source": "$ctx", "fn": "loadFactorPct",
         "metric": "reactivePowerAvgKw", "unit": "kW"},
    ]}
    blanked = enforce_honest_blank(di, _UPS_BASKET, is_group_card=True)
    assert di["fields"] == []
    assert len(blanked) == 2                                   # one via the reuse wall, one via the quantity wall
    assert any("power not measured" in b for b in blanked)


def test_c38_ctx_const_thresholds_blank():
    """c38 [DEFECT B]: emit-authored const thresholds 120/100 A against a ~300 A live load, $ctx-stamped on a group
    page — the const-source wall now runs there too (was: 'enforce_honest_blank returns [] when is_group_card')."""
    di = {"fields": [
        {"slot": "data.thresholds[0].value", "kind": "const", "source": "$ctx", "value": 120,
         "metric": "current_threshold_max", "unit": "A"},
        {"slot": "data.thresholds[1].value", "kind": "const", "source": "$ctx", "value": 100,
         "metric": "current_threshold_min", "unit": "A"},
    ]}
    blanked = enforce_honest_blank(di, _UPS_BASKET, is_group_card=True)
    assert di["fields"] == []
    assert all("no real DB source" in b for b in blanked)
