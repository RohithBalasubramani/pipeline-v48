"""ems_exec/executor/xaxis.py — POST-FILL X-AXIS LABEL DERIVATION. One concern: a chart's clock-label axis
(xLabels ['00:00'…'22:00'] in the harvested default) is seed CHROME the build-time strip blanks to ''s — and the fill
never re-bound it, so a REAL filled series rendered against 10 empty tick labels with no reason (2026-07-06 cards
44/46). This pass re-derives those labels from the card's OWN bucket-timestamp axis AFTER the series fill:

  · a leaf whose DEFAULT is a list of CLOCK-LIKE strings (config row xaxis.clock_patterns) but whose completed value
    is blank (empty / all-'' ) is a TIME-LABEL AXIS → refill with evenly-spaced HH:MM labels formatted in the SITE
    timezone (config.windows.site_tz) from the sibling epoch-ms axis the kind='time' fill wrote;
  · the sibling axis leaf itself, when its DEFAULT proves INDEX semantics (small ints [0,4,…,35], not epochs), is
    rewritten to the chosen INTEGER TICK POSITIONS — the FE contract (HistoryPanel: xScale(xLabelIndexes[i])) places
    labels by series index, and raw epoch values would fly off-scale;
  · BUCKET-AXIS FALLBACK [c44 2026-07-06 round 2]: when NO epoch sibling exists in the payload (the emit declared no
    time slot — or mis-declared it onto a Y-scale leaf the card-37 guard rightly refused), the labels derive from the
    card's OWN bucket-timestamp axis via the LAZY `ts_provider` the executor passes (the SAME _anchor_timestamps its
    series fill bucketed by — real bucket times, never invented); a default-proven INDEX sibling that is still blank
    gets the integer positions. Valve: app_config xaxis.bucket_fallback ('on' unless 'off');
  · when no timestamp source exists at all the labels stay blank and a per-leaf gap record is emitted (reasons-always).

Shape-driven + default-proven only — NO key names, NO card ids. apply(out, default_payload, gaps, ts_provider)
mutates in place. Valve: app_config xaxis.derive_labels ('on' unless 'off'). Never raises. [atomic]
"""
from __future__ import annotations

import re


def _enabled():
    try:
        from config.app_config import cfg
        return str(cfg("xaxis.derive_labels", "on")).strip().lower() != "off"
    except Exception:
        return True


def _fallback_enabled():
    """BUCKET-AXIS FALLBACK valve (DB row xaxis.bucket_fallback, 'on' unless 'off') — whether a label axis with NO
    epoch sibling may derive from the executor's own bucket-timestamp provider."""
    try:
        from config.app_config import cfg
        return str(cfg("xaxis.bucket_fallback", "on")).strip().lower() != "off"
    except Exception:
        return True


def _clock_patterns():
    """The clock-label regexes (DB row xaxis.clock_patterns, json list) — code default: HH:MM(:SS)."""
    default = [r"^\d{1,2}:\d{2}(:\d{2})?$"]
    try:
        from config.app_config import cfg
        raw = cfg("xaxis.clock_patterns", default) or default
    except Exception:
        raw = default
    pats = []
    for p in raw:
        try:
            pats.append(re.compile(str(p)))
        except re.error:
            continue
    return pats


def _fmt():
    try:
        from config.app_config import cfg
        return str(cfg("xaxis.label_format", "%H:%M"))
    except Exception:
        return "%H:%M"


def _is_clock_list(v, pats):
    return (isinstance(v, list) and len(v) >= 2 and
            all(isinstance(x, str) and x.strip() and any(p.match(x.strip()) for p in pats) for x in v))


def _is_blank_str_list(v):
    return isinstance(v, list) and (not v or all(x is None or x == "" or x == "—" for x in v))


def _is_scrubbed_clock_list(v):
    """SCRUB-RESIDUE evidence [stripped-default fallback]: the build-time strip blanks every temporal-axis label to ''
    — so a default that is a list of ≥2 all-'' STRINGS is a scrubbed CLOCK/DATE axis (only temporal/provenance/
    narrative strings get blanked; chrome label lists keep their text byte-identical). Weaker than the raw default's
    clock proof, used only when the caller could not supply the raw shape_ref."""
    return isinstance(v, list) and len(v) >= 2 and all(isinstance(x, str) and x == "" for x in v)


def _is_epoch_list(v):
    return (isinstance(v, list) and len(v) >= 2 and
            all(isinstance(x, (int, float)) and not isinstance(x, bool) and x > 1e10 for x in v) and
            all(v[i] <= v[i + 1] for i in range(len(v) - 1)))


def _is_index_default(v):
    """DEFAULT-proven INDEX axis: a short list of small non-negative ints (tick positions), never epoch ms."""
    return (isinstance(v, list) and len(v) >= 2 and
            all(isinstance(x, int) and not isinstance(x, bool) and 0 <= x < 10000 for x in v))


def _positions(n_labels, n_points):
    n = max(2, min(int(n_labels), int(n_points)))
    if n_points < 2:
        return [0][:n_points]
    return sorted({round(i * (n_points - 1) / (n - 1)) for i in range(n)})


def _label(ms, tz, fmt):
    from datetime import datetime, timezone
    try:
        return datetime.fromtimestamp(float(ms) / 1000.0, tz=timezone.utc).astimezone(tz).strftime(fmt)
    except Exception:
        return None


