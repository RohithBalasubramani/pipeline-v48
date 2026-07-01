"""Seed Parameter rows for all 5 MFM types.

Common parameters (126) are shared by every type. Each type gets
its own type-specific extras appended.

Counts:
  transformer = 127 common
  ht_panel    = 127 common
  lt_panel    = 127 common + 42 LT-specific         = 169
  ups         = 127 common + 12 UPS-specific + 81 UPS-overview = 220
  apfc        = 127 common + 12 APFC-specific       = 139

Note: the identity columns (id, ts, panel_id, panel_name) are columns in the
external panel_readings table but are NOT Parameter rows — they pass through
the live/history endpoints as-is.
"""

from django.core.management.base import BaseCommand
from lt_panels.models import MFMType, Parameter


# (column_name, display_name, kind, unit, spec) — shared across all 5 MFM types
COMMON_PARAMETERS = [
    # ── Measured: Energy M1–M15 (25) ──
    ('voltage_ry', 'Voltage R-Y', 'measured', 'V', 'M1'),
    ('voltage_yb', 'Voltage Y-B', 'measured', 'V', 'M1'),
    ('voltage_br', 'Voltage B-R', 'measured', 'V', 'M1'),
    ('voltage_r_n', 'Voltage R-N', 'measured', 'V', 'M2'),
    ('voltage_y_n', 'Voltage Y-N', 'measured', 'V', 'M2'),
    ('voltage_b_n', 'Voltage B-N', 'measured', 'V', 'M2'),
    ('current_r', 'Current R', 'measured', 'A', 'M3'),
    ('current_y', 'Current Y', 'measured', 'A', 'M3'),
    ('current_b', 'Current B', 'measured', 'A', 'M3'),
    ('current_neutral', 'Neutral Current', 'measured', 'A', 'M4'),
    ('active_power_total_kw', 'Active Power Total', 'measured', 'kW', 'M5'),
    ('reactive_power_total_kvar', 'Reactive Power Total', 'measured', 'kVAR', 'M6'),
    ('apparent_power_total_kva', 'Apparent Power Total', 'measured', 'kVA', 'M7'),
    ('frequency_hz', 'Frequency', 'measured', 'Hz', 'M8'),
    ('active_energy_import_kwh', 'Active Energy Import', 'measured', 'kWh', 'M9'),
    ('reactive_energy_import_kvarh', 'Reactive Energy Import', 'measured', 'kVARh', 'M10'),
    ('apparent_energy_kvah', 'Apparent Energy', 'measured', 'kVAh', 'M11'),
    ('phase_angle_deg', 'Phase Angle', 'measured', '°', 'M12'),
    ('peak_current_a', 'Peak Current', 'measured', 'A', 'M13'),
    ('peak_voltage_v', 'Peak Voltage', 'measured', 'V', 'M14'),
    ('demand_present_kva', 'Present Demand', 'measured', 'kVA', 'M15'),
    ('demand_avg_kva', 'Average Demand', 'measured', 'kVA', 'M15'),
    ('demand_max_kva', 'Max Demand', 'measured', 'kVA', 'M15'),
    ('demand_present_kw', 'Present Demand kW', 'measured', 'kW', 'M15'),
    ('demand_max_kw', 'Max Demand kW', 'measured', 'kW', 'M15'),

    # ── Measured: Power Quality PQ1–PQ10 (21) ──
    ('power_factor_total', 'Power Factor Total', 'measured', '', 'PQ1'),
    ('thd_voltage_r_pct', 'THD Voltage R', 'measured', '%', 'PQ2'),
    ('thd_voltage_y_pct', 'THD Voltage Y', 'measured', '%', 'PQ2'),
    ('thd_voltage_b_pct', 'THD Voltage B', 'measured', '%', 'PQ2'),
    ('thd_current_r_pct', 'THD Current R', 'measured', '%', 'PQ3'),
    ('thd_current_y_pct', 'THD Current Y', 'measured', '%', 'PQ3'),
    ('thd_current_b_pct', 'THD Current B', 'measured', '%', 'PQ3'),
    ('harmonic_3rd_pct', '3rd Harmonic', 'measured', '%', 'PQ4'),
    ('harmonic_5th_pct', '5th Harmonic', 'measured', '%', 'PQ4'),
    ('harmonic_7th_pct', '7th Harmonic', 'measured', '%', 'PQ4'),
    ('harmonic_11th_pct', '11th Harmonic', 'measured', '%', 'PQ4'),
    ('harmonic_13th_pct', '13th Harmonic', 'measured', '%', 'PQ4'),
    ('voltage_unbalance_pct', 'Voltage Unbalance', 'measured', '%', 'PQ5'),
    ('current_unbalance_pct', 'Current Unbalance', 'measured', '%', 'PQ6'),
    ('sag_events_24h', 'Sag Events 24h', 'measured', 'count', 'PQ7'),
    ('swell_events_24h', 'Swell Events 24h', 'measured', 'count', 'PQ7'),
    ('voltage_variation_pct', 'Voltage Variation', 'measured', '%', 'PQ8'),
    ('flicker_pst', 'Flicker Pst', 'measured', '', 'PQ9'),
    ('flicker_plt', 'Flicker Plt', 'measured', '', 'PQ9'),
    ('crest_factor_voltage', 'Crest Factor Voltage', 'measured', '', 'PQ10'),
    ('crest_factor_current', 'Crest Factor Current', 'measured', '', 'PQ10'),

    # ── Derived: KPIs 1.x (8) ──
    ('kpi_kw_load_pct_of_rated', 'kW Load % of Rated', 'derived', '%', '1.1'),
    ('kpi_load_factor', 'Load Factor', 'derived', '', '1.2'),
    ('kpi_demand_headroom_kva', 'Demand Headroom', 'derived', 'kVA', '1.3'),
    ('kpi_demand_headroom_pct', 'Demand Headroom %', 'derived', '%', '1.3'),
    ('kpi_displacement_pf', 'Displacement PF', 'derived', '', '1.4'),
    ('kpi_true_pf', 'True PF', 'derived', '', '1.4'),
    ('kpi_voltage_deviation_pct', 'Voltage Deviation', 'derived', '%', '1.5'),
    ('kpi_neutral_to_phase_ratio_pct', 'Neutral-to-Phase Ratio', 'derived', '%', '1.6'),

    # ── Derived: Energy & Cost 2.x (7) ──
    ('energy_cost_per_hour', 'Energy Cost / Hour', 'derived', '₹', '2.1'),
    ('energy_cost_per_day', 'Energy Cost / Day', 'derived', '₹', '2.1'),
    ('energy_cost_total', 'Energy Cost Total', 'derived', '₹', '2.1'),
    ('energy_loss_ratio', 'Energy Loss Ratio', 'derived', '', '2.2'),
    ('specific_energy_consumption', 'Specific Energy Consumption', 'derived', 'kWh/unit', '2.3'),
    ('cumulative_vs_budget_kwh', 'Cumulative vs Budget', 'derived', 'kWh', '2.4'),
    ('cost_per_kva_demand', 'Cost per kVA Demand', 'derived', '₹/kVA', '2.6'),

    # ── Derived: Power 3.x (10) ──
    ('rate_of_change_power_kw_per_min', 'Rate of Change (Power)', 'derived', 'kW/min', '3.1'),
    ('rate_of_change_voltage_v_per_min', 'Rate of Change (Voltage)', 'derived', 'V/min', '3.2'),
    ('power_factor_r', 'Power Factor R', 'derived', '', '3.3'),
    ('power_factor_y', 'Power Factor Y', 'derived', '', '3.3'),
    ('power_factor_b', 'Power Factor B', 'derived', '', '3.3'),
    ('ratio_kw_kva', 'Ratio kW/kVA', 'derived', '', '3.4'),
    ('ratio_kvar_kva', 'Ratio kVAR/kVA', 'derived', '', '3.4'),
    ('ratio_kw_kvar', 'Ratio kW/kVAR', 'derived', '', '3.4'),
    ('pf_gap_vs_full_load', 'PF Gap vs Full Load', 'derived', '', '3.5'),
    ('reactive_power_trend', 'Reactive Power Trend', 'derived', 'kVAR', '3.6'),

    # ── Derived: Power Quality 4.x (9) ──
    ('thd_compliance_ieee519', 'THD Compliance IEEE519', 'derived', '', '4.1'),
    ('thd_compliance_v_avg', 'THD Compliance V Avg', 'derived', '%', '4.1'),
    ('thd_compliance_i_avg', 'THD Compliance I Avg', 'derived', '%', '4.1'),
    ('k_factor', 'K-Factor', 'derived', '', '4.2'),
    ('negative_sequence_voltage_pct', 'Negative Sequence Voltage', 'derived', '%', '4.3'),
    ('negative_sequence_current_pct', 'Negative Sequence Current', 'derived', '%', '4.4'),
    ('harmonic_loss_factor_fhl', 'Harmonic Loss Factor (FHL)', 'derived', '', '4.5'),
    ('true_rms_voltage', 'True RMS Voltage', 'derived', 'V', '4.6'),
    ('fundamental_rms_voltage', 'Fundamental RMS Voltage', 'derived', 'V', '4.6'),

    # ── Derived: Single-MFM power flow (4) ──
    ('hv_input_kw', 'HV Input Power', 'derived', 'kW', 'D-PWR'),
    ('lv_output_kw', 'LV Output Power', 'derived', 'kW', 'D-PWR'),
    ('active_power_loss_kw', 'Active Power Loss', 'derived', 'kW', 'D-PWR'),
    ('active_power_loss_pct', 'Active Power Loss %', 'derived', '%', 'D-PWR'),

    # ── Derived: Voltage aggregates (3) ──
    ('voltage_avg', 'Voltage Average (L-N)', 'derived', 'V', 'D-V'),
    ('voltage_ll_avg', 'Voltage Average (L-L)', 'derived', 'V', 'D-V'),
    ('voltage_max', 'Voltage Max', 'derived', 'V', 'D-V'),
    ('voltage_min', 'Voltage Min', 'derived', 'V', 'D-V'),

    # ── Derived: Current aggregates (3) ──
    ('current_avg', 'Current Average', 'derived', 'A', 'D-I'),
    ('current_max', 'Current Max', 'derived', 'A', 'D-I'),
    ('current_min', 'Current Min', 'derived', 'A', 'D-I'),

    # ── Derived: Per-phase deviations (6) ──
    ('voltage_r_deviation_pct', 'Voltage R Deviation', 'derived', '%', 'D-V'),
    ('voltage_y_deviation_pct', 'Voltage Y Deviation', 'derived', '%', 'D-V'),
    ('voltage_b_deviation_pct', 'Voltage B Deviation', 'derived', '%', 'D-V'),
    ('current_r_deviation_pct', 'Current R Deviation', 'derived', '%', 'D-I'),
    ('current_y_deviation_pct', 'Current Y Deviation', 'derived', '%', 'D-I'),
    ('current_b_deviation_pct', 'Current B Deviation', 'derived', '%', 'D-I'),

    # ── Derived: Current spreads (4) ──
    ('current_max_spread', 'Current Max Spread', 'derived', 'A', 'D-I'),
    ('current_spread_br', 'Current Spread B-R', 'derived', 'A', 'D-I'),
    ('current_spread_ry', 'Current Spread R-Y', 'derived', 'A', 'D-I'),
    ('current_spread_by', 'Current Spread B-Y', 'derived', 'A', 'D-I'),

    # ── Derived: Power Quality summaries (2) ──
    ('pq_constraint', 'Power Quality Constraint', 'derived', '', 'D-PQ'),
    ('dominant_harmonic_order', 'Dominant Harmonic Order', 'derived', '', 'D-PQ'),

    # ── Derived: Energy deltas — today (4) ──
    ('active_energy_today_kwh', "Today's Active Energy", 'derived', 'kWh', 'D-E'),
    ('reactive_energy_today_kvarh', "Today's Reactive Energy", 'derived', 'kVARh', 'D-E'),
    ('apparent_energy_today_kvah', "Today's Apparent Energy", 'derived', 'kVAh', 'D-E'),
    ('loss_energy_today_kwh', 'Active Loss Energy Today', 'derived', 'kWh', 'D-PWR'),
    ('voltage_rate_change_v_per_min', 'Voltage Rate of Change', 'derived', 'V/min', 'D-V'),
    ('current_rate_change_a_per_min', 'Current Rate of Change', 'derived', 'A/min', 'D-I'),

    # ── Derived: Rates (2) ──
    ('power_rate_kw_per_h', 'Power Rate', 'derived', 'kW/h', 'D-PWR'),
    ('thd_movement_pct_per_h', 'THD Movement Rate', 'derived', '%/h', 'D-PQ'),

    # ── Derived: Today's peaks (value + timestamp pairs) (10) ──
    ('peak_demand_today_kw', "Today's Peak Demand", 'derived', 'kW', 'D-DMD'),
    ('peak_demand_at_time', "Today's Peak Demand At", 'derived', 'timestamp', 'D-DMD'),
    ('max_voltage_deviation_today_pct', 'Max V Deviation Today', 'derived', '%', 'D-V'),
    ('max_voltage_deviation_at_time', 'Max V Deviation At', 'derived', 'timestamp', 'D-V'),
    ('max_unbalance_today_pct', 'Max Unbalance Today', 'derived', '%', 'D-V'),
    ('max_unbalance_at_time', 'Max Unbalance At', 'derived', 'timestamp', 'D-V'),
    ('worst_spread_today_v', 'Worst V Spread Today', 'derived', 'V', 'D-V'),
    ('peak_current_today_a', "Today's Peak Current", 'derived', 'A', 'D-I'),
    ('avg_current_today_a', "Today's Average Current", 'derived', 'A', 'D-I'),
    ('max_current_unbalance_today_pct', 'Max I Unbalance Today', 'derived', '%', 'D-I'),

    # ── Derived: Trend status (4) ──
    ('power_trend_status', 'Power Trend', 'derived', '', 'D-TREND'),
    ('sec_trend_status', 'SEC Trend', 'derived', '', 'D-TREND'),
    ('load_factor_trend_status', 'Load Factor Trend', 'derived', '', 'D-TREND'),
    ('peak_demand_trend_status', 'Peak Demand Trend', 'derived', '', 'D-TREND'),

    # ── Derived: Sustained breach (2) ──
    ('sustained_thd_breach_active', 'Sustained THD Breach Active', 'derived', '', 'D-PQ'),
    ('sustained_thd_breach_started_at', 'Sustained THD Breach Since', 'derived', 'timestamp', 'D-PQ'),

    # ── Nested JSONB blobs (3) ──
    ('feeder_breakdown', 'Feeder Breakdown', 'derived', '', '8.2/8.4'),
    ('energy_cost_breakdown', 'Energy Cost Breakdown', 'derived', '', '2.5'),
    ('flags', 'Threshold Flags', 'derived', '', ''),
]


