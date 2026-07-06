"""WALL PRECISION REWORK [corpus-replay baseline outputs/wall_replay_baseline.json — 2,073 FP suspects triaged].

Pins the RULE-level precision fixes (layer2/gates.py + layer2/quantity_class.py + quantity.* config rows) and, in the
same breath, the fabrication catches that MUST keep firing (the acceptance spot-checks):

  RELEASES (was a false positive, now keeps):
    · rule (i) derived: a fn with PARTIAL measured basis keeps (card-72 family — activeEnergyTodayKwh declaring
      import+export on an import-only meter; the executor computes real-or-None from its canonical binding);
    · rule (ii): a same-quantity annotation re-bind (maxY + maxLine.value + label ← current_max) is ONE measurement
      rendered in several places, never the smear;
    · rule (iii): lolPct ← loss_of_life_pct (the 'aging.' ancestor-bleed FP — both sides now classify lifetime);
      an amps-dimensioned spread stat into an 'A' metrics cell (ordered compatible pair current ← deviation-spread);
    · rule (iii-b): maxY ← current_max / minY ← current_min / demandYMax ← worstPeakKw / both bounds ← a domain/band
      fn — a REAL measured extremum/range of the series' own quantity is not a 'live sample' axis fabrication;
    · rule (iv): structural display consts (decimals / selectedSampleIndex / areaOpacity / layout / windowDays) state
      no measurement; a scalar citing one element of a LIST consts.* row resolves.

  STILL FIRES (the fabrication classes, unchanged):
    power→hotspotC · the 131 A sourceless const · thd_current→h5 · loadFactor→readiness · hvInputKw boundary proxy ·
    expectedLoad ← direct read · degenerate axis reads (yMax=yMin ← instantaneous kW; minY ← worstPeakKw) ·
    maxDeviation ← voltageStatutoryBand (reverse of the ordered pair NOT granted) · derived fn with NO measured basis.

Hermetic (vocab pinned to the code defaults — the DB rows are exact mirrors via db/seed_quantity_class.sql)."""
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
    monkeypatch.setattr(qc, "_compatible_pairs", lambda: {(a, b) for a, b in
                                                          qc._COMPATIBLE_SLOT_SOURCE_PAIRS_DEFAULT})
    monkeypatch.setattr(qc, "_structural_const_tokens", lambda: set(qc._STRUCTURAL_CONST_TOKENS_DEFAULT))
    monkeypatch.setattr(qc, "_const_rows", lambda: {"voltageband": ("consts.voltage_band", [410.0, 430.0])})
    yield


# ── rule (i) derived: PARTIAL measured basis keeps; NO basis still blanks ───────────────────────────────────────────

def test_derived_partial_basis_keeps_card72_family():
    """activeEnergyTodayKwh declares import+export; the meter logs only import — the executor honest-degrades
    per-input (real delta from the import counter), so the gate keeps the bind. Corpus: ~300 fn-membership FPs."""
    basket = {"columns": [{"column": "active_energy_import_kwh"}]}
    di = {"fields": [{"slot": "energyReliability.activeMwh", "kind": "derived", "fn": "activeEnergyTodayKwh",
                      "base_columns": ["active_energy_import_kwh", "active_energy_export_kwh"],
                      "metric": "active_mwh", "source": "live"}]}
    assert enforce_honest_blank(di, basket) == []
    assert len(di["fields"]) == 1


def test_derived_no_measured_basis_still_blanks():
    """A fn whose EVERY declared base is absent has no basis on this asset — hallucinated bind, still blanks."""
    basket = {"columns": [{"column": "active_power_total_kw"}]}
    di = {"fields": [{"slot": "history.stats[0].value", "kind": "derived", "fn": "voltageHistoryDomain",
                      "base_columns": ["voltage_avg", "voltage_r_n"], "metric": "v_domain", "source": "live"}]}
    blanked = enforce_honest_blank(di, basket)
    assert di["fields"] == [] and "not measured on this asset" in blanked[0]


