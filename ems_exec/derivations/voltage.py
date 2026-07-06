"""derivations/voltage.py — VOLTAGE nameplate/derived recoveries (pure fns, no DB). Each takes a `ctx` dict the consumer
fills from the live frame and returns the value, or None to honest-degrade (never a fabricated number).

Recoverable from compat because it KEPT voltage_avg + kpi_voltage_deviation_pct (the deviation is the inverse seam to the
nominal). [best-possible-recovery: cards 37/44]"""
from __future__ import annotations

import math


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def nominal_voltage_ln(ctx):
    """L-N nominal = measured avg ÷ (1 + deviation%). 239.2 / (1 + (-0.15)/100) ≈ 240 V L-N (415 L-L). real_exact."""
    row = ctx.get("row") or {}
    v, dev = row.get("voltage_avg"), row.get("kpi_voltage_deviation_pct")
    try:
        v = float(v); dev = float(dev)
    except (TypeError, ValueError):
        return None
    denom = 1.0 + dev / 100.0
    return v / denom if denom > 0 else None


def statutory_band(ctx):
    """±10% IS-12360 statutory band around the recovered L-N nominal → {min, max}. real_exact (band = standard ±10%)."""
    nom = nominal_voltage_ln(ctx)
    if nom is None:
        return None
    return {"min": round(nom * 0.90, 1), "max": round(nom * 1.10, 1), "nominal": round(nom, 1)}


def worst_v_dev(ctx):
    """Worst voltage-deviation magnitude over a bucket = max(|max_dev|, |min_dev|). Ported from CMD_V2 backend2
    voltagecurrent.py:157-164 — a plain max() of the signed kpi_voltage_deviation_pct column alone MISSES a deep negative
    sag (the worst deviation is the largest magnitude in EITHER direction). Honest-degrade to None when neither the max
    nor the min deviation is present. ctx accepts either the pre-aggregated bucket extremes
    {max_dev, min_dev} (e.g. from a max/min bucket read) OR a raw {series} of rows with kpi_voltage_deviation_pct."""
    row = ctx or {}
    mx, mn = _f(row.get("max_dev")), _f(row.get("min_dev"))
    if mx is None and mn is None:
        vals = []
        for r in (row.get("series") or []):
            x = r.get("kpi_voltage_deviation_pct") if isinstance(r, dict) else None
            if isinstance(x, (int, float)):
                vals.append(float(x))
        if not vals:
            return None
        mx, mn = max(vals), min(vals)
    hi = abs(mx) if mx is not None else 0.0
    lo = abs(mn) if mn is not None else 0.0
    return round(max(hi, lo), 2)


def worst_phase_spread(ctx):
    """Worst PHASE SPREAD over the window = max over the observed samples of (max(phase) − min(phase)) across the L-N
    phase magnitudes (voltage_r_n / voltage_y_n / voltage_b_n) — the real 'Worst Spread' a voltage-history card means
    (DB ground truth ≤ a few volts on a healthy feeder; the card-44 defect shipped the ~240 V NOMINAL as a 'spread').
    ctx: {series:[{voltage_r_n, voltage_y_n, voltage_b_n}, …]} (falls back to the latest {row} when no series — a
    single-sample spread, real but instantaneous). Honest-degrade to None when fewer than 2 phases are present in every
    sample (a spread needs at least two phases — never fabricated from one)."""
    rows = ctx.get("series") or []
    if not rows and ctx.get("row"):
        rows = [ctx.get("row")]
    worst = None
    for r in rows:
        if not isinstance(r, dict):
            continue
        ph = [v for v in (_f(r.get("voltage_r_n")), _f(r.get("voltage_y_n")), _f(r.get("voltage_b_n")))
              if v is not None]
        if len(ph) < 2:
            continue
        spread = max(ph) - min(ph)
        if worst is None or spread > worst:
            worst = spread
    return round(worst, 2) if worst is not None else None


def voltage_history_domain(ctx):
    """Chart Y-domain + expected band for a voltage-history card, computed over the observed L-N phase series in compat
    (voltage_r_n / voltage_y_n / voltage_b_n or voltage_avg). real_exact — buildChartDomain over real samples."""
    series = ctx.get("series") or []
    vals = []
    for r in series:
        for k in ("voltage_avg", "voltage_r_n", "voltage_y_n", "voltage_b_n"):
            x = r.get(k)
            if isinstance(x, (int, float)):
                vals.append(float(x))
    if not vals:
        return None
    lo, hi = min(vals), max(vals)
    pad = max((hi - lo) * 0.1, 1.0)
    band = statutory_band({"row": (series[-1] if series else {})})
    return {
        "minY": round(lo - pad, 1), "maxY": round(hi + pad, 1),
        "expectedMin": band["min"] if band else None,
        "expectedMax": band["max"] if band else None,
    }
