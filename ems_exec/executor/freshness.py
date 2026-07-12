"""ems_exec/executor/freshness.py — HONEST freshness derivation [family H, cards 36/37/38 class].

THE DEFECT: the RTM panels (PowerEnergyPanel / VoltageMonitorPanel / CurrentMonitorPanel) render a LiveTag from a
`freshness` view-model ({status, label, tone, lastUpdateLabel, title} — CMD_V2 RealTimeFreshnessViewModel). The strip
blanked its state leaves ('' / 'Last update —'), and StatusBadge indexes its palette by `tone` → PALETTE[''] is
undefined → `.bg` throws and the Boundary masked three REAL cards.

THE HONEST FIX: freshness IS derivable — it is a pure function of the fill's own newest-sample age, byte-faithful to
CMD_V2's OWN buildFreshness (realTimeMonitoringViewModel.ts):

    no newest timestamp             → status 'unknown', label 'Offline',  tone 'neutral', 'Last update —'
    age > freshness.stale_after_s   → status 'stale',   label 'Stale',    tone 'warning', 'Last update HH:MM:SS'
    else                            → status 'live',    label 'Live',     tone 'fail',    'Last update HH:MM:SS'

('fail' is the red LIVE color in CMD_V2's palette — see LiveTag.tsx.) The timestamp is the REAL newest sample of the
card's own asset table (ems_exec.data.neuract.latest_ts), formatted HH:MM:SS in the SITE timezone
(config.windows.site_tz) — never a fabricated clock. The threshold is the DB row app_config `freshness.stale_after_s`
(code default 180 s == CMD_V2 RTM_STALE_FALLBACK_THRESHOLD_MS).

Shape-driven (the freshness KEY CONTRACT {status,label,tone,lastUpdateLabel}), NO card ids. BLANK-ONLY writes: an
authored/bound non-blank state is never overwritten; with no asset table the leaves stay blank (the FE guard renders
neutral chrome). Runs as a late fill pass; never raises.
"""
from __future__ import annotations

from datetime import datetime, timezone

DASH = "—"
CONTRACT = ("status", "label", "tone", "lastUpdateLabel")   # the RealTimeFreshnessViewModel key signature


def _stale_after_s():
    """DB row app_config `freshness.stale_after_s` — code default 180 s (== CMD_V2's RTM 3-minute fallback)."""
    try:
        from config.app_config import cfg
        return float(cfg("freshness.stale_after_s", 180.0))
    except Exception:
        return 180.0


def _site_tz():
    try:
        from config.windows import site_tz
        return site_tz()
    except Exception:
        return timezone.utc


def _blank(v):
    return v is None or v == "" or v == DASH


def _is_freshness(d):
    return isinstance(d, dict) and all(k in d for k in CONTRACT)


def _fmt_age(seconds):
    """CMD_V2 formatAge: <90 s → 'Ns ago'; <90 min → 'Nm ago'; else 'XhYm ago' (byte-faithful rounding)."""
    total_s = max(0, round(seconds))
    if total_s < 90:
        return f"{total_s}s ago"
    total_m = round(total_s / 60)
    if total_m < 90:
        return f"{total_m}m ago"
    hours, minutes = total_m // 60, total_m % 60
    return f"{hours}h {minutes}m ago" if minutes > 0 else f"{hours}h ago"


def _derive(newest, now=None):
    """The freshness leaves for a newest-sample timestamp (None → the no-timestamp state). Pure; byte-faithful to
    CMD_V2 buildFreshness."""
    if newest is None:
        return {"status": "unknown", "label": "Offline", "tone": "neutral",
                "lastUpdateLabel": f"Last update {DASH}", "title": "No backend timestamp is available yet"}
    if now is None:
        from replay.clock import now as _replay_now             # frozen during replay: live/stale badge reproduces
        now = _replay_now(timezone.utc)
    if newest.tzinfo is None:
        newest = newest.replace(tzinfo=timezone.utc)
    label_hms = newest.astimezone(_site_tz()).strftime("%H:%M:%S")
    age_s = (now - newest).total_seconds()
    if age_s > _stale_after_s():
        return {"status": "stale", "label": "Stale", "tone": "warning",
                "lastUpdateLabel": f"Last update {label_hms}",
                "title": f"Latest backend row {label_hms} ({_fmt_age(age_s)})"}
    return {"status": "live", "label": "Live", "tone": "fail",
            "lastUpdateLabel": f"Last update {label_hms}", "title": f"Latest backend row {label_hms}"}


def _walk(node, derived):
    if isinstance(node, dict):
        if _is_freshness(node) and _blank(node.get("status")) and _blank(node.get("tone")):
            node.update(derived)
        else:
            for v in node.values():
                _walk(v, derived)
    elif isinstance(node, list):
        for v in node:
            _walk(v, derived)


def apply(out, asset_table, now=None, newest=None):
    """Derive every BLANK freshness view-model in the completed payload from the asset's newest-sample age. `newest`
    (datetime) overrides the DB read for tests. No freshness contract in the payload → no reads, no-op. Never raises."""
    if not isinstance(out, (dict, list)):
        return out
    try:
        # cheap pre-scan: only hit the DB when a blank freshness contract actually exists in this payload
        found = []

        def _scan(n):
            if isinstance(n, dict):
                if _is_freshness(n) and _blank(n.get("status")) and _blank(n.get("tone")):
                    found.append(True)
                else:
                    for v in n.values():
                        _scan(v)
            elif isinstance(n, list):
                for v in n:
                    _scan(v)

        _scan(out)
        if not found:
            return out
        if newest is None and asset_table:
            from ems_exec.data import neuract as _nx
            newest = _nx.latest_ts(asset_table)
        _walk(out, _derive(newest, now=now))
    except Exception:
        pass
    return out
