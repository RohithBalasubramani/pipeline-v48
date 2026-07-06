"""ems_exec/renderers/_story/energy_distribution.py — the Energy & Distribution AI-summary story (loss / meter-gap /
best-path), pre-judged in Python from REAL neuract window-energy deltas over the panel members.

Mirrors backend2 energydist.py:118-158 `_ai_story` / `_ai_fallback`: energy per member = the import-counter delta over
the selected window; measured input = the panel's own delta (else the member sum); the metered-vs-measured gap is
UNMETERED distribution (not loss); genuine loss = max(0, measured − delivered); the badge is 'review' when the loss %
exceeds the expected band OR the meter gap flags over-metering, else 'accounting'. Every threshold is a DB-driven knob
(config.energy_balance_policy) with the backend2 code default. Honest-degrade: no measured input / no members → a
"no energy accounted" story whose fallback text says exactly that (never a fabricated 0%). [atomic]
"""
from __future__ import annotations

from ems_exec.renderers._story import _facts


def _cfg():
    """(over_metered_frac, unmetered_surface_frac, expected_loss_band_pct) — DB-driven with the backend2 code defaults."""
    try:
        from config import energy_balance_policy as _eb
        return (_eb.num("energy_balance.over_metered_frac", 0.02),
                _eb.num("energy_balance.unmetered_surface_frac", 0.01),
                _eb.num("energy_balance.expected_loss_band_pct", 3.0))
    except Exception:
        return 0.02, 0.01, 3.0


def _no_data(panel_name, coverage):
    story = {"panel": panel_name, "status": "no_energy_accounted", "reporting_members": coverage["reporting_count"],
             "expected_members": coverage["expected_count"]}
    fb = {"text": ("%s has no metered energy for the selected range — %d of %d members reporting; "
                   "distribution accounting unavailable."
                   % (panel_name, coverage["reporting_count"], coverage["expected_count"]))}
    return story, fb, "accounting"


def build(asset, card, ctx, members):
    over_metered_frac, unmetered_surface_frac, expected_loss_band_pct = _cfg()
    members, coverage = (members if isinstance(members, tuple) else _facts.resolve_members(ctx))
    window = ctx.get("window")
    panel_name = _facts._name_for(ctx.get("mfm_id")) or ctx.get("asset_table") or "Panel"

    # per-member window energy delta (kWh). Honest None for a member with no counter delta → excluded from the sum.
    rows = []
    for m in members:
        kwh, _kvarh = _facts.energy_delta(m.get("table"), window)
        rows.append({"name": m["name"], "kwh": kwh})

    metered_rows = [r for r in rows if r["kwh"] is not None]
    if not metered_rows:
        return _no_data(panel_name, coverage)

    metered_out = sum(r["kwh"] for r in metered_rows)
    # measured input = the panel's OWN counter delta when the panel is itself data-bearing; else the member sum.
    panel_kwh, _ = _facts.energy_delta(ctx.get("asset_table"), window)
    measured = panel_kwh if panel_kwh is not None else metered_out

    unmetered = max(0.0, measured - metered_out)
    delivered = metered_out + unmetered
    loss = max(0.0, measured - delivered)                       # genuine measurement loss (≈0 when fully accounted)
    gap = metered_out - measured                                # negative = normal under-metering (that's `unmetered`)
    over_metered = (gap > measured * over_metered_frac) if measured else False
    loss_pct = (loss / measured * 100.0) if measured else 0.0
    meter_gap_pct = (gap / measured * 100.0) if measured else 0.0
    within = loss_pct < expected_loss_band_pct
    meter_gap_status = "Review" if over_metered else "OK"

    ranked = sorted(metered_rows, key=lambda r: -r["kwh"])
    best = ranked[0] if ranked else None
    best_share = (best["kwh"] / delivered * 100.0) if (best and delivered) else None

    badge = "review" if (over_metered or loss_pct >= expected_loss_band_pct) else "accounting"

    story = {
        "panel": panel_name, "range_window": _window_label(window),
        "reporting_members": coverage["reporting_count"], "expected_members": coverage["expected_count"],
        "energy": {
            "measured_input_kwh": round(measured),
            "delivered_kwh": round(delivered),
            "metered_kwh": round(metered_out),
            "unmetered_kwh": round(unmetered),
            "loss_pct": round(loss_pct, 1),
            "loss_verdict": (("within the expected %g%% band" % expected_loss_band_pct) if within
                             else ("above the expected %g%% band" % expected_loss_band_pct)),
            "meter_gap_pct": round(meter_gap_pct, 1),
            "meter_gap_status": meter_gap_status,
        },
        "best_path": ({"name": best["name"], "share_pct": round(best_share)} if best_share is not None else None),
        "top_consumers": [{"name": r["name"], "share_pct": round(r["kwh"] / delivered * 100)}
                          for r in ranked[:3] if delivered],
    }
    fb = {"text": _fallback_text(loss_pct, expected_loss_band_pct, meter_gap_pct, meter_gap_status, best, best_share)}
    return story, fb, badge


def _fallback_text(loss_pct, band, meter_gap_pct, status, best, best_share):
    """Deterministic one-liner over the REAL numbers — used verbatim when the model is unavailable (mirrors the FE
    template so behaviour degrades to today's wording). NEVER fabricates a number."""
    if loss_pct < band:
        txt = ("Loss at %.1f%% is within the expected %g%% band; distribution running normally."
               % (loss_pct, band))
    else:
        txt = ("Loss at %.1f%% exceeds the expected %g%% band — inspect winding temperature and phase loading."
               % (loss_pct, band))
    txt += " Meter gap %.1f%% (%s)." % (meter_gap_pct, status)
    if best and best_share is not None:
        txt += " %s carries %d%% of delivered energy." % (best["name"], round(best_share))
    return txt


def _window_label(window):
    if isinstance(window, (list, tuple)) and len(window) == 2 and (window[0] or window[1]):
        return {"start": window[0], "end": window[1]}
    return "latest"