# LT Panel asset metrics — 42 columns added on top of COMMON_PARAMETERS
# (9 core LT 8.x + 6 windowed energy + 27 solar-incomer extras; solar cols are
# NULL for non-solar LT panels)
LT_PANEL_EXTRAS = [
    # ── LT-specific 8.x (9) ──
    ('distribution_loss_pct', 'Distribution Loss', 'derived', '%', '8.1'),
    ('load_balance_index', 'Load Balance Index', 'derived', '', '8.3'),
    ('demand_vs_rated_capacity_pct', 'Demand vs Rated Capacity', 'derived', '%', '8.5'),
    ('avg_vs_max_demand_gap_kva', 'Avg vs Max Demand Gap', 'derived', 'kVA', '8.6'),
    ('demand_growth_pct_per_month', 'Demand Growth / Month', 'derived', '%', '8.7'),
    ('breaker_trips_last_month', 'Breaker Trips Last Month', 'derived', 'count', '8.8'),
    ('thermal_overload_trend_pct', 'Thermal Overload Trend', 'derived', '%', '8.9'),
    ('busbar_temperature_c', 'Busbar Temperature', 'derived', '°C', '8.10'),
    ('busbar_temperature_rise_c', 'Busbar Temperature Rise', 'derived', '°C', '8.10'),

    # ── Week / month windowed energy (6) — LT-side billing dashboards ──
    ('active_energy_this_week_kwh',     "Week's Active Energy",     'derived', 'kWh',   'D-E'),
    ('reactive_energy_this_week_kvarh', "Week's Reactive Energy",   'derived', 'kVARh', 'D-E'),
    ('apparent_energy_this_week_kvah',  "Week's Apparent Energy",   'derived', 'kVAh',  'D-E'),
    ('active_energy_this_month_kwh',    "Month's Active Energy",    'derived', 'kWh',   'D-E'),
    ('reactive_energy_this_month_kvarh',"Month's Reactive Energy",  'derived', 'kVARh', 'D-E'),
    ('apparent_energy_this_month_kvah', "Month's Apparent Energy",  'derived', 'kVAh',  'D-E'),

    # ── Solar-Incomer extras (27) — populated only when load_profile == 'solar' ──
    # PV / DC-side (7)
    ('irradiance_w_per_m2',           'Irradiance',                 'derived', 'W/m²',  'D-SOLAR'),
    ('pv_dc_estimate_kw',             'PV DC Estimate',             'derived', 'kW',    'D-SOLAR'),
    ('pv_module_temperature_c',       'PV Module Temperature',      'derived', '°C',    'D-SOLAR'),
    ('dc_string_voltage_v',           'DC String Voltage',          'derived', 'V',     'D-SOLAR'),
    ('dc_string_current_a',           'DC String Current',          'derived', 'A',     'D-SOLAR'),
    ('pv_strings_healthy_count',      'PV Strings Healthy',         'derived', 'count', 'D-SOLAR'),
    ('pv_strings_watch_count',        'PV Strings on Watch',        'derived', 'count', 'D-SOLAR'),

    # Inverter DC→AC (4)
    ('inverter_status',               'Inverter Status',            'derived', '',      'D-SOLAR-INV'),
    ('inverter_temperature_c',        'Inverter Temperature',       'derived', '°C',    'D-SOLAR-INV'),
    ('inverter_efficiency_pct',       'Inverter Efficiency',        'derived', '%',     'D-SOLAR-INV'),
    ('dc_to_ac_loss_kw',              'DC-to-AC Loss',              'derived', 'kW',    'D-SOLAR-INV'),

    # Export / Grid handoff (5)
    ('pcc_accepted_kw',               'PCC Accepted Power',         'derived', 'kW',    'D-SOLAR-EXP'),
    ('mfm_export_kw',                 'MFM Export Power',           'derived', 'kW',    'D-SOLAR-EXP'),
    ('curtailment_kw',                'Curtailment',                'derived', 'kW',    'D-SOLAR-EXP'),
    ('pcc_feed_breaker_state',        'PCC Feed Breaker State',     'derived', '',      'D-SOLAR-EXP'),
    ('mfm_communication_status',      'MFM Communication Status',   'derived', '',      'D-SOLAR-EXP'),

    # IEC 61724 solar performance (5)
    ('performance_ratio_pct',         'Performance Ratio',          'derived', '%',       'D-SOLAR-PERF'),
    ('specific_yield_kwh_per_kwp',    'Specific Yield',             'derived', 'kWh/kWp', 'D-SOLAR-PERF'),
    ('capacity_utilization_factor_pct','Capacity Utilization Factor','derived', '%',      'D-SOLAR-PERF'),
    ('clear_sky_index',               'Clear Sky Index',            'derived', '',        'D-SOLAR-PERF'),
    ('daily_irradiance_wh_per_m2',    'Daily Irradiance',           'derived', 'Wh/m²',   'D-SOLAR-PERF'),

    # Generation peaks windowed (4)
    ('peak_generation_today_kw',          "Today's Peak Generation",     'derived', 'kW',        'D-PEAK'),
    ('peak_generation_today_at_time',     "Today's Peak Generation At",  'derived', 'timestamp', 'D-PEAK'),
    ('peak_irradiance_today_w_per_m2',    "Today's Peak Irradiance",     'derived', 'W/m²',      'D-PEAK'),
    ('peak_irradiance_today_at_time',     "Today's Peak Irradiance At",  'derived', 'timestamp', 'D-PEAK'),

    # Status composite (2)
    ('solar_components_warning_count', 'Solar Components on Warning', 'derived', 'count', 'D-SOLAR-STATUS'),
    ('solar_components_normal_count',  'Solar Components Normal',     'derived', 'count', 'D-SOLAR-STATUS'),
]


