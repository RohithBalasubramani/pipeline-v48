"""Overview — UPS strategy.

Targets the UPS Overview screen (URL:
  /equipment/pcc-panels/<pcc>/ups/ups-<n>)

Widget layout (top → bottom on the page):

  header_loading       Loading %      pill  — kpi_kw_load_pct_of_rated
  header_battery_temp  Battery temp   pill  — ups_battery_temperature_c
  header_autonomy      Autonomy       pill  — ups_autonomy_min
  header_i_unbalance   I unbalance    pill  — current_unbalance_pct

  ai_summary           narrative banner (operating mode, source, kW @ Hz, autonomy)

  input_vs_output_voltage   INPUT V · OUTPUT V · Δ% · regulation%
  output_load               kVA · used% · free kVA · active kW · rated kVA
  output_frequency          Hz · deviation Hz · sync window · transfer inhibit
  output_phase_balance      unbalance% · R/Y/B/N currents · neutral/avg

  rectifier_status   OK pill — "Online · AC-DC healthy"
  inverter_status    OK pill — "Online · DC-AC carrying load"
  bypass_sync        OK pill — "Locked · Sync window ready"
  static_switch      OK pill — "Armed · Transfer available"

  energy_autonomy    Reserve runway · SOC · Protected kWh · Transfers · Test cadence
  output_power_quality  THD V/I · PF · Crest · THD V exposure
"""
from .._overview_base import (
    BaseOverviewStrategy,
    LiveGauge, LiveSpark, LiveBars, StaticKpi, Narrative,
)
from .._common import (
    label_current_unbalance, label_voltage_unbalance, label_pf,
    label_ups_mode, label_ups_subsystem_status, label_ups_bypass_sync,
    label_ups_static_switch, label_ups_sync_window, label_ups_input_source,
    label_ups_battery_temp, label_ups_battery_soc, label_ups_autonomy,
    label_ups_loading, label_voltage_regulation, label_thd_exposure,
    label_transfer_inhibit,
)


