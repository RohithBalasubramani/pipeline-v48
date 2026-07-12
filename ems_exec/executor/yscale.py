"""ems_exec/executor/yscale.py — POST-FILL Y-SCALE DERIVATION (single concern).

DEFECT FAMILY (cards 44/46/48/49 round 1; 37/38/40 round 3): a chart payload carries a Y-SCALE — a {maxY,minY[,yTicks]}
/ {yMax,yMin} pair (including PREFIX pairs like demandYMax/demandYMin) or a ticks-ONLY axis (PhaseMonitorChart yTicks,
where the FE derives yMax=Number(yTicks[0]) / yMin=Number(yTicks[last])) — SEPARATE from the series it scales. After
the executor fills the real series values those scale leaves are still the STRIPPED placeholder (0.0 / []) — or a
degenerate emit-bound latest sample (yMax=yMin=183.0) — and the real series renders OFF-SCALE / flat / NaN.

FIX (GENERIC, no card ids): after fill, every object that carries a scale (pair or ticks-only) AND a sibling SERIES of
real values gets its scale recomputed from the series' OWN min/max:
  · PAIR DISCOVERY is suffix-based: a key ending in a max token ('maxY'/'yMax') pairs with the SAME-PREFIX min key
    ('demandYMax' ↔ 'demandYMin'); each pair derives independently.
  · SERIES DISCOVERY is shape-driven: sibling numeric lists (excluding epoch/time axes), series-of-objects with a
    numeric list under a value key ('values'/'data'), and per-element numeric scalars of object rows (bars[{time,
    active,reactive}]) — element time/chrome keys excluded. A non-empty PREFIX prefers same-prefix series (demand* ←
    demandBars) so a dual-axis chart never mixes scales.
  · `shape_ref` (the RAW harvested default) is the SHAPE ORACLE: tick element TYPE (numeric-string labels '430' vs
    numbers), tick COUNT, and the ZERO-FLOOR convention (default min == 0 → the derived floor stays 0, bar charts
    baseline at zero). No value is ever copied from it.
Honest: a scale with NO sibling real values is left blank — an empty chart is honest-blank, never a fabricated axis.
The expected-band leaves (expectedMax/expectedMin) are DATA (a nameplate/derived band), NOT axis geometry — untouched.

The scale-key vocabulary + tick count are editable app_config rows (config.vocab); code defaults match the CMD_V2
chart primitives. Every DOMAIN-BAND knob is an app_config row with a code-default mirror (NO magic literals steer the
axis): chart.const_axis_zero_hi (all-zero top), chart.const_axis_band_halfwidth (non-zero constant ±band),
chart.yscale_pad_pct (varying-series headroom). [atomic; one concern; never fabricates a scale for absent data]
"""
from __future__ import annotations

_DEFAULT_MAX_TOKENS = ("maxy", "ymax")
_DEFAULT_MIN_TOKENS = ("miny", "ymin")
_DEFAULT_TICKS_KEY = "yTicks"
_DEFAULT_SERIES_KEYS = ("series",)
_DEFAULT_VALUES_KEYS = ("values", "data")
_DEFAULT_TICK_COUNT = 5
# element keys that are NEVER series values (time axis / identity chrome inside a row object)
_ELEMENT_SKIP_KEYS = ("time", "t", "ts", "timestamp", "label", "id", "key", "band", "color")


from config.failopen import cfg_num as _cfg_num   # THE guarded numeric knob reader (D3)


def _vocab_list(name, default):
    try:
        from config.vocab import vocab
        v = vocab(name)
        if isinstance(v, (list, tuple)) and v:
            return tuple(str(x) for x in v)
    except Exception:
        pass
    return default


def _max_tokens():
    return tuple(t.lower() for t in _vocab_list("yscale_max_keys", _DEFAULT_MAX_TOKENS))


def _min_tokens():
    return tuple(t.lower() for t in _vocab_list("yscale_min_keys", _DEFAULT_MIN_TOKENS))