def _gap(slot):
    try:
        from config.reason_templates import reason as _reason
        sentence = _reason("unbound_by_emit", metric=slot)
    except Exception:
        sentence = "unbound_by_emit"
    return {"slot": slot, "cause": "unbound_by_emit", "metric": slot, "column": None, "fn": None, "reason": sentence}


def apply(out, default_payload, gaps=None, ts_provider=None):
    """Derive every blank default-proven clock-label axis of `out` (in place). `ts_provider` (optional, LAZY) returns
    the card's OWN bucket-timestamp axis (epoch ms) — the fallback source when the payload carries no epoch sibling.
    Appends a per-leaf gap record for an underivable one (no timestamp source). Returns `out`; never raises."""
    try:
        if not _enabled() or not isinstance(out, dict) or not isinstance(default_payload, dict):
            return out
        from config.windows import site_tz
        _walk(out, default_payload, _clock_patterns(), site_tz(), _fmt(), gaps if isinstance(gaps, list) else [], "",
              ts_provider if _fallback_enabled() else None)
    except Exception:
        pass
    return out


def _provided_ts(ts_provider):
    """The provider's bucket axis when it is a usable epoch list (≥2 ascending epoch-ms), else None. Never raises."""
    if ts_provider is None:
        return None
    try:
        ts = ts_provider()
    except Exception:
        return None
    return list(ts) if _is_epoch_list(ts) else None


def _walk(node, dnode, pats, tz, fmt, gaps, path, ts_provider):
    if isinstance(node, dict) and isinstance(dnode, dict):
        label_keys = [k for k, dv in dnode.items()
                      if (_is_clock_list(dv, pats) or _is_scrubbed_clock_list(dv)) and _is_blank_str_list(node.get(k))]
        if label_keys:
            epoch_keys = [k for k, v in node.items() if k not in label_keys and _is_epoch_list(v)]
            for k in label_keys:
                slot = f"{path}.{k}" if path else k
                # PAIRED-AXIS preference: when several epoch siblings exist (sampleTimestamps + timeLabelTimestamps),
                # the label axis pairs with the sibling whose DEFAULT length equals the label count (the FE zips
                # label[i] with ts[i]); else the first epoch sibling stands.
                n_labels = len(dnode[k])
                ts_key = next((ek for ek in epoch_keys
                               if isinstance(dnode.get(ek), list) and len(dnode.get(ek)) == n_labels), None) \
                    or (epoch_keys[0] if epoch_keys else None)
                if ts_key is None:
                    # BUCKET-AXIS FALLBACK [c44 round 2]: no epoch sibling in the payload (the emit declared no time
                    # slot / mis-declared it onto a Y-scale leaf) → the card's OWN bucket-timestamp axis (the lazy
                    # ts_provider = the executor's _anchor_timestamps, the SAME axis its series were bucketed by)
                    # derives the labels; a default-proven INDEX sibling still blank gets the tick positions.
                    fts = _provided_ts(ts_provider)
                    if fts is None:
                        gaps.append(_gap(slot))                # underivable → reasons-always, never a silent blank
                        continue
                    pos = _positions(n_labels, len(fts))
                    labels = [_label(fts[p], tz, fmt) for p in pos]
                    if not labels or any(x is None for x in labels):
                        gaps.append(_gap(slot))
                        continue
                    node[k] = labels
                    for ik, idv in dnode.items():
                        if ik == k or ik in label_keys or not _is_index_default(idv):
                            continue                           # only a default-PROVEN index axis takes positions
                        cur = node.get(ik)
                        if cur is None or cur == [] or _is_blank_str_list(cur):
                            node[ik] = [int(p) for p in pos]
                    continue
                ts = node[ts_key]
                pos = _positions(n_labels, len(ts))
                labels = [_label(ts[p], tz, fmt) for p in pos]
                if not labels or any(x is None for x in labels):
                    gaps.append(_gap(slot))
                    continue
                node[k] = labels
                # the sibling axis leaf → tick POSITIONS when its semantics are INDEX, proven either by the DEFAULT
                # (a small-int list [0,4,…,35]) or — when the seed-blank erased that evidence ([]) — by the SHAPE:
                # fewer labels than points means the labels are index-MAPPED ticks, not a per-point axis (the FE
                # places label i at xScale(indexes[i]); raw epoch-ms values there fly off a 0..N-1 scale).
                dts = dnode.get(ts_key)
                if _is_index_default(dts) or ((not dts or dts == []) and n_labels < len(ts)):
                    node[ts_key] = [int(p) for p in pos]
                elif (isinstance(dts, list) and len(dts) == n_labels and len(ts) > len(labels)
                      and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in dts)):
                    # PAIRED PER-LABEL TS AXIS [card 36 timeLabelTimestamps]: the default proves label[i] ↔ ts[i]
                    # pairing (equal-length NUMERIC ts list — epoch OR relative-ms offsets) but the time fill wrote
                    # the FULL bucket axis — subset the ts axis to the SAME picked positions so the FE zip stays
                    # aligned. Values stay the card's own real bucket timestamps (never invented).
                    node[ts_key] = [ts[p] for p in pos]
        for k, v in node.items():
            if isinstance(v, (dict, list)):
                _walk(v, dnode.get(k), pats, tz, fmt, gaps, f"{path}.{k}" if path else k, ts_provider)
    elif isinstance(node, list) and isinstance(dnode, list):
        for i, el in enumerate(node):
            if isinstance(el, (dict, list)):
                dref = dnode[i] if i < len(dnode) else (dnode[0] if dnode else None)
                _walk(el, dref, pats, tz, fmt, gaps, f"{path}[{i}]", ts_provider)
