"""ems_exec/executor/norm_series.py — POST-FILL NORMALIZED-SERIES CONTRACT (single concern). [card 36, 2026-07-06]

DEFECT: PowerEnergyChart-family strip charts take NORMALIZED series — the component's yScale is clamp(value, 0, 1)
(PowerEnergyChart.tsx:114) and CMD_V2's own view-model normalizes API samples via normalizeSeries/rangeFromSamples
(realTimeMonitoringViewModel.ts). The executor's bucketed fill wrote RAW kW (171-201) into that contract → every point
clamps to 1.0 and flatlines at the plot top, with the numeric-string label axis (yLabels) left the stripped [].

FIX (GENERIC, shape-proven only — no card ids, no key names in logic):
  · CONTRACT DETECTION: a leaf whose RAW-DEFAULT value (shape_ref) is a list of ≥1 numeric lists with EVERY point in
    [0,1] is a NORMALIZED series contract. Only the raw default can prove this (the strip erases it to [[],[]]);
    no shape_ref → untouched.
  · NORMALIZE: the filled raw series normalize over ONE shared range across ALL the leaf's series — CMD_V2's own
    apiMode convention (rangeFromSamples: 10% headroom each side; a flat series pads ±max(1, 5%)). A None point stays
    None (honest gap); values already produced by an empty fill stay [] (honest).
  · LABEL AXIS: the sibling leaf whose RAW default is a list of NUMERIC STRINGS ('380','340',…) is that chart's
    shared value-label axis — derive len(default) evenly spaced labels max→min from the SAME range (CMD_V2
    buildSharedPowerYLabels: integer strings). A currently-BLANK label leaf is written; a legitimately filled
    STRING-label axis is never clobbered.
  · MIS-BOUND LABEL AXIS [card 36 yLabels, 2026-07-06]: an axis-LABEL slot NEVER ships a bound data series. When the
    emit bound a raw column at the label slot (the fill wrote N raw FLOATS where the default proves NUMERIC STRINGS —
    a type-contract violation, so this can never hit a legit label fill), the mis-bound values are REPLACED by the
    few monotonic derived labels: from the shared normalization range when this pass normalized the sibling series,
    else from the bound series' OWN range (same rangeFromSamples headroom). Underivable (<2 bound numbers, no
    normalization range) → honest-blank [] (the strip convention), never the series itself.
Zero fabrication: every number derives from the card's OWN filled series; the shape oracle contributes shapes only.
[atomic; never raises]
"""
from __future__ import annotations

import re

_NUM_STR = re.compile(r"^\s*-?\d+(\.\d+)?\s*$")


def _nums(seq):
    return [x for x in seq if isinstance(x, (int, float)) and not isinstance(x, bool)]


def _is_norm_default(dv):
    """Shape proof: a list of numeric lists whose EVERY real point lies in [0,1] (≥2 points overall)."""
    if not (isinstance(dv, list) and dv and all(isinstance(s, list) for s in dv)):
        return False
    pts = [x for s in dv for x in _nums(s)]
    return len(pts) >= 2 and all(0.0 <= x <= 1.0 for x in pts)


def _is_numeric_string_list(dv):
    return (isinstance(dv, list) and len(dv) >= 2 and
            all(isinstance(x, str) and _NUM_STR.match(x) for x in dv))


def _blank_list(v):
    return isinstance(v, list) and (not v or all(x is None or x == "" for x in v))


def _misbound_series(v):
    """A LABEL-slot value that is actually a bound DATA SERIES: a list carrying ≥2 real NUMBERS and not a single
    string — the default proves this axis carries NUMERIC STRINGS, so numbers here are a type-contract violation
    (an emit field bound a raw column at the label slot). A legit label fill (strings) never matches."""
    return (isinstance(v, list) and len(_nums(v)) >= 2 and
            not any(isinstance(x, str) for x in v))


def _range(vals):
    """CMD_V2 rangeFromSamples: 10% headroom each side; flat → ±max(1, 5%|hi|)."""
    lo, hi = min(vals), max(vals)
    if lo == hi:
        pad = max(1.0, abs(hi) * 0.05)
        return lo - pad, hi + pad
    span = hi - lo
    return lo - span * 0.1, hi + span * 0.1


def apply(payload, shape_ref):
    """Normalize every shape-proven normalized-series leaf of `payload` (in place) + derive its sibling numeric-string
    label axis from the shared range. Returns `payload`; never raises."""
    try:
        if isinstance(payload, dict) and isinstance(shape_ref, dict):
            _walk(payload, shape_ref)
    except Exception:
        pass
    return payload


def _walk(node, shape):
    if isinstance(node, dict) and isinstance(shape, dict):
        norm_keys = [k for k, dv in shape.items()
                     if _is_norm_default(dv) and isinstance(node.get(k), list)]
        for k in norm_keys:
            series = node[k]
            vals = [x for s in series if isinstance(s, list) for x in _nums(s)]
            if not vals:
                continue                                        # honest-empty fill → nothing to normalize
            lo = hi = None
            if not all(0.0 <= x <= 1.0 for x in vals):          # raw fill → normalize over ONE shared range
                lo, hi = _range(vals)
                span = (hi - lo) or 1.0
                node[k] = [[(min(1.0, max(0.0, (x - lo) / span)) if isinstance(x, (int, float))
                             and not isinstance(x, bool) else None) for x in s] if isinstance(s, list) else s
                           for s in series]
            # sibling numeric-string LABEL axis (shape-proven) — derive max→min integer labels over the SAME range.
            # A BLANK label leaf fills; a MIS-BOUND one (raw series shipped in the label slot) is REPLACED — from the
            # shared range when this pass normalized, else from the bound series' OWN range; a legit STRING-label
            # axis is never clobbered.
            for lk, ldv in shape.items():
                if lk == k or not _is_numeric_string_list(ldv):
                    continue
                cur = node.get(lk)
                misbound = _misbound_series(cur)
                if not (_blank_list(cur) or misbound):
                    continue                                    # a filled STRING-label axis is never clobbered
                rlo, rhi = lo, hi
                if rlo is None and misbound:
                    rlo, rhi = _range(_nums(cur))               # bound series' OWN range (same headroom convention)
                if rlo is None:
                    if misbound:
                        node[lk] = []                           # underivable → honest-blank, never the series itself
                    continue
                steps = len(ldv) - 1
                node[lk] = [str(round(rhi - (rhi - rlo) * i / steps)) for i in range(len(ldv))]
        for k, v in node.items():
            if isinstance(v, (dict, list)):
                _walk(v, shape.get(k))
    elif isinstance(node, list) and isinstance(shape, list):
        for i, el in enumerate(node):
            if isinstance(el, (dict, list)):
                sh = shape[i] if i < len(shape) else (shape[0] if shape else None)
                _walk(el, sh)
