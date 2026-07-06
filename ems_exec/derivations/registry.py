"""derivations/registry.py — the DB-KEYED derivation resolver. A recovered value's formula depends on WHICH database the
feeder reads from (its inputs may exist in one db and not another). `db_key_from_dblink` parses the db identity from the
feeder's connection string; `RESOLVERS[db_key][value_key]` is the formula descriptor; `resolve(db_link, value_key, ctx)`
runs it and returns the value (with fidelity), or None to honest-degrade.

PROVISION FOR ADDING A DB: add a new db_key branch to RESOLVERS with that db's formula set — the SAME value_key can map
to a different formula (or be absent → honest-degrade). The LIVE data is `compat` (cmp_mfm_* views over the raw neuract
logging), which has NO rated/nameplate columns — so `sectionContracts`/`ratedKw` honest-degrade there, NEVER fabricate.
The `lt_panels` branch below is the DEPRECATED legacy simulator (the only place a rated column ever existed); it's kept
purely as the worked example of the DB-keyed mechanism — no live feeder reads it (every db_link pins search_path=compat).

ctx contract (the consumer fills what it has from the live frame):
  row     : latest compat row dict (instantaneous columns)
  series  : time-ordered list of rows (window/trend fns)
  start_row / end_row : window endpoints (cumulative-energy deltas)
  incomers / consumers / feeders : per-child rows (topology aggregation)
  name    : asset name (UPS rated parse)
  target_efficiency_pct : optional config (expected loss)
"""
from __future__ import annotations

import re
from urllib.parse import unquote

from . import voltage, energy, power, topology, nameplate, current, power_quality


def db_key_from_dblink(db_link):
    """Identify the database a feeder reads from, from its connection string. The compat repoint selects its schema via
    `options=-c search_path=compat` (dbname is target_version1); the legacy lt_panels link has no search_path so the
    dbname IS the key. Returns e.g. 'compat' | 'lt_panels'. Defaults to 'compat'."""
    s = unquote(db_link or "")
    m = re.search(r"search_path[=:]\s*([A-Za-z0-9_]+)", s)
    if m:
        return m.group(1).lower()
    m = re.search(r"/([A-Za-z0-9_]+)(?:\?|$)", s)
    if m:
        return m.group(1).lower()
    return "compat"


# ── per-db formula tables ────────────────────────────────────────────────────
# Each value descriptor: {fn: ctx->value|None, columns:[...], fidelity, recover_class}.
def _d(fn, columns, fidelity, recover_class):
    return {"fn": fn, "columns": columns, "fidelity": fidelity, "recover_class": recover_class}


