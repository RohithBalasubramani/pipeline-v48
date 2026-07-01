"""derivations/power_quality.py — POWER-QUALITY recoveries (pure fns, no DB). compat KEPT power_factor_total and the
aggregate thd_current_*_pct, so the displacement angle is the exact PF identity and the I-THD trend is a windowed
statistic. It did NOT keep per-order harmonics (h5/h7) → k-factor / harmonic source stay impossible. [none-reaudit flip:
cards 47/49]"""
from __future__ import annotations

import math


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def pf_angle_deg(ctx):
    """Displacement angle φ = acos(power_factor) in degrees — the exact PF identity. real_exact. ctx: {row} (latest)."""
    pf = _f((ctx.get("row") or {}).get("power_factor_total"))
    if pf is None:
        return None
    pf = max(-1.0, min(1.0, abs(pf)))
    return round(math.degrees(math.acos(pf)), 1)


def true_pf(ctx):
    """True power factor = active_power_total_kw / apparent_power_total_kva (clamp ≤1) — the exact PF definition.
    real_exact. ctx: {row} (latest)."""
    row = ctx.get("row") or {}
    p = _f(row.get("active_power_total_kw"))
    s = _f(row.get("apparent_power_total_kva"))
    if p is None or s is None or s == 0:
        return None
    return round(min(1.0, abs(p) / abs(s)), 3)


def displacement_pf(ctx):
    """Displacement PF ≈ power_factor_total (compat keeps the aggregate PF column). real_exact. ctx: {row} (latest)."""
    pf = _f((ctx.get("row") or {}).get("power_factor_total"))
    if pf is None:
        return None
    return round(min(1.0, abs(pf)), 3)


def _ithd(row):
    """Average current THD% across phases from the aggregate compat columns."""
    vals = [_f(row.get(c)) for c in ("thd_current_r_pct", "thd_current_y_pct", "thd_current_b_pct")]
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def thd_compliance_ieee519(ctx):
    """IEEE-519 compliance flag: avg I-THD% across phases ≤ 8 → 1.0 else 0.0 (None if no thd cols). real_approx.
    ctx: {row} (latest)."""
    ithd = _ithd(ctx.get("row") or {})
    if ithd is None:
        return None
    return 1.0 if ithd <= 8 else 0.0


def _split_windows(series):
    """Order a {ts}-bearing series and split into prior/recent halves; returns (prior_rows, recent_rows)."""
    rows = [r for r in (series or []) if r.get("ts") is not None]
    if len(rows) < 4:
        return None, None
    rows.sort(key=lambda r: r["ts"])
    mid = len(rows) // 2
    return rows[:mid], rows[mid:]


def thd_trend_label(ctx):
    """I-THD direction over the window: mean(recent) vs mean(prior) → 'Rising'|'Falling'|'Flat' (±2% deadband).
    real_approx (windowed statistic). ctx: {series:[rows with thd_current_*_pct, ts]}."""
    prior, recent = _split_windows(ctx.get("series"))
    if not prior or not recent:
        return None
    p = [_ithd(r) for r in prior]; q = [_ithd(r) for r in recent]
    p = [x for x in p if x is not None]; q = [x for x in q if x is not None]
    if not p or not q:
        return None
    dp = (sum(q) / len(q)) - (sum(p) / len(p))
    base = (sum(p) / len(p)) or 1.0
    pct = dp / base * 100.0
    return "Rising" if pct > 2 else "Falling" if pct < -2 else "Flat"


def thd_trend_rate_pct_per_hour(ctx):
    """I-THD rate of change = (mean recent − mean prior) ÷ mean prior × 100 ÷ window hours. real_approx (linear-trend
    assumption). ctx: {series}."""
    prior, recent = _split_windows(ctx.get("series"))
    if not prior or not recent:
        return None
    p = [_ithd(r) for r in prior]; q = [_ithd(r) for r in recent]
    p = [x for x in p if x is not None]; q = [x for x in q if x is not None]
    if not p or not q:
        return None
    try:
        hrs = (recent[-1]["ts"] - prior[0]["ts"]).total_seconds() / 3600.0
    except (TypeError, AttributeError):
        return None
    base = (sum(p) / len(p)) or 1.0
    if hrs <= 0:
        return None
    return round(((sum(q) / len(q)) - (sum(p) / len(p))) / base * 100.0 / hrs, 2)
