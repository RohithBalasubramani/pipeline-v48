"""Shared status-label callables used across per-type strategies.

Each function takes a single value and returns a label string (or None when
the value is missing). Strategies wire these into their `status_rules` dict.

This package was atomised from a former single `_common.py` module: the public
surface is unchanged — `from .._common import label_pf` (etc.) keeps working
because every name is re-exported here. Callables are grouped by concern into
single-purpose sub-modules.
"""

from .energy_power import (
    label_power_rate,
    label_loss_pct,
    label_capacity_pct,
)
from .power_quality_summary import (
    label_flicker_pst,
    label_crest_factor,
    label_thd_movement,
    label_ieee519,
    label_pq_severity,
    label_pq_filter_state,
    label_pq_capacitor_bank,
    label_pq_active_issues,
    label_pf_displacement_gap,
)
from .distortion_harmonics import (
    label_pf,
    label_v_thd,
    label_i_thd,
    label_k_factor,
    label_phase_angle,
)
from .voltage_current import (
    label_voltage_deviation,
    label_voltage_unbalance,
    label_current_unbalance,
    label_neutral_ratio,
)
from .solar import (
    label_inverter_status,
    label_inverter_efficiency,
    label_irradiance,
    label_breaker_state,
    label_comm_status,
    label_strings_watch,
    label_curtailment,
    label_performance_ratio,
)
from .ups import (
    label_ups_mode,
    label_ups_subsystem_status,
    label_ups_bypass_sync,
    label_ups_static_switch,
    label_ups_sync_window,
    label_ups_input_source,
    label_ups_battery_temp,
    label_ups_battery_soc,
    label_ups_autonomy,
    label_ups_loading,
    label_voltage_regulation,
    label_thd_exposure,
    label_transfer_inhibit,
)

__all__ = [
    # energy_power
    'label_power_rate',
    'label_loss_pct',
    'label_capacity_pct',
    # power_quality_summary
    'label_flicker_pst',
    'label_crest_factor',
    'label_thd_movement',
    'label_ieee519',
    'label_pq_severity',
    'label_pq_filter_state',
    'label_pq_capacitor_bank',
    'label_pq_active_issues',
    'label_pf_displacement_gap',
    # distortion_harmonics
    'label_pf',
    'label_v_thd',
    'label_i_thd',
    'label_k_factor',
    'label_phase_angle',
    # voltage_current
    'label_voltage_deviation',
    'label_voltage_unbalance',
    'label_current_unbalance',
    'label_neutral_ratio',
    # solar
    'label_inverter_status',
    'label_inverter_efficiency',
    'label_irradiance',
    'label_breaker_state',
    'label_comm_status',
    'label_strings_watch',
    'label_curtailment',
    'label_performance_ratio',
    # ups
    'label_ups_mode',
    'label_ups_subsystem_status',
    'label_ups_bypass_sync',
    'label_ups_static_switch',
    'label_ups_sync_window',
    'label_ups_input_source',
    'label_ups_battery_temp',
    'label_ups_battery_soc',
    'label_ups_autonomy',
    'label_ups_loading',
    'label_voltage_regulation',
    'label_thd_exposure',
    'label_transfer_inhibit',
]