# ── rule (ii): same-quantity annotation re-binds keep; classified cross-quantity cells land on wall (iii) ───────────

def test_same_quantity_annotation_rebind_keeps():
    """card 46: maxY (axis) + maxLine.value + maxLine.label.value + stats cell ← current_max beside a real current
    series — ONE measured window-max rendered in several places. Corpus: the single biggest reuse-FP family."""
    basket = {"columns": [{"column": "current_r", "unit": "A"}, {"column": "current_max", "unit": "A"},
                          {"column": "current_min", "unit": "A"}]}
    di = {"fields": [
        {"slot": "history.data.series[0].values", "kind": "bucketed", "column": "current_r",
         "metric": "current_r", "source": "live"},
        {"slot": "history.data.maxY", "kind": "raw", "column": "current_max", "metric": "current_max",
         "source": "live"},
        {"slot": "history.data.minY", "kind": "raw", "column": "current_min", "metric": "current_min",
         "source": "live"},
        {"slot": "history.data.maxLine.value", "kind": "raw", "column": "current_max", "metric": "max_line",
         "source": "live"},
        {"slot": "history.data.maxLine.label.value", "kind": "raw", "column": "current_max", "metric": "max_label",
         "source": "live"},
    ]}
    assert enforce_honest_blank(di, basket) == []
    assert len(di["fields"]) == 5


# ── rule (iii): vocabulary + ordered-pair precision ─────────────────────────────────────────────────────────────────

def test_lolpct_from_loss_of_life_column_keeps_but_power_still_blanks():
    """aging.points[*].lolPct ← loss_of_life_pct is the exactly-right bind (both sides lifetime — the 'aging.'
    ancestor no longer bleeds); the same slot ← active_power_total_kw stays a catch."""
    basket = {"columns": [{"column": "loss_of_life_pct", "unit": "%"},
                          {"column": "active_power_total_kw", "unit": "kW"}]}
    di = {"fields": [
        {"slot": "aging.points[*].lolPct", "kind": "bucketed", "column": "loss_of_life_pct",
         "metric": "loss_of_life_pct", "source": "live"},
        {"slot": "aging.legend[0].value", "kind": "raw", "column": "active_power_total_kw",
         "metric": "lolPct", "source": "live"},
    ]}
    blanked = enforce_honest_blank(di, basket)
    assert [f["slot"] for f in di["fields"]] == ["aging.points[*].lolPct"]
    assert len(blanked) == 1 and "power" in blanked[0]


def test_spread_stat_into_amps_cell_keeps_but_reverse_and_crest_still_blank():
    """Ordered pair (current ← deviation-spread): the card-46 'Max Spread (A)' metrics cell ← current_max_spread is a
    REAL amps-dimensioned spread stat. NOT granted in reverse (maxDeviation ← voltageStatutoryBand still blanks) and
    never for crest-factor ← spread (the card-47 catch)."""
    basket = {"columns": [{"column": "current_max_spread", "unit": "A"},
                          {"column": "kpi_voltage_deviation_pct", "unit": "%"}]}
    di = {"fields": [
        {"slot": "health.data.metrics[1].value", "kind": "raw", "column": "current_max_spread",
         "metric": "current_max_spread", "unit": "A", "source": "live"},
        {"slot": "history.maxDeviation", "kind": "derived", "fn": "voltageStatutoryBand",
         "base_columns": ["kpi_voltage_deviation_pct"], "metric": "maxDeviation", "source": "live"},
        {"slot": "snapshot.crestFactor.value", "kind": "raw", "column": "current_max_spread",
         "metric": "crestFactor", "source": "live"},
    ]}
    blanked = enforce_honest_blank(di, basket)
    assert [f["slot"] for f in di["fields"]] == ["health.data.metrics[1].value"]
    assert any("deviation-spread not measured" in b for b in blanked)      # maxDeviation ← band fn (reverse) blanks
    assert any("crest-factor not measured" in b for b in blanked)


