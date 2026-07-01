"""Shared Energy & Power derived metrics (Path A — WS-layer compute).

Used by every type's `EnergyPower` strategy to derive the values the
frontend's `inputOutput` widget expects but the simulator doesn't ship
as columns. Computed per-tick from raw values already in the row.

Mirrors the deriver pattern in `_pq_labels.py`: pure functions of a
single row dict, returned via `compute_status(row)` so the FE can read
them from `frame.status.<key>`.

The reasoning for putting numbers in `status`: it's the only per-tick
side-channel the column-row consumer pattern exposes. Frontend already
parses `status` as a free-form dict. No new wire-frame field needed.
"""
from __future__ import annotations


def derive_efficiency_pct(row):
    """Live AC efficiency = lv_output / hv_input × 100.

    UPS: inverter AC output / rectifier AC input
    Transformer: LV side / HV side
    """
    hv = row.get('hv_input_kw')
    lv = row.get('lv_output_kw')
    if hv is None or lv is None or hv == 0:
        return None
    return round(lv / hv * 100, 2)


def derive_delta_pct(row):
    """HV-to-LV gap as % of LV — drives the "+2.9%" arrow between tiles."""
    hv = row.get('hv_input_kw')
    lv = row.get('lv_output_kw')
    if hv is None or lv is None or lv == 0:
        return None
    return round((hv - lv) / lv * 100, 2)


def derive_active_energy_loss_today_kwh(row):
    """Approximation: today's active-energy × loss% / 100.

    Exact integral of loss_kw over today would need history; this
    constant-loss-ratio approximation is what's tractable per-tick.
    Good enough for the tile display; not for billing.
    """
    e = row.get('active_energy_today_kwh')
    pct = row.get('active_power_loss_pct')
    if e is None or pct is None:
        return None
    return round(e * pct / 100.0, 2)


def derive_expected_energy_loss_today_kwh(row, *, rated_efficiency_pct=98.0):
    """Expected loss = active_energy_today_kwh × (1/rated_eff − 1).

    `rated_efficiency_pct` is a per-MFM config constant; pass it from
    the strategy if available. Defaults to 98% (typical transformer).
    """
    e = row.get('active_energy_today_kwh')
    if e is None or not rated_efficiency_pct:
        return None
    return round(e * (100.0 / rated_efficiency_pct - 1), 2)


def derive_loss_pct_of_input(row):
    """Same number as active_power_loss_pct but named the way FE expects."""
    pct = row.get('active_power_loss_pct')
    return round(pct, 2) if pct is not None else None


def derive_all_ep(row, *, rated_efficiency_pct=98.0):
    """Bundle: return every derived E&P metric as one dict."""
    out = {}
    for fn, key in [
        (derive_efficiency_pct,              'efficiency_pct'),
        (derive_delta_pct,                   'hv_lv_delta_pct'),
        (derive_active_energy_loss_today_kwh,'active_energy_loss_today_kwh'),
        (derive_loss_pct_of_input,           'loss_pct_of_input'),
    ]:
        v = fn(row)
        if v is not None:
            out[key] = v
    v = derive_expected_energy_loss_today_kwh(row, rated_efficiency_pct=rated_efficiency_pct)
    if v is not None:
        out['expected_energy_loss_today_kwh'] = v
    return out
