"""SEAM 2 — the Layer-2 emit HONEST-BLANK gate (layer2/gates.enforce_honest_blank, wired into gate_data_instructions).

A data slot whose OWN quantity has NO backing column in the asset basket must render an honest blank — never a proxy
fn/column of another quantity, never a constant, never a value reused from a sibling slot (mandate: DATA only from
neuract; per-LEAF honest degradation). These deterministic unit tests pin the two generic, data-driven rules:
  (i) a field whose bound column / derived base-column (or empty nameplate denominator) is absent for the asset is
      DROPPED (the leaf honest-blanks);
 (ii) the SAME fn/column smeared across ≥2 distinct-quantity scalar slots (the live c54/c55/c57 pattern) is reduced to
      at most ONE legitimate slot.
A real-column slot, a $ctx group atom, and a series+legend+axis co-bind are UNTOUCHED (no false positives)."""
from layer2.gates import enforce_honest_blank, gate_data_instructions


def test_proxy_into_no_column_slot_is_blanked():
    """A raw field bound to an ABSENT column and a derived field whose base column is absent both honest-blank; a
    field bound to a REAL basket column survives untouched."""
    basket = {"columns": [{"column": "voltage_r_n"}]}
    di = {"fields": [
        {"slot": "v.r", "kind": "raw", "column": "voltage_r_n", "metric": "voltage_r", "source": "live"},      # real
        {"slot": "score.transfer", "kind": "raw", "column": "ups_transfer_score",                              # absent
         "metric": "transfer_score", "source": "live"},
        {"slot": "d.readiness", "kind": "derived", "fn": "readinessFn", "base_columns": ["ups_readiness_col"],  # absent
         "metric": "readiness", "source": "live"},
    ]}
    blanked = enforce_honest_blank(di, basket)
    kept = [f["slot"] for f in di["fields"]]
    assert kept == ["v.r"]                                        # the real-column slot is the ONLY survivor
    assert len(blanked) == 2
    assert any("ups_transfer_score" in b for b in blanked)
    assert any("ups_readiness_col" in b for b in blanked)


def test_real_column_slot_is_untouched():
    """A field bound to a real basket column of its own quantity is never blanked (no false positive)."""
    basket = {"columns": [{"column": "active_power_total_kw"}]}
    di = {"fields": [{"slot": "kpi.load", "kind": "raw", "column": "active_power_total_kw",
                      "metric": "load_kw", "source": "live"}]}
    assert enforce_honest_blank(di, basket) == []
    assert [f["slot"] for f in di["fields"]] == ["kpi.load"]


def test_one_energy_value_reused_across_transfer_count_slots_all_blank():
    """c55: one energy fn (activeEnergyTodayKwh over active_energy_import_kwh) smeared across days-since / count-30d /
    lifetime scalar slots — all transfer-activity quantities an energy counter cannot answer (FIVE WALLS #5). Since
    the quantity vocab now classifies `lastTransferDays` (transferdays → count) alongside the two explicit-count
    slots, EVERY cell blanks per-cell via the QUANTITY WALL — none survives. (Previously `lastTransferDays` was
    UNCLASSIFIED and slipped through as a false 'legitimate' survivor: an energy kWh shown as days-since-transfer.
    Classifying it closed that gap — 0 fabrications instead of 1.)"""
    basket = {"columns": [{"column": "active_energy_import_kwh"}]}
    di = {"fields": [
        {"slot": "activity.lastTransferDays", "kind": "derived", "fn": "activeEnergyTodayKwh",
         "base_columns": ["active_energy_import_kwh"], "metric": "ups_days_since_last_transfer", "source": "live"},
        {"slot": "activity.count30d", "kind": "derived", "fn": "activeEnergyTodayKwh",
         "base_columns": ["active_energy_import_kwh"], "metric": "ups_transfers_30d", "source": "live"},
        {"slot": "activity.lifetimeTransfers", "kind": "derived", "fn": "activeEnergyTodayKwh",
         "base_columns": ["active_energy_import_kwh"], "metric": "ups_transfers_lifetime", "source": "live"},
    ]}
    blanked = enforce_honest_blank(di, basket)
    assert len(di["fields"]) == 0                                 # every transfer-count cell honest-blanks
    assert len(blanked) == 3 and all("count not measured by this meter" in b for b in blanked)


