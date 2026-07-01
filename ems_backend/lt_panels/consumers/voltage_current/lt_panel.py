"""Voltage & Current — LT panel (PCC) strategy.

Ported from legacy VoltageCurrentLiveConsumer.
"""
from .._base import BaseLiveStrategy
from .._common import (
    label_voltage_deviation, label_voltage_unbalance,
    label_current_unbalance, label_neutral_ratio,
)


class LtPanelVoltageCurrent(BaseLiveStrategy):
    columns = [
        # Voltage
        'voltage_r_n', 'voltage_y_n', 'voltage_b_n',
        'voltage_avg', 'voltage_max', 'voltage_min',
        'voltage_r_deviation_pct', 'voltage_y_deviation_pct', 'voltage_b_deviation_pct',
        'kpi_voltage_deviation_pct',
        'voltage_unbalance_pct',
        # Current
        'current_r', 'current_y', 'current_b', 'current_neutral',
        'current_avg', 'current_max', 'current_min',
        'current_r_deviation_pct', 'current_y_deviation_pct', 'current_b_deviation_pct',
        'current_unbalance_pct',
        'current_max_spread', 'current_spread_br', 'current_spread_ry', 'current_spread_by',
        'kpi_neutral_to_phase_ratio_pct',
        # 60-s rolling rate-of-change (detail V&C rate-of-change card)
        'voltage_rate_change_v_per_min', 'current_rate_change_a_per_min',
        # Today's event counters
        'sag_events_24h', 'swell_events_24h',
    ]
    status_rules = {
        'voltage_r_deviation_pct':        label_voltage_deviation,
        'voltage_y_deviation_pct':        label_voltage_deviation,
        'voltage_b_deviation_pct':        label_voltage_deviation,
        'kpi_voltage_deviation_pct':      label_voltage_deviation,
        'voltage_unbalance_pct':          label_voltage_unbalance,
        'current_r_deviation_pct':        label_voltage_deviation,
        'current_y_deviation_pct':        label_voltage_deviation,
        'current_b_deviation_pct':        label_voltage_deviation,
        'current_unbalance_pct':          label_current_unbalance,
        'kpi_neutral_to_phase_ratio_pct': label_neutral_ratio,
    }
