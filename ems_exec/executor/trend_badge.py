"""ems_exec/executor/trend_badge.py — HONEST rail/trend status-badge derivation [family H, cards 7/10 class].

THE DEFECT: the RTM rail cards (RealTimeMonitoringRail / TrendCard) render a status pill from a `statusBadge`
view-model ({tone, label, dsTone, key?, vocab?} — CMD_V2 RailStatusBadge). The strip blanked its enum leaves ('') and
RailStatusPill indexes STATUS_PILL_TONES by the blank → `.bg` throws and the Boundary masked REAL cards.

THE HONEST FIX: the badge IS derivable — CMD_V2's OWN rule (realTimeRailViewModel.ts trendDir/dirBadge) is a pure
function of the card's own BOUND series (the fill wrote it from neuract):

    diff = series[-1] - series[0];  pct = |diff| / max(1, series[0])
    pct < display.trend_flat_pct (default 0.02, CMD_V2's constant)  → key 'stable',  tone 'success'
    diff > 0                                                        → key 'rising',  tone 'warning'
    else                                                            → key 'falling', tone 'success'
    dsTone: success → 'normal', warning → 'alarm' (RAIL_TONE_TO_DS); label = vocab[key] (payload-carried word set,
    default Rising/Falling/Stable — TREND_LABEL_DEFAULTS).

The series is REAL bound data; the derived word is a deterministic restatement of it — a derivation, not a
fabrication. NO series (or a blank/short one) → the badge stays blank (underivable; the FE renders color-only chrome).

Shape-driven (any dict under a key ending 'statusBadge', with the series found as a sibling `series` list or inside a
sibling `trend.series`), NO card ids. BLANK-ONLY writes. Runs as a late fill pass; never raises.
"""
from __future__ import annotations

DASH = "—"
TREND_LABEL_DEFAULTS = {"rising": "Rising", "falling": "Falling", "stable": "Stable"}
RAIL_TONE_TO_DS = {"success": "normal", "warning": "alarm"}


def _flat_pct():
    """DB row app_config `display.trend_flat_pct` — code default 0.02 (CMD_V2 trendDir's constant)."""
    try:
        from config.app_config import cfg
        return float(cfg("display.trend_flat_pct", 0.02))
    except Exception:
        return 0.02


def _blank(v):
    return v is None or v == "" or v == DASH


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _series_of(parent):
    """The numeric series the badge describes: the sibling `series` list, else the sibling `trend.series` (the rail
    header badge sits beside the whole trend card). First/last must be REAL numbers — else underivable → None."""
    for cand in (parent.get("series"), (parent.get("trend") or {}).get("series") if isinstance(parent.get("trend"), dict) else None):
        if isinstance(cand, list) and len(cand) >= 2 and _num(cand[0]) and _num(cand[-1]):
            return cand
    return None


def _derive(series, vocab=None):
    """CMD_V2 trendDir + dirBadge, byte-faithful. Returns {key, tone, dsTone, label}."""
    diff = series[-1] - series[0]
    pct = abs(diff) / max(1.0, float(series[0]))
    if pct < _flat_pct():
        key = "stable"
    else:
        key = "rising" if diff > 0 else "falling"
    tone = "warning" if key == "rising" else "success"
    words = vocab if isinstance(vocab, dict) else {}
    label = words.get(key) or TREND_LABEL_DEFAULTS[key]
    return {"key": key, "tone": tone, "dsTone": RAIL_TONE_TO_DS[tone], "label": label}


def _walk(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if (str(k).lower().endswith("statusbadge") and isinstance(v, dict)
                    and _blank(v.get("tone")) and _blank(v.get("label"))):
                series = _series_of(node)
                if series is not None:
                    v.update(_derive(series, vocab=v.get("vocab")))
            _walk(v)
    elif isinstance(node, list):
        for v in node:
            _walk(v)


def apply(out):
    """Derive every BLANK trend status badge in the completed payload from its own bound series. Never raises."""
    if not isinstance(out, (dict, list)):
        return out
    try:
        _walk(out)
    except Exception:
        pass
    return out
