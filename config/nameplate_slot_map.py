"""config/nameplate_slot_map.py — maps a CMD V2 payload data-slot (ratedKw / contractedKw / energyTargetKwh …) to the
derive_ratings key that supplies its REAL per-asset value. A const slot listed here is a NAMEPLATE reference value, so
L3 resolves it from the asset nameplate (config.nameplates.derive_ratings_for), NOT the baked seed literal L2 copied off
the default payload — so a demo number (425 / 415 / 3500) is NEVER passed through as a 'configured' const. Slots NOT
listed keep their literal (a universal standard like the IEEE-519 THD limit is a real const, not a per-asset seed).

DB-tunable, fall-open: an editable `data_quality_policy` row `rating_slot.<slot>` overrides the code default; a missing
row / DB outage falls back to the default map so behaviour is stable until a row exists. [no-seed const; RN-01/02]
"""
from config import quality_policy as _qp

# CMD V2 payload slot -> derive_ratings key (the per-asset nameplate value that must replace any baked literal).
# Also keyed by the METRIC names Layer 2 emits on a const rating field (the executor probes slot THEN metric) — so a
# const like {slot:'supply.denominator', metric:'contracted_capacity_kw', value:<copied-from-the-default>} resolves the
# asset's REAL contracted kW (or honest-blanks), never the Storybook literal. [card-9 fabricated-denominator fix]
_DEFAULT = {
    "ratedKw": "rated_kw",
    "contractedKw": "contracted_kw",
    "energyTargetKwh": "energy_target_kwh_today",
    "ratedKva": "rated_kva",
    "ratedCurrentA": "rated_current_a",
    "criticalLoadKw": "critical_load_kw",
    # metric-name spellings (Layer-2 const rating fields carry metric, not a camelCase slot)
    "contracted_capacity_kw": "contracted_kw",
    "contracted_kw": "contracted_kw",
    "rated_capacity_kw": "rated_kw",
    "rated_kw": "rated_kw",
    "rated_kva": "rated_kva",
    "rated_current_a": "rated_current_a",
}


def rating_key_for(slot):
    """The derive_ratings key that supplies `slot`'s real per-asset value, or None if `slot` is not a nameplate
    reference value (→ keep its literal). An editable `data_quality_policy` row `rating_slot.<slot>` overrides the
    default map (non-empty value = the derive_ratings key to use)."""
    if not slot:
        return None
    override = _qp.txt("rating_slot." + str(slot), "")
    if override:
        return override
    return _DEFAULT.get(str(slot))