# UPS-specific battery / backup metrics — 12 columns
UPS_EXTRAS = [
    ('ups_actual_vs_rated_backup_min',  'UPS Backup vs Rated',           'derived', 'min',     'D-UPS'),
    ('ups_battery_aging_pct_per_year',  'UPS Battery Aging Rate',        'derived', '%/year',  'D-UPS'),
    ('ups_cycles_to_eol',               'UPS Cycles to End of Life',     'derived', 'cycles',  'D-UPS'),
    ('ups_charge_efficiency_pct',       'UPS Charge Efficiency',         'derived', '%',       'D-UPS'),
    ('ups_discharge_c_rate',            'UPS Discharge C-Rate',          'derived', 'C',       'D-UPS'),
    ('ups_energy_loss_kw',              'UPS Energy Loss',               'derived', 'kW',      'D-UPS'),
    ('ups_cost_per_month',              'UPS Cost / Month',              'derived', '₹',       'D-UPS'),
    ('ups_efficiency_at_load_pct',      'UPS Efficiency at Load',        'derived', '%',       'D-UPS'),
    ('ups_transfer_events_month',       'UPS Transfer Events / Month',   'derived', 'count',   'D-UPS'),
    ('ups_time_on_battery_hrs_month',   'UPS Time on Battery / Month',   'derived', 'h',       'D-UPS'),
    ('ups_mtbf_transfers_hrs',          'UPS MTBF Between Transfers',    'derived', 'h',       'D-UPS'),
    ('ups_bypass_utilization_pct',      'UPS Bypass Utilization',        'derived', '%',       'D-UPS'),
]


