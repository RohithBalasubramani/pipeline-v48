"""ems_exec/renderers/_agg.py — PURE panel-aggregate MATH (no I/O, no DB, no neuract read).

The panel_aggregate renderer fans a panel out to its member meters (data.neuract_live edges) and rolls the members'
REAL electrical up by QUANTITY. This module is the shared, honest-null-safe arithmetic that rollup needs — factored out
of topology_sld's _sum_kw / _avg_pf / _sum_col / _node_kwh so the SLD renderer and the KPI/table/radar/sankey aggregate
renderer compute the SAME way (magnitude → Σ, PF/voltage/THD → mean, current → Σ).

DESIGN CONTRACT (every fn honest-null-safe — None in → None out, an all-empty input → None, NEVER a fabricated 0):
  · sum_magnitude(vals)     — Σ over the members that actually reported a value (power/energy/current/kva/kvar/neutral).
  · mean(vals)              — arithmetic mean over the members that reported (pf/voltage/freq/thd/harmonic/percent).
  · maximum(vals) / minimum — the worst-case pick (iWorst/vWorst trend lines, worst-feeder arg-max drivers).
  · windowed_delta(pairs)   — Σ of per-member (end−start) cumulative-counter deltas (kWh energy over the ctx window).
  · coverage_verdict(r, e)  — {reporting, expected, verdict}: render (all report) / partial (some) / honest_blank (none).

WHICH columns Σ vs MEAN is the RENDERER's explicit per-column decision (panel_aggregate._SUM_COLS — a fixed,
readable set over the known schema), not a name-matching guess. [atomic; pure; no I/O]
"""
from __future__ import annotations


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  honest-null number coercion — the ONE place a value becomes a finite float or None (denorm/inf/NaN/text → None)
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def num(x):
    """A finite float, or None (honest-null). None / non-finite / non-numeric text → None. Mirrors topology_sld._num."""
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if f == f and f not in (float("inf"), float("-inf")) else None


def _reals(vals):
    """The finite-float subset of `vals` (drops None / non-finite / text) — the honest reporting set for a reducer."""
    return [v for v in (num(x) for x in (vals or [])) if v is not None]


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  the reducers — one per quantity class. Every one: honest-null (empty reporting set → None, never a fabricated 0.0).
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def sum_magnitude(vals, ndigits=2):
    """Σ of |value| over the members that reported — for MAGNITUDE quantities (kw / kwh / kva / kvar / current /
    neutralA). None when NO member reported (honest-null: an all-dark side is unknown, not zero).

    Per-member abs BEFORE summing: a negative member reading is a reverse-CT orientation artifact in this plant (the
    codebase convention `negative_power_convention=abs_with_flag`; backend2's 'sign-safe sum — magnitude of reverse
    feeders'). A panel feeding 3×~175 kW UPS (CT-reversed, read negative) + 261 kW BPDB distributes ~786 kW — a signed
    sum nets that to -364, and abs()-at-the-leaf cannot recover the true total."""
    real = _reals(vals)
    return round(sum(abs(v) for v in real), ndigits) if real else None


def mean(vals, ndigits=3):
    """Arithmetic mean over the members that reported — for INTENSIVE quantities (pf / voltage / freq / thd / harmonic /
    percent / utilization). None when no member reported. Ports topology_sld._avg_pf (denominator = reporting count)."""
    real = _reals(vals)
    return round(sum(real) / len(real), ndigits) if real else None


def maximum(vals, ndigits=2):
    """The worst-case (largest) value across reporting members — for the iWorst/vWorst trend lines + worst-feeder pick.
    None when no member reported (honest-null)."""
    real = _reals(vals)
    return round(max(real), ndigits) if real else None


def minimum(vals, ndigits=2):
    """The smallest value across reporting members. None when no member reported (honest-null)."""
    real = _reals(vals)
    return round(min(real), ndigits) if real else None


def windowed_delta(pairs, ndigits=1):
    """Σ of per-member cumulative-counter deltas (end − start), clamped ≥ 0 — the panel's windowed ENERGY (kWh) over the
    ctx window. `pairs` = [(start_value, end_value), …] one per member. A pair with a missing baseline is skipped; None
    when NO member yielded a real delta (honest-null, never a fabricated 0). Ports topology_sld._node_kwh, summed."""
    total = None
    for start, end in (pairs or []):
        e0, e1 = num(start), num(end)
        if e0 is None or e1 is None:
            continue
        total = (total or 0.0) + max(e1 - e0, 0.0)
    return round(total, ndigits) if total is not None else None


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  the quantity → reducer map — the single ground-truth per-column reduction (what SUMs vs what MEANs)
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════






# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  coverage verdict — the honest denominator (how many members reported vs how many were expected)
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def coverage_verdict(reporting, expected):
    """{reporting, expected, verdict}: render (every expected member reported), partial (some did), honest_blank (none /
    orphan). This is the panel-level coverage badge the FE shows so a partial fleet sum is NEVER passed off as complete."""
    r = int(reporting or 0)
    e = int(expected or 0)
    if e <= 0 or r <= 0:
        verdict = "honest_blank"
    elif r >= e:
        verdict = "render"
    else:
        verdict = "partial"
    return {"reporting": r, "expected": e, "verdict": verdict}
