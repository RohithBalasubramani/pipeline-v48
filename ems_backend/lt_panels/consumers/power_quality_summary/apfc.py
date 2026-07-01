"""Power Quality summary — APFC strategy.

APFC's PQ tab focus is on capacitor compensation health:
  - PF before / after compensation
  - Compensation ratio %
  - Bank utilization %, step switching duty, capacitor degradation
  - Resonance risk Hz, detuning effectiveness
  - Remaining capacitor life (months)

Plus the standard Path A PQ labels (severity, issue type, source, action,
filter, cap bank, next priority, nonlinear signature) — derived in
`compute_status` from the same raw cols every type has.
"""
from .lt_panel import LtPanelPowerQualitySummary
from .._common import label_pf, label_capacity_pct


class ApfcPowerQualitySummary(LtPanelPowerQualitySummary):
    columns = LtPanelPowerQualitySummary.columns + [
        # APFC-specific compensation telemetry
        'apfc_pf_before',
        'apfc_pf_after',
        'apfc_compensation_ratio_pct',
        'apfc_bank_utilization_pct',
        'apfc_step_switching_duty',
        'apfc_cap_degradation_idx_pct',
        'apfc_remaining_cap_life_months',
        'apfc_resonance_risk_hz',
        'apfc_detuning_effectiveness_pct',
        'apfc_compensation_flag',
    ]
    status_rules = {
        **LtPanelPowerQualitySummary.status_rules,
        'apfc_pf_before':              label_pf,
        'apfc_pf_after':               label_pf,
        'apfc_bank_utilization_pct':   label_capacity_pct,
        'apfc_compensation_ratio_pct': label_capacity_pct,
    }