# APFC-specific compensation / capacitor metrics — 12 columns
APFC_EXTRAS = [
    ('apfc_pf_before',                   'APFC PF Before',                  'derived', '',        'D-APFC'),
    ('apfc_pf_after',                    'APFC PF After',                   'derived', '',        'D-APFC'),
    ('apfc_compensation_ratio_pct',      'APFC Compensation Ratio',         'derived', '%',       'D-APFC'),
    ('apfc_savings_per_month',           'APFC Savings / Month',            'derived', '₹',       'D-APFC'),
    ('apfc_penalty_avoided_per_month',   'APFC Penalty Avoided / Month',    'derived', '₹',       'D-APFC'),
    ('apfc_bank_utilization_pct',        'APFC Bank Utilization',           'derived', '%',       'D-APFC'),
    ('apfc_step_switching_duty',         'APFC Step Switching Duty',        'derived', '%',       'D-APFC'),
    ('apfc_cap_degradation_idx_pct',     'APFC Capacitor Degradation',      'derived', '%',       'D-APFC'),
    ('apfc_remaining_cap_life_months',   'APFC Remaining Capacitor Life',   'derived', 'months',  'D-APFC'),
    ('apfc_resonance_risk_hz',           'APFC Resonance Risk',             'derived', 'Hz',      'D-APFC'),
    ('apfc_detuning_effectiveness_pct',  'APFC Detuning Effectiveness',     'derived', '%',       'D-APFC'),
    ('apfc_compensation_flag',           'APFC Compensation Flag',          'derived', '',        'D-APFC'),
]


