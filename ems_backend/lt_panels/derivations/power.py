"""derivations/power.py — POWER recoveries (pure fns, no DB). compat KEPT active_power_total_kw + apparent_power_total_kva,
so peaks, load factor and rate-of-change are real from the observed series. [best-possible-recovery: cards 15/36/42]"""
from __future__ import annotations


def _series(ctx, col):
    return [float(r[col]) for r in (ctx.get("series") or []) if isinstance(r.get(col), (int, float))]


def load_factor_pct(ctx):
    """Load factor = avg(active_power) ÷ peak(active_power) × 100 — the textbook identity over the window. real_approx
    (depends on window coverage). ctx: {series:[rows with active_power_total_kw]}."""
    vals = _series(ctx, "active_power_total_kw")
    if not vals:
        return None
    pk = max(vals)
    return round(sum(vals) / len(vals) / pk * 100.0, 1) if pk > 0 else None


def worst_peak_kw(ctx):
    """Peak active power over the window = max(active_power_total_kw). real_exact (windowed max, label as observed)."""
    vals = _series(ctx, "active_power_total_kw")
    return round(max(vals), 1) if vals else None


def worst_peak_at(ctx):
    """ts of the window's peak active power. real_exact. ctx: {series}."""
    rows = [r for r in (ctx.get("series") or []) if isinstance(r.get("active_power_total_kw"), (int, float))]
    if not rows:
        return None
    return max(rows, key=lambda r: r["active_power_total_kw"]).get("ts")


def apparent_peak_kva(ctx):
    """Peak apparent power over the window = max(apparent_power_total_kva). real_approx (observed peak, not a nameplate)."""
    vals = _series(ctx, "apparent_power_total_kva")
    return round(max(vals), 1) if vals else None


def active_power_delta_per_min(ctx):
    """Rate of change of active power = (last − prev) ÷ Δminutes over the last two samples. real_exact. ctx: {series}."""
    rows = [r for r in (ctx.get("series") or []) if isinstance(r.get("active_power_total_kw"), (int, float))]
    if len(rows) < 2:
        return None
    a, b = rows[-2], rows[-1]
    ta, tb = a.get("ts"), b.get("ts")
    try:
        dt_min = (tb - ta).total_seconds() / 60.0
    except (TypeError, AttributeError):
        return None
    if dt_min <= 0:
        return None
    return round((b["active_power_total_kw"] - a["active_power_total_kw"]) / dt_min, 2)
