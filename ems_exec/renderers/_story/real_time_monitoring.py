"""ems_exec/renderers/_story/real_time_monitoring.py — the Real-Time / Individual-Feeder AI-summary story (cards 8 & 28),
pre-judged in Python from REAL neuract latest-row snapshots.

Two shapes, one builder:
  · PANEL scope (card 8) — the leading feeder across the panel members: its live kW and load % (kVA vs the member's
    nameplate rating), plus the panel's average PF. Ranks members by live kW.
  · SINGLE FEEDER (card 28) — a single feeder's fused status verdict: live load % (apparent kVA vs rated kVA), PF,
    voltage-deviation %, phase balance (current unbalance %), and busbar temperature when the table exposes it.

Load % needs a REAL rating denominator: config.nameplates.rated_kva(asset_table) → None honest-degrades the load % slot
(never a fabricated denominator). Severity bands (load %, PF floor, deviation) are DB-driven knobs (config.app_config)
with code defaults. Honest-degrade: no live power/PF/voltage → a "no live data" story whose fallback says so. [atomic]
"""
from __future__ import annotations

from ems_exec.renderers._story import _facts


def _knobs():
    """Severity knobs (load%, PF floor, voltage-deviation band) — DB-driven with code defaults (behaviour-identical)."""
    try:
        from config.app_config import cfg
        return {
            "load_warn": cfg("rtm.load_warn_pct", 85.0), "load_crit": cfg("rtm.load_crit_pct", 100.0),
            "pf_floor": cfg("rtm.pf_floor", 0.9), "pf_warn": cfg("rtm.pf_warn", 0.95),
            "dev_warn": cfg("rtm.voltage_dev_warn_pct", 5.0), "dev_crit": cfg("rtm.voltage_dev_crit_pct", 10.0),
            "unbal_warn": cfg("rtm.current_unbal_warn_pct", 10.0),
            "temp_warn": cfg("rtm.busbar_temp_warn_c", 65.0), "temp_crit": cfg("rtm.busbar_temp_crit_c", 75.0),
        }
    except Exception:
        return {"load_warn": 85.0, "load_crit": 100.0, "pf_floor": 0.9, "pf_warn": 0.95,
                "dev_warn": 5.0, "dev_crit": 10.0, "unbal_warn": 10.0, "temp_warn": 65.0, "temp_crit": 75.0}


# busbar / winding temperature columns are non-standard across tables — probe these in order (honest None if none exist).
_TEMP_COLS = ["busbar_temperature_c", "busbar_temp_c", "main_tf_1_wind_temp", "main_tf_1_oil_temp",
              "winding_temperature_c", "temperature_c"]


def _rated_kva(asset_table):
    try:
        from config import nameplates as _np
        return _np.rated_kva(asset_table)
    except Exception:
        return None


def _load_pct(kva, rated):
    if not isinstance(kva, (int, float)) or not isinstance(rated, (int, float)) or rated <= 0:
        return None
    return kva / rated * 100.0


def _unsigned_pf(live):
    """The UNSIGNED true PF for a snapshot — kpi_true_pf first, else |power_factor_total| (reverse-CT sign). The SAME
    convention the panel-aggregate row uses, so the narrative badge/average never contradicts the tile PF (the
    'avg PF -0.499 (critical) vs 0.99 (Stable)' inconsistency)."""
    pf = live.get("kpi_true_pf")
    if isinstance(pf, (int, float)) and not isinstance(pf, bool):
        return pf
    s = live.get("power_factor_total")
    if isinstance(s, (int, float)) and not isinstance(s, bool):
        return abs(s)
    return None


def _load_sev(pct, k):
    if pct is None:
        return None
    if pct >= k["load_crit"]:
        return "critical"
    if pct >= k["load_warn"]:
        return "warning"
    return "normal"


def _no_data(name, coverage):
    story = {"subject": name, "status": "no_live_data", "reporting_members": coverage["reporting_count"],
             "expected_members": coverage["expected_count"]}
    fb = {"text": ("%s reported no live electrical data — %d of %d members reporting; status verdict unavailable."
                   % (name, coverage["reporting_count"], coverage["expected_count"]))}
    return story, fb, "accounting"


