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


# ── ENERGY-POLARITY QUANTITY GUARD (Family G: fab-by-mislabel — card 72 reactive-slot ← active-energy fn) ─────────────
# The coarse unit_quantity above collapses kWh and kVArh both to 'energy', so it CANNOT stop an active-energy fn
# (windowEnergyKwh) from filling a REACTIVE-energy slot (MVARh) with the active 24h delta labeled as reactive. The
# registry's own _QUANTITY map DOES carry the fine polarity (active-energy-* vs reactive-energy-* vs apparent-energy-*):
# it is the single source of truth for "what a library fn MEASURES". This guard reads BOTH the slot's declared polarity
# (from its unit/label/quantity token — MVARh/kvarh/reactive → reactive) and the bound fn's output polarity (from
# _QUANTITY[fn]) and, when both are known and DISAGREE, refuses the binding so the slot honest-blanks instead of
# rendering a real number of the WRONG quantity. Same electrical family (energy/power) only — a voltage fn on a current
# slot is already caught elsewhere; this closes the active↔reactive↔apparent polarity leak specifically. Generic, no
# card ids, driven entirely by the editable registry _QUANTITY table. Unknown polarity on EITHER side → pass through
# (never a guessed blank).
_POLARITY_TOKENS = {
    "reactive": ("reactive", "mvarh", "kvarh", "var"),
    "apparent": ("apparent", "mvah", "kvah", "kva", "-va"),
    "active":   ("active", "real", "mwh", "kwh", "-kw"),
}


def _polarity_of_token(*tokens):
    """The energy/power POLARITY ('active'|'reactive'|'apparent') implied by any of the given text tokens (a slot's
    unit + label + declared quantity), or None when no token disambiguates. Reactive/apparent are checked BEFORE active
    so 'MVARh' (contains 'va') resolves reactive, and 'kVAh' resolves apparent, before the active fallback."""
    blob = " ".join(str(t) for t in tokens if t).lower()
    if not blob:
        return None
    for pol in ("reactive", "apparent", "active"):
        for tok in _POLARITY_TOKENS[pol]:
            needle = tok[1:] if tok.startswith("-") else tok
            if needle in blob:
                return pol
    return None


def _fn_output_polarity(fn_key):
    """The POLARITY of what a library fn MEASURES, from the registry's _QUANTITY family ('active-energy-kwh' → active).
    None when the fn is unclassified or its family carries no polarity (voltage/current/pf/etc.)."""
    if not fn_key:
        return None
    try:
        from ems_exec.derivations import registry as _reg
        fam = (_reg._QUANTITY.get(fn_key) or "")
    except Exception:
        return None
    for pol in ("reactive", "apparent", "active"):
        if fam.startswith(pol + "-"):
            return pol
    return None


def _polarity_conflict(field, fn_key):
    """True when the SLOT's declared polarity (unit/label/quantity token) and the bound FN's output polarity are BOTH
    known and DISAGREE — a fab-by-mislabel binding (active-energy fn → reactive-energy slot). Both unknown / either
    unknown / agree → False (the binding stands; this guard never blanks a slot it cannot prove wrong).

    The slot side reads ONLY the slot's OWN meaning — its unit + label + declared quantity. It DELIBERATELY excludes the
    field's `metric` when the metric IS the bound fn's key (the common metric-wins case): a camelCase fn identifier embeds
    a UNIT-symbol fragment that lies about polarity — `activeEnergyMvah` contains 'mvah' (an apparent needle) though it
    measures ACTIVE energy in MWh, so feeding it into the slot side falsely flagged an active leaf as apparent and
    blanked a real 27.8 MWh (card 72, the fix that over-swung). The metric == fn is self-referential — it can't be a
    mislabel signal against itself. A metric that DIFFERS from the fn (a real reactive-slot ← active-fn mislabel) still
    contributes, so the genuine Family-G fab (windowEnergyKwh → a Reactive/MVARh slot) is still caught by unit+label."""
    metric = field.get("metric")
    metric_signal = None if (metric and fn_key and str(metric) == str(fn_key)) else metric
    slot_pol = _polarity_of_token(field.get("unit"), field.get("label"), field.get("quantity"), metric_signal)
    fn_pol = _fn_output_polarity(fn_key)
    return bool(slot_pol and fn_pol and slot_pol != fn_pol)
