"""ems_exec/executor/display.py — DISPLAY-SIBLING RECONCILE (F2: no Storybook projection survives beside a filled value).

THE DEFECT [F2, fabrication]: the fill executor overlays a leaf's `value` from neuract but a CMD_V2 reading is a STRUCTURED
object — `{value, displayValue, decimals, prefix, unitSuffix}` (fmtMetric contract) — and a health bar is
`{value, delta, deltaText, widthPct, markerPct, …}`. Overwriting only `value` leaves the SIBLING PROJECTION holding the
harvested Storybook default: a real value=426.75 renders next to a stale displayValue='325.9', an honest-blank value='—'
next to a fake '2165', a live current beside a seed delta='+3.0%'. Every one is a fabricated number the FE actually shows.

THE GENERIC FIX (shape-driven — NO card ids, NO per-card code):

  1. displayValue INVARIANT (global): CMD_V2's fmtMetric defines displayValue = value.toFixed(decimals) when value is a
     finite number, else the METRIC_PLACEHOLDER '—'. That invariant holds for EVERY {value, displayValue} object, so we
     recompute displayValue from the CURRENT value everywhere — it can only ever make the string CONSISTENT with the value
     it sits beside; it can NEVER introduce a seed. Uses the object's own `decimals` (default 0). A string-typed value
     ("419") is coerced for formatting; an un-coercible / blank value → the placeholder.

  2. UNRECOMPUTABLE PROJECTIONS (scoped to the leaves the executor WROTE): a `delta` / `deltaText` / a `*Delta*/min` rate
     string is a %-change or per-minute RATE vs a previous reading — a baseline the per-card executor does NOT compute. So
     for an object whose `value` the fill actually WROTE (real or honest-blank), we BLANK these projections to the
     placeholder rather than let a Storybook delta render beside a live value. (Only WRITTEN-value objects are touched so a
     purely-chrome object the executor never bound keeps its authored content.)

Byte-faithful to CMD_V2 (components/charts/primitives/fmtMetric.ts): displayValue = toFixed(decimals) | '—'. The
value/time/label KEY names come from the DB vocabulary (config.vocab) with a closed code default — no hardcoded card shape.
Runs as the LAST fill pass (after roster + yscale), over the completed payload. Never raises; never fabricates.
"""
from __future__ import annotations

import re

PLACEHOLDER = "—"                                              # == CMD_V2 fmtMetric METRIC_PLACEHOLDER


def _value_keys():
    """The object keys that carry the fillable numeric VALUE (config.vocab 'element_value_keys' — the SAME enumeration
    the executor's series-element fill uses) with a closed code default. A {value|values|y|…} + displayValue object is a
    metric reading; its displayValue must track its value."""
    try:
        from config.vocab import vocab
        keys = [str(k) for k in (vocab("element_value_keys") or [])]
    except Exception:
        keys = []
    return keys or ["value", "values", "y", "kw", "kwh", "count"]


def _delta_keys():
    """The DISPLAY-PROJECTION sibling keys that are a %-change / rate string with NO per-card baseline — blank them
    beside a written value rather than leak a Storybook delta. DB-overridable (config.vocab 'delta_projection_keys');
    closed code default covers the CMD_V2 reading/health shapes (delta, deltaText, and any *DeltaPerMinute rate)."""
    try:
        from config.vocab import vocab
        keys = [str(k) for k in (vocab("delta_projection_keys") or [])]
    except Exception:
        keys = []
    return keys or ["delta", "deltaText", "deltaTone"]


_RATE_KEY_RE = re.compile(r"delta.*per.*min|dkwdt|deltapermin", re.IGNORECASE)


def _num(v):
    """A value coerced to float for formatting, or None (a blank/placeholder/non-numeric value → the placeholder)."""
    if v is None or v == PLACEHOLDER or v == "":
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def _fmt(value, decimals):
    """CMD_V2 fmtMetric: value.toFixed(decimals) when finite, else the placeholder. `decimals` defaults to 0."""
    n = _num(value)
    if n is None:
        return PLACEHOLDER
    try:
        d = int(decimals) if decimals is not None else 0
    except (TypeError, ValueError):
        d = 0
    return f"{n:.{d}f}"


def _reconcile_object(obj, value_keys):
    """Reconcile ONE metric-reading object's display siblings from its CURRENT value. Returns True if this looked like a
    metric object (had a value + a displayValue sibling). Only rewrites displayValue — the global invariant. Never raises."""
    if not isinstance(obj, dict):
        return False
    if "displayValue" not in obj:
        return False
    vkey = next((k for k in value_keys if k in obj), None)
    if vkey is None:
        return False
    val = obj.get(vkey)
    if isinstance(val, (list, dict)):                          # a value that is itself a series/object is not a scalar reading
        return False
    obj["displayValue"] = _fmt(val, obj.get("decimals"))      # displayValue ≡ fmt(value) — never a seed
    return True


def _blank_projection(obj, keys):
    """Blank the un-recomputable %-change / rate projection siblings of a WRITTEN-value object (delta/deltaText/rate).
    A scalar projection → '—'; a structured deltaText {value,unit,…} → its value slot placeholdered (chrome kept)."""
    if not isinstance(obj, dict):
        return
    for k in list(obj.keys()):
        if k in keys or _RATE_KEY_RE.search(str(k)):
            cur = obj.get(k)
            if isinstance(cur, dict):
                for vk in ("value", "displayValue"):
                    if vk in cur:
                        cur[vk] = PLACEHOLDER
            elif isinstance(cur, (str, int, float)) and not isinstance(cur, bool):
                obj[k] = PLACEHOLDER


def _walk_global(node, value_keys):
    """Enforce the displayValue invariant on EVERY {value, displayValue} object in the tree (recompute from value).
    `value_keys` is threaded through the recursion (no shared mutable state — safe under the host's parallel card fill)."""
    if isinstance(node, dict):
        _reconcile_object(node, value_keys)
        for v in node.values():
            _walk_global(v, value_keys)
    elif isinstance(node, list):
        for v in node:
            _walk_global(v, value_keys)


# dotted-path addressing: the ONE shared home (ems_exec/executor/paths.py)
from ems_exec.executor.paths import _parent_of


def apply(payload, written_value_paths=None):
    """Reconcile display siblings across the COMPLETED payload (F2). Two passes, both shape-driven:

      GLOBAL  — displayValue ≡ fmt(value) for every {value, displayValue} object (never a seed displayValue).
      WRITTEN — for each leaf path the executor WROTE (written_value_paths), blank its object's un-recomputable
                %-change / rate projection siblings (delta/deltaText/*PerMin) so no Storybook delta renders beside it.

    Mutates + returns `payload`. Never raises (a reconcile failure leaves the payload as fill produced it)."""
    if not isinstance(payload, (dict, list)):
        return payload
    try:
        value_keys = _value_keys()
        _walk_global(payload, value_keys)
        if written_value_paths:
            dkeys = set(_delta_keys())
            done = set()
            for p in written_value_paths:
                parent = _parent_of(payload, p)
                if parent is None or id(parent) in done:
                    continue
                done.add(id(parent))
                _reconcile_object(parent, value_keys)         # ensure this object's displayValue matches (idempotent)
                _blank_projection(parent, dkeys)
    except Exception:
        pass
    return payload
