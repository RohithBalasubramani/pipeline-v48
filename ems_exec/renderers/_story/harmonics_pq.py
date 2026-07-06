"""ems_exec/renderers/_story/harmonics_pq.py — the Harmonics & PQ AI-summary story (card 25: current focus, period, worst
feeders by THD, and the selected feeder's specifics when one is picked), pre-judged in Python from REAL neuract snapshots
over the panel members.

Severity is judged off the IEEE-519 harmonic-distortion headroom columns (thd_voltage_*_pct → the per-phase max, and
thd_current_*_pct), each vs its statutory limit. Every limit is a DB-driven knob (config.event_thresholds V_THD/I_THD)
with the IEEE-519 code default. Python ranks the members by worst voltage-THD, picks the worst feeder, and (when ctx pins
a specific member via ctx['mfm_id']) surfaces that feeder's own THD as the "selected feeder specifics". Honest-degrade:
no member reports THD → a "no harmonics data" story whose fallback says so (never a fabricated distortion %). [atomic]
"""
from __future__ import annotations

from ems_exec.renderers._story import _facts


def _limits():
    """(v_thd_limit_pct, i_thd_limit_pct) — DB-driven (config.event_thresholds) with the IEEE-519 code defaults."""
    try:
        from config import event_thresholds as _et
        return (_et.num("V_THD", 5.0), _et.num("I_THD", 8.0))
    except Exception:
        return 5.0, 8.0


def _phase_max(live, cols):
    vals = [live.get(c) for c in cols]
    nums = [v for v in vals if isinstance(v, (int, float))]
    return max(nums) if nums else None


def _sev(mag, limit):
    if mag is None:
        return None
    if mag >= limit:
        return "critical"
    if mag >= limit * 0.7:
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

    snaps = _facts.snapshots_for(members)
    ranked = []
    selected = None
    for s in snaps:
        live = s.get("live") or {}
        vthd = _phase_max(live, _V_COLS)
        ithd = _phase_max(live, _I_COLS)
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
