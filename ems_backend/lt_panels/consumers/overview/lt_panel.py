"""Overview — LT Panel strategy (Solar Incomer flavour).

Targets the Solar Incomer Overview screen (URL:
  /equipment/pcc-panels/<pcc>/incoming/solar-incomer-<n>)

Widget layout (left→right, top→bottom on the page):

  header_status      status pill: "All 4 / 1 Warning / 3 Normal"
  header_kpis        Output · Irradiance · Efficiency · Export tiles
  kpi_live_output    big tile — AC output after inverter conversion
  kpi_irradiance     big tile — PV plane irradiance
  kpi_efficiency     big tile — DC→AC conversion %
  kpi_today          big tile — measured solar energy export today
  generation_profile chart    — hourly peak today + Generation vs Export lines
  source_accounting  StaticKpi block — PV DC est · Inverter AC · PCC accepted · Conversion loss
  operator_summary   StaticKpi block — Curtailment · String watch
  source_status      LiveBars — PV strings healthy / Inverter / MFM live / PCC feed
  ai_summary         Narrative

Solar-specific columns become NULL for non-solar LT panels (PCC, transformer
incomers, busbar feeders). Future: branch the widget set by panel load_profile.
"""
from .._overview_base import (
    BaseOverviewStrategy,
    LiveGauge, LiveSpark, LiveBars, StaticKpi, WindowedKpi, Narrative,
)
from .._common import (
    label_inverter_status, label_inverter_efficiency, label_irradiance,
    label_breaker_state, label_comm_status, label_strings_watch,
    label_curtailment, label_performance_ratio,
)


def _label_components(value):
    """Header pill status — warning_count > 0 means at least one component is unhealthy."""
    if value is None:
        return None
    return 'Warning' if value > 0 else 'Normal'


class LtPanelOverview(BaseOverviewStrategy):
    interval_seconds = 1.0

    widgets = [
        # ── Header status pill (All N / Warning / Normal) ───────────────
        StaticKpi(
            name='header_status',
            columns=[
                'solar_components_warning_count',
                'solar_components_normal_count',
            ],
            status=_label_components,
            status_column='solar_components_warning_count',
        ),

        # ── Header KPI strip (4 small tiles next to the asset name) ─────
        StaticKpi(
            name='header_kpis',
            columns=[
                'active_power_total_kw',     # Output (Live)
                'irradiance_w_per_m2',       # Irradiance
                'inverter_efficiency_pct',   # Efficiency (Good badge)
                'mfm_export_kw',             # Export (Metered)
            ],
            status=label_inverter_efficiency,
            status_column='inverter_efficiency_pct',
        ),

        # ── Big KPI cards (top-right grid of 4) ─────────────────────────
        LiveGauge(
            name='kpi_live_output',
            columns=['active_power_total_kw'],
        ),
        LiveGauge(
            name='kpi_irradiance',
            columns=['irradiance_w_per_m2'],
            status=label_irradiance, status_column='irradiance_w_per_m2',
        ),
        LiveGauge(
            name='kpi_efficiency',
            columns=['inverter_efficiency_pct'],
            status=label_inverter_efficiency, status_column='inverter_efficiency_pct',
        ),
        LiveGauge(
            name='kpi_today',
            columns=['active_energy_today_kwh'],
        ),

        # ── Generation Profile (today, hourly) ──────────────────────────
        # Live tick exposes the current peak + the latest two series points;
        # the full hourly trace is fetched via the GenerationHistory WS
        # (separate dispatcher — TODO if/when designed).
        LiveSpark(
            name='generation_profile',
            columns=[
                'peak_generation_today_kw',
                'peak_generation_today_at_time',
                'active_power_total_kw',     # Generation series point
                'pcc_accepted_kw',           # Export series point
            ],
        ),

        # ── Source Accounting (DC → AC → PCC handoff) ───────────────────
        StaticKpi(
            name='source_accounting',
            columns=[
                'pv_dc_estimate_kw',         # PV DC estimate
                'active_power_total_kw',     # Inverter AC
                'pcc_accepted_kw',           # PCC accepted
                'dc_to_ac_loss_kw',          # Conversion loss
            ],
        ),

        # ── Operator Summary (curtailment + string watch) ───────────────
        StaticKpi(
            name='operator_summary',
            columns=[
                'curtailment_kw',
                'pv_strings_watch_count',
                'pv_strings_healthy_count',
            ],
            status=label_curtailment, status_column='curtailment_kw',
        ),

        # ── Solar Source Overview (status row of 4 pills) ───────────────
        LiveBars(
            name='source_status',
            columns=[
                'pv_strings_healthy_count',  # PV strings healthy
                'pv_strings_watch_count',
                'inverter_status',           # Inverter online
                'mfm_communication_status',  # MFM-004 live
                'pcc_feed_breaker_state',    # PCC feed closed
            ],
            status=label_inverter_status, status_column='inverter_status',
        ),

        # ── Performance side-card (IEC 61724) — optional drill-in ───────
        StaticKpi(
            name='performance',
            columns=[
                'performance_ratio_pct',
                'specific_yield_kwh_per_kwp',
                'capacity_utilization_factor_pct',
                'clear_sky_index',
                'daily_irradiance_wh_per_m2',
            ],
            status=label_performance_ratio, status_column='performance_ratio_pct',
        ),

        # ── DC-side inverter detail (drill-in) ──────────────────────────
        StaticKpi(
            name='inverter_detail',
            columns=[
                'inverter_status',
                'inverter_temperature_c',
                'pv_module_temperature_c',
                'dc_string_voltage_v',
                'dc_string_current_a',
            ],
            status=label_inverter_status, status_column='inverter_status',
        ),

        # ── Status pills used by the schematic ──────────────────────────
        StaticKpi(
            name='pcc_feed_status',
            columns=['pcc_feed_breaker_state'],
            status=label_breaker_state, status_column='pcc_feed_breaker_state',
        ),
        StaticKpi(
            name='mfm_comm_status',
            columns=['mfm_communication_status'],
            status=label_comm_status, status_column='mfm_communication_status',
        ),
        StaticKpi(
            name='pv_string_health',
            columns=['pv_strings_watch_count', 'pv_strings_healthy_count'],
            status=label_strings_watch, status_column='pv_strings_watch_count',
        ),

        # ── Range-filtered: peak generation across windows (TODO once
        # the WindowedKpi slow loop is wired in _overview_base) ──────────
        WindowedKpi(
            name='peak_generation_windowed',
            columns=[
                'peak_generation_today_kw',
                'peak_generation_today_at_time',
                'peak_irradiance_today_w_per_m2',
                'peak_irradiance_today_at_time',
            ],
            ranges=['today', 'this_week', 'this_month'],
            default_range='today',
        ),

        # ── AI narrative banner ─────────────────────────────────────────
        Narrative(name='ai_summary', refresh_seconds=10.0),
    ]