def test_c54_readiness_scores_all_blank():
    """c54: one load-factor proxy (loadFactorPct over active_power_total_kw) smeared across composite + 3 permissive
    score cells → all render the same ~96.3. PRECISION REWORK: the bind is CLASSIFIED (load-factor), so every
    readiness-claiming cell blanks per-cell via the QUANTITY WALL (iii) with its own honest reason — a load-factor
    fn is NOT a readiness score, so NO cell ships a re-labelled load factor (same catch, better reasons)."""
    basket = {"columns": [{"column": "active_power_total_kw"}]}
    di = {"fields": [
        {"slot": "readiness.score", "kind": "derived", "fn": "loadFactorPct",
         "base_columns": ["active_power_total_kw"], "metric": "ups_transfer_composite_score", "source": "live"},
        {"slot": "readiness.metrics[0].value", "kind": "derived", "fn": "loadFactorPct",
         "base_columns": ["active_power_total_kw"], "metric": "ups_input_permissive_score", "source": "live"},
        {"slot": "readiness.metrics[1].value", "kind": "derived", "fn": "loadFactorPct",
         "base_columns": ["active_power_total_kw"], "metric": "ups_bypass_permissive_score", "source": "live"},
        {"slot": "readiness.metrics[2].value", "kind": "derived", "fn": "loadFactorPct",
         "base_columns": ["active_power_total_kw"], "metric": "ups_sync_permissive_score", "source": "live"},
    ]}
    blanked = enforce_honest_blank(di, basket)
    assert di["fields"] == []                                     # nothing fabricated survives
    assert len(blanked) == 4
    assert sum("readiness not measured by this meter" in b for b in blanked) == 4


def test_series_legend_axis_cobind_is_not_blanked():
    """No false positive: a SERIES and its own legend latest-value + axis min/max share the series' column — that is
    ONE quantity across related slots (a series anchor is present), NOT the reuse defect."""
    basket = {"columns": [{"column": "active_power_total_kw"}]}
    di = {"fields": [
        {"slot": "chart.series[0].values", "kind": "bucketed", "column": "active_power_total_kw",
         "metric": "load_series", "role": "series", "source": "live"},
        {"slot": "chart.legend[0].value", "kind": "raw", "column": "active_power_total_kw",
         "metric": "load_latest", "source": "live"},
        {"slot": "chart.loadAxis.max", "kind": "raw", "column": "active_power_total_kw",
         "metric": "load_axis_max", "source": "live"},
        {"slot": "chart.loadAxis.min", "kind": "raw", "column": "active_power_total_kw",
         "metric": "load_axis_min", "source": "live"},
    ]}
    assert enforce_honest_blank(di, basket) == []                 # series-anchored group is untouched
    assert len(di["fields"]) == 4


def test_same_metric_repeat_is_not_blanked():
    """Guard: the SAME metric shown in two slots (a mirror, not distinct quantities) is not a reuse defect — the rule
    only fires on ≥2 DISTINCT metrics."""
    basket = {"columns": [{"column": "active_power_total_kw"}]}
    di = {"fields": [
        {"slot": "a", "kind": "raw", "column": "active_power_total_kw", "metric": "load_kw", "source": "live"},
        {"slot": "b", "kind": "raw", "column": "active_power_total_kw", "metric": "load_kw", "source": "live"},
    ]}
    assert enforce_honest_blank(di, basket) == []
    assert len(di["fields"]) == 2


def test_empty_nameplate_denominator_blanked_when_known_missing():
    """c57 tail: a derived fn with a nameplate:* denominator honest-blanks when the asset's rating is KNOWN-empty
    (basket.nameplate.rated_present=False); it survives when present or unknown (executor guards divide-by-empty)."""
    fld = {"slot": "cap.score", "kind": "derived", "fn": "kpiKwLoadPctOfRated",
           "base_columns": ["active_power_total_kw", "nameplate:rated_kva"], "metric": "cap", "source": "live"}
    cols = [{"column": "active_power_total_kw"}]
    b_missing = {"columns": cols, "nameplate": {"rated_present": False}}
    assert len(enforce_honest_blank({"fields": [dict(fld)]}, b_missing)) == 1     # empty rating → blank
    b_present = {"columns": cols, "nameplate": {"rated_present": True}}
    assert enforce_honest_blank({"fields": [dict(fld)]}, b_present) == []          # rating present → keep
    assert enforce_honest_blank({"fields": [dict(fld)]}, {"columns": cols}) == []  # unknown → keep (safe default)


