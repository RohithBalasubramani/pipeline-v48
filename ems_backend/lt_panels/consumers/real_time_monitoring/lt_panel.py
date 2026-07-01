"""Real Time Monitoring — LT panel (PCC) strategy.

Ported verbatim from the legacy MFMLiveConsumer.COLUMNS list.
"""
from .._base import BaseLiveStrategy


class LtPanelRealTimeMonitoring(BaseLiveStrategy):
    columns = [
        # Power & Energy
        'active_power_total_kw', 'reactive_power_total_kvar', 'apparent_power_total_kva',
        'active_energy_import_kwh', 'reactive_energy_import_kvarh',
        'rate_of_change_power_kw_per_min',
        # Voltage
        'voltage_r_n', 'voltage_y_n', 'voltage_b_n',
        'voltage_avg', 'voltage_max', 'voltage_min',
        # Current
        'current_r', 'current_y', 'current_b', 'current_neutral',
        'current_avg', 'current_max', 'current_min',
    ]
    # No status rules on the legacy RTM consumer.
    status_rules = {}