# Recoverable on EVERY db that kept the base columns (compat kept these). Keyed by the frontend value_key.
_COMPAT = {
    "nominalVoltageLN":       _d(voltage.nominal_voltage_ln, ["voltage_avg", "kpi_voltage_deviation_pct"], "real_exact", "standard_formula"),
    "voltageStatutoryBand":   _d(voltage.statutory_band, ["voltage_avg", "kpi_voltage_deviation_pct"], "real_exact", "standard_formula"),
    "voltageHistoryDomain":   _d(voltage.voltage_history_domain, ["voltage_avg", "voltage_r_n", "voltage_y_n", "voltage_b_n"], "real_exact", "standard_formula"),
    # windowed voltage-history stats (card-44 family): the REAL 'Worst Spread' (max per-sample phase gap) and the REAL
    # worst deviation magnitude — series-scoped statistics, never a nominal/latest-row stand-in.
    "worstPhaseSpreadV":      _d(voltage.worst_phase_spread, ["voltage_r_n", "voltage_y_n", "voltage_b_n"], "real_exact", "T3_statistical"),
    "worstVoltageDeviationPct": _d(voltage.worst_v_dev, ["kpi_voltage_deviation_pct"], "real_exact", "T3_statistical"),
    # windowEnergyKwh's formula is ROW-DRIVEN (derivation_binding.expression); the python fn stays as the DB-outage
    # fallback because expected_loss_kwh still composes it (verify-before-dead: not deletable).
    "windowEnergyKwh":        _d(energy.window_energy_kwh, ["active_energy_import_kwh"], "real_exact", "windowed_delta"),
    "todaysEnergyTotalKwh":   _d(energy.todays_energy_total_kwh, ["active_energy_import_kwh", "reactive_energy_import_kvarh"], "real_exact", "windowed_delta"),
    # ROW-DRIVEN (fn=None): the formula IS the derivation_binding.expression row; python body deleted after the live
    # 3-table parity gate (2026-07-03). No expression row reachable → honest None.
    "progressActivePct":      _d(None, ["active_energy_import_kwh", "reactive_energy_import_kvarh"], "real_exact", "windowed_delta"),
    "activeEnergyMvah":       _d(energy.mvah_active, ["active_energy_import_kwh"], "real_exact", "exact_alt_column"),
    "reactiveEnergyMvarh":    _d(energy.mvah_reactive, ["reactive_energy_import_kvarh"], "real_exact", "exact_alt_column"),
    "cumulativeApparentMvah": _d(energy.cumulative_apparent_mvah, ["active_energy_import_kwh", "reactive_energy_import_kvarh"], "real_exact", "standard_formula"),
    "expectedLossKwh":        _d(energy.expected_loss_kwh, ["active_energy_import_kwh"], "real_exact", "standard_formula"),
    "loadFactorPct":          _d(power.load_factor_pct, ["active_power_total_kw"], "real_approx", "standard_formula"),
    "worstPeakKw":            _d(power.worst_peak_kw, ["active_power_total_kw"], "real_exact", "standard_formula"),
    "worstPeakAt":            _d(power.worst_peak_at, ["active_power_total_kw", "ts"], "real_exact", "standard_formula"),
    "apparentPeakKva":        _d(power.apparent_peak_kva, ["apparent_power_total_kva"], "real_approx", "windowed_delta"),
    "activePowerDeltaPerMinute": _d(power.active_power_delta_per_min, ["active_power_total_kw", "ts"], "real_exact", "standard_formula"),
    "lossPct":                _d(topology.distribution_loss_pct, ["active_power_total_kw"], "real_exact", "topology_aggregation"),
    "aiSummary":              _d(topology.ai_loss_summary, ["active_power_total_kw"], "real_exact", "topology_aggregation"),
    "sectionTrendSums":       _d(topology.section_trend_sums, ["active_power_total_kw"], "real_exact", "topology_aggregation"),
    "upsRatedKva":            _d(lambda ctx: nameplate.ups_rated_kva(ctx.get("name")), ["<asset name>"], "real_approx", "exact_alt_column"),
    # none-reaudit flips — recoverable on compat via electrical identity / windowed statistic:
    "neutralCurrent":         _d(current.neutral_current, ["current_r", "current_y", "current_b"], "real_approx", "T2_identity"),
    "neutralToPhaseRatioPct": _d(current.neutral_to_phase_ratio_pct, ["current_r", "current_y", "current_b", "current_avg"], "real_approx", "T2_identity"),
    "pfAngleDeg":             _d(power_quality.pf_angle_deg, ["power_factor_total"], "real_exact", "T2_identity"),
    # ROW-DRIVEN (fn=None): formulas are derivation_binding.expression rows; python bodies deleted after live parity.
    "truePf":                 _d(None, ["active_power_total_kw", "apparent_power_total_kva"], "real_exact", "T2_identity"),
    "displacementPf":         _d(None, ["power_factor_total"], "real_exact", "exact_alt_column"),
    "thdComplianceIeee519":   _d(power_quality.thd_compliance_ieee519, ["thd_current_r_pct", "thd_current_y_pct", "thd_current_b_pct"], "real_approx", "T2_identity"),
    "thdTrendLabel":          _d(power_quality.thd_trend_label, ["thd_current_r_pct", "thd_current_y_pct", "thd_current_b_pct", "ts"], "real_approx", "T3_statistical"),
    "thdTrendRatePctPerHour": _d(power_quality.thd_trend_rate_pct_per_hour, ["thd_current_r_pct", "thd_current_y_pct", "thd_current_b_pct", "ts"], "real_approx", "T4_extrapolation"),

    # ── FRAME target-column fills (the E&P tiles the consumer asks for as columns neuract never stored) ───────────────
    # These value_keys are keyed to the CONSUMER'S target column names in RECOVERY_FN below. Their inputs are the REAL
    # neuract registers (active/reactive import+export energy, active/apparent power) + the config nameplate rated_kw,
    # supplied by the consumer's fill_derived ctx enrichment. All reversed-CT aware; every fn honest-degrades to None.
    "activeEnergyTodayKwh":       _d(energy.active_energy_today_kwh, ["active_energy_import_kwh", "active_energy_export_kwh"], "real_exact", "windowed_delta"),
    "activeEnergyThisWeekKwh":    _d(energy.active_energy_this_week_kwh, ["active_energy_import_kwh", "active_energy_export_kwh"], "real_exact", "windowed_delta"),
    "activeEnergyThisMonthKwh":   _d(energy.active_energy_this_month_kwh, ["active_energy_import_kwh", "active_energy_export_kwh"], "real_exact", "windowed_delta"),
    "reactiveEnergyTodayKvarh":   _d(energy.reactive_energy_today_kvarh, ["reactive_energy_import_kvarh", "reactive_energy_export_kvarh"], "real_exact", "windowed_delta"),
    "reactiveEnergyThisWeekKvarh":  _d(energy.reactive_energy_this_week_kvarh, ["reactive_energy_import_kvarh", "reactive_energy_export_kvarh"], "real_exact", "windowed_delta"),
    "reactiveEnergyThisMonthKvarh": _d(energy.reactive_energy_this_month_kvarh, ["reactive_energy_import_kvarh", "reactive_energy_export_kvarh"], "real_exact", "windowed_delta"),
    "apparentEnergyTodayKvah":    _d(energy.apparent_energy_today_kvah, ["active_energy_import_kwh", "reactive_energy_import_kvarh"], "real_exact", "standard_formula"),
    "apparentEnergyThisWeekKvah": _d(energy.apparent_energy_this_week_kvah, ["active_energy_import_kwh", "reactive_energy_import_kvarh"], "real_exact", "standard_formula"),
    "apparentEnergyThisMonthKvah": _d(energy.apparent_energy_this_month_kvah, ["active_energy_import_kwh", "reactive_energy_import_kvarh"], "real_exact", "standard_formula"),
    "specificEnergyConsumption":  _d(energy.specific_energy_consumption, ["active_energy_import_kwh"], "real_exact", "standard_formula"),
    # DEAD-COUNTER RECOVERY: windowed kWh/kVArh from ∫power when the cumulative energy registers are all-NULL but power is
    # live. real_approx (a sampled integral, honest note 'integrated from power'). Series-scoped: the executor supplies the
    # windowed power series. Also the shared fallback the windowed-delta energy fns above call when their counter is dead.
    "energyFromPowerKwh":         _d(energy.energy_from_power_kwh, ["active_power_total_kw", "ts"], "real_approx", "integrated_from_power"),
    "reactiveEnergyFromPowerKvarh": _d(energy.reactive_energy_from_power_kvarh, ["reactive_power_total_kvar", "ts"], "real_approx", "integrated_from_power"),
    "kpiKwLoadPctOfRated":        _d(power.kpi_kw_load_pct_of_rated, ["active_power_total_kw", "nameplate:rated_kva"], "real_exact", "nameplate_lookup"),
    "kpiLoadFactor":              _d(power.kpi_load_factor, ["active_power_total_kw", "nameplate:rated_kva"], "real_exact", "nameplate_lookup"),
    "activePowerLossKw":          _d(power.active_power_loss_kw, ["hv_input_kw", "lv_output_kw"], "real_exact", "standard_formula"),
    "activePowerLossPct":         _d(power.active_power_loss_pct, ["hv_input_kw", "lv_output_kw"], "real_exact", "standard_formula"),
    "rateOfChangePowerKwPerMin":  _d(power.rate_of_change_power_kw_per_min, ["active_power_total_kw", "ts"], "real_exact", "standard_formula"),
    "loadFactorWindowPct":        _d(power.load_factor_pct, ["active_power_total_kw"], "real_approx", "standard_formula"),
}

