"""Overview — Transformer strategy.

Widget catalogue from Appendix A.1 of the plan
(/home/rohith/.claude/plans/now-we-need-websockets-polymorphic-lightning.md).

Column names below are PLACEHOLDERS taken from the widget intent. The fetch
layer (services._select_existing) silently drops columns that don't exist on
the panel_readings table and pads them with None in the response — so the
widget envelopes keep their full shape and the user can swap real column
names in widget by widget without breaking anything.

  ## TODO map widget → real column names (from user)
  power_factor:        pf_total / displacement / true / harmonic_gap / last_pf_drop
  voltage_deviation:   voltage_avg / voltage_nominal_v / voltage_deviation_pct
  grid_frequency:      frequency_hz / deviation_hz / worst_today / worst_at / duration
  phase_balance:       i_R / i_Y / i_B / i_N / unbalance_pct / avg_phase
  k_factor / hlf / ieee_519
  loading / hot_spot / efficiency / rul   (header KPI strip)
  energy_consumption:  windowed; today / this_week / this_month
  kw_load_pct:         load_pct / load_kw / rated_kw / peak_pct_today
  ai_summary:          narrative
"""
from .._overview_base import (
    BaseOverviewStrategy,
    LiveGauge, LiveSpark, LiveBars, StaticKpi, WindowedKpi, Narrative,
)
from .._common import (
    label_pf, label_voltage_deviation, label_voltage_unbalance, label_k_factor,
)


class TransformerOverview(BaseOverviewStrategy):
    interval_seconds = 1.0

    widgets = [
        # ── Live gauges ─────────────────────────────────────────────────
        LiveGauge(
            name='power_factor',
            columns=[
                'power_factor_total',  # TODO: confirm — driving value
                'kpi_displacement_pf',
                'kpi_true_pf',
                'harmonic_gap',        # TODO: confirm column name
            ],
            status=label_pf, status_column='power_factor_total',
            last_event_query='last_pf_drop',  # TODO: implement event lookup
        ),
        LiveGauge(
            name='voltage_deviation',
            columns=[
                'voltage_avg',
                'voltage_nominal_v',           # TODO: confirm
                'kpi_voltage_deviation_pct',
            ],
            status=label_voltage_deviation, status_column='kpi_voltage_deviation_pct',
        ),
        # ── Live sparkline ─────────────────────────────────────────────
        LiveSpark(
            name='grid_frequency',
            columns=[
                'frequency_hz',                # TODO: confirm
                'frequency_deviation_hz',      # TODO
                'worst_freq_today_hz',         # TODO
                'worst_freq_today_at',         # TODO
                'worst_freq_duration_s',       # TODO
            ],
        ),
        # ── Live bars (R/Y/B/N) ────────────────────────────────────────
        LiveBars(
            name='phase_balance',
            columns=[
                'current_r', 'current_y', 'current_b', 'current_neutral',
                'voltage_unbalance_pct',
                'current_avg',
            ],
            status=label_voltage_unbalance, status_column='voltage_unbalance_pct',
        ),
        # ── KPI cards ──────────────────────────────────────────────────
        StaticKpi(name='k_factor',  columns=['k_factor'],
                  status=label_k_factor, status_column='k_factor'),
        StaticKpi(name='hlf',       columns=['harmonic_loss_factor_fhl']),
        StaticKpi(name='ieee_519',
                  columns=['thd_compliance_ieee519',
                           'thd_voltage_r_pct', 'thd_current_r_pct', 'k_factor']),
        # ── Header KPI strip ───────────────────────────────────────────
        StaticKpi(name='loading',    columns=['kpi_kw_load_pct_of_rated']),
        StaticKpi(name='hot_spot',   columns=['hot_spot_c']),       # TODO
        StaticKpi(name='efficiency', columns=['efficiency_pct']),   # TODO
        StaticKpi(name='rul',        columns=['rul_years']),        # TODO
        # ── Range-filtered widgets ─────────────────────────────────────
        # TODO: dispatcher slow-cadence loop + range-filter receive() handler
        WindowedKpi(
            name='energy_consumption',
            columns=['active_kwh', 'reactive_kvarh', 'subsidy_kwh'],   # TODO: confirm aggregations
            ranges=['today', 'this_week', 'this_month'],
            default_range='today',
        ),
        WindowedKpi(
            name='kw_load_pct',
            columns=['kpi_kw_load_pct_of_rated', 'active_power_total_kw',
                     'rated_kw', 'peak_pct_today'],                    # TODO
        ),
        # ── AI narrative ───────────────────────────────────────────────
        # TODO: implement narrative generation in dispatcher slow loop
        Narrative(name='ai_summary', refresh_seconds=10.0),
    ]
