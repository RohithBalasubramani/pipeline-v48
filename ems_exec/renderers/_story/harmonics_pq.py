"""ems_exec/renderers/_story/harmonics_pq.py — the Harmonics & PQ AI-summary story (card 25: current focus, period, worst
feeders by THD, and the selected feeder's specifics when one is picked), pre-judged in Python from REAL neuract snapshots
over the panel members.

Each feeder's THD is the REAL neuract THD: the AVG of its per-phase thd_voltage_*_pct / thd_current_*_pct columns over
the SELECTED WINDOW (the canonical THD backend2 / the thdComplianceIeee519 derivation report), NOT the peak phase of one
latest instant — a peak-of-one-sample over-states the distortion and can fabricate a breach the real avg never has.
Each is compared vs its statutory limit — a DB-driven knob (config.event_thresholds V_THD/I_THD) with the IEEE-519 code
default. Python ranks the members by worst voltage-THD, picks the worst feeder, and (when ctx pins a specific member via
ctx['mfm_id']) surfaces that feeder's own THD as the "selected feeder specifics". Honest-degrade: a member with no
phase-THD logged over the window is OMITTED from the worst-list, and no member reporting THD → a "no harmonics data"
story whose fallback says so (never a fabricated distortion %; a breach is only ever claimed when the real avg ≥ the
limit). [atomic]
"""
from __future__ import annotations

from ems_exec.renderers._story import _facts
from ems_exec.data import neuract as _nx


def _limits():
    """(v_thd_limit_pct, i_thd_limit_pct) — DB-driven (config.event_thresholds) with the IEEE-519 code defaults."""
    try:
        from config import event_thresholds as _et
        return (_et.num("V_THD", 5.0), _et.num("I_THD", 8.0))
    except Exception:
        return 5.0, 8.0


def _window_thd(table, cols, window):
    """The REAL THD% for one feeder = the AVG of its per-phase thd_*_r/y/b_pct columns over the WINDOW.

    This is the canonical THD the neuract data reports (avg over thd_current_r/y/b, matching backend2 / the
    thdComplianceIeee519 derivation), NOT the peak-phase of one latest instant. Reads ONLY neuract via the one door
    (data.neuract.series → per-bucket per-phase AVGs over [start,end]), then averages the phases present in each bucket
    and averages those bucket means. None when the table has no phase-THD column logged over the window — so a feeder
    with no real THD honest-degrades (and is omitted from the worst-list) rather than inventing a value. [honest-degrade]"""
    if not table:
        return None
    start, end = (window or (None, None))[0], (window or (None, None))[1]
    rows = _nx.series(table, cols, start, end)
    if not rows:
        return None
    bucket_means = []
    for r in rows:
        phase_vals = [r.get(c) for c in cols]
        phase_vals = [v for v in phase_vals if isinstance(v, (int, float)) and not isinstance(v, bool)]
        if phase_vals:
            bucket_means.append(sum(phase_vals) / len(phase_vals))
    if not bucket_means:
        return None
    return sum(bucket_means) / len(bucket_means)


def _sev(mag, limit):
    if mag is None:
        return None
    if mag >= limit:
        return "critical"
    if mag >= limit * _facts.sev_warn_fraction():
        return "warning"
    return "normal"


_V_COLS = ["thd_voltage_r_pct", "thd_voltage_y_pct", "thd_voltage_b_pct"]
_I_COLS = ["thd_current_r_pct", "thd_current_y_pct", "thd_current_b_pct"]


def _no_data(panel_name, coverage):
    story = {"panel": panel_name, "status": "no_harmonics_data", "reporting_members": coverage["reporting_count"],
             "expected_members": coverage["expected_count"]}
    fb = {"text": ("%s reported no harmonic data for the selected period — %d of %d members reporting; "
                   "THD assessment unavailable."
                   % (panel_name, coverage["reporting_count"], coverage["expected_count"]))}
    return story, fb, "accounting"


def build(asset, card, ctx, members):
    v_limit, i_limit = _limits()
    members, coverage = (members if isinstance(members, tuple) else _facts.resolve_members(ctx))
    panel_name = _facts._name_for(ctx.get("mfm_id")) or ctx.get("asset_table") or "Panel"
    selected_mfm = ctx.get("mfm_id")

    window = ctx.get("window")
    snaps = _facts.snapshots_for(members)
    ranked = []
    selected = None
    for s in snaps:
        # REAL THD = the window-average of the per-phase thd_*_r/y/b_pct columns (the neuract-reported THD), NOT the
        # peak phase of one latest instant. A feeder with no phase-THD logged over the window → None (omitted below).
        vthd = _window_thd(s.get("table"), _V_COLS, window)
        ithd = _window_thd(s.get("table"), _I_COLS, window)
        if vthd is None and ithd is None:
            continue
        rec = {"name": s["name"], "vthd": (round(vthd, 2) if vthd is not None else None),
               "ithd": (round(ithd, 2) if ithd is not None else None),
               "vthd_mag": (vthd if vthd is not None else -1.0)}
        ranked.append(rec)
        if selected_mfm is not None and s.get("mfm_id") == selected_mfm and (vthd is not None or ithd is not None):
            selected = rec

    if not ranked:
        return _no_data(panel_name, coverage)

    ranked.sort(key=lambda r: -r["vthd_mag"])
    worst = ranked[0]
    worst_sev = _sev(worst["vthd"], v_limit)
    breaches = sum(1 for r in ranked if r["vthd"] is not None and r["vthd"] >= v_limit)

    badge = "review" if (worst_sev in ("warning", "critical") or breaches) else "accounting"

    story = {
        "panel": panel_name, "period_window": _window_label(ctx.get("window")),
        "focus": (selected["name"] if selected else panel_name),
        "reporting_members": coverage["reporting_count"], "expected_members": coverage["expected_count"],
        "limits": {"voltage_thd_pct": v_limit, "current_thd_pct": i_limit},
        "worst_feeders": [{"name": r["name"], "voltage_thd_pct": r["vthd"], "current_thd_pct": r["ithd"]}
                          for r in ranked[:3]],
        "worst_feeder": {"name": worst["name"], "voltage_thd_pct": worst["vthd"],
                         "current_thd_pct": worst["ithd"], "severity": worst_sev},
        "breach_count": breaches,
        "selected_feeder": ({"name": selected["name"], "voltage_thd_pct": selected["vthd"],
                             "current_thd_pct": selected["ithd"]} if selected else None),
    }
    fb = {"text": _fallback_text(worst, worst_sev, v_limit, breaches, selected)}
    return story, fb, badge


def _fallback_text(worst, worst_sev, v_limit, breaches, selected):
    if worst["vthd"] is not None:
        txt = ("Worst voltage THD %.1f%% at %s (%s vs %g%% IEEE-519 limit)"
               % (worst["vthd"], worst["name"], worst_sev or "normal", v_limit))
    else:
        txt = "Worst-feeder voltage THD unavailable; current THD leading at %s" % worst["name"]
    if worst["ithd"] is not None:
        txt += ", current THD %.1f%%" % worst["ithd"]
    txt += "."
    if breaches:
        txt += " %d feeder%s over the voltage-THD limit." % (breaches, "" if breaches == 1 else "s")
    if selected and selected["vthd"] is not None:
        txt += " Selected %s at %.1f%% voltage THD." % (selected["name"], selected["vthd"])
    return txt


def _window_label(window):
    if isinstance(window, (list, tuple)) and len(window) == 2 and (window[0] or window[1]):
        return {"start": window[0], "end": window[1]}
    return "latest"