# NAMEPLATE-DRIVEN rated/contract keys — the ONLY rated source is the editable cmd_catalog.asset_nameplate table (read
# via config.nameplates by asset TABLE), NOT a fabricated 'live kW ÷ load%' back-out from columns neuract never had.
# ctx carries the resolved asset table under `asset_table`/`table` (and per-feeder `table` for the topology aggregate).
# A missing nameplate row → None (honest-degrade the loading% slot; never a fabricated denominator). [RN-01, DID-03]
def _ctx_table(ctx):
    ctx = ctx or {}
    return ctx.get("asset_table") or ctx.get("table") or (ctx.get("row") or {}).get("asset_table")


_NAMEPLATE = {
    "ratedKw":          _d(lambda ctx: nameplate.feeder_rated_kw(_ctx_table(ctx)),
                           ["nameplate:rated_kva"], "real_exact", "nameplate_lookup"),
    "ratedKva":         _d(lambda ctx: nameplate.rated_kva(_ctx_table(ctx)),
                           ["nameplate:rated_kva"], "real_exact", "nameplate_lookup"),
    "sectionContracts": _d(lambda ctx: nameplate.section_contracts(ctx.get("feeders")),
                           ["nameplate:rated_kva"], "real_exact", "nameplate_lookup"),
}

