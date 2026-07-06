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


# truePf / displacementPf are ROW-DRIVEN now: their formulas live in cmd_catalog.derivation_binding.expression
# (executed by derivations/evaluate.py); the python bodies were DELETED 2026-07-03 after the live 3-table parity gate
# (UPS gic_01_n3_ups_01_p1 / dg_1_mfm / gic_30_n1_11kv_power_transformer_grid_inc_se — expression ≡ python).


def _ithd(row):
    """Average current THD% across phases from the aggregate compat columns."""
    vals = [_f(row.get(c)) for c in ("thd_current_r_pct", "thd_current_y_pct", "thd_current_b_pct")]
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def _maxp_ithd(row):
    """Worst (max) current THD% across the three phases — the per-phase fallback for when the aggregate
    `thd_compliance_i_avg` compliance column is absent. Mirrors backend2 powerquality/feeder_powerquality `_maxp`
    over (thd_current_r/y/b). None when no phase column is present (honest-degrade)."""
    vals = [_f(row.get(c)) for c in ("thd_current_r_pct", "thd_current_y_pct", "thd_current_b_pct")]
    vals = [v for v in vals if v is not None]
    return max(vals) if vals else None


def i_thd_pct(ctx):
    """I-THD% for the PQ fleet/feeder view: prefer the aggregate `thd_compliance_i_avg` compliance column; when it is
    absent fall back to the MAX of the per-phase thd_current_r/y/b columns (backend2 `_maxp` fallback). None when neither
    is available (honest-degrade — renders "—", never a fabricated 0). real_approx. ctx: {row} (latest)."""
    row = ctx.get("row") or {}
    agg = _f(row.get("thd_compliance_i_avg"))
    if agg is not None:
        return round(agg, 1)
    mx = _maxp_ithd(row)
    return round(mx, 1) if mx is not None else None


def i_thd_peak_pct(ctx):
    """Worst per-phase current THD% (MAX over thd_current_r/y/b) — the peak the fleet `pq_priority` row surfaces as
    `i_thd_pk_pct`, independent of whether the aggregate column exists. None when no phase column present. real_approx.
    ctx: {row} (latest)."""
    mx = _maxp_ithd(ctx.get("row") or {})
    return round(mx, 1) if mx is not None else None


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
