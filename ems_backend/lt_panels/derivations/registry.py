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
    "windowEnergyKwh":        _d(energy.window_energy_kwh, ["active_energy_import_kwh"], "real_exact", "windowed_delta"),
    "todaysEnergyTotalKwh":   _d(energy.todays_energy_total_kwh, ["active_energy_import_kwh", "reactive_energy_import_kvarh"], "real_exact", "windowed_delta"),
    "progressActivePct":      _d(energy.progress_active_pct, ["active_energy_import_kwh", "reactive_energy_import_kvarh"], "real_exact", "windowed_delta"),
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
    "truePf":                 _d(power_quality.true_pf, ["active_power_total_kw", "apparent_power_total_kva"], "real_exact", "T2_identity"),
    "displacementPf":         _d(power_quality.displacement_pf, ["power_factor_total"], "real_exact", "exact_alt_column"),
    "thdComplianceIeee519":   _d(power_quality.thd_compliance_ieee519, ["thd_current_r_pct", "thd_current_y_pct", "thd_current_b_pct"], "real_approx", "T2_identity"),
    "thdTrendLabel":          _d(power_quality.thd_trend_label, ["thd_current_r_pct", "thd_current_y_pct", "thd_current_b_pct", "ts"], "real_approx", "T3_statistical"),
    "thdTrendRatePctPerHour": _d(power_quality.thd_trend_rate_pct_per_hour, ["thd_current_r_pct", "thd_current_y_pct", "thd_current_b_pct", "ts"], "real_approx", "T4_extrapolation"),
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
}


def catalog():
    """The library spec SHOWN to Layer 2 so the AI references a real fn by value_key with the columns it needs. The AI
    picks a value_key whose base_columns are all in the asset's basket; if none fits (the 4 walls), it honest-degrades."""
    return [{"fn": k, "base_columns": v["columns"], "fidelity": v["fidelity"], "recover_class": v["recover_class"]}
            for k, v in LIBRARY.items()]


def run(value_key, ctx):
    """Generic executor — run the AI-referenced library formula on ctx ({row}|{series}|{feeders}|{name}|{start_row,end_row}).
    Returns the value, or None to honest-degrade (unknown fn, or the inputs were missing/insufficient). NEVER fabricates."""
    desc = LIBRARY.get(value_key)
    if desc is None:
        return None
    try:
        v = desc["fn"](ctx or {})
    except Exception:
        v = None
    return None if (v is None or v == {}) else v


def describe(db_link, value_key):
    """The descriptor (fidelity/columns/recover_class) for a value on a db, or None if that db can't recover it."""
    return RESOLVERS.get(db_key_from_dblink(db_link), {}).get(value_key)


def resolve(db_link, value_key, ctx):
    """Compute `value_key` for the feeder's db. Returns {value, fidelity, recover_class, db_key} or None (honest-degrade:
    no formula for this value on this db, or the inputs were missing). NEVER fabricates."""
    db = db_key_from_dblink(db_link)
    desc = RESOLVERS.get(db, {}).get(value_key)
    if desc is None:
        return None
    try:
        value = desc["fn"](ctx or {})
    except Exception:
        value = None
    if value is None or value == {}:
        return None
    return {"value": value, "fidelity": desc["fidelity"], "recover_class": desc["recover_class"], "db_key": db}
