"""ems_exec/executor/verify.py — per-value verification: denorm-garbage clamp + negative-power sign convention.
DB-driven (config.quality_policy). One concern; fill.py re-exports byte-compatibly. [atomic]
"""
from __future__ import annotations

from config import quality_policy as _qp


def _verify(value, quantity=None):
    """Return a clean value or None. A GENUINE non-number (NaN / Inf / non-numeric text / None) -> None (honest
    'no_reading'); a genuine negative power/energy -> abs() under the configured convention. A tiny NONZERO reading
    (e.g. 1e-40) and a real 0.0 both PASS THROUGH UNCHANGED — a small-but-real reading is data, not garbage. The
    negative-power sign convention is a config knob.

    (The old |x|<denorm_epsilon clamp is REMOVED: it dropped genuine small readings; the meaningful-data probe in
    grounding.meaningful still reads denorm_epsilon for its own has-data gate — that is a separate, non-per-value gate.)"""
    if value is None:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None                                            # non-numeric text is a genuine non-number -> honest-blank
    if value != value or value in (float("inf"), float("-inf")):
        return None                                            # NaN / Inf -> honest 'no_reading' (never rides the payload)
    if value < 0 and quantity in ("power", "energy"):
        if _qp.txt("negative_power_convention", "abs_with_flag") == "abs_with_flag":
            value = abs(value)
    return value


def _quantity_of(field):
    """The field's measured quantity from the AI's DECLARED unit — a fixed dimensional lookup (kW→power, kWh→energy;
    config.vocab unit_quantities row, editable). NO token/name matching: only feeds the negative-power abs() convention
    in _verify, so an undeclared unit simply skips that convention (pass-through — never a guess)."""
    try:
        from config.vocab import unit_quantity
        return unit_quantity(field.get("unit"))
    except Exception:
        return None
