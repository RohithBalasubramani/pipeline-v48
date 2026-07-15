"""derivations/current.py — CURRENT recoveries (pure fns, no DB). compat dropped the meter-native current_neutral column,
but it KEPT the per-phase magnitudes (current_r/y/b), so neutral current is recoverable via the unbalanced-magnitude
phasor identity (assumes 120° phase spacing → real_approx). [none-reaudit flip: cards 38/45]"""
from __future__ import annotations

import math


from ._coerce import f as _f


def neutral_current(ctx):
    """Estimated neutral current = √(Ir²+Iy²+Ib² − IrIy − IyIb − IbIr) from the per-phase magnitudes. real_approx: exact
    only if phases are 120° apart (the standard assumption); the meter-native current_neutral, when present on the live
    socket, supersedes this. ctx: {row: {current_r, current_y, current_b}}."""
    row = ctx.get("row") or {}
    # prefer a measured neutral if the frame carries one (live socket); else estimate from phase magnitudes
    meas = _f(row.get("current_neutral"))
    if meas is not None:
        return round(meas, 1)
    r, y, b = _f(row.get("current_r")), _f(row.get("current_y")), _f(row.get("current_b"))
    if None in (r, y, b):
        return None
    q = r * r + y * y + b * b - r * y - y * b - b * r
    return round(math.sqrt(q), 1) if q >= 0 else 0.0


def neutral_to_phase_ratio_pct(ctx):
    """Neutral as % of average phase current = I_N ÷ current_avg × 100 (a loading/unbalance health signal). real_approx
    (rides the neutral estimate). ctx: {row} with current_avg + the neutral inputs."""
    i_n = neutral_current(ctx)
    avg = _f((ctx.get("row") or {}).get("current_avg"))
    if i_n is None or avg is None or avg <= 0:
        return None
    return round(i_n / avg * 100.0, 1)


def _phases(ctx):
    row = ctx.get("row") or {}
    return [v for v in (_f(row.get("current_r")), _f(row.get("current_y")), _f(row.get("current_b"))) if v is not None]


def phase_current_avg(ctx):
    """Mean of the present per-phase currents (current_r/y/b) — the REAL average when the meter's own current_avg
    register is dead/all-null (HT CT wiring: current_avg present-but-NULL while the phase magnitudes are live). Not
    fabrication — it is the arithmetic mean of measured phases. real_exact. None when no phase is present."""
    vals = _phases(ctx)
    return round(sum(vals) / len(vals), 1) if vals else None


def phase_current_unbalance_pct(ctx):
    """Current unbalance % = (max − min) ÷ mean × 100 over the present per-phase currents — the real unbalance when the
    meter's current_unbalance_pct register is dead. real_exact. None when fewer than two phases are present or mean 0."""
    vals = _phases(ctx)
    if len(vals) < 2:
        return None
    m = sum(vals) / len(vals)
    return round((max(vals) - min(vals)) / m * 100.0, 1) if m else None
