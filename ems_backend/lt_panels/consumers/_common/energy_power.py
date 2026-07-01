"""Energy & Power status-label callables.

Each function takes a single value and returns a label string (or None when
the value is missing). Strategies wire these into their `status_rules` dict.
"""


def label_power_rate(value):
    if value is None:
        return None
    if value > 1.0:
        return 'Rising'
    if value < -1.0:
        return 'Falling'
    return 'Steady'


def label_loss_pct(value):
    if value is None:
        return None
    if value < 5.0:
        return 'Low'
    if value < 10.0:
        return 'Normal'
    if value < 12.0:
        return 'Elevated'
    return 'High'


def label_capacity_pct(value):
    if value is None:
        return None
    if value < 70.0:
        return 'On track'
    if value < 90.0:
        return 'Watch'
    return 'Critical'