class UpsOverview(BaseOverviewStrategy):
    interval_seconds = 1.0

    widgets = [
        # ── Header status strip (4 small pills) ─────────────────────────
        StaticKpi(
            name='header_loading',
            columns=['kpi_kw_load_pct_of_rated'],
            status=label_ups_loading, status_column='kpi_kw_load_pct_of_rated',
        ),
        StaticKpi(
            name='header_battery_temp',
            columns=['ups_battery_temperature_c'],
            status=label_ups_battery_temp, status_column='ups_battery_temperature_c',
        ),
        StaticKpi(
            name='header_autonomy',
            columns=['ups_autonomy_min', 'ups_battery_soc_pct'],
            status=label_ups_autonomy, status_column='ups_autonomy_min',
        ),
        StaticKpi(
            name='header_i_unbalance',
            columns=['current_unbalance_pct'],
            status=label_current_unbalance, status_column='current_unbalance_pct',
        ),

        # ── Input vs Output Voltage card ─────────────────────────────────
        LiveGauge(
            name='input_vs_output_voltage',
            columns=[
                'ups_input_voltage_v',                  # INPUT 416 V
                'ups_input_voltage_deviation_pct',      # +0.3% from nominal
                'voltage_avg',                          # OUTPUT 418 V
                'kpi_voltage_deviation_pct',            # +0.8% from nominal
                'ups_output_input_voltage_delta_pct',   # Δ +0.5%
                'ups_voltage_regulation_pct',           # regulation +0.5%
            ],
            status=label_voltage_regulation,
            status_column='ups_voltage_regulation_pct',
        ),

        # ── Output Load card ─────────────────────────────────────────────
        LiveGauge(
            name='output_load',
            columns=[
                'apparent_power_total_kva',     # 192 kVA
                'active_power_total_kw',        # 170 kW active
                'kpi_kw_load_pct_of_rated',     # used 33%
                'ups_kva_used_pct',
                'ups_kva_free_kva',             # 400 kVA free
            ],
            status=label_ups_loading,
            status_column='kpi_kw_load_pct_of_rated',
        ),

        # ── Output Frequency card ────────────────────────────────────────
        LiveSpark(
            name='output_frequency',
            columns=[
                'frequency_hz',                  # 49.99 Hz
                'frequency_deviation_hz',        # -0.012 Hz
                'ups_sync_window_state',         # Available
                'ups_transfer_inhibit_reason',   # None
            ],
            status=label_ups_sync_window,
            status_column='ups_sync_window_state',
        ),

        # ── Output Phase Balance card ────────────────────────────────────
        LiveBars(
            name='output_phase_balance',
            columns=[
                'voltage_unbalance_pct',         # 7.4%
                'current_r', 'current_y', 'current_b', 'current_neutral',
                'current_avg',
            ],
            status=label_voltage_unbalance,
            status_column='voltage_unbalance_pct',
        ),

        # ── Four subsystem status pills ──────────────────────────────────
        StaticKpi(
            name='rectifier_status',
            columns=['ups_rectifier_status'],
            status=label_ups_subsystem_status,
            status_column='ups_rectifier_status',
        ),
        StaticKpi(
            name='inverter_status',
            columns=['ups_inverter_status'],
            status=label_ups_subsystem_status,
            status_column='ups_inverter_status',
        ),
        StaticKpi(
            name='bypass_sync',
            columns=['ups_bypass_sync_state', 'ups_sync_window_state'],
            status=label_ups_bypass_sync,
            status_column='ups_bypass_sync_state',
        ),
        StaticKpi(
            name='static_switch',
            columns=['ups_static_switch_state', 'ups_transfer_inhibit_reason'],
            status=label_ups_static_switch,
            status_column='ups_static_switch_state',
        ),

        # ── Energy & Autonomy card ───────────────────────────────────────
        StaticKpi(
            name='energy_autonomy',
            columns=[
                'ups_autonomy_min',              # 44 min reserve runway
                'ups_battery_soc_pct',           # 92% SOC
                'kpi_kw_load_pct_of_rated',      # at 33% load
                'ups_protected_energy_kwh',      # 17,708 kWh
                'ups_transfer_events_today',     # transfers today
                'ups_transfer_events_month',     # transfers this month
                'ups_time_on_battery_today_sec',
                'ups_last_transfer_at',
                'ups_days_since_last_test',      # 3m
                'ups_days_to_next_test',         # 19d
            ],
            status=label_ups_battery_soc,
            status_column='ups_battery_soc_pct',
        ),

        # ── Output Power Quality card ────────────────────────────────────
        StaticKpi(
            name='output_power_quality',
            columns=[
                'thd_voltage_r_pct', 'thd_voltage_y_pct', 'thd_voltage_b_pct',
                'thd_current_r_pct', 'thd_current_y_pct', 'thd_current_b_pct',
                'power_factor_total',
                'crest_factor_current',
                'crest_factor_voltage',
                'ups_thd_v_exposure_pct',
                'ups_thd_i_exposure_pct',
            ],
            status=label_thd_exposure,
            status_column='ups_thd_v_exposure_pct',
        ),

        # ── Mode banner / AI summary drivers ─────────────────────────────
        StaticKpi(
            name='operating_mode',
            columns=[
                'ups_operating_mode',
                'ups_input_source_status',
                'active_power_total_kw',
                'frequency_hz',
                'ups_autonomy_min',
            ],
            status=label_ups_mode,
            status_column='ups_operating_mode',
        ),
        StaticKpi(
            name='input_source',
            columns=['ups_input_source_status'],
            status=label_ups_input_source,
            status_column='ups_input_source_status',
        ),
        StaticKpi(
            name='transfer_inhibit',
            columns=['ups_transfer_inhibit_reason'],
            status=label_transfer_inhibit,
            status_column='ups_transfer_inhibit_reason',
        ),

        # ── Drill-in detail for the Power Quality card ───────────────────
        StaticKpi(
            name='power_factor',
            columns=['power_factor_total', 'kpi_displacement_pf', 'kpi_true_pf',
                     'harmonic_gap'],
            status=label_pf, status_column='power_factor_total',
        ),

        # ── AI narrative banner ─────────────────────────────────────────
        Narrative(name='ai_summary', refresh_seconds=10.0),
    ]