# UPS Overview / page-specific extras — 81 columns, no status tags (those live in WS).
# See PAGES_PARAMETER_SPEC.md `## UPS — Overview page` and `## UPS — Master parameter list`.
UPS_OVERVIEW_EXTRAS = [
    # ── Energy windowed (6) ──
    ('active_energy_this_week_kwh',          "Week's Active Energy",          'derived', 'kWh',       'D-E'),
    ('reactive_energy_this_week_kvarh',      "Week's Reactive Energy",        'derived', 'kVARh',     'D-E'),
    ('apparent_energy_this_week_kvah',       "Week's Apparent Energy",        'derived', 'kVAh',      'D-E'),
    ('active_energy_this_month_kwh',         "Month's Active Energy",         'derived', 'kWh',       'D-E'),
    ('reactive_energy_this_month_kvarh',     "Month's Reactive Energy",       'derived', 'kVARh',     'D-E'),
    ('apparent_energy_this_month_kvah',      "Month's Apparent Energy",       'derived', 'kVAh',      'D-E'),

    # ── Projection + budget delta (3) ──
    ('projected_eod_kwh',                    'Projected EOD Energy',          'derived', 'kWh',       'D-PROJ'),
    ('budget_delta_kwh',                     'Budget Delta',                  'derived', 'kWh',       'D-PROJ'),
    ('projected_power_kw',                   'Projected Power (15-min)',      'derived', 'kW',        'D-PROJ'),

    # ── Peak kW Load % windowed (6) ──
    ('peak_load_pct_today',                  "Today's Peak Load %",           'derived', '%',         'D-PEAK'),
    ('peak_load_pct_today_at_time',          "Today's Peak Load At",          'derived', 'timestamp', 'D-PEAK'),
    ('peak_load_pct_this_week',              "Week's Peak Load %",            'derived', '%',         'D-PEAK'),
    ('peak_load_pct_this_week_at_time',      "Week's Peak Load At",           'derived', 'timestamp', 'D-PEAK'),
    ('peak_load_pct_this_month',             "Month's Peak Load %",           'derived', '%',         'D-PEAK'),
    ('peak_load_pct_this_month_at_time',     "Month's Peak Load At",          'derived', 'timestamp', 'D-PEAK'),

    # ── Available capacity (1) ──
    ('available_capacity_pct',               'Available Capacity',            'derived', '%',         'D-PEAK'),

    # ── PF extras (2) ──
    ('harmonic_gap',                         'Harmonic Gap',                  'derived', '',          'D-PF'),
    ('last_pf_drop_at',                      'Last PF Drop At',               'derived', 'timestamp', 'D-PF'),

    # ── Frequency windowed (10) ──
    ('frequency_deviation_hz',                       'Frequency Deviation',           'derived', 'Hz',        'D-FREQ'),
    ('worst_frequency_today_hz',                     "Today's Worst Frequency",       'derived', 'Hz',        'D-FREQ'),
    ('worst_frequency_today_at_time',                "Today's Worst Frequency At",    'derived', 'timestamp', 'D-FREQ'),
    ('frequency_excursion_duration_today_sec',       "Today's Frequency Excursion",   'derived', 's',         'D-FREQ'),
    ('worst_frequency_this_week_hz',                 "Week's Worst Frequency",        'derived', 'Hz',        'D-FREQ'),
    ('worst_frequency_this_week_at_time',            "Week's Worst Frequency At",     'derived', 'timestamp', 'D-FREQ'),
    ('frequency_excursion_duration_this_week_sec',   "Week's Frequency Excursion",    'derived', 's',         'D-FREQ'),
    ('worst_frequency_this_month_hz',                "Month's Worst Frequency",       'derived', 'Hz',        'D-FREQ'),
    ('worst_frequency_this_month_at_time',           "Month's Worst Frequency At",    'derived', 'timestamp', 'D-FREQ'),
    ('frequency_excursion_duration_this_month_sec',  "Month's Frequency Excursion",   'derived', 's',         'D-FREQ'),

    # ── Busbar temperatures per phase (3) ──
    ('busbar_temperature_r_c',               'Busbar R Temperature',          'derived', '°C',        'D-THERM'),
    ('busbar_temperature_y_c',               'Busbar Y Temperature',          'derived', '°C',        'D-THERM'),
    ('busbar_temperature_b_c',               'Busbar B Temperature',          'derived', '°C',        'D-THERM'),

    # ── Peak flicker (2) ──
    ('peak_flicker_pst_today',               "Today's Peak Flicker Pst",      'derived', '',          'D-PQ'),
    ('peak_flicker_pst_at_time',             "Today's Peak Flicker At",       'derived', 'timestamp', 'D-PQ'),

    # ── V&C extras (2) ──
    ('neutral_peak_today_a',                 "Today's Neutral Peak",          'derived', 'A',         'D-I'),
    ('neutral_peak_events_today',            "Today's Neutral High Events",   'derived', 'count',     'D-I'),

    # ── Voltage rate-of-change (1) ──
    ('voltage_rate_change_v_per_min',        'Voltage Rate of Change',        'derived', 'V/min',     'D-V'),

    # ── UPS Overview screen extras (29) — battery / status / input / regulation ──
    # Battery side (8)
    ('ups_battery_temperature_c',     'Battery Temperature',           'derived', '°C',        'D-UPS-BAT'),
    ('ups_battery_soc_pct',           'Battery State of Charge',       'derived', '%',         'D-UPS-BAT'),
    ('ups_autonomy_min',              'Autonomy',                      'derived', 'min',       'D-UPS-BAT'),
    ('ups_protected_energy_kwh',      'Protected Energy',              'derived', 'kWh',       'D-UPS-BAT'),
    ('ups_last_test_at',              'Last Battery Test At',          'derived', 'timestamp', 'D-UPS-BAT'),
    ('ups_next_test_at',              'Next Battery Test At',          'derived', 'timestamp', 'D-UPS-BAT'),
    ('ups_days_since_last_test',      'Days Since Last Test',          'derived', 'day',       'D-UPS-BAT'),
    ('ups_days_to_next_test',         'Days to Next Test',             'derived', 'day',       'D-UPS-BAT'),

    # Status / mode (7)
    ('ups_operating_mode',            'Operating Mode',                'derived', '',          'D-UPS-MODE'),
    ('ups_rectifier_status',          'Rectifier Status',              'derived', '',          'D-UPS-MODE'),
    ('ups_inverter_status',           'Inverter Status',               'derived', '',          'D-UPS-MODE'),
    ('ups_bypass_sync_state',         'Bypass Sync State',             'derived', '',          'D-UPS-MODE'),
    ('ups_static_switch_state',       'Static Switch State',           'derived', '',          'D-UPS-MODE'),
    ('ups_sync_window_state',         'Sync Window State',             'derived', '',          'D-UPS-MODE'),
    ('ups_transfer_inhibit_reason',   'Transfer Inhibit Reason',       'derived', '',          'D-UPS-MODE'),

    # Input rectifier-side (5)
    ('ups_input_voltage_v',           'UPS Input Voltage',             'derived', 'V',         'D-UPS-IN'),
    ('ups_input_voltage_deviation_pct','UPS Input Voltage Deviation',  'derived', '%',         'D-UPS-IN'),
    ('ups_input_frequency_hz',        'UPS Input Frequency',           'derived', 'Hz',        'D-UPS-IN'),
    ('ups_input_current_a',           'UPS Input Current',             'derived', 'A',         'D-UPS-IN'),
    ('ups_input_source_status',       'UPS Input Source Status',       'derived', '',          'D-UPS-IN'),

    # Voltage regulation / load headroom (4)
    ('ups_voltage_regulation_pct',        'Voltage Regulation',        'derived', '%',         'D-UPS-VREG'),
    ('ups_output_input_voltage_delta_pct','Output-Input Voltage Delta','derived', '%',         'D-UPS-VREG'),
    ('ups_kva_free_kva',              'kVA Free',                      'derived', 'kVA',       'D-UPS-LOAD'),
    ('ups_kva_used_pct',              'kVA Used',                      'derived', '%',         'D-UPS-LOAD'),

    # Transfers / battery time — today (3)
    ('ups_transfer_events_today',     "Today's Transfer Events",       'derived', 'count',     'D-UPS-XFER'),
    ('ups_time_on_battery_today_sec', "Today's Time on Battery",       'derived', 's',         'D-UPS-XFER'),
    ('ups_last_transfer_at',          'Last Transfer At',              'derived', 'timestamp', 'D-UPS-XFER'),

    # Power-quality exposure (2)
    ('ups_thd_v_exposure_pct',        'THD V Exposure (24h)',          'derived', '%',         'D-UPS-PQ'),
    ('ups_thd_i_exposure_pct',        'THD I Exposure (24h)',          'derived', '%',         'D-UPS-PQ'),

    # ── Voltage phase-pair spreads (4) — mirror of current_spread_* in COMMON ──
    ('voltage_max_spread_v',          'Voltage Max Spread',            'derived', 'V', 'D-V'),
    ('voltage_spread_ry_v',           'Voltage Spread R-Y',            'derived', 'V', 'D-V'),
    ('voltage_spread_yb_v',           'Voltage Spread Y-B',            'derived', 'V', 'D-V'),
    ('voltage_spread_br_v',           'Voltage Spread B-R',            'derived', 'V', 'D-V'),

    # ── Worst-spread pair + primary event labels for V history (2) ──
    ('worst_spread_today_pair',       "Today's Worst Spread Pair",     'derived', '',  'D-V'),
    ('primary_voltage_event_today',   "Today's Primary Voltage Event", 'derived', '',  'D-V'),

    # ── UPS Power Quality screen (10) — 2 measured + 8 derived ──
    # Measured (M) — hardware status enums
    ('pq_filter_state',                'Filter State',                 'measured', '', 'D-PQ-STATE'),
    ('pq_capacitor_bank_state',        'Capacitor Bank State',         'measured', '', 'D-PQ-STATE'),

    # Derived (D) — labels + composites
    ('pq_dominant_harmonic_secondary', 'Secondary Dominant Harmonic',  'derived', '',     'D-PQ'),
    ('pq_critical_issue_type',         'Critical PQ Issue Type',       'derived', '',     'D-PQ'),
    ('pq_severity_label',              'PQ Severity Label',            'derived', '',     'D-PQ'),
    ('pq_active_issue_count',          'Active PQ Issue Count',        'derived', 'count','D-PQ'),
    ('pq_likely_source_label',         'Likely PQ Source',             'derived', '',     'D-PQ'),
    ('pq_next_priority_label',         'PQ Next Priority',             'derived', '',     'D-PQ'),
    ('pq_nonlinear_signature_label',   'Nonlinear Signature',          'derived', '',     'D-PQ'),
    ('pf_displacement_gap',            'PF Displacement Gap',          'derived', '',     'D-PQ'),
]