def _ticks_key():
    return (_vocab_list("yscale_ticks_key", (_DEFAULT_TICKS_KEY,)) or (_DEFAULT_TICKS_KEY,))[0]


def is_scale_key(key):
    """True when a leaf KEY is part of the y-scale vocabulary (yTicks / a max/min pair token) — the executor's
    time-fill guard uses this so a mis-declared kind='time' field can never epoch-fill a VALUE axis (card 37)."""
    k = str(key or "").lower()
    if not k:
        return False
    if k == _ticks_key().lower():
        return True
    return any(k.endswith(t) for t in _max_tokens() + _min_tokens())


def _tick_count():
    try:
        from config.app_config import cfg
        n = int(cfg("chart.yscale_ticks", _DEFAULT_TICK_COUNT))
        return n if n >= 2 else _DEFAULT_TICK_COUNT
    except Exception:
        return _DEFAULT_TICK_COUNT


_DEFAULT_CONST_ZERO_HI = 1.0
_DEFAULT_CONST_BAND_HALFWIDTH = 1.0
_DEFAULT_PAD_PCT = 0.05


def const_zero_hi():
    """Axis TOP for an ALL-ZERO constant series — the explicit 0..<this> y-domain the scale passes ship so a zero
    series (an off DG) never renders on a zero-range / negative-floor axis. DB row chart.const_axis_zero_hi; code
    default 1.0. Shared by this pass and norm_series (the normalized-strip-chart label axis)."""
    return _cfg_num("chart.const_axis_zero_hi", _DEFAULT_CONST_ZERO_HI, positive=True)


def const_band_halfwidth():
    """Half-width of the symmetric band around a NON-ZERO CONSTANT series (line mid-axis, never a zero-range axis). DB
    row chart.const_axis_band_halfwidth; code default 1.0 (±1 → the historical 269..271 band on a 270 constant)."""
    return _cfg_num("chart.const_axis_band_halfwidth", _DEFAULT_CONST_BAND_HALFWIDTH, positive=True)


def pad_pct():
    """Fractional headroom padded on EACH side of a VARYING series' data range. DB row chart.yscale_pad_pct; code
    default 0.05 (5% — the historical _nice_bounds headroom)."""
    return _cfg_num("chart.yscale_pad_pct", _DEFAULT_PAD_PCT)


def _numbers(seq):
    return [x for x in seq if isinstance(x, (int, float)) and not isinstance(x, bool)]


def _is_epoch_list(v):
    from ems_exec.executor.epoch import is_epoch_number_list
    return is_epoch_number_list(v)


_ELEMENT_TIME_KEYS = ("time", "t", "ts", "timestamp")


def _element_values(el, values_keys):
    """Real numeric values of ONE series element, per-bucket rows ONLY:
      · a numeric LIST under a value key ('values'/'data') — the classic multi-series element; else
      · the numeric scalar keys of a TIME-keyed row (bars {time,active,reactive} → active+reactive) — the presence
        of a time member proves a per-bucket data row. A {label,value} KPI/stat/legend tile array carries NO time
        member and NO value list → NEVER an axis source (its 4.52% tile must not drag a 230 V axis)."""
    vals = []
    for vk in values_keys:
        vv = el.get(vk)
        if isinstance(vv, list):
            vals += _numbers(vv)
    if vals:
        return vals
    if not any(k in el for k in _ELEMENT_TIME_KEYS):
        return []
    for k, v in el.items():
        if str(k).lower() in _ELEMENT_SKIP_KEYS:
            continue
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            vals.append(v)
    return vals


def _scale_keys_of(obj, max_tokens, min_tokens, ticks_key):
    """Every scale-participating key of `obj` (pair members + the ticks key) — so series discovery can skip them."""
    out = set()
    for k in obj:
        kl = str(k).lower()
        if kl == ticks_key.lower() or any(kl.endswith(t) for t in max_tokens + min_tokens):
            out.add(k)
    return out


