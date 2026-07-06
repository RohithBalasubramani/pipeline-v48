"""layer2/coherence.py — WINDOW/LABEL COHERENCE (one atomic concern). [c14 'Monthly'+range=this-month on a 24h fill;
c16 range=last-7-days beside a 24h-backfilled window]

A card's period CHROME (a `periodLabel`/`range` metadata leaf) and its DECLARED range must agree with the FILL WINDOW
the consumer will actually use (di.consumer.range / the backfilled di.window bounds) — a 'Monthly' label over a 24-hour
delta is a mislabeled number, i.e. fabrication by caption. Deterministic, generic (no card/slot ids), DB-policy-driven
with code-default mirrors [db/seed_emit_coherence.sql]:

  gates.window_label_policy — 'morph' (default: rewrite the leaf to the TRUTHFUL label/range token) | 'blank' (empty
                              the leaf) | 'off'.
  windows.period_families   — period token → family (day/week/month). BOTH sides must classify to flag — an
                              unclassified label ('Live', a plant name) NEVER flags (the quantity-wall principle:
                              unclassified = compatible).
  windows.range_labels      — range token → the truthful human label a morph writes ('last-24h' → 'Last 24h').
  gates.period_label_keys   — the metadata leaf KEYS that declare a period/range (periodLabel, range, …). Key-exact,
                              case-insensitive; leaves inside a *options* picker array are chrome (never touched).

Telemetry rides di._window_label (+ each rewritten path into _applied_morphs) — a per-LEAF self-heal, never a card
gate. The sibling half of the coherence contract lives in layer2/build._backfill_default_window: the AI's OWN declared
range now drives the backfilled window bounds, so declared range == fill window by construction."""
import re

from config.app_config import cfg

_PERIOD_FAMILIES_DEFAULT = {
    "today": "day", "daily": "day", "yesterday": "day", "day": "day",
    "last-24h": "day", "last 24h": "day", "last-24-hours": "day", "24h": "day",
    "weekly": "week", "this-week": "week", "last-7-days": "week", "week": "week", "7d": "week",
    "monthly": "month", "this-month": "month", "last-month": "month", "last-30-days": "month",
    "month": "month", "30d": "month",
}

_RANGE_LABELS_DEFAULT = {
    "today": "Today", "yesterday": "Yesterday", "last-24h": "Last 24h",
    "last-7-days": "Weekly", "this-week": "Weekly",
    "this-month": "Monthly", "last-month": "Monthly", "last-30-days": "Monthly",
}

_LABEL_KEYS_DEFAULT = ["periodLabel", "period", "periodText", "rangeLabel", "windowLabel",
                       "range", "selectedRange", "timeRange"]


def _norm(s):
    return re.sub(r"\s+", " ", str(s or "").strip().lower())


def _families():
    return {_norm(k): str(v) for k, v in (cfg("windows.period_families", _PERIOD_FAMILIES_DEFAULT) or {}).items()}


def _labels():
    return {_norm(k): str(v) for k, v in (cfg("windows.range_labels", _RANGE_LABELS_DEFAULT) or {}).items()}


def _label_keys():
    return {_norm(k) for k in (cfg("gates.period_label_keys", _LABEL_KEYS_DEFAULT) or [])}


def family(token):
    """The period FAMILY (day/week/month) a range token / display label names, or None (unclassified — never flags)."""
    return _families().get(_norm(token))


def fill_range(di):
    """The range token of the fill window the consumer will use: the shipped consumer's range first (that IS what the
    endpoint receives), else the window's own declared/backfilled range."""
    di = di or {}
    c = di.get("consumer") if isinstance(di.get("consumer"), dict) else {}
    w = di.get("window") if isinstance(di.get("window"), dict) else {}
    bf = w.get("backfill") if isinstance(w.get("backfill"), dict) else {}
    for tok in (c.get("range"), bf.get("range"), w.get("range"), w.get("lookback")):
        if tok:
            return str(tok)
    return None


def fill_family(di):
    """(family, range_token) of the ACTUAL fill window: the range token when it classifies, else the window
    start/end SPAN bucketed to a family (±tolerance bands; an in-between span returns None — never flags)."""
    tok = fill_range(di)
    fam = family(tok)
    if fam:
        return fam, tok
    w = (di or {}).get("window") if isinstance((di or {}).get("window"), dict) else {}
    try:
        from datetime import datetime
        days = (datetime.fromisoformat(str(w.get("end"))) -
                datetime.fromisoformat(str(w.get("start")))).total_seconds() / 86400.0
    except Exception:
        return None, tok
    if 0.5 <= days <= 2:
        return "day", tok
    if 5 <= days <= 10:
        return "week", tok
    if 25 <= days <= 45:
        return "month", tok
    return None, tok


def reconcile_window_labels(exact_metadata, di):
    """Walk exact_metadata for period-declaring STRING leaves (key ∈ gates.period_label_keys, not inside a *options*
    picker array) whose value names a DIFFERENT period family than the fill window. Per policy the leaf is MORPHED to
    the truthful value (a label key → windows.range_labels[fill range]; a range-value key → the fill range token) or
    BLANKED (''), in place. Returns [{path, key, from, to, reason}] telemetry (di._window_label); [] when policy=off,
    no fill family resolves, or everything already agrees. Never raises, never fabricates — it only ever writes the
    fill window's OWN truth or an empty string."""
    pol = _norm(cfg("gates.window_label_policy", "morph"))
    if pol in ("off", "") or not isinstance(exact_metadata, dict):
        return []
    fam, tok = fill_family(di)
    if not fam:
        return []                                              # fill window unclassified → never flag (no false positive)
    keys, fams, labels = _label_keys(), _families(), _labels()
    out = []

    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                p = f"{path}.{k}" if path else str(k)
                if "options" in _norm(k):
                    continue                                   # a picker's option list is chrome — never touched
                if isinstance(v, str) and _norm(k) in keys:
                    lfam = fams.get(_norm(v))
                    if lfam and lfam != fam:
                        is_label = any(t in _norm(k) for t in ("label", "text"))
                        new = ""
                        if pol == "morph":
                            new = labels.get(_norm(tok), "") if is_label else (tok or "")
                        o[k] = new
                        out.append({"path": p, "key": k, "from": v, "to": new,
                                    "reason": f"period leaf said {v!r} ({lfam}) but the fill window is "
                                              f"{tok or fam!r} ({fam}) — leaf {'morphed to the window truth' if new else 'blanked'} "
                                              "(a label must agree with the window the consumer fills from)"})
                    continue
                walk(v, p)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")

    walk(exact_metadata, "")
    return out