# Transformer-specific extras — 107 columns across 14 groups
# Derived from the Overview / RTM / Energy & Power / Voltage & Current / Thermal & Life
# / Loss Analysis / Power Quality / Harmonics pages (see PAGES_PARAMETER_SPEC.md).
TRANSFORMER_EXTRAS = [
    # ── Thermal & Cooling (12) ──
    ('winding_temperature_c',           'Winding Temperature',          'derived', '°C',     'D-THERM'),
    ('winding_hotspot_temperature_c',   'Winding Hot Spot Temperature', 'derived', '°C',     'D-THERM'),
    ('top_oil_temperature_c',           'Top Oil Temperature',          'derived', '°C',     'D-THERM'),
    ('oil_temperature_rise_c',          'Oil Temperature Rise',         'derived', '°C',     'D-THERM'),
    ('ambient_temperature_c',           'Ambient Temperature',          'derived', '°C',     'D-THERM'),
    ('temperature_rate_c_per_min',      'Temperature Rate',             'derived', '°C/min', 'D-THERM'),
    ('cooling_fan_1_status',            'Cooling Fan 1 Status',         'derived', '',       'D-THERM'),
    ('cooling_fan_2_status',            'Cooling Fan 2 Status',         'derived', '',       'D-THERM'),
    ('cooling_fan_3_status',            'Cooling Fan 3 Status',         'derived', '',       'D-THERM'),
    ('cooling_fan_4_status',            'Cooling Fan 4 Status',         'derived', '',       'D-THERM'),
    ('cooling_fans_active_count',       'Cooling Fans Active',          'derived', 'count',  'D-THERM'),
    ('cooling_pump_status',             'Cooling Pump Status',          'derived', '',       'D-THERM'),

    # ── Life / Aging / RUL (5) ──
    ('aging_rate_pu',                   'Aging Rate',                   'derived', 'pu',     'D-LIFE'),
    ('equivalent_life_consumed_years',  'Equivalent Life Consumed',     'derived', 'years',  'D-LIFE'),
    ('remaining_useful_life_years',     'Remaining Useful Life',        'derived', 'years',  'D-LIFE'),
    ('insulation_life_consumed_pct',    'Insulation Life Consumed',     'derived', '%',      'D-LIFE'),
    ('faa_acceleration_factor',         'FAA Acceleration Factor',      'derived', 'pu',     'D-LIFE'),

    # ── Efficiency / Losses (6) ──
    ('efficiency_pct',                  'Efficiency',                   'derived', '%',      'D-EFF'),
    ('total_loss_kw',                   'Total Loss',                   'derived', 'kW',     'D-EFF'),
    ('copper_loss_kw',                  'Copper Loss',                  'derived', 'kW',     'D-EFF'),
    ('iron_loss_kw',                    'Iron Loss',                    'derived', 'kW',     'D-EFF'),
    ('load_loss_kw',                    'Load Loss',                    'derived', 'kW',     'D-EFF'),
    ('stray_loss_kw',                   'Stray Loss',                   'derived', 'kW',     'D-EFF'),

    # ── Oil System (6) ──
    ('oil_level_pct',                   'Oil Level',                    'derived', '%',      'D-OIL'),
    ('oil_bdv_kv',                      'Oil BDV',                      'derived', 'kV',     'D-OIL'),
    ('oil_moisture_ppm',                'Oil Moisture',                 'derived', 'ppm',    'D-OIL'),
    ('oil_acidity_mg_koh',              'Oil Acidity',                  'derived', 'mg KOH', 'D-OIL'),
    ('oil_dga_total_ppm',               'Oil DGA Total',                'derived', 'ppm',    'D-OIL'),
    ('oil_sump_temperature_c',          'Oil Sump Temperature',         'derived', '°C',     'D-OIL'),

    # ── Bushings (6) ──
    ('hv_bushing_ir_test_gohm',         'HV Bushing IR Test',           'derived', 'GΩ',     'D-BUSH'),
    ('hv_bushing_leakage_ma',           'HV Bushing Leakage',           'derived', 'mA',     'D-BUSH'),
    ('hv_lv_ratio_deviation_pct',       'HV-LV Ratio Deviation',        'derived', '%',      'D-BUSH'),
    ('lv_bushing_contact_temp_c',       'LV Bushing Contact Temp',      'derived', '°C',     'D-BUSH'),
    ('lv_phase_loading_pct',            'LV Phase Loading',             'derived', '%',      'D-BUSH'),
    ('lv_voltage_regulation_pct',       'LV Voltage Regulation',        'derived', '%',      'D-BUSH'),

    # ── Tap Changer (4) ──
    ('tap_changer_position',            'Tap Changer Position',         'derived', '',       'D-TAP'),
    ('tap_changer_operations_count',    'Tap Changer Operations',       'derived', 'count',  'D-TAP'),
    ('tap_changer_motor_status',        'Tap Changer Motor Status',     'derived', '',       'D-TAP'),
    ('tap_changer_optimal_position',    'Tap Changer Optimal Position', 'derived', '',       'D-TAP'),

    # ── Buchholz Relay (3) ──
    ('buchholz_gas_volume_ml',                  'Buchholz Gas Volume',          'derived', 'ml',     'D-BUCH'),
    ('buchholz_gas_accumulation_rate_ml_per_day', 'Buchholz Gas Rate',          'derived', 'ml/day', 'D-BUCH'),
    ('buchholz_relay_status',                   'Buchholz Relay Status',        'derived', '',       'D-BUCH'),

    # ── PF extras (3) ──
    ('harmonic_gap',                    'Harmonic Gap',                 'derived', '',         'D-PF'),
    ('last_pf_drop_at',                 'Last PF Drop At',              'derived', 'timestamp','D-PF'),
    ('last_pf_drop_cause',              'Last PF Drop Cause',           'derived', '',         'D-PF'),

    # ── Frequency windowed (10) ──
    ('frequency_deviation_hz',                          'Frequency Deviation',          'derived', 'Hz',        'D-FREQ'),
    ('worst_frequency_today_hz',                        "Today's Worst Frequency",      'derived', 'Hz',        'D-FREQ'),
    ('worst_frequency_today_at_time',                   "Today's Worst Frequency At",   'derived', 'timestamp', 'D-FREQ'),
    ('frequency_excursion_duration_today_sec',          "Today's Frequency Excursion",  'derived', 's',         'D-FREQ'),
    ('worst_frequency_this_week_hz',                    "Week's Worst Frequency",       'derived', 'Hz',        'D-FREQ'),
    ('worst_frequency_this_week_at_time',               "Week's Worst Frequency At",    'derived', 'timestamp', 'D-FREQ'),
    ('frequency_excursion_duration_this_week_sec',      "Week's Frequency Excursion",   'derived', 's',         'D-FREQ'),
    ('worst_frequency_this_month_hz',                   "Month's Worst Frequency",      'derived', 'Hz',        'D-FREQ'),
    ('worst_frequency_this_month_at_time',              "Month's Worst Frequency At",   'derived', 'timestamp', 'D-FREQ'),
    ('frequency_excursion_duration_this_month_sec',     "Month's Frequency Excursion",  'derived', 's',         'D-FREQ'),

    # ── Peak Load % windowed (6) ──
    ('peak_load_pct_today',             "Today's Peak Load %",          'derived', '%',         'D-PEAK'),
    ('peak_load_pct_today_at_time',     "Today's Peak Load At",         'derived', 'timestamp', 'D-PEAK'),
    ('peak_load_pct_this_week',         "Week's Peak Load %",           'derived', '%',         'D-PEAK'),
    ('peak_load_pct_this_week_at_time', "Week's Peak Load At",          'derived', 'timestamp', 'D-PEAK'),
    ('peak_load_pct_this_month',        "Month's Peak Load %",          'derived', '%',         'D-PEAK'),
    ('peak_load_pct_this_month_at_time', "Month's Peak Load At",        'derived', 'timestamp', 'D-PEAK'),

    # ── Energy windowed (6) ──
    ('active_energy_this_week_kwh',     "Week's Active Energy",         'derived', 'kWh',    'D-E'),
    ('reactive_energy_this_week_kvarh', "Week's Reactive Energy",       'derived', 'kVARh',  'D-E'),
    ('apparent_energy_this_week_kvah',  "Week's Apparent Energy",       'derived', 'kVAh',   'D-E'),
    ('active_energy_this_month_kwh',    "Month's Active Energy",        'derived', 'kWh',    'D-E'),
    ('reactive_energy_this_month_kvarh', "Month's Reactive Energy",     'derived', 'kVARh',  'D-E'),
    ('apparent_energy_this_month_kvah', "Month's Apparent Energy",      'derived', 'kVAh',   'D-E'),

    # ── Issue counts (10) ──
    ('health_overall_status',           'Health Overall Status',        'derived', '',      'D-HEALTH'),
    ('issue_count_total',               'Total Issues',                 'derived', 'count', 'D-HEALTH'),
    ('issue_count_critical',            'Critical Issues',              'derived', 'count', 'D-HEALTH'),
    ('issue_count_warning',             'Warning Issues',               'derived', 'count', 'D-HEALTH'),
    ('issue_count_normal',              'Normal Issues',                'derived', 'count', 'D-HEALTH'),
    ('issue_count_electrical',          'Electrical Issues',            'derived', 'count', 'D-HEALTH'),
    ('issue_count_thermal',             'Thermal Issues',               'derived', 'count', 'D-HEALTH'),
    ('issue_count_oil_system',          'Oil System Issues',            'derived', 'count', 'D-HEALTH'),
    ('issue_count_protection',          'Protection Issues',            'derived', 'count', 'D-HEALTH'),
    ('issue_count_kpi',                 'KPI Issues',                   'derived', 'count', 'D-HEALTH'),

    # ── Hotspot composite statuses (12) ──
    ('status_conservator_tank',         'Conservator Tank Status',         'derived', '', 'D-STATUS'),
    ('status_lv_bushings',              'LV Bushings Status',              'derived', '', 'D-STATUS'),
    ('status_hv_bushings',              'HV Bushings Status',              'derived', '', 'D-STATUS'),
    ('status_pressure_relief_device',   'Pressure Relief Device Status',   'derived', '', 'D-STATUS'),
    ('status_buchholz_relay',           'Buchholz Relay Hotspot Status',   'derived', '', 'D-STATUS'),
    ('status_silica_gel_breather',      'Silica Gel Breather Status',      'derived', '', 'D-STATUS'),
    ('status_tap_changer',              'Tap Changer Hotspot Status',      'derived', '', 'D-STATUS'),
    ('status_radiator_bank',            'Radiator Bank Status',            'derived', '', 'D-STATUS'),
    ('status_winding_oil_temp',         'Winding & Oil Temp Status',       'derived', '', 'D-STATUS'),
    ('status_marshalling_box',          'Marshalling Box Status',          'derived', '', 'D-STATUS'),
    ('status_loading_efficiency',       'Loading & Efficiency Status',     'derived', '', 'D-STATUS'),
    ('status_rul_insulation_life',      'RUL & Insulation Life Status',    'derived', '', 'D-STATUS'),

    # ── Page-specific derived (18) ──
    ('projected_power_kw',              'Projected Power',                 'derived', 'kW',        'D-PROJ'),
    ('min_efficiency_today_pct',        "Today's Min Efficiency",          'derived', '%',         'D-EFF'),
    ('min_efficiency_today_at_time',    "Today's Min Efficiency At",       'derived', 'timestamp', 'D-EFF'),
    ('peak_hotspot_today_c',            "Today's Peak Hotspot Temp",       'derived', '°C',        'D-THERM'),
    ('peak_hotspot_at_time',            "Today's Peak Hotspot At",         'derived', 'timestamp', 'D-THERM'),
    ('derated_capacity_kva',            'Derated Capacity',                'derived', 'kVA',       'D-DERATE'),
    ('derating_headroom_kva',           'Derating Headroom',               'derived', 'kVA',       'D-DERATE'),
    ('derating_factor_pct',             'Derating Factor',                 'derived', '%',         'D-DERATE'),
    ('voltage_regulation_pct',          'Voltage Regulation',              'derived', '%',         'D-VREG'),
    ('voltage_drop_now_v',              'Voltage Drop Now',                'derived', 'V',         'D-VREG'),
    ('eddy_heating_multiplier',         'Eddy Heating Multiplier',         'derived', 'x',         'D-HARM'),
    ('harmonic_winding_heat_pct',       'Harmonic Winding Heat',           'derived', '%',         'D-HARM'),
    ('extra_harmonic_loss_pct',         'Extra Harmonic Loss',             'derived', '%',         'D-HARM'),
    ('hv_lv_voltage_ratio',             'HV-LV Voltage Ratio',             'derived', '',          'D-BUSH'),
    ('peak_flicker_pst_today',          "Today's Peak Flicker Pst",        'derived', '',          'D-PQ'),
    ('peak_flicker_pst_at_time',        "Today's Peak Flicker At",         'derived', 'timestamp', 'D-PQ'),
    ('primary_voltage_event_label',     'Primary Voltage Event',           'derived', '',          'D-EVT'),
    ('earth_fault_active',              'Earth Fault Active',              'derived', '',          'D-PROT'),
]


