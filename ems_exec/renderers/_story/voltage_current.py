"""ems_exec/renderers/_story/voltage_current.py — the Voltage & Current AI-summary story (card 19: event counts, panels
affected, worst V/I severities, a "Likely Drivers" hypothesis), pre-judged in Python from REAL neuract snapshots over the
panel members.

The simulator's boolean *_event_active flags rarely fire, so — like backend2 voltagecurrent.py — severities are judged
off the RAW numeric columns crossing their statutory bands: voltage deviation (kpi_voltage_deviation_pct) vs the ±sag/
swell band, current unbalance (current_unbalance_pct) vs its statutory limit. Every band is a DB-driven knob
(config.event_thresholds) with the IS-12360 / IEEE code default. Python counts how many members breach, picks the worst
V and worst I member, and derives a likely-driver hypothesis from WHICH quantity dominates. Honest-degrade: no member
reports voltage/current → a "no V/I data" story whose fallback says so (never a fabricated severity). [atomic]
"""
from __future__ import annotations

from ems_exec.renderers._story import _facts


def _bands():
    """(sag_pct, swell_pct, i_unbal_pct) statutory bands — DB-driven (config.event_thresholds) with IS/IEEE defaults."""
    try:
        from config import event_thresholds as _et
        return (abs(_et.num("SAG", -10.0)), _et.num("SWELL", 10.0), _et.num("I_UNBAL", 10.0))
    except Exception:
        return 10.0, 10.0, 10.0


def _sev(mag, warn, crit):
    if mag is None:
        return None
    if mag >= crit:
        return "critical"
    if mag >= warn:
        return "warning"
    return "normal"


def _no_data(panel_name, coverage):
    story = {"panel": panel_name, "status": "no_vi_data", "reporting_members": coverage["reporting_count"],
             "expected_members": coverage["expected_count"]}
    fb = {"text": ("%s reported no voltage/current data for the selected bucket — %d of %d members reporting; "
                   "severities and drivers unavailable."
                   % (panel_name, coverage["reporting_count"], coverage["expected_count"]))}
    return story, fb, "accounting"


def build(asset, card, ctx, members):
    sag_pct, swell_pct, i_unbal_limit = _bands()
    members, coverage = (members if isinstance(members, tuple) else _facts.resolve_members(ctx))
    panel_name = _facts._name_for(ctx.get("mfm_id")) or ctx.get("asset_table") or "Panel"

    snaps = _facts.snapshots_for(members)
    # worst voltage deviation (|kpi_voltage_deviation_pct|) and worst current unbalance across the reporting members.
    v_worst = i_worst = None
    v_events = i_events = 0
    v_seen = i_seen = 0
    for s in snaps:
        live = s.get("live") or {}
        vdev = live.get("kpi_voltage_deviation_pct")
        iunb = live.get("current_unbalance_pct")
        if isinstance(vdev, (int, float)):
            v_seen += 1
            mag = abs(vdev)
            if mag >= min(sag_pct, swell_pct):
                v_events += 1
            if v_worst is None or mag > v_worst["mag"]:
                # NAME the quantity honestly [c19 wording defect]: 'sag'/'swell' are EVENT words — a deviation that
                # never crossed its statutory band is NOT a sag ('0 events … worst sag of -4.06%' self-contradicts;
                # -4.06% is simply the worst DEVIATION). Only a band-crossing magnitude earns the event word.
                band = swell_pct if vdev > 0 else sag_pct
                kind = ("swell" if vdev > 0 else "sag") if mag >= band else "deviation"
                v_worst = {"name": s["name"], "mag": mag, "signed": round(vdev, 2), "kind": kind}
        if isinstance(iunb, (int, float)):
            i_seen += 1
            if iunb >= i_unbal_limit:
                i_events += 1
            if i_worst is None or iunb > i_worst["mag"]:
                i_worst = {"name": s["name"], "mag": round(iunb, 2)}

    if v_seen == 0 and i_seen == 0:
        return _no_data(panel_name, coverage)

    v_sev = _sev(v_worst["mag"], min(sag_pct, swell_pct) * 0.7, min(sag_pct, swell_pct)) if v_worst else None
    i_sev = _sev(i_worst["mag"], i_unbal_limit * 0.7, i_unbal_limit) if i_worst else None
    driver = _likely_driver(v_worst, v_sev, i_worst, i_sev, sag_pct, swell_pct, i_unbal_limit)

    badge = "review" if (v_sev in ("warning", "critical") or i_sev in ("warning", "critical")
                         or v_events or i_events) else "accounting"

    story = {
        "panel": panel_name, "range_window": _window_label(ctx.get("window")),
        "reporting_members": coverage["reporting_count"], "expected_members": coverage["expected_count"],
        "event_counts": {"voltage_deviation": v_events, "current_unbalance": i_events},
        "worst_voltage": ({"member": v_worst["name"], "deviation_pct": v_worst["signed"],
                           "type": v_worst["kind"], "severity": v_sev} if v_worst else None),
        "worst_current": ({"member": i_worst["name"], "unbalance_pct": i_worst["mag"],
                           "severity": i_sev} if i_worst else None),
        "likely_driver": driver,
    }
    fb = {"text": _fallback_text(v_events, i_events, v_worst, v_sev, i_worst, i_sev, driver)}
    return story, fb, badge


def _likely_driver(v_worst, v_sev, i_worst, i_sev, sag_pct, swell_pct, i_unbal_limit):
    """A pre-judged hypothesis string over the real numbers (the model narrates it, never invents one)."""
    v_bad = v_sev in ("warning", "critical")
    i_bad = i_sev in ("warning", "critical")
    if v_bad and i_bad:
        return ("combined phase imbalance and voltage %s at %s — check load distribution and upstream tap"
                % (v_worst["kind"], v_worst["name"]))
    if i_bad:
        return ("single-phase / unbalanced loading at %s (%.1f%% current unbalance vs %g%% limit)"
                % (i_worst["name"], i_worst["mag"], i_unbal_limit))
    if v_bad:
        band = swell_pct if v_worst["kind"] == "swell" else (sag_pct if v_worst["kind"] == "sag"
                                                             else min(sag_pct, swell_pct))
        return ("voltage %s at %s (%.1f%% vs %g%% band) — likely upstream tap / feeder loading"
                % (v_worst["kind"], v_worst["name"], v_worst["mag"], band))
    return "no dominant driver — voltage and current within their statutory bands"


def _fallback_text(v_events, i_events, v_worst, v_sev, i_worst, i_sev, driver):
    parts = []
    total = (v_events or 0) + (i_events or 0)
    parts.append("%d V/I band-crossing%s detected (%d voltage, %d current)."
                 % (total, "" if total == 1 else "s", v_events or 0, i_events or 0))
    if v_worst:
        parts.append("Worst voltage %s %+.1f%% at %s (%s)."
                     % (v_worst["kind"], v_worst["signed"], v_worst["name"], v_sev or "normal"))
    if i_worst:
        parts.append("Worst current unbalance %.1f%% at %s (%s)."
                     % (i_worst["mag"], i_worst["name"], i_sev or "normal"))
    if driver:
        parts.append("Likely driver: %s." % driver)
    return " ".join(parts)


def _window_label(window):
    if isinstance(window, (list, tuple)) and len(window) == 2 and (window[0] or window[1]):
        return {"start": window[0], "end": window[1]}
    return "latest"
