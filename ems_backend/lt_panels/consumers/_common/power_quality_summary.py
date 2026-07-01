"""Power Quality summary status-label callables.

Each function takes a single value and returns a label string (or None when
the value is missing). Strategies wire these into their `status_rules` dict.
"""


def label_flicker_pst(value):
    if value is None:
        return None
    if value < 0.5:
        return 'Normal'
    if value < 1.0:
        return 'Elevated'
    return 'High'


def label_crest_factor(value):
    """Ideal crest factor is sqrt(2) ~ 1.414. Within +/-0.05 = Normal."""
    if value is None:
        return None
    if abs(value - 1.414) <= 0.05:
        return 'Normal'
    if abs(value - 1.414) <= 0.15:
        return 'Watch'
    return 'High'


def label_thd_movement(value):
    if value is None:
        return None
    av = abs(value)
    if av < 10:
        return 'Normal'
    if av < 30:
        return 'Elevated'
    return 'High'


def label_ieee519(value):
    """May be a bool, 'Pass'/'Fail' string, or int."""
    if value is None:
        return None
    if isinstance(value, bool):
        return 'Pass' if value else 'Fail'
    if isinstance(value, str):
        return value.title()
    if isinstance(value, (int, float)):
        return 'Pass' if value else 'Fail'
    return str(value)


# ── Power Quality (UPS) ─────────────────────────────────────────────────────

def label_pq_severity(value):
    """Pass-through with normalisation."""
    if value is None:
        return None
    s = str(value).lower()
    if s == 'normal':   return 'Normal'
    if s == 'watch':    return 'Watch'
    if s == 'critical': return 'Critical'
    return str(value).title()


def label_pq_filter_state(value):
    if value is None:
        return None
    s = str(value).lower()
    if s == 'normal':    return 'Normal'
    if s == 'saturated': return 'Watch'
    if s == 'fault':     return 'Fault'
    if s == 'bypass':    return 'Bypass'
    return str(value).title()


def label_pq_capacitor_bank(value):
    if value is None:
        return None
    s = str(value).lower().replace('_', ' ')
    if s == 'normal':         return 'Normal'
    if s == 'watch':          return 'Watch'
    if s == 'overcurrent':    return 'Overcurrent'
    if s == 'disconnected':   return 'Disconnected'
    return str(value).title()


def label_pq_active_issues(value):
    """Active issue count → severity bucket."""
    if value is None:
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    if n == 0:  return 'Clear'
    if n == 1:  return 'Active Issue'
    return f'{n} Active Issues'


def label_pf_displacement_gap(value):
    """Gap between fundamental PF and true PF. High gap = strong harmonic distortion."""
    if value is None:
        return None
    av = abs(value)
    if av < 0.03: return 'Tight'
    if av < 0.10: return 'Watch'
    return 'Wide'
