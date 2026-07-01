"""Overview — APFC strategy.

Per-MFM widget envelope (column-row backed). APFC's purpose is automatic
PF correction, so the Overview headline is the PF tile + compensation
ratio + capacitor bank health + monthly savings.

This is a "good-enough" first cut — when an APFC-specific UI spec
lands, swap the widget list for the actual layout.
"""
from .._overview_base import (
    BaseOverviewStrategy,
    LiveGauge, LiveSpark, StaticKpi, Narrative,
)
from .._common import (
    label_pf, label_capacity_pct, label_voltage_unbalance, label_current_unbalance,
)


class ApfcOverview(BaseOverviewStrategy):
    interval_seconds = 1.0

    widgets = [
        # ── Headline PF + compensation effectiveness ─────────────────────
        LiveGauge(
            name='power_factor',
            columns=[
                'power_factor_total',
                'kpi_displacement_pf',
                'kpi_true_pf',
                'apfc_pf_before',
                'apfc_pf_after',
            ],
            status=label_pf, status_column='power_factor_total',
        ),
        StaticKpi(
            name='compensation_ratio',
            columns=['apfc_compensation_ratio_pct'],
            status=label_capacity_pct, status_column='apfc_compensation_ratio_pct',
        ),

        # ── Capacitor bank health ────────────────────────────────────────
        StaticKpi(
            name='bank_health',
            columns=[
                'apfc_bank_utilization_pct',
                'apfc_step_switching_duty',
                'apfc_cap_degradation_idx_pct',
                'apfc_remaining_cap_life_months',
            ],
            status=label_capacity_pct, status_column='apfc_bank_utilization_pct',
        ),
        StaticKpi(
            name='resonance',
            columns=[
                'apfc_resonance_risk_hz',
                'apfc_detuning_effectiveness_pct',
                'apfc_compensation_flag',
            ],
        ),

        # ── Savings / monetary impact ────────────────────────────────────
        StaticKpi(
            name='savings',
            columns=[
                'apfc_savings_per_month',
                'apfc_penalty_avoided_per_month',
            ],
        ),

        # ── Standard headline KPIs (same as transformer overview) ───────
        StaticKpi(name='loading',
                  columns=['kpi_kw_load_pct_of_rated'],
                  status=label_capacity_pct,
                  status_column='kpi_kw_load_pct_of_rated'),
        StaticKpi(name='voltage_balance',
                  columns=['voltage_unbalance_pct'],
                  status=label_voltage_unbalance,
                  status_column='voltage_unbalance_pct'),
        StaticKpi(name='current_balance',
                  columns=['current_unbalance_pct'],
                  status=label_current_unbalance,
                  status_column='current_unbalance_pct'),

        # ── Grid frequency spark ─────────────────────────────────────────
        LiveSpark(
            name='grid_frequency',
            columns=['frequency_hz'],
        ),

        # ── AI narrative banner ─────────────────────────────────────────
        Narrative(name='ai_summary', refresh_seconds=10.0),
    ]