def build(asset, card, ctx, members):
    k = _knobs()
    members, coverage = (members if isinstance(members, tuple) else _facts.resolve_members(ctx))
    subject = _facts._name_for(ctx.get("mfm_id")) or ctx.get("asset_table") or "Feeder"

    # SINGLE FEEDER (card 28): one member and it IS the scoped asset → the fused per-feeder verdict.
    single = len(members) == 1
    if single:
        return _single_feeder(subject, members[0], ctx, k, coverage)
    return _panel_leader(subject, members, ctx, k, coverage)


# ── card 28: individual feeder — fused status verdict ────────────────────────────────────────────────────────────────
def _single_feeder(subject, member, ctx, k, coverage):
    table = member.get("table") or ctx.get("asset_table")
    live = _facts.live_snapshot(table)
    cols = _facts.LIVE_COLS + _TEMP_COLS
    if table:
        extra = {c: v for c, v in (_facts._nx.latest(table, _TEMP_COLS) or {}).items()}
        live = {**live, **extra}
    kw = live.get("active_power_total_kw")
    kva = live.get("apparent_power_total_kva")
    pf = _unsigned_pf(live)
    vdev = live.get("kpi_voltage_deviation_pct")
    unbal = live.get("current_unbalance_pct")
    temp = next((live.get(c) for c in _TEMP_COLS if isinstance(live.get(c), (int, float))), None)

    if not any(isinstance(x, (int, float)) for x in (kw, kva, pf, vdev)):
        return _no_data(subject, coverage)

    rated = _rated_kva(table)
    load_pct = _load_pct(kva, rated)
    load_sev = _load_sev(load_pct, k)
    pf_sev = _pf_sev(pf, k)
    dev_sev = _dev_sev(vdev, k)
    temp_sev = _temp_sev(temp, k)
    unbal_sev = "warning" if (isinstance(unbal, (int, float)) and unbal >= k["unbal_warn"]) else (
        "normal" if isinstance(unbal, (int, float)) else None)

    verdict = _worst([load_sev, pf_sev, dev_sev, temp_sev, unbal_sev])
    badge = "review" if verdict in ("warning", "critical") else "accounting"

    story = {
        "feeder": subject, "range_window": _window_label(ctx.get("window")),
        "overall_verdict": verdict,
        "load": ({"kw": _r(kw), "kva": _r(kva), "load_pct": _r(load_pct), "rated_kva": _r(rated),
                  "severity": load_sev} if (kw is not None or kva is not None) else None),
        "power_factor": ({"pf": _r(pf, 3), "severity": pf_sev} if pf is not None else None),
        "voltage_deviation": ({"deviation_pct": _r(vdev), "severity": dev_sev} if vdev is not None else None),
        "phase_balance": ({"current_unbalance_pct": _r(unbal), "severity": unbal_sev} if unbal is not None else None),
        "busbar_temperature": ({"temp_c": _r(temp), "severity": temp_sev} if temp is not None else None),
    }
    fb = {"text": _single_fallback(subject, verdict, load_pct, load_sev, pf, pf_sev, vdev, dev_sev, temp, unbal)}
    return story, fb, badge


def _single_fallback(name, verdict, load_pct, load_sev, pf, pf_sev, vdev, dev_sev, temp, unbal):
    lead = "%s status %s." % (name, verdict or "normal")
    bits = []
    if load_pct is not None:
        bits.append("load %.0f%% (%s)" % (load_pct, load_sev or "normal"))
    if pf is not None:
        bits.append("PF %.2f (%s)" % (pf, pf_sev or "normal"))
    if vdev is not None:
        bits.append("voltage %+.1f%% (%s)" % (vdev, dev_sev or "normal"))
    if isinstance(unbal, (int, float)):
        bits.append("phase unbalance %.1f%%" % unbal)
    if isinstance(temp, (int, float)):
        bits.append("busbar %.0f°C" % temp)
    return lead + (" " + ", ".join(bits) + "." if bits else "")


