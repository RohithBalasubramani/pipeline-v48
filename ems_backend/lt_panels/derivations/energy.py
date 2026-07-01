"""derivations/energy.py — ENERGY recoveries (pure fns, no DB). compat KEPT active_energy_import_kwh +
reactive_energy_import_kvarh (cumulative), so period energy is a windowed delta and MVAh is the quadrature sum.
[best-possible-recovery: cards 14/39]"""
from __future__ import annotations

import math


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def window_energy_kwh(ctx):
    """Period active energy = cumulative import at window END − at window START (a windowed_delta). real_exact.
    ctx: {start_row, end_row} each with active_energy_import_kwh."""
    s = _f((ctx.get("start_row") or {}).get("active_energy_import_kwh"))
    e = _f((ctx.get("end_row") or {}).get("active_energy_import_kwh"))
    if s is None or e is None:
        return None
    return round(max(e - s, 0.0), 1)


def todays_energy_total_kwh(ctx):
    """Today's active+reactive energy = windowed deltas of the two cumulative import columns. real_exact.
    ctx: {start_row, end_row} with active_energy_import_kwh + reactive_energy_import_kvarh."""
    s, e = ctx.get("start_row") or {}, ctx.get("end_row") or {}
    a0, a1 = _f(s.get("active_energy_import_kwh")), _f(e.get("active_energy_import_kwh"))
    r0, r1 = _f(s.get("reactive_energy_import_kvarh")), _f(e.get("reactive_energy_import_kvarh"))
    if None in (a0, a1):
        return None
    active = max(a1 - a0, 0.0)
    reactive = max((r1 - r0), 0.0) if None not in (r0, r1) else 0.0
    return round(active + reactive, 1)


def progress_active_pct(ctx):
    """Active share of today's active+reactive energy (the progress-bar split). real_exact. ctx as todays_energy."""
    s, e = ctx.get("start_row") or {}, ctx.get("end_row") or {}
    a0, a1 = _f(s.get("active_energy_import_kwh")), _f(e.get("active_energy_import_kwh"))
    r0, r1 = _f(s.get("reactive_energy_import_kvarh")), _f(e.get("reactive_energy_import_kvarh"))
    if None in (a0, a1, r0, r1):
        return None
    active, reactive = max(a1 - a0, 0.0), max(r1 - r0, 0.0)
    tot = active + reactive
    return round(active / tot * 100.0, 1) if tot > 0 else None


def mvah_active(ctx):
    """Cumulative active energy import in MWh (MVAh active leg). real_exact. ctx: {row}."""
    a = _f((ctx.get("row") or {}).get("active_energy_import_kwh"))
    return round(a / 1000.0, 2) if a is not None else None


def mvah_reactive(ctx):
    """Cumulative reactive energy import in MVArh. real_exact. ctx: {row}."""
    r = _f((ctx.get("row") or {}).get("reactive_energy_import_kvarh"))
    return round(r / 1000.0, 2) if r is not None else None


def cumulative_apparent_mvah(ctx):
    """Apparent energy MVAh = hypot(active MVAh, reactive MVArh) — the textbook quadrature identity. real_exact."""
    a, r = mvah_active(ctx), mvah_reactive(ctx)
    if a is None:
        return None
    return round(math.hypot(a, r or 0.0), 2)


def expected_loss_kwh(ctx):
    """Expected loss = window energy × (1 − target_efficiency%/100). real_exact ONLY when target_efficiency_pct is wired
    from config; else None (honest-degrade). ctx: {start_row, end_row, target_efficiency_pct}."""
    eff = _f(ctx.get("target_efficiency_pct"))
    if eff is None:
        return None
    win = window_energy_kwh(ctx)
    if win is None:
        return None
    return round(win * (1.0 - eff / 100.0), 1)
