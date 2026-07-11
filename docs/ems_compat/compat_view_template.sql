-- ems_compat/compat_view_template.sql
-- ONE parameterized compat-view template — wraps any clean neuract meter (neuract.mfm_{NNN})
-- into the exact contract ems_backend's services.py expects, so consumers run UNCHANGED.
-- Substitute {NNN} = neuract mfm table number, {PANEL_ID} = the injected panel/feeder id literal.
--   CREATE OR REPLACE VIEW compat.cmp_mfm_{NNN} AS <this SELECT> FROM neuract.mfm_{NNN};
--
-- Built from the neuract-column-contract workflow (wf_e3fc1ded-450), verifier-corrected.
-- Coverage truth-table: ems_compat/COVERAGE.md. Column-tolerant fetch (services._select_existing)
-- pads NULL for any column neuract cannot supply, so omitted columns just blank the widget — never error.

SELECT
    -- ---- timestamp + identity injection ----
    timestamp_utc::timestamptz                       AS ts,             -- dispatcher reads row['ts']; fixes type + ordering
    '{PANEL_ID}'::text                               AS panel_id,       -- injected literal (one view per meter)

    -- ---- DIRECT electrical core (names already match neuract) ----
    active_power_total_kw,
    reactive_power_total_kvar,
    apparent_power_total_kva,
    power_factor_total,
    frequency_hz,
    current_avg,
    current_r, current_y, current_b,
    voltage_r_n, voltage_y_n, voltage_b_n,
    voltage_ry, voltage_yb, voltage_br,                                 -- raw L-L (expose directly; consumers that want L-L read these)
    voltage_ll_avg,
    active_power_r_kw, active_power_y_kw, active_power_b_kw,            -- per-phase power (neuract surplus, harmless)
    reactive_power_r_kvar, reactive_power_y_kvar, reactive_power_b_kvar,
    apparent_power_r_kva, apparent_power_y_kva, apparent_power_b_kva,
    power_factor_r, power_factor_y, power_factor_b,
    active_energy_import_kwh,                                           -- cumulative counters (period energy = window-delta at services layer)
    reactive_energy_import_kvarh,
    active_energy_export_kwh, reactive_energy_export_kvarh,

    -- ---- ALIASES ----
    voltage_ln_avg                                   AS voltage_avg,    -- legacy single avg == phase-to-neutral avg (NOT voltage_ll_avg)

    -- ---- DIRECT THD (per phase) ----
    thd_voltage_r_pct, thd_voltage_y_pct, thd_voltage_b_pct,
    thd_current_r_pct, thd_current_y_pct, thd_current_b_pct,
    -- DERIVED THD compliance averages (NULL-tolerant mean — corrected from the naive /3.0) :
    ( (COALESCE(thd_voltage_r_pct,0)+COALESCE(thd_voltage_y_pct,0)+COALESCE(thd_voltage_b_pct,0))
      / NULLIF( (thd_voltage_r_pct IS NOT NULL)::int+(thd_voltage_y_pct IS NOT NULL)::int+(thd_voltage_b_pct IS NOT NULL)::int, 0) ) AS thd_compliance_v_avg,
    ( (COALESCE(thd_current_r_pct,0)+COALESCE(thd_current_y_pct,0)+COALESCE(thd_current_b_pct,0))
      / NULLIF( (thd_current_r_pct IS NOT NULL)::int+(thd_current_y_pct IS NOT NULL)::int+(thd_current_b_pct IS NOT NULL)::int, 0) ) AS thd_compliance_i_avg,

    -- ---- DERIVED min/max/spread (per-phase R/Y/B) ----
    LEAST(voltage_r_n, voltage_y_n, voltage_b_n)                       AS voltage_min,
    GREATEST(voltage_r_n, voltage_y_n, voltage_b_n)                    AS voltage_max,
    LEAST(current_r, current_y, current_b)                            AS current_min,
    GREATEST(current_r, current_y, current_b)                         AS current_max,
    GREATEST(current_r,current_y,current_b) - LEAST(current_r,current_y,current_b) AS current_max_spread,
    ABS(current_b - current_r)                                        AS current_spread_br,
    ABS(current_r - current_y)                                        AS current_spread_ry,
    ABS(current_b - current_y)                                        AS current_spread_by,
    GREATEST(voltage_ry,voltage_yb,voltage_br) - LEAST(voltage_ry,voltage_yb,voltage_br) AS voltage_max_spread_v,

    -- ---- DERIVED unbalance / deviation (ref = measured avg; swap for config nominal-V if/when joined) ----
    CASE WHEN current_avg > 0 THEN 100.0 * GREATEST(ABS(current_r-current_avg),ABS(current_y-current_avg),ABS(current_b-current_avg)) / current_avg ELSE 0 END AS current_unbalance_pct,
    CASE WHEN voltage_ln_avg > 0 THEN 100.0 * GREATEST(ABS(voltage_r_n-voltage_ln_avg),ABS(voltage_y_n-voltage_ln_avg),ABS(voltage_b_n-voltage_ln_avg)) / voltage_ln_avg ELSE 0 END AS voltage_unbalance_pct,
    CASE WHEN voltage_ln_avg > 0 THEN 100.0 * GREATEST(ABS(voltage_r_n-voltage_ln_avg),ABS(voltage_y_n-voltage_ln_avg),ABS(voltage_b_n-voltage_ln_avg)) / voltage_ln_avg ELSE 0 END AS kpi_voltage_deviation_pct,
    CASE WHEN voltage_ln_avg > 0 THEN 100.0*(voltage_r_n-voltage_ln_avg)/voltage_ln_avg ELSE 0 END AS voltage_r_deviation_pct,
    CASE WHEN voltage_ln_avg > 0 THEN 100.0*(voltage_y_n-voltage_ln_avg)/voltage_ln_avg ELSE 0 END AS voltage_y_deviation_pct,
    CASE WHEN voltage_ln_avg > 0 THEN 100.0*(voltage_b_n-voltage_ln_avg)/voltage_ln_avg ELSE 0 END AS voltage_b_deviation_pct,
    CASE WHEN current_avg > 0 THEN 100.0*(current_r-current_avg)/current_avg ELSE 0 END AS current_r_deviation_pct,
    CASE WHEN current_avg > 0 THEN 100.0*(current_y-current_avg)/current_avg ELSE 0 END AS current_y_deviation_pct,
    CASE WHEN current_avg > 0 THEN 100.0*(current_b-current_avg)/current_avg ELSE 0 END AS current_b_deviation_pct

    -- ===== INTENTIONALLY OMITTED — no truthful neuract source; app pads NULL (see COVERAGE.md) =====
    -- CORRECTED: do NOT alias active/reactive_energy_today_* to the cumulative import counters (cumulative != today-reset).
    --   "today/week/month" energy = window-delta (MAX-MIN over period) at the services layer, like fetch_energy_delta.
    -- current_neutral, kpi_neutral_to_phase_ratio_pct      (neuract has NO neutral current; not derivable from R/Y/B magnitudes)
    -- *_event_active booleans (sag/swell/current_imbalance/neutral_stress + 6 PQ + sustained_thd_breach + apfc_compensation_flag)
    -- sag_events_24h/swell_events_24h, *_rate_change_*_per_min, rate_of_change_*   (rolling/derivative — app-computed)
    -- kpi_kw_load_pct_of_rated, kpi_load_factor, demand_*, peak_*                  (need nameplate / window rollups)
    -- harmonic_3/5/7/11/13_pct, k_factor, harmonic_loss_factor_fhl, dominant_harmonic_order, phase_angle_deg,
    --   kpi_true_pf, kpi_displacement_pf, crest_factor_*, flicker_pst/plt, thd_compliance_ieee519  (need per-order/waveform)
    -- period & apparent energies (no kVAh counter at all), budget/projection/SEC
    -- transformer thermal/loss/efficiency/RUL, ALL ups_*, ALL solar/PV, ALL apfc_*   (separate device schemas)
    -- config_nameplate (rated_kva/rated_kw/voltage_nominal_v/...): JOIN config tables separately
    -- breaker/health/alerts/comms status, *_trend_status, *_at_time timestamps
FROM neuract.mfm_{NNN};
