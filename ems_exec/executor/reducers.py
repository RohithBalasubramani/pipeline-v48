"""ems_exec/executor/reducers.py — the CLOSED reducer vocabulary for roster aggregate KPIs. ZERO card knowledge: which
key reduces how arrives entirely in the recipe/emission's agg spec; the math delegates to ems_exec/renderers/_agg.py
(the shared honest-null-safe arithmetic). Every reducer honest-nulls on an empty reporting set — never a fabricated 0.

Reducer vocabulary (closed — anything else honest-nulls):
    sum_magnitude {"agg":"sum_magnitude","of":k,"r":n}   Σ|element[k]| over reporting elements.
    mean          {"agg":"mean","of":k,"r":n}            arithmetic mean of element[k].
    maximum / minimum                                     worst/best-case pick of element[k].
    argmax        {"agg":"argmax","of":k,"abs":bool}     the WHOLE element with the largest real element[k]; abs=true
                  ranks by |element[k]| (the worst pick for a SIGNED quantity, e.g. the largest-magnitude voltage
                  deviation whether it is a sag (negative) or a swell (positive)).
    count_breach  {"agg":"count_breach","of":k,"floor":f,"dir":"above|below"} count of elements whose element[k]
                  crosses f — dir='above' (default) counts element[k] > f; dir='below' counts element[k] < f (for a
                  SIGNED quantity's negative-side event, e.g. a voltage SAG where deviation < -floor). None if none report.
    sum_of        {"agg":"sum_of","keys":[...]}          Σ of already-computed sibling agg values (int-safe).
    count_status  {"agg":"count_status","status":s}      count of elements whose status-op value means s (synonym fold).
    first_nonnull {"agg":"first_nonnull","of":k}         the first real element[k] in member order.
    len           {"agg":"len"}                          how many elements (the roster size for that role subset).
    alias         {"agg":"alias","of":k}                 a copy of the already-computed sibling agg k.
    const         {"agg":"const","v":...}                the literal.

[atomic; pure; input = the evaluated elements (+ the slot's element spec for status-key discovery) — no I/O]
"""
from __future__ import annotations

from ems_exec.renderers import _agg


def _num(x):
    return _agg.num(x)


def _vals(elements, key):
    return [e.get(key) for e in (elements or []) if isinstance(e, dict)]


def _status_keys(element_spec):
    """The element keys bound by the `status` OP (from the slot's element spec) — discovered from binding metadata, so
    count_status stays free of any hardcoded key name."""
    return [k for k, b in (element_spec or {}).items()
            if isinstance(b, dict) and (b.get("b") or "").strip().lower() == "status"]


def reduce(spec, elements, *, computed=None, context=None, element_spec=None, policy=None):
    """ONE aggregate KPI from the evaluated `elements` per the closed vocabulary above. `computed` = the sibling agg
    values already produced (for alias / sum_of); `context` = run-level values (e.g. {'panel_kwh': …}). Honest-null on
    empty / unknown. Never raises.

    plausible_range [lo, hi] (optional, ANY reducer): a numeric result OUTSIDE the physically-plausible band → None
    (honest-null). The recipe states the physics (e.g. efficiencyPct [0,100] — feeder output cannot exceed source
    input; outside means the two sides are on mismatched metering bases, so the true value is UNKNOWN, not the raw
    ratio). A non-numeric result (argmax's element dict, const strings) passes through untouched."""
    out = _reduce_raw(spec, elements, computed=computed, context=context, element_spec=element_spec, policy=policy)
    try:
        rng = spec.get("plausible_range") if isinstance(spec, dict) else None
        if (isinstance(rng, (list, tuple)) and len(rng) == 2
                and isinstance(out, (int, float)) and not isinstance(out, bool)):
            lo, hi = _num(rng[0]), _num(rng[1])
            if lo is not None and hi is not None and not (lo <= float(out) <= hi):
                return None
    except Exception:
        return None
    return out


def _reduce_raw(spec, elements, *, computed=None, context=None, element_spec=None, policy=None):
    if not isinstance(spec, dict):
        return None
    op = (spec.get("agg") or "").strip().lower()
    of = spec.get("of")
    try:
        if op == "sum_magnitude":
            return _agg.sum_magnitude(_vals(elements, of), ndigits=spec.get("r", 2))
        if op == "mean":
            return _agg.mean(_vals(elements, of), ndigits=spec.get("r", 3))
        if op == "maximum":
            return _agg.maximum(_vals(elements, of), ndigits=spec.get("r", 2))
        if op == "minimum":
            return _agg.minimum(_vals(elements, of), ndigits=spec.get("r", 2))
        if op == "argmax":
            real = [e for e in (elements or []) if isinstance(e, dict) and _num(e.get(of)) is not None]
            rank = (lambda e: abs(_num(e.get(of)))) if spec.get("abs") else (lambda e: _num(e.get(of)))
            return max(real, key=rank) if real else None
        if op == "count_breach":
            floor = _num(spec.get("floor"))
            real = [v for v in (_num(x) for x in _vals(elements, of)) if v is not None]
            if not real or floor is None:
                return None                                   # a blank is NOT a zero-breach (honest)
            below = (spec.get("dir") or "above").strip().lower() == "below"
            return sum(1 for v in real if (v < floor if below else v > floor))
        if op == "sum_of":
            got = [(computed or {}).get(k) for k in (spec.get("keys") or [])]
            ints = [v for v in got if isinstance(v, (int, float)) and not isinstance(v, bool)]
            return round(sum(ints), spec.get("r", 0) or None) if ints else None
        if op == "count_status":
            keys = _status_keys(element_spec)
            if not keys or policy is None:
                return 0 if elements is not None else None
            target = spec.get("status")
            return sum(1 for e in (elements or []) if isinstance(e, dict)
                       and any(policy.status_matches(e.get(k), target) for k in keys))
        if op == "first_nonnull":
            for v in _vals(elements, of):
                if _num(v) is not None:
                    return _num(v)
            return None
        if op == "len":
            return len(elements or [])
        if op == "alias":
            return (computed or {}).get(of)
        if op == "difference":
            a = _num((computed or {}).get(spec.get("of")))
            b = _num((computed or {}).get(spec.get("by")))
            if a is None or b is None:
                return None                                    # an unknown side → honest-null (never a fabricated delta)
            d = a - b
            if d < 0:
                # a NEGATIVE physical difference (e.g. loss = source − feeders when the feeders sum HIGHER than the
                # source) means the two sides are on MISMATCHED metering bases — the true value is UNKNOWN:
                #   nonneg_null  → honest-null (the loss cannot be computed on this pairing; FE display-dashes)
                #   clamp_nonneg → 0.0 (legacy; reads as "zero loss", a fabricated number — prefer nonneg_null)
                if spec.get("nonneg_null"):
                    return None
                if spec.get("clamp_nonneg"):
                    d = 0.0
            return round(d, spec.get("r", 2))
        if op == "ratio_pct":
            a = _num((computed or {}).get(spec.get("of")))
            b = _num((computed or {}).get(spec.get("by")))
            if a is None or b in (None, 0):
                return None                                    # unknown / zero denominator → honest-null (no /0 fiction)
            return round(a / b * 100.0, spec.get("r", 2))
        if op == "const":
            return spec.get("v")
        if op in (context or {}):                              # a run-level context value named directly (panel_kwh)
            return (context or {}).get(op)
    except Exception:
        return None
    return None                                                # unknown reducer → honest-null (closed vocabulary)
