"""layer1b/basket/describe.py — derive (label, kind, unit) from a neuract/compat column name. The neuract schema is
self-describing (active_power_total_kw, voltage_ln_avg, thd_voltage_r_pct), so the dictionary is built from real columns,
not the stale lt_parameter. The ONE place to tune column naming conventions. [neuract migration]"""
import re

_DERIVED = re.compile(r"(_pct$|_deviation_|_spread$|_unbalance|^current_(min|max)$|_status$|_loss_)")
_UNITS = (("_kwh", "kWh"), ("_kvah", "kVAh"), ("_kvarh", "kVArh"),
          ("_kw", "kW"), ("_kva", "kVA"), ("_kvar", "kVAr"), ("_pct", "%"), ("_hz", "Hz"))


def unit(col):
    c = col.lower()
    for suf, u in _UNITS:
        if c.endswith(suf):
            return u
    if c.startswith("voltage_"):
        return "V"
    if c.startswith("current_"):
        return "A"
    if c.startswith("frequency"):
        return "Hz"
    if c.startswith("thd_"):
        return "%"
    return ""                       # power_factor / dimensionless


def kind(col):
    return "derived" if _DERIVED.search(col.lower()) else "raw"


def describe(col):
    return [col.replace("_", " ").strip().title(), kind(col), unit(col)]