def test_group_ctx_fields_skip_basket_check_but_walls_apply():
    """DEFECT G closure + PRECISION REWORK: a $ctx GROUP atom still skips the BASKET-membership rule (i) — its buffer
    keys are metric keys, not basket columns, so an empty basket never blanks it — and the REUSE/SMEAR wall (ii)
    still applies, but on QUANTITY distinctness: an UNCLASSIFIED buffer key smeared across ≥2 cells that classify
    DISTINCT quantities keeps only the first (a CLASSIFIED bind's cross-quantity cells blank per-cell via the
    quantity wall instead — the c41/c42 named fabrications ride their own boundary/expectation walls)."""
    # same buffer key, SAME metric (a mirror) → no defect, and rule (i) never fires on $ctx (empty basket ok)
    di = {"fields": [
        {"slot": "a", "kind": "raw", "column": "kw", "metric": "m1", "source": "$ctx"},
        {"slot": "b", "kind": "raw", "column": "kw", "metric": "m1", "source": "$ctx"},
    ]}
    assert enforce_honest_blank(di, {"columns": []}, is_group_card=True) == []
    assert len(di["fields"]) == 2
    # PRECISION REWORK: an UNCLASSIFIED buffer key ('x7' names no quantity) smeared across cells claiming DISTINCT
    # quantities (voltage vs current), no series anchor → the smear wall keeps the first scalar, drops the rest
    di2 = {"fields": [
        {"slot": "a", "kind": "raw", "column": "x7", "metric": "voltage_avg", "source": "$ctx"},
        {"slot": "b", "kind": "raw", "column": "x7", "metric": "current_avg", "source": "$ctx"},
    ]}
    blanked = enforce_honest_blank(di2, {"columns": []}, is_group_card=True)
    assert [f["slot"] for f in di2["fields"]] == ["a"]
    assert len(blanked) == 1 and "reused across distinct scalar slots" in blanked[0]
    # DISTINCT-metric but same/unclassified-quantity cells sharing one bind are NOT the smear defect any more —
    # one measurement legitimately rendered in two places (maxLine.value + summary.sideValue ← the same reading)
    di3 = {"fields": [
        {"slot": "history.maxLine.value", "kind": "raw", "column": "kw", "metric": "m1", "source": "$ctx"},
        {"slot": "history.summary.sideValue", "kind": "raw", "column": "kw", "metric": "m2", "source": "$ctx"},
    ]}
    assert enforce_honest_blank(di3, {"columns": []}, is_group_card=True) == []
    assert len(di3["fields"]) == 2


def test_gate_self_heals_and_records_telemetry_not_a_card_gate():
    """Wired path: gate_data_instructions runs the honest-blank pre-pass IN PLACE, records di._honest_blanked
    telemetry, and returns ok=True (a self-healed leaf is a per-leaf degradation, not a card-blocking defect); the
    reduced fields[] then validates cleanly."""
    basket = {"columns": [{"column": "active_energy_import_kwh"}]}
    di = {"fields": [
        {"slot": "activity.metrics[0].value", "kind": "derived", "fn": "activeEnergyTodayKwh",
         "base_columns": ["active_energy_import_kwh"], "metric": "days_since", "source": "live"},
        {"slot": "activity.count30d", "kind": "derived", "fn": "activeEnergyTodayKwh",
         "base_columns": ["active_energy_import_kwh"], "metric": "count_30d", "source": "live"},
        {"slot": "activity.lifetimeTransfers", "kind": "derived", "fn": "activeEnergyTodayKwh",
         "base_columns": ["active_energy_import_kwh"], "metric": "lifetime", "source": "live"},
    ]}
    ok, issues = gate_data_instructions(di, basket)
    assert ok and not issues                                      # self-healed → not a card gate failure
    assert len(di["fields"]) == 1                                 # blanked in place
    assert len(di.get("_honest_blanked") or []) == 2             # telemetry recorded


def test_validate_fail_column_honest_blanks_not_payload_error():
    """[card 47] A field bound to a validate-FAIL column (real column, 100%-null data on this meter — e.g. harmonics
    thd_* on a UPS) must NOT hard-fail the card. The executor still fills any live rows and blanks the null rest
    per-leaf; conforms stays True (no payload_error), the reason rides _honest_blanked telemetry, and the field is
    KEPT so live rows still fill. A genuinely hallucinated column is a separate path (dropped by the pre-pass)."""
    from layer2.gates import gate_data_instructions
    basket = {"columns": [
        {"column": "thd_current_r_pct", "verdict": "fail", "validate_reasons": ["null_rate 1.00 > 0.5"]},
        {"column": "current_r", "verdict": "pass"},
    ]}
    di = {"fields": [
        {"slot": "snapshot.iThd.valuePct", "kind": "raw", "source": "live", "column": "thd_current_r_pct"},
        {"slot": "snapshot.amps.value", "kind": "raw", "source": "live", "column": "current_r"},
    ]}
    ok, issues = gate_data_instructions(di, basket)
    assert ok is True, issues                                    # conforms — NOT a payload_error
    assert issues == []
    assert any("thd_current_r_pct" in r for r in (di.get("_honest_blanked") or []))
    assert len(di["fields"]) == 2                                # field kept so current_r fills + thd null-blanks per-leaf
