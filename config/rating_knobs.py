"""config/rating_knobs.py — the editable knobs the nameplate→ratings derivation reads (feeder PF, LV line voltage,
alarm/contract/critical/target factors). NO magic number lives in derive_ratings — every scalar is an editable
`data_quality_policy` row under the `rating.` namespace, read here (mirrors config.l3_policy's reuse of that table).

Ported from CMD/backend2/core/config.py:16-47 (feeder_rating_overrides): the assumed 0.9 PF for kVA→kW, the 415 V LT
line-to-line for the current rating, the 120% alarm, 0.9× contracted, 0.5× critical, 12h energy target, and the
capacity-utilization PF (energydist.py:71-78 _cap_util). Every one is a ROW a reviewer edits, not a constant in logic.

fall-open: a missing row OR a DB outage → the code default (config.quality_policy.num already fails soft), so
derive_ratings behaves identically until a row exists. [DB-driven config / RN-01/05]
"""
from config import quality_policy as _qp


def feeder_pf():
    """Assumed power factor for the nameplate kVA→kW conversion. Editable row rating.feeder_pf (default 0.9)."""
    return _qp.num("rating.feeder_pf", 0.9)


def lv_line_v():
    """LT 3-phase line-to-line voltage used for the rated-current derivation, in volts. Editable row rating.lv_line_v
    (default 415). Only the DEFAULT current basis — a per-asset nominal_voltage_ll on the nameplate still wins."""
    return _qp.num("rating.lv_line_v", 415.0)


def current_alarm_factor():
    """Multiplier on rated current for the high-current alarm threshold. Editable row rating.current_alarm_factor
    (default 1.2 → alarm at 120% of rated)."""
    return _qp.num("rating.current_alarm_factor", 1.2)


def contracted_factor():
    """Fraction of rated kW taken as the contracted/sanctioned kW when no per-asset contract exists. Editable row
    rating.contracted_factor (default 0.9)."""
    return _qp.num("rating.contracted_factor", 0.9)


def critical_load_factor():
    """Fraction of rated kW taken as the critical-load kW. Editable row rating.critical_load_factor (default 0.5)."""
    return _qp.num("rating.critical_load_factor", 0.5)


def energy_target_hours():
    """Equivalent full-load hours/day used for the daily energy target (target_kwh = rated_kw × hours). Editable row
    rating.energy_target_hours (default 12 → ~50% load factor over 24h)."""
    return _qp.num("rating.energy_target_hours", 12.0)


def capacity_pf():
    """PF used for the window CAPACITY (capacity_kwh = rated_kva × pf × hours), from energydist _cap_util. Editable row
    rating.capacity_pf (default 0.9)."""
    return _qp.num("rating.capacity_pf", 0.9)
