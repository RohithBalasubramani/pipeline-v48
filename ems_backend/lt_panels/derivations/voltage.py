"""derivations/voltage.py — VOLTAGE nameplate/derived recoveries (pure fns, no DB). Each takes a `ctx` dict the consumer
fills from the live frame and returns the value, or None to honest-degrade (never a fabricated number).

Recoverable from compat because it KEPT voltage_avg + kpi_voltage_deviation_pct (the deviation is the inverse seam to the
nominal). [best-possible-recovery: cards 37/44]"""
from __future__ import annotations

import math


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
