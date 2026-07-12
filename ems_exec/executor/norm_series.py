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
  · CONSTANT-SERIES GUARANTEE [DG-1 card 36 all-zeros, 2026-07-07]: a filled series whose every point is EQUAL and
    inside [0,1] (an off DG's honest all-zero kW) is indistinguishable from an already-normalized fill, so the raw
    branch above skips it and a blank label axis stays [] — the FE, given a constant series + no y-scale leaves,
    degenerates its y-domain (epoch digits rendered as the y-axis). When such a constant sits beside a label axis
    that NEEDS deriving (blank / mis-bound with no range), an EXPLICIT sane domain anchors both: ALL-ZERO → 0..1
    (cfg chart.const_axis_zero_hi; the zero line stays on the honest 0 floor), any other constant → the SAME flat
    rangeFromSamples band a raw constant already gets (line mid-axis). Labels are duplicate-safe (a narrow domain
    escalates decimals — never '1','1','0','0'). A VARYING series keeps the current computed scale, byte-identical.
Zero fabrication: every number derives from the card's OWN filled series; the shape oracle contributes shapes only.
Every domain-band knob is an app_config row with a code-default mirror (chart.norm_range_pad_pct headroom,
chart.norm_flat_pad_min / chart.norm_flat_pad_pct for a flat series, chart.const_axis_zero_hi for all-zero) — no magic
literal steers the range. [atomic; never raises]
"""
from __future__ import annotations

import re

_NUM_STR = re.compile(r"^\s*-?\d+(\.\d+)?\s*$")

_DEFAULT_RANGE_PAD_PCT = 0.1
_DEFAULT_FLAT_PAD_MIN = 1.0
_DEFAULT_FLAT_PAD_PCT = 0.05


from config.failopen import cfg_num as _cfg_num   # THE guarded numeric knob reader (D3)


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
    """CMD_V2 rangeFromSamples: chart.norm_range_pad_pct headroom each side (code default 10%); a flat series →
    ±max(chart.norm_flat_pad_min, chart.norm_flat_pad_pct·|hi|) (code defaults 1.0 / 5%). Every band is a DB knob with
    a code-default mirror — no magic literal steers the range."""
    lo, hi = min(vals), max(vals)
    if lo == hi:
        pad = max(_cfg_num("chart.norm_flat_pad_min", _DEFAULT_FLAT_PAD_MIN, positive=True),
                  abs(hi) * _cfg_num("chart.norm_flat_pad_pct", _DEFAULT_FLAT_PAD_PCT))
        return lo - pad, hi + pad
    span = hi - lo
    p = _cfg_num("chart.norm_range_pad_pct", _DEFAULT_RANGE_PAD_PCT)
    return lo - span * p, hi + span * p


def _const_domain(c):
    """The EXPLICIT sane (lo, hi) around a CONSTANT sample value `c`: all-zero → 0..1 (yscale.const_zero_hi, the
    cfg-tunable top — a zero series keeps its honest 0 floor), any other constant → this module's own flat _range
    convention (CMD_V2 rangeFromSamples: ± max(1, 5%|c|), line mid-axis)."""
    if c == 0.0:
        try:
            from ems_exec.executor.yscale import const_zero_hi
            return 0.0, const_zero_hi()
        except Exception:
            return 0.0, 1.0
    return _range([c])


def _label_strings(rhi, rlo, n):
    """`n` evenly spaced max→min label strings over [rlo, rhi]. Integer strings when already distinct — byte-identical
    to the historical str(round()) labels — else decimals escalate until every label is distinct, so a NARROW domain
    (a constant's 0..1 band) never prints a duplicated tick column ('1','1','1','0','0','0')."""
    steps = max(1, n - 1)
    xs = [rhi - (rhi - rlo) * i / steps for i in range(n)]
    labels = [str(round(x)) for x in xs]
    for nd in (1, 2, 3, 4):
        if len(set(labels)) == len(labels):
            return labels
        labels = [str(round(x, nd)) for x in xs]
    return labels


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
            # CONSTANT-series anchor [DG-1 card 36]: an all-EQUAL fill inside [0,1] skipped the raw branch (lo=hi=None)
            # yet anchors nothing — if a label axis below needs deriving, this explicit domain (all-zero → 0..1, else
            # the flat _range band) scales BOTH the labels and the series. Varying series: const_dom stays None.
            const_dom = _const_domain(vals[0]) if (lo is None and min(vals) == max(vals)) else None
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
                if rlo is None and const_dom is not None:
                    rlo, rhi = const_dom                        # CONSTANT series + label axis to derive → anchor the
                    span = (rhi - rlo) or 1.0                   # explicit domain and re-scale the series onto it
                    node[k] = [[(min(1.0, max(0.0, (x - rlo) / span)) if isinstance(x, (int, float))
                                 and not isinstance(x, bool) else None) for x in s] if isinstance(s, list) else s
                               for s in series]
                    lo, hi = rlo, rhi                           # any further label sibling shares this anchored range
                    const_dom = None                            # anchor once
                if rlo is None:
                    if misbound:
                        node[lk] = []                           # underivable → honest-blank, never the series itself
                    continue
                node[lk] = _label_strings(rhi, rlo, len(ldv))
        for k, v in node.items():
            if isinstance(v, (dict, list)):
                _walk(v, shape.get(k))
    elif isinstance(node, list) and isinstance(shape, list):
        for i, el in enumerate(node):
            if isinstance(el, (dict, list)):
                sh = shape[i] if i < len(shape) else (shape[0] if shape else None)
                _walk(el, sh)