# neuract = the LIVE db. It gets the compat superset PLUS the nameplate-driven rated/contract keys (which resolve from
# asset_nameplate, so they are honest wherever a nameplate row exists and honest-degrade to None where it doesn't).
_NEURACT = dict(_COMPAT)
_NEURACT.update(_NAMEPLATE)

# DEPRECATED legacy simulator alias — kept only so an old db_link that still pins search_path=lt_panels resolves the same
# nameplate-driven keys (no live feeder reads it; the fabricated capacity/load-pct back-out is DELETED).
_LT_PANELS = _NEURACT

RESOLVERS = {
    "compat": _COMPAT,
    "lt_panels": _LT_PANELS,
    "neuract": _NEURACT,
}


# ── flat library + generic executor (the AI-DRIVEN path) ─────────────────────────────────────────────────────────────
# The AI (Layer 2) references a formula BY NAME (data_instructions.fields[].fn = a value_key below) using only columns it
# was shown in the asset's basket. Because it only references a fn whose base_columns exist in the basket, the choice is
# automatically DB-correct — so the library is FLAT (no per-db split needed for the AI path). `run()` is the one generic
# executor. The per-db RESOLVERS above remain only for the deterministic config-emit seam (section_contracts).
LIBRARY = dict(_LT_PANELS)                                     # superset: every value_key (compat keys ⊆ lt_panels keys)

# ROW-SCOPE RECOVERY BASELINE — {dropped_column → fn} for the columns a consumer FETCHES that its DB may not have. The
# SELECTION is deterministic (a column is "dropped" iff the live row returns None), NOT an AI guess: a consumer auto-
# recovers any of these columns it lists in `columns`, with no per-consumer declaration. Each fn fills exactly this one
# real column from the per-phase / PF inputs that survive. (The AI MAY still extend this via the WS `derived` query.)
RECOVERY_FN = {
    "current_neutral":                "neutralCurrent",
    "kpi_neutral_to_phase_ratio_pct": "neutralToPhaseRatioPct",
    "phase_angle_deg":                "pfAngleDeg",
    "kpi_true_pf":                    "truePf",
    "kpi_displacement_pf":            "displacementPf",
    "thd_compliance_ieee519":         "thdComplianceIeee519",
    # ── ENERGY & POWER target columns (E&P tiles) — recovered from the real neuract registers + config nameplate ──────
    "active_energy_today_kwh":        "activeEnergyTodayKwh",
    "active_energy_this_week_kwh":    "activeEnergyThisWeekKwh",
    "active_energy_this_month_kwh":   "activeEnergyThisMonthKwh",
    "reactive_energy_today_kvarh":    "reactiveEnergyTodayKvarh",
    "reactive_energy_this_week_kvarh":  "reactiveEnergyThisWeekKvarh",
    "reactive_energy_this_month_kvarh": "reactiveEnergyThisMonthKvarh",
    "apparent_energy_today_kvah":     "apparentEnergyTodayKvah",
    "apparent_energy_this_week_kvah": "apparentEnergyThisWeekKvah",
    "apparent_energy_this_month_kvah": "apparentEnergyThisMonthKvah",
    "specific_energy_consumption":    "specificEnergyConsumption",
    "kpi_kw_load_pct_of_rated":       "kpiKwLoadPctOfRated",
    "kpi_load_factor":                "kpiLoadFactor",
    "active_power_loss_kw":           "activePowerLossKw",
    "active_power_loss_pct":          "activePowerLossPct",
    "rate_of_change_power_kw_per_min": "rateOfChangePowerKwPerMin",
}