# Type code → full parameter list to seed for that type
TYPE_PARAMETERS = {
    'transformer': COMMON_PARAMETERS + TRANSFORMER_EXTRAS,
    'ht_panel':    COMMON_PARAMETERS,
    'lt_panel':    COMMON_PARAMETERS + LT_PANEL_EXTRAS,
    'ups':         COMMON_PARAMETERS + UPS_EXTRAS + UPS_OVERVIEW_EXTRAS,
    'apfc':        COMMON_PARAMETERS + APFC_EXTRAS,
}


class Command(BaseCommand):
    help = 'Seed Parameter rows for all 5 MFM types (Transformer, HT Panel, LT Panel, UPS, APFC).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--wipe',
            action='store_true',
            help='Delete all existing Parameter rows before seeding.',
        )

    def handle(self, *args, **opts):
        if opts['wipe']:
            n, _ = Parameter.objects.all().delete()
            self.stdout.write(f'Wiped {n} existing Parameter rows.')

        # Make sure each MFMType exists
        for code, name in [('transformer', 'Transformer'),
                           ('ht_panel',    'HT Panel'),
                           ('lt_panel',    'LT Panel'),
                           ('ups',         'UPS'),
                           ('apfc',        'APFC')]:
            MFMType.objects.get_or_create(code=code, defaults={'name': name})

        for code, params in TYPE_PARAMETERS.items():
            mt = MFMType.objects.get(code=code)
            created, updated = 0, 0
            for column_name, name, kind, unit, spec in params:
                _, was_created = Parameter.objects.update_or_create(
                    mfm_type=mt,
                    column_name=column_name,
                    defaults={'name': name, 'kind': kind, 'unit': unit, 'spec': spec},
                )
                if was_created:
                    created += 1
                else:
                    updated += 1
            total = mt.parameters.count()
            self.stdout.write(self.style.SUCCESS(
                f'  {code:12s}: seeded {len(params):3d} ({created} new, {updated} updated). Total in DB: {total}'
            ))
