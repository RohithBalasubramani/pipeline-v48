"""grounding/normalizers.py — deterministic value normalizers (NO AI). Turn a raw meter scalar into a render-safe
value + a machine flag, using EDITABLE policy from config.quality_policy. Nothing here fetches — callers pass the raw
value(s); these are pure functions over policy.

The four normalizers (all covered failure modes in brackets):
  denorm_clamp    — |x| < denorm_epsilon → denormalized-float garbage (e.g. -4.6e-44) → no-reading.        [DS-06]
  power_sign      — genuine negative power (UPS/incomer) → magnitude + reverse-flow flag, per policy.       [DS-06/VC-03]
  pf_normalize    — PF: |PF|≤1 magnitude + lead/lag flag from the sign; never discard the sign.             [VC-07/DID-04]
  rate_of_change  — Δvalue/Δt from two real samples (there is NO rate_of_change_* column in neuract).       [VC-10]
  register_kind   — tag a column cumulative-counter vs spot so a lifetime odometer never renders as a spot. [VC-06/DID-04]

Every threshold/policy string (denorm_epsilon, negative_power_convention, pf_sign_policy, cumulative_counter_policy)
is a cmd_catalog row read through config.quality_policy — zero magic numbers here.
"""
from __future__ import annotations

from config import quality_policy as qp
from config import reason_templates as rt

# cumulative-counter column suffixes (the lifetime odometers) — policy-typed via register_kind. These are the *_import_/
# *_export_ cumulative energy registers whose raw latest value is a lifetime total, not a period/spot reading.
_CUMULATIVE_HINTS = ("active_energy_import_kwh", "active_energy_export_kwh",
                     "reactive_energy_import_kvarh", "reactive_energy_export_kvarh",
                     "apparent_energy_kvah")


def _f(x):
    if x in (None, "", "NULL"):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# ── denorm clamp ─────────────────────────────────────────────────────────────────────────────────────────────────
def denorm_clamp(value):
    """A scalar → (clean_value, flag). If |value| < denorm_epsilon it is denormalized-float garbage (gic_30_* carry
    -4.6e-44) → return (None, 'denorm_garbage') so the caller renders no-reading, NOT a broken/pinned gauge needle.
    Otherwise (value, None). None-in → (None, None). [DS-06]"""
    v = _f(value)
    if v is None:
        return None, None
    eps = qp.num("denorm_epsilon", 1e-30)
    if abs(v) < eps:
        return None, "denorm_garbage"
    return v, None


# ── power sign / reverse-flow flag ───────────────────────────────────────────────────────────────────────────────
def power_sign(value):
    """Active/apparent power scalar → {value, magnitude, direction, reversed, reason, raw}. Runs denorm_clamp FIRST
    (so -4.6e-44 is dropped, not treated as reverse flow). For a genuine negative power (UPS discharge / incomer export)
    the policy 'negative_power_convention' decides:
        'abs_with_flag' (default) → value=magnitude(|x|), direction='reverse', reversed=True   [VC-03/DS-06]
        'keep_sign'               → value=raw (renderer honours its own sign contract)
    A positive power → direction='forward', reversed=False. [DS-06/VC-03]"""
    clean, dflag = denorm_clamp(value)
    if clean is None:
        return {"value": None, "magnitude": None, "direction": None, "reversed": False,
                "reason": (rt.reason("denorm_garbage") if dflag else None), "raw": _f(value)}
    if clean >= 0:
        return {"value": clean, "magnitude": clean, "direction": "forward",
                "reversed": False, "reason": None, "raw": clean}
    # genuine negative power.
    policy = qp.txt("negative_power_convention", "abs_with_flag")
    if policy == "keep_sign":
        return {"value": clean, "magnitude": abs(clean), "direction": "reverse",
                "reversed": True, "reason": None, "raw": clean}
    # abs_with_flag (default): magnitude + reverse-flow flag.
    return {"value": abs(clean), "magnitude": abs(clean), "direction": "reverse",
            "reversed": True, "reason": None, "raw": clean}