# What each library fn MEASURES — its output QUANTITY family. Layer 2 may bind an fn ONLY when this quantity equals the
# slot's own quantity (from its label/unit); a fn that computes a DIFFERENT measure is a WRONG-QUANTITY binding even if
# its name sounds close (neutralToPhaseRatioPct is a neutral-to-phase RATIO — never a current-unbalance %). One flat map,
# single source of truth; adding an fn adds one row. A null/absent quantity = unclassified (the AI falls back to name +
# base_columns). Families are the fn's real output measure, kept coarse enough to match a slot's label/unit token.
_QUANTITY = {
    "nominalVoltageLN": "nominal-voltage", "voltageStatutoryBand": "voltage-statutory-band",
    "voltageHistoryDomain": "voltage-axis-domain",
    "worstPhaseSpreadV": "voltage-spread-v", "worstVoltageDeviationPct": "voltage-deviation-percent",
    "windowEnergyKwh": "active-energy-kwh", "todaysEnergyTotalKwh": "active-energy-kwh",
    "progressActivePct": "energy-progress-percent", "activeEnergyMvah": "active-energy-mvah",
    "reactiveEnergyMvarh": "reactive-energy-mvarh", "cumulativeApparentMvah": "apparent-energy-mvah",
    "expectedLossKwh": "energy-loss-kwh", "loadFactorPct": "load-factor-percent",
    "worstPeakKw": "peak-active-power-kw", "worstPeakAt": "peak-time", "apparentPeakKva": "peak-apparent-power-kva",
    "activePowerDeltaPerMinute": "active-power-rate-kw-per-min", "lossPct": "distribution-loss-percent",
    "aiSummary": "narrative-text", "sectionTrendSums": "section-trend-sum", "upsRatedKva": "rated-apparent-power-kva",
    "neutralCurrent": "neutral-current-a", "neutralToPhaseRatioPct": "neutral-to-phase-ratio-percent",
    "pfAngleDeg": "pf-angle-deg", "truePf": "true-power-factor", "displacementPf": "displacement-power-factor",
    "thdComplianceIeee519": "thd-compliance", "thdTrendLabel": "thd-trend-label",
    "thdTrendRatePctPerHour": "thd-trend-rate-percent-per-hour",
    "activeEnergyTodayKwh": "active-energy-kwh", "activeEnergyThisWeekKwh": "active-energy-kwh",
    "activeEnergyThisMonthKwh": "active-energy-kwh", "reactiveEnergyTodayKvarh": "reactive-energy-kvarh",
    "reactiveEnergyThisWeekKvarh": "reactive-energy-kvarh", "reactiveEnergyThisMonthKvarh": "reactive-energy-kvarh",
    "apparentEnergyTodayKvah": "apparent-energy-kvah", "apparentEnergyThisWeekKvah": "apparent-energy-kvah",
    "apparentEnergyThisMonthKvah": "apparent-energy-kvah", "specificEnergyConsumption": "specific-energy-consumption",
    "energyFromPowerKwh": "active-energy-kwh", "reactiveEnergyFromPowerKvarh": "reactive-energy-kvarh",
    "kpiKwLoadPctOfRated": "load-percent-of-rated", "kpiLoadFactor": "load-factor",
    "activePowerLossKw": "active-power-loss-kw", "activePowerLossPct": "active-power-loss-percent",
    "rateOfChangePowerKwPerMin": "active-power-rate-kw-per-min", "loadFactorWindowPct": "load-factor-percent",
    "ratedKw": "rated-power-kw", "ratedKva": "rated-apparent-power-kva", "sectionContracts": "section-contract-kva",
}


