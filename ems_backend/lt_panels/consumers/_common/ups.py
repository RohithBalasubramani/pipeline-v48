"""UPS status-label callables.

Each function takes a single value and returns a label string (or None when
the value is missing). Strategies wire these into their `status_rules` dict.
"""


def label_ups_mode(value):
    if value is None:
        return None
    s = str(value).lower().replace('-', '_')
    if s == 'double_conversion': return 'Double-Conversion'
    if s == 'eco':               return 'Eco'
    if s == 'bypass':            return 'Bypass'
    if s == 'battery':           return 'On Battery'
    if s == 'standby':           return 'Standby'
    return str(value).title()


def label_ups_subsystem_status(value):
    """Generic OK/fault for rectifier · inverter."""
    if value is None:
        return None
    s = str(value).lower()
    if s in ('online', 'ok'):       return 'OK'
    if s == 'derating':             return 'Watch'
    if s in ('offline', 'standby'): return 'Standby'
    if s in ('fault', 'overload'):  return 'Fault'
    return str(value).title()


def label_ups_bypass_sync(value):
    if value is None:
        return None
    s = str(value).lower()
    if s == 'locked':   return 'Locked'
    if s == 'unlocked': return 'Watch'
    if s == 'lost':     return 'Lost'
    return str(value).title()


def label_ups_static_switch(value):
    if value is None:
        return None
    s = str(value).lower()
    if s == 'armed':        return 'Armed'
    if s == 'disarmed':     return 'Disarmed'
    if s == 'transferred':  return 'Transferred'
    return str(value).title()


def label_ups_sync_window(value):
    if value is None:
        return None
    s = str(value).lower().replace('-', '_')
    if s in ('available', 'in_window'): return 'Available'
    if s == 'out_of_sync':              return 'Out of Sync'
    if s == 'locked':                   return 'Locked'
    return str(value).title()


def label_ups_input_source(value):
    if value is None:
        return None
    s = str(value).lower()
    if s == 'healthy':  return 'Healthy'
    if s == 'degraded': return 'Watch'
    if s == 'lost':     return 'Lost'
    return str(value).title()


def label_ups_battery_temp(value):
    if value is None:
        return None
    if value < 30:  return 'Normal'
    if value < 40:  return 'Normal'
    if value < 45:  return 'Watch'
    return 'High'


def label_ups_battery_soc(value):
    if value is None:
        return None
    if value >= 85:  return 'Ready'
    if value >= 60:  return 'Watch'
    if value >= 30:  return 'Low'
    return 'Critical'


def label_ups_autonomy(value):
    """Autonomy minutes left at current load."""
    if value is None:
        return None
    if value >= 30:  return 'Ready'
    if value >= 15:  return 'Watch'
    if value >= 5:   return 'Low'
    return 'Critical'


def label_ups_loading(value):
    """Loading % of rated kVA. Inverter typically derates at >80%."""
    if value is None:
        return None
    if value < 50:  return 'Fair'
    if value < 80:  return 'Normal'
    if value < 95:  return 'Watch'
    return 'Overload'


def label_voltage_regulation(value):
    """± output-vs-input voltage regulation, %"""
    if value is None:
        return None
    av = abs(value)
    if av < 1.0:  return 'Tight'
    if av < 2.5:  return 'Normal'
    if av < 5.0:  return 'Watch'
    return 'Loose'


def label_thd_exposure(value):
    """% of 24h window above THD limit."""
    if value is None:
        return None
    if value < 20:  return 'Clean'
    if value < 50:  return 'Watch'
    return 'High'


def label_transfer_inhibit(value):
    """'None' is the healthy state — anything else means transfers are blocked."""
    if value is None:
        return None
    s = str(value).lower()
    if s in ('none', 'ok', ''):  return 'None'
    return str(value).title()