# ── power-factor sign / lead-lag flag ────────────────────────────────────────────────────────────────────────────
def pf_normalize(value, active_power=None):
    """Power-factor scalar → {value, magnitude, quadrant, sign_consistent, reason, raw}. Per policy 'pf_sign_policy'
    (default 'magnitude_plus_leadlag'): clamp |PF|≤1 to a magnitude, and carry the sign as a lead/lag (import/export)
    flag — NEVER abs() the sign away silently. [VC-07/DID-04]

    quadrant:   'lagging' (PF>0, inductive/import) | 'leading' (PF<0, capacitive/export/reverse).
    sign_consistent: when active_power is given, whether sign(PF)==sign(power); a mismatch is surfaced (reason) so a
                     bad reading degrades rather than rendering a spurious negative PF as a fault. [VC-07]"""
    v = _f(value)
    if v is None:
        return {"value": None, "magnitude": None, "quadrant": None,
                "sign_consistent": None, "reason": None, "raw": None}
    magnitude = min(abs(v), 1.0)          # clamp to the CMD card's 0..1 contract.
    quadrant = "leading" if v < 0 else "lagging"

    policy = qp.txt("pf_sign_policy", "magnitude_plus_leadlag")
    # magnitude_plus_leadlag (default) → present magnitude, carry the sign as the quadrant flag.
    # 'keep_sign' → present the raw signed value (card must handle the sign itself).
    value_out = v if policy == "keep_sign" else magnitude

    sign_consistent, reason = None, None
    ap = _f(active_power)
    if ap is not None and abs(ap) > 0 and abs(v) > 0:
        sign_consistent = ((v < 0) == (ap < 0))
        if not sign_consistent:
            reason = rt.reason("structurally_null", metric="power factor sign")
    return {"value": value_out, "magnitude": magnitude, "quadrant": quadrant,
            "sign_consistent": sign_consistent, "reason": reason, "raw": v}


# ── rate of change from samples ──────────────────────────────────────────────────────────────────────────────────
def rate_of_change(samples, per="min"):
    """Δvalue/Δt from real consecutive samples — there is NO rate_of_change_* column in neuract, so any rate tile MUST
    be derived here (else it binds an absent column → always null). [VC-10]

    `samples` — list of (ts_seconds, value) OR (ts_seconds, value) tuples/lists, oldest→newest or any order (sorted
                here by ts). Denorm-garbage / None values are dropped (a false 0 must never dive a nonzero trend).
    `per`     — 'sec' | 'min' | 'hour' → the Δt unit for the returned rate.
    Returns (rate, None) or (None, reason) when <2 clean samples or Δt==0."""
    unit = {"sec": 1.0, "min": 60.0, "hour": 3600.0}.get(per, 60.0)
    clean = []
    for s in samples or []:
        if s is None or len(s) < 2:
            continue
        t = _f(s[0])
        v, dflag = denorm_clamp(s[1])
        if t is None or v is None:
            continue
        clean.append((t, v))
    if len(clean) < 2:
        return None, rt.reason("structurally_null", metric="rate of change")
    clean.sort(key=lambda p: p[0])
    (t0, v0), (t1, v1) = clean[0], clean[-1]
    dt = t1 - t0
    if dt == 0:
        return None, rt.reason("structurally_null", metric="rate of change")
    return round((v1 - v0) / dt * unit, 3), None


# ── cumulative-vs-spot tag ───────────────────────────────────────────────────────────────────────────────────────
def register_kind(column):
    """Tag a column 'cumulative' (a lifetime odometer — *_energy_import/export_*) vs 'spot' (an instantaneous reading).
    Policy 'cumulative_counter_policy' (default 'window_delta') says a cumulative counter must be rendered as a windowed
    MAX-MIN delta, never a raw spot value. Returns {kind, render_as, reason}. [VC-06/DID-04]"""
    col = (column or "").lower()
    is_cumulative = any(h in col for h in _CUMULATIVE_HINTS)
    if is_cumulative:
        policy = qp.txt("cumulative_counter_policy", "window_delta")
        return {"kind": "cumulative", "render_as": policy,
                "reason": rt.reason("window_clamped", since="the window start")
                          if policy == "window_delta" else None}
    return {"kind": "spot", "render_as": "spot", "reason": None}