def test_named_fabrications_still_fire():
    """The acceptance spot-checks: power→hotspotC, thd_current→h5, loadFactor→readiness all still blank."""
    basket = {"columns": [{"column": "active_power_total_kw", "unit": "kW"},
                          {"column": "thd_current_r_pct", "unit": "%"}]}
    di = {"fields": [
        {"slot": "timeline.points[*].hotspotC", "kind": "bucketed", "column": "active_power_total_kw",
         "metric": "hotspotC", "source": "live"},
        {"slot": "snapshot.h5.valuePct", "kind": "raw", "column": "thd_current_r_pct", "metric": "h5",
         "source": "live"},
        {"slot": "backupReadiness.score", "kind": "derived", "fn": "loadFactorPct",
         "base_columns": ["active_power_total_kw"], "metric": "readiness", "source": "live"},
    ]}
    blanked = enforce_honest_blank(di, basket)
    assert di["fields"] == []
    assert any("temperature not measured" in b for b in blanked)
    assert any("voltage-harmonic not measured" in b for b in blanked)
    assert any("readiness not measured" in b for b in blanked)


# ── rule (iii-b): directional axis sources keep; sample/degenerate reads still blank ───────────────────────────────

_SERIES = {"slot": "data.series[0].values", "kind": "bucketed", "column": "active_power_total_kw",
           "metric": "kw_series", "source": "live"}
_PWR_BASKET = {"columns": [{"column": "active_power_total_kw", "unit": "kW"},
                           {"column": "voltage_avg", "unit": "V"}]}


def test_axis_directional_extremum_sources_keep():
    """demandYMax ← fn worstPeakKw (a real windowed peak) and both bounds ← a domain fn keep beside the series."""
    di = {"fields": [
        dict(_SERIES),
        {"slot": "data.demandYMax", "kind": "derived", "fn": "worstPeakKw",
         "base_columns": ["active_power_total_kw"], "metric": "demandYMax", "source": "live"},
    ]}
    assert enforce_honest_blank(di, _PWR_BASKET) == []
    assert len(di["fields"]) == 2


def test_axis_sample_and_degenerate_reads_still_blank():
    """yMax AND yMin ← the instantaneous kW column (card-40-round-2 zero-range axis) still blank — the source name
    carries no extremum/range token; likewise minY ← worstPeakKw (a PEAK is never a floor)."""
    di = {"fields": [
        dict(_SERIES),
        {"slot": "data.yMax", "kind": "raw", "column": "active_power_total_kw", "metric": "yMax", "source": "live"},
        {"slot": "data.yMin", "kind": "raw", "column": "active_power_total_kw", "metric": "yMin", "source": "live"},
        {"slot": "data.demandYMin", "kind": "derived", "fn": "worstPeakKw",
         "base_columns": ["active_power_total_kw"], "metric": "demandYMin", "source": "live"},
    ]}
    blanked = enforce_honest_blank(di, _PWR_BASKET)
    assert [f["slot"] for f in di["fields"]] == ["data.series[0].values"]
    assert len(blanked) == 3 and all("axis" in b for b in blanked)


def test_axis_cross_quantity_source_still_blanks():
    """maxY ← voltage_avg under a POWER series is still the cross-quantity axis fabrication (card-40-round-1)."""
    di = {"fields": [
        dict(_SERIES),
        {"slot": "data.maxY", "kind": "raw", "column": "voltage_avg", "metric": "maxY", "source": "live"},
    ]}
    blanked = enforce_honest_blank(di, _PWR_BASKET)
    assert [f["slot"] for f in di["fields"]] == ["data.series[0].values"]
    assert len(blanked) == 1 and "while this card's series measure" in blanked[0]


# ── rule (iv): structural consts + list-row citation; the 131 A class still fires ───────────────────────────────────