def _series_candidates(obj, series_keys, values_keys, skip_keys):
    """[(key, [values])] — every sibling of the scale that carries REAL series values, shape-discovered:
      · a list of numbers (≥2, NOT epoch-like — a time axis is never a value series);
      · a list of objects → per-element numeric values (value-key lists first, else numeric scalars minus chrome).
    Keys that are themselves scale members / time-ish are skipped."""
    out = []
    for k, v in obj.items():
        if k in skip_keys:
            continue
        kl = str(k).lower()
        if kl.endswith(("ms", "indexes", "timestamps")) or kl in ("xlabels", "xlabelindexes"):
            continue
        if not isinstance(v, list) or not v:
            continue
        if all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v):
            if len(v) >= 2 and not _is_epoch_list(v):
                out.append((k, list(v)))
            continue
        if all(isinstance(x, dict) for x in v):
            vals = []
            for el in v:
                vals += _element_values(el, values_keys)
            if vals:
                out.append((k, vals))
    # legacy vocab series keys keep priority ordering (a 'series' sibling first)
    pri = {sk.lower(): i for i, sk in enumerate(series_keys)}
    out.sort(key=lambda kv: pri.get(str(kv[0]).lower(), len(pri)))
    return out


def _values_for_prefix(cands, prefix):
    """The value pool a scale PAIR derives from: same-prefix series first ('demand' → demandBars), else every
    candidate (one shared axis over all sibling series — the CMD_V2 apiMode convention)."""
    if prefix:
        hit = [vals for k, vals in cands if str(k).lower().startswith(prefix.lower())]
        if hit:
            return [x for vals in hit for x in vals]
    return [x for _k, vals in cands for x in vals]


def _nice_bounds(lo, hi):
    """A padded (min, max) around the data range — chart.yscale_pad_pct headroom each side (code default 5%). Equal
    lo/hi (a CONSTANT series) always gets an explicit sane band: ALL-ZERO → 0..chart.const_axis_zero_hi (a dark/off
    asset's zero line sits on an honest 0-floor axis, never a negative-floor one), any other constant a
    ±chart.const_axis_band_halfwidth band so the line sits mid-axis. Never a zero-range axis [DG-1 card-36 family,
    2026-07-07]. Every band comes from a DB knob with a code-default mirror — no magic literal steers the axis."""
    if lo == hi:
        if lo == 0.0:
            return 0.0, const_zero_hi()
        hw = const_band_halfwidth()
        return lo - hw, hi + hw
    span = hi - lo
    pad = span * pad_pct()
    return lo - pad, hi + pad


def _ticks(lo, hi, n):
    step = (hi - lo) / (n - 1)
    return [round(hi - step * i, 6) for i in range(n)]          # descending (top→bottom), matching the CMD_V2 axis order


def _tick_shape(shape_obj, ticks_key):
    """(as_strings, count) — the DEFAULT payload's tick element TYPE + COUNT at this object (shape oracle). A default
    of numeric STRINGS ('430','422',…) means the FE Number()s label strings; None shape → (False, None)."""
    if not isinstance(shape_obj, dict):
        return False, None
    dv = shape_obj.get(ticks_key)
    if isinstance(dv, list) and dv:
        as_str = all(isinstance(x, str) for x in dv)
        return as_str, len(dv)
    return False, None


def _zero_floor(shape_obj, min_key):
    """True when the DEFAULT's own min at this key is 0 — the chart baselines at zero (bar charts); the derived floor
    then stays 0 instead of a padded data-min."""
    if not isinstance(shape_obj, dict):
        return False
    dv = shape_obj.get(min_key)
    return isinstance(dv, (int, float)) and not isinstance(dv, bool) and float(dv) == 0.0


def _fmt_tick(x, as_str):
    if not as_str:
        return x
    return str(int(round(x))) if abs(x) >= 10 else str(round(x, 2))


