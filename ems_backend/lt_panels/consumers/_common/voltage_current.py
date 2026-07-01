"""Voltage & Current status-label callables.

Each function takes a single value and returns a label string (or None when
the value is missing). Strategies wire these into their `status_rules` dict.
"""


def label_voltage_deviation(value):
    if value is None:
        return None
    av = abs(value)
    if av <= 3:
        return 'Normal'
    if av <= 5:
        return 'Watch'
    return 'Critical'


def label_voltage_unbalance(value):
    if value is None:
        return None
    if value < 2:
        return 'Normal'
    if value < 3:
        return 'Watch'
    return 'High'


def label_current_unbalance(value):
    if value is None:
        return None
    if value < 10:
        return 'Normal'
    if value < 20:
        return 'Elevated'
    return 'High'


def label_neutral_ratio(value):
    if value is None:
        return None
    av = abs(value)
    if av < 10:
        return 'Normal'
    if av < 20:
        return 'Elevated'
    return 'High'