def catalog():
    """The library spec SHOWN to Layer 2 so the AI references a real fn by value_key with the columns it needs. The AI
    picks a value_key whose base_columns are all in the asset's basket AND whose `quantity` equals the slot's quantity;
    if none fits (the 4 walls), it honest-degrades."""
    return [{"fn": k, "base_columns": v["columns"], "fidelity": v["fidelity"], "recover_class": v["recover_class"],
             "quantity": _QUANTITY.get(k)}
            for k, v in LIBRARY.items()]


# ── ROW-DRIVEN formulas (the DB is authoritative) ────────────────────────────────────────────────────────────────────
# A derivation_binding row that carries a non-null `expression` IS the formula: the generic safe interpreter
# (derivations.evaluate) executes it over the same ctx the python fn would have seen. The python fn is only the
# fall-through for metrics whose row has no expression (series/topology/stateful/config-wired formulas — the retained
# generic core) or when the catalog DB is unreachable. A migrated metric whose python body was DELETED has fn=None in
# its descriptor: expression-or-honest-None, never a fabricated fallback.
def _expression_for(value_key):
    """The metric's DB expression text, or None (no row / NULL expression / DB outage → python fall-through)."""
    try:
        from . import expressions as _expr
        return _expr.expression_of(value_key)
    except Exception:
        return None


def _execute(desc, value_key, ctx):
    """One dispatch: DB expression row first (authoritative WHEN it produces a value), else the retained python fn, else
    honest None.

    EXPRESSION-DEGRADE FALL-THROUGH: a row expression that honest-degrades to None (a missing/None input — e.g. the
    cumulative energy counter is all-NULL) is NOT the final answer; it falls through to the retained python fn, which may
    RECOVER the value another way (windowEnergyKwh integrates the observed power series when its counter is dead). The
    expression still WINS whenever it yields a number (authoritative for the happy path); only its honest-degrade defers
    to the fn. A fn=None descriptor (collapsed python body) → honest None. Never fabricates."""
    fn = desc.get("fn") if desc else None
    expr = _expression_for(value_key)
    if expr:
        from . import evaluate as _ev
        v = _ev.evaluate(expr, ctx or {})
        if v is not None:
            return v                                            # expression produced a real value → authoritative
        # expression honest-degraded (None) → let the python fn attempt a recovery (∫power fallback, series stats, …)
    if fn is None:
        return None
    try:
        return fn(ctx or {})
    except Exception:
        return None


def run(value_key, ctx):
    """Generic executor — run the AI-referenced library formula on ctx ({row}|{series}|{feeders}|{name}|{start_row,end_row}).
    A derivation_binding row with an `expression` executes ROW-DRIVEN via the safe evaluator (the DB row is
    authoritative); else the retained python fn. Returns the value, or None to honest-degrade (unknown fn, or the
    inputs were missing/insufficient). NEVER fabricates."""
    desc = LIBRARY.get(value_key)
    if desc is None:
        return None
    v = _execute(desc, value_key, ctx)
    return None if (v is None or v == {}) else v


def describe(db_link, value_key):
    """The descriptor (fidelity/columns/recover_class) for a value on a db, or None if that db can't recover it."""
    return RESOLVERS.get(db_key_from_dblink(db_link), {}).get(value_key)


def resolve(db_link, value_key, ctx):
    """Compute `value_key` for the feeder's db. A derivation_binding row with an `expression` executes ROW-DRIVEN via
    the safe evaluator (the DB row is authoritative); else the retained python fn. Returns {value, fidelity,
    recover_class, db_key} or None (honest-degrade: no formula for this value on this db, or the inputs were missing).
    NEVER fabricates."""
    db = db_key_from_dblink(db_link)
    desc = RESOLVERS.get(db, {}).get(value_key)
    if desc is None:
        return None
    value = _execute(desc, value_key, ctx)
    if value is None or value == {}:
        return None
    return {"value": value, "fidelity": desc["fidelity"], "recover_class": desc["recover_class"], "db_key": db}
