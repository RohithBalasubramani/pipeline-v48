"""Solar Incomer status-label callables.

Each function takes a single value and returns a label string (or None when
the value is missing). Strategies wire these into their `status_rules` dict.
"""


def label_inverter_status(value):
    """Pass-through with a normalised default."""
    if value is None:
        return None
    s = str(value).lower()
    if s == 'online':   return 'Online'
    if s == 'derating': return 'Derating'
    if s == 'fault':    return 'Fault'
    if s == 'offline':  return 'Offline'
    return str(value).title()


def label_inverter_efficiency(value):
    if value is None:
        return None
    if value >= 96.0: return 'Good'
    if value >= 92.0: return 'Watch'
    return 'Poor'


def label_irradiance(value):
    if value is None:
        return None
    if value < 50:    return 'Night'
    if value < 300:   return 'Low'
    if value < 700:   return 'Moderate'
    return 'High'


def label_breaker_state(value):
    if value is None:
        return None
    s = str(value).lower()
    if s == 'closed':  return 'Closed'
    if s == 'open':    return 'Open'
    if s == 'tripped': return 'Tripped'
    return str(value).title()


def label_comm_status(value):
    if value is None:
        return None
    s = str(value).lower()
    if s == 'live':    return 'Live'
    if s == 'stale':   return 'Stale'
    if s == 'offline': return 'Offline'
    return str(value).title()


def label_strings_watch(value):
    """How many PV strings are below health threshold."""
    if value is None:
        return None
    if value == 0:  return 'Healthy'
    if value <= 2:  return 'Watch'
    return 'Degraded'


def label_curtailment(value):
    """kW of curtailment — anything above zero is throttling."""
    if value is None:
        return None
    if value < 1.0:  return 'None'
    if value < 20.0: return 'Light'
    return 'Heavy'


def label_performance_ratio(value):
    """IEC 61724 — typical good PR is 0.75–0.85."""
    if value is None:
        return None
    if value >= 80: return 'Good'
    if value >= 70: return 'Acceptable'
    return 'Poor'