def _pairs_of(obj, max_tokens, min_tokens):
    """[(max_key, min_key, prefix)] — suffix-matched scale pairs of this object (yMax↔yMin, maxY↔minY,
    demandYMax↔demandYMin). Case-preserving on the real keys."""
    out = []
    lower = {str(k).lower(): k for k in obj}
    for k in obj:
        kl = str(k).lower()
        for mt in max_tokens:
            if not kl.endswith(mt):
                continue
            prefix = kl[: -len(mt)]
            for nt in min_tokens:
                mk = lower.get(prefix + nt)
                if mk is not None:
                    out.append((k, mk, prefix))
                    break
            break
    return out


def apply(payload, shape_ref=None):
    """Recompute every y-scale (pair AND ticks-only) from its sibling series' real min/max, in place; returns the
    (possibly-updated) payload. `shape_ref` = the RAW harvested default (shape oracle only). Never raises — a scale-
    derivation hiccup must never sink a filled card."""
    try:
        max_tokens = _max_tokens()
        min_tokens = _min_tokens()
        ticks_key = _ticks_key()
        series_keys = _vocab_list("yscale_series_keys", _DEFAULT_SERIES_KEYS)
        # element LIST-value keys: the DB vocab UNION the code defaults — the vocab row predates the 'data' element
        # key (PhaseMonitorChart series[{data,color}]), and only LIST-typed members are ever read under these keys,
        # so a scalar 'value' key can never leak through this path.
        values_keys = tuple(dict.fromkeys(list(_vocab_list("element_value_keys", ())) + list(_DEFAULT_VALUES_KEYS)))
        _walk(payload, shape_ref if isinstance(shape_ref, (dict, list)) else None,
              max_tokens, min_tokens, ticks_key, series_keys, values_keys, _tick_count())
    except Exception:
        pass
    return payload


def _walk(node, shape, max_tokens, min_tokens, ticks_key, series_keys, values_keys, nticks):
    if isinstance(node, dict):
        pairs = _pairs_of(node, max_tokens, min_tokens)
        has_ticks = ticks_key in node and isinstance(node.get(ticks_key), list)
        if pairs or has_ticks:
            skip = _scale_keys_of(node, max_tokens, min_tokens, ticks_key)
            cands = _series_candidates(node, series_keys, values_keys, skip)
            derived_range = None
            for mk, mn, prefix in pairs:
                vals = _values_for_prefix(cands, prefix)
                if not vals:
                    continue                                    # no real data → honest-blank scale stands
                lo, hi = _nice_bounds(min(vals), max(vals))
                if _zero_floor(shape, mn) and min(vals) >= 0:
                    lo = 0.0                                    # default-proven zero-baseline chart keeps its floor
                node[mk] = round(hi, 6)
                node[mn] = round(lo, 6)
                if not prefix:
                    derived_range = (lo, hi)
            if has_ticks:
                rng = derived_range
                if rng is None:
                    vals = _values_for_prefix(cands, "")
                    rng = _nice_bounds(min(vals), max(vals)) if vals else None
                if rng is not None:
                    as_str, dcount = _tick_shape(shape, ticks_key)
                    n = dcount if (dcount and dcount >= 2) else nticks
                    node[ticks_key] = [_fmt_tick(t, as_str) for t in _ticks(rng[0], rng[1], n)]
                # else: no real values → the honest-blank ticks stand (empty chart is honest)
        for k, v in node.items():
            if isinstance(v, (dict, list)):
                _walk(v, shape.get(k) if isinstance(shape, dict) else None,
                      max_tokens, min_tokens, ticks_key, series_keys, values_keys, nticks)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            if isinstance(v, (dict, list)):
                sh = None
                if isinstance(shape, list):
                    sh = shape[i] if i < len(shape) else (shape[0] if shape else None)
                _walk(v, sh, max_tokens, min_tokens, ticks_key, series_keys, values_keys, nticks)