def test_structural_display_consts_keep():
    """decimals / selectedSampleIndex / areaOpacity / layout / windowDays state NO measurement — kept (corpus: ~450
    broken-chrome FPs); a quantity-named const (0.0 kW) beside them still blanks."""
    di = {"fields": [
        {"slot": "gauge.decimals", "kind": "const", "value": 0, "metric": "decimals", "source": "const"},
        {"slot": "live.selectedSampleIndex", "kind": "const", "value": 11, "metric": "selectedSampleIndex",
         "source": "const"},
        {"slot": "railVM.trend.areaOpacity", "kind": "const", "value": 0.0, "metric": "areaOpacity",
         "source": "const"},
        {"slot": "grid.layout", "kind": "const", "value": 28, "metric": "layout", "source": "const"},
        {"slot": "trend.windowDays", "kind": "const", "value": 30, "metric": "windowDays", "source": "const"},
        {"slot": "duty.topKpis[1].value", "kind": "const", "value": 0.0, "metric": "kw", "source": "const"},
    ]}
    blanked = enforce_honest_blank(di, {"columns": []})
    assert [f["slot"] for f in di["fields"]] == ["gauge.decimals", "live.selectedSampleIndex",
                                                 "railVM.trend.areaOpacity", "grid.layout", "trend.windowDays"]
    assert len(blanked) == 1 and "no real DB source" in blanked[0]         # the 0.0-kW measurement const still blanks


def test_const_scalar_citing_list_row_element_resolves():
    """A [min,max] consts.* band row cited as two scalars (expectedMin=410 / expectedMax=430) resolves — the equality
    check licenses row MEMBERSHIP, not only the full list; a value NOT in the row still blanks."""
    di = {"fields": [
        {"slot": "history.expectedMin", "kind": "const", "value": 410, "metric": "voltage_band", "source": "const"},
        {"slot": "history.expectedMax", "kind": "const", "value": 430.0, "metric": "voltage_band", "source": "const"},
        {"slot": "history.expectedMid", "kind": "const", "value": 445, "metric": "voltage_band", "source": "const"},
    ]}
    blanked = enforce_honest_blank(di, {"columns": []})
    assert [f["slot"] for f in di["fields"]] == ["history.expectedMin", "history.expectedMax"]
    assert len(blanked) == 1 and "no real DB source" in blanked[0]


def test_const_131a_still_blanks():
    """The named 131 A fabrication (no nameplate slot, no consts.* row) is untouched by every release above."""
    di = {"fields": [{"slot": "data.maxLine.value", "kind": "const", "value": 131, "metric": "I_RATED",
                      "source": "const"}]}
    blanked = enforce_honest_blank(di, {"columns": [{"column": "current_avg", "unit": "A"}]})
    assert di["fields"] == [] and "no real DB source" in blanked[0]


# ── boundary + expectation walls: untouched by the rework ───────────────────────────────────────────────────────────

def test_boundary_and_expectation_walls_untouched():
    """hvInputKw/lvOutputKw ← the meter's own power column still blank via the BOUNDARY wall (with its topology
    reason, no longer a positional reuse drop); expectedLoad ← a direct read still blanks via the EXPECTATION wall."""
    basket = {"columns": [{"column": "active_power_total_kw", "unit": "kW"}]}
    di = {"fields": [
        {"slot": "data.hvInputKw", "kind": "raw", "column": "active_power_total_kw", "metric": "hv_input_kw",
         "source": "live"},
        {"slot": "data.lvOutputKw", "kind": "raw", "column": "active_power_total_kw", "metric": "lv_output_kw",
         "source": "live"},
        {"slot": "data.expectedLoad", "kind": "raw", "column": "active_power_total_kw", "metric": "expectedLoad",
         "source": "live"},
    ]}
    blanked = enforce_honest_blank(di, basket)
    assert di["fields"] == []
    assert sum("topology boundary quantity" in b for b in blanked) == 2
    assert sum("never an expected/forecast value" in b for b in blanked) == 1
