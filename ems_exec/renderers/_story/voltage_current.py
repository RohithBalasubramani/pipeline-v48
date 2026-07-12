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

    warn_frac = _facts.sev_warn_fraction()
    v_sev = _sev(v_worst["mag"], min(sag_pct, swell_pct) * warn_frac, min(sag_pct, swell_pct)) if v_worst else None
    i_sev = _sev(i_worst["mag"], i_unbal_limit * warn_frac, i_unbal_limit) if i_worst else None
    driver = _likely_driver(v_worst, v_sev, i_worst, i_sev, sag_pct, swell_pct, i_unbal_limit)

    badge = "review" if (v_sev in ("warning", "critical") or i_sev in ("warning", "critical")
                         or v_events or i_events) else "accounting"

    asked = (ctx.get("metric") or "").strip().lower()           # the 1a asked-about quantity ('voltage'/'current'/…)
    period_label = _period_label(ctx.get("window"))             # honest period for the drivers/title prose
    story = {
        "panel": panel_name, "range_window": _window_label(ctx.get("window")),
        "reporting_members": coverage["reporting_count"], "expected_members": coverage["expected_count"],
        "event_counts": {"voltage_deviation": v_events, "current_unbalance": i_events},
        "worst_voltage": ({"member": v_worst["name"], "deviation_pct": v_worst["signed"],
                           "type": v_worst["kind"], "severity": v_sev} if v_worst else None),
        "worst_current": ({"member": i_worst["name"], "unbalance_pct": i_worst["mag"],
                           "severity": i_sev} if i_worst else None),
        "likely_driver": driver,
        # LEAF BINDS [F5 unaudited-side-channel]: the very facts the blank stat leaves want are ALREADY computed here —
        # bind ONLY what we truly know (worst-V/I member + magnitude, the honest period label) into the card's REAL
        # payload leaves so they render REAL not unbound. narrative_ai applies + strips this private key; zero fabrication
        # (a fact we did not compute — vMax/vMin/neutralA/per-type splits — stays honest-blank, never invented).
        "_leaf_binds": _leaf_binds(v_worst, i_worst, period_label),
    }
    fb = {"text": _fallback_text(v_events, i_events, v_worst, v_sev, i_worst, i_sev, driver, asked)}
    return story, fb, badge


def _leaf_binds(v_worst, i_worst, period_label):
    """{payload_leaf_path: real_value} for the facts THIS builder truly computed → the card-19/25 V&C summary leaves.
    Only present facts are bound (a None worst → its leaves stay honest-blank). Paths are the V&C summary shape this
    page owns; narrative_ai writes ONLY leaves the skeleton already carries (no shape growth)."""
    binds = {"summary.period.label": period_label}
    if v_worst:
        binds["summary.stats.worstVoltage.vDeviation"] = v_worst["signed"]
        binds["summary.stats.worstVoltage.panel"] = v_worst["name"]
    if i_worst:
        binds["summary.stats.worstCurrent.iUnbalance"] = i_worst["mag"]
        binds["summary.stats.worstCurrent.panel"] = i_worst["name"]
    return binds


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


def _fallback_text(v_events, i_events, v_worst, v_sev, i_worst, i_sev, driver, asked=None):
    """The deterministic fallback sentence (used verbatim on any model failure). LEADS with the ASKED-ABOUT quantity
    [c19 voltage-question→current-led defect]: a voltage question opens with the voltage fact, a current question with
    the current fact; the band-crossing count and the other quantity follow. No `asked` → the original order stands."""
    total = (v_events or 0) + (i_events or 0)
    count = ("%d V/I band-crossing%s detected (%d voltage, %d current)."
             % (total, "" if total == 1 else "s", v_events or 0, i_events or 0))
    v_part = ("Worst voltage %s %+.1f%% at %s (%s)."
              % (v_worst["kind"], v_worst["signed"], v_worst["name"], v_sev or "normal")) if v_worst else None
    i_part = ("Worst current unbalance %.1f%% at %s (%s)."
              % (i_worst["mag"], i_worst["name"], i_sev or "normal")) if i_worst else None
    d_part = ("Likely driver: %s." % driver) if driver else None
    a = (asked or "").strip().lower()
    if a == "voltage" and v_part:
        ordered = [v_part, count, i_part, d_part]
    elif a == "current" and i_part:
        ordered = [i_part, count, v_part, d_part]
    else:
        ordered = [count, v_part, i_part, d_part]
    return " ".join(p for p in ordered if p)


def _norm_window(window):
    """Normalise the accepted window shapes → {start, end[, range]} or None. DICT-AWARE: the FE threads a
    {range,start,end,sampling} dict (not just a 2-tuple), which the old 2-tuple-only test treated as no-window."""
    if isinstance(window, dict):
        s, e = window.get("start"), window.get("end")
        if s or e:
            return {"start": s, "end": e, "range": window.get("range")}
        return None
    if isinstance(window, (list, tuple)) and len(window) == 2 and (window[0] or window[1]):
        return {"start": window[0], "end": window[1]}
    return None


def _window_label(window):
    """The honest FACTS-BASIS label for the story. This builder judges severities over the LATEST snapshot per member
    (_facts.live_snapshot → latest row), so the honest basis is 'latest' REGARDLESS of any FE date window — returning
    the window span here would MISLABEL a latest-snapshot analysis as a windowed one [never mislabel]. `_norm_window`
    makes the accepted shapes dict-aware so a future WINDOWED-facts path can light this up (return the span) without a
    dict-blind crash; until that read exists, the label stays the honest 'latest'."""
    _norm_window(window)                                        # dict-aware (validated; a windowed read would use it)
    return "latest"


def _period_label(window):
    """The honest PERIOD label for the drivers/title prose ('Redistribution at <label>; …' / '… · <label>'). The
    severities are the LATEST snapshot, so the honest period is the latest reading — NEVER a windowed claim over
    snapshot facts. A blank label leaves the FE prose dangling ('Redistribution at ;'), so it must always be real."""
    _norm_window(window)                                        # dict-aware; a windowed-facts path would name the span
    return "the latest reading"