# ── card 8: real-time panel — the leading feeder + panel average PF ───────────────────────────────────────────────────
def _panel_leader(subject, members, ctx, k, coverage):
    snaps = _facts.snapshots_for(members)
    rows, pfs = [], []
    for s in snaps:
        live = s.get("live") or {}
        kw = live.get("active_power_total_kw")
        kva = live.get("apparent_power_total_kva")
        pf = _unsigned_pf(live)
        if isinstance(pf, (int, float)):
            pfs.append(pf)
        if isinstance(kw, (int, float)):
            rated = _rated_kva(s.get("table"))
            rows.append({"name": s["name"], "kw": kw, "kva": kva, "pf": pf,
                         "load_pct": _load_pct(kva, rated), "rated": rated})

    if not rows and not pfs:
        return _no_data(subject, coverage)

    avg_pf = round(sum(pfs) / len(pfs), 3) if pfs else None
    leader = max(rows, key=lambda r: r["kw"], default=None)
    load_sev = _load_sev(leader["load_pct"], k) if leader else None
    pf_sev = _pf_sev(avg_pf, k)

    badge = "review" if (load_sev in ("warning", "critical") or pf_sev in ("warning", "critical")) else "accounting"

    story = {
        "panel": subject, "range_window": _window_label(ctx.get("window")),
        "reporting_members": coverage["reporting_count"], "expected_members": coverage["expected_count"],
        "leading_feeder": ({"name": leader["name"], "kw": _r(leader["kw"]), "load_pct": _r(leader["load_pct"]),
                            "rated_kva": _r(leader["rated"]), "severity": load_sev} if leader else None),
        "average_power_factor": ({"pf": avg_pf, "severity": pf_sev} if avg_pf is not None else None),
        "active_feeders": len(rows),
    }
    fb = {"text": _panel_fallback(subject, leader, load_sev, avg_pf, pf_sev, len(rows))}
    return story, fb, badge


def _panel_fallback(name, leader, load_sev, avg_pf, pf_sev, n):
    if leader:
        lp = ("%.0f%% load" % leader["load_pct"]) if leader["load_pct"] is not None else "load n/a"
        txt = ("%s is the leading feeder at %.1f kW (%s, %s)."
               % (leader["name"], leader["kw"], lp, load_sev or "normal"))
    else:
        txt = "%s: no active-power reading across members." % name
    if avg_pf is not None:
        txt += " Panel average PF %.2f (%s) across %d feeders." % (avg_pf, pf_sev or "normal", n)
    return txt


# ── severity helpers ─────────────────────────────────────────────────────────────────────────────────────────────────
def _pf_sev(pf, k):
    if not isinstance(pf, (int, float)):
        return None
    if pf < k["pf_floor"]:
        return "critical"
    if pf < k["pf_warn"]:
        return "warning"
    return "normal"


def _dev_sev(vdev, k):
    if not isinstance(vdev, (int, float)):
        return None
    mag = abs(vdev)
    if mag >= k["dev_crit"]:
        return "critical"
    if mag >= k["dev_warn"]:
        return "warning"
    return "normal"


def _temp_sev(temp, k):
    if not isinstance(temp, (int, float)):
        return None
    if temp >= k["temp_crit"]:
        return "critical"
    if temp >= k["temp_warn"]:
        return "warning"
    return "normal"


_ORDER = {"critical": 3, "warning": 2, "normal": 1, None: 0}


def _worst(sevs):
    best, best_rank = "normal", 1
    saw = False
    for s in sevs:
        if s is None:
            continue
        saw = True
        if _ORDER[s] > best_rank:
            best, best_rank = s, _ORDER[s]
    return best if saw else "normal"


def _r(v, nd=1):
    return round(v, nd) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _window_label(window):
    if isinstance(window, (list, tuple)) and len(window) == 2 and (window[0] or window[1]):
        return {"start": window[0], "end": window[1]}
    return "latest"
