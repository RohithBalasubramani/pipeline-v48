"""Distortion & Harmonics status-label callables.

Each function takes a single value and returns a label string (or None when
the value is missing). Strategies wire these into their `status_rules` dict.
"""


def label_pf(value):
    if value is None:
        return None
    if value >= 0.95:
        return 'Excellent'
    if value >= 0.90:
        return 'Good'
    if value >= 0.85:
        return 'Acceptable'
    return 'Poor'


def label_v_thd(value):
    if value is None:
        return None
    if value < 5:
        return 'Pass'
    if value < 6:
        return 'Watch'
    return 'Fail'


def label_i_thd(value):
    if value is None:
        return None
    if value < 6:
        return 'Pass'
    if value < 8:
        return 'Watch'
    return 'Fail'


def label_k_factor(value):
    if value is None:
        return None
    if value < 4:
        return 'Normal'
    if value < 7:
        return 'Watch'
    return 'High'


def label_phase_angle(value):
    if value is None:
        return None
    av = abs(value)
    if av < 20:
        return 'Normal'
    if av < 25:
        return 'Watch'
    return 'High'
