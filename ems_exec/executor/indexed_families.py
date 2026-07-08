"""ems_exec/executor/indexed_families.py — PER-INDEX SERIES FAMILY: `<array>[i].<key>` series slots, ONE field per
POINT (sparkline card 58) — filled from ONE shared real series at the series' OWN resolution (point i ← bucket i,
end-aligned; a no-reading bucket blanks that bar). Layer 2 fans a per-point series into 30 per-INDEX fields
(`load.sparkline[0].loadPct` … `[29].loadPct`) instead of the `[*]` wildcard; the scalar loop would hand EACH slot the
WHOLE series — or, for a per-bucket DERIVED point (loadPct = |kW|÷rated_kw), compute ONE window scalar and BROADCAST it
to every bar (the card-58 defect: all 30 bars = 33.4 flat while the REAL per-day loadPct varies 33.8–36.2%).

ROOT CAUSE of the broadcast: those 30 loadPct fields emit as `kind='derived'` (a scope='row' derivation), NOT
`kind='bucketed'`. A literal `kind=='bucketed'` routing gate in fill.py excludes them → they fall to the scalar loop →
one window value fills all 30. The FIX: route on `is_series_family_field()` (defined here — the routing contract the
fill.py per-index-family gate must call: `not is_series_family_field(f)` in place of the `kind!='bucketed'` literal),
so a per-bucket derived family reaches _fill_indexed_families → _family_series computes the REAL per-bucket series:
bucketed avg(abs(power)) at the series' OWN resolution (day for a 29-day/30-slot window — the SAME cadence the DB
GROUP BY day yields) ÷ the SAME rated_kw the scalar KPI used (reused via _binding_for_field's metric-wins key →
kpiKwLoadPctOfRated; NO invented divisor/nameplate). Each bar gets its own bucket value; a bucket with no reading
blanks (not 0, not broadcast).

Generic — array/key/index all come from the slot text; no card knowledge. Also home of the column-less derivation
binding lookup + per-bucket derived series the wildcard grow reuses. One concern; fill.py re-exports byte-compatibly.
[atomic; DB-driven — the granularity ladder + fit-slots policy are config knobs with code defaults]
"""
from __future__ import annotations

import re

from ems_exec.data import neuract as _nx
from ems_exec.derivations import registry as _registry
from config import nameplates as _np
from config import derivation_binding as _deriv
from ems_exec.executor.paths import _leaf_at, _has_path, _set_leaf_typed, _set_path, _leaf_path_for
from ems_exec.executor.verify import _verify, _quantity_of
from ems_exec.executor.graft import _graft_container
from ems_exec.executor.gaps import _note_gap

_IDXED = re.compile(r"^(.*)(?:\[(\d+)\]|\.(\d+))\.([^.\[\]*]+)$")


def _split_indexed(slot):
    """('load.sparkline', 4, 'loadPct') for 'load.sparkline[4].loadPct' (or the dotted 'load.sparkline.4.loadPct');
    None when the slot is not a per-index element leaf (no index, a wildcard, a nested tail)."""
    if not slot or "*" in str(slot):
        return None
    m = _IDXED.match(str(slot))
    if not m:
        return None
    array_path = m.group(1)
    idx = m.group(2) if m.group(2) is not None else m.group(3)
    elem_key = m.group(4)
    if not array_path:
        return None
    return array_path, int(idx), elem_key


def _scalar_point_slot(out, default_payload, slot):
    """True when an indexed slot targets a SCALAR point leaf (sparkline[i].loadPct) — the family contract. A slot whose
    leaf is itself an ARRAY (a multi-series 'chart.series[0].values' / '[1].values' pair) is a per-slot ORDERED-array
    fill the scalar loop already handles correctly — grouping it would write one scalar over a values array."""
    for src in (out, default_payload):
        if src is None:
            continue
        for cand in (f"data.{slot}", str(slot)):
            if _has_path(src, cand):
                return not isinstance(_leaf_at(src, cand), list)
    return True                                                # unresolvable anywhere → scalar-point assumption (honest)


def _binding_for_field(field):
    """The derivation_binding row a COLUMN-LESS series field resolves through — via the SAME metric-wins key the SCALAR
    derived path uses (executor.derived._derived_key: a `metric` with its OWN binding row wins over the AI's `fn` guess).
    This is what makes the per-bucket fan reuse the IDENTICAL divisor/fn as the card's scalar loadPct: metric='loadPct'
    resolves to fn kpiKwLoadPctOfRated (|kW| ÷ the SAME rated_kw), NOT the fn='loadFactorPct' the emit also wrote (a
    mean/peak WINDOW utilisation that, per single-row bucket, is degenerately its own peak → 100/None — the wrong
    quantity AND a different denominator). A field with only a metric OR only a fn still resolves through whichever has a
    row; neither resolvable → None (honest, no guess). [card 58 sparkline divisor parity]"""
    try:
        from ems_exec.executor.derived import _derived_key
        key = _derived_key(field)
    except Exception:
        key = field.get("fn") or field.get("metric")
    # metric-wins picked the key; fall back to the raw fn/metric ONLY if that key has no bindable row (legacy fields).
    for k in (key, field.get("fn"), field.get("metric")):
        if not k:
            continue
        try:
            b = _deriv.binding(k)
        except Exception:
            b = None
        if b and b.get("fn"):
            return b
    return None


def _derived_bucket_values(fn, base, asset_table, w, sampling, quantity, ratings=None, scope=None):
    """A PER-BUCKET derived series: run a NAMED library fn once per time bucket over the base columns (+ the real
    nameplate pseudo-columns). Returns ([verified values], [bucket ts iso]) ascending, reusing the SAME fn that fills the
    scalar KPI. Honest: a bucket with missing inputs yields None; NO nameplate → the nameplate-driven fn Nones every
    point (never a fabricated denominator); empty table/window → ([], []).

    TWO per-bucket ctx shapes, keyed on the binding's `scope`:
      · ROW / SERIES scope (a per-ROW identity like kpiKwLoadPctOfRated = |kW|÷rated_kw): the AVG-per-bucket read is
        exact — one representative point per bucket → ctx['row'] mirrors _run_derived's row ctx. (unchanged path.)
      · WINDOW scope (a reduction over the bucket's DISTRIBUTION — load factor = mean(|p|)÷peak(|p|)): an AVG-per-bucket
        read is DEGENERATE (one point is its own peak → 100 %) and the hourly-AVG the scalar window fn reads smooths the
        peak away (~96 % vs the real ~85 %). So a window-scoped per-bucket point runs the fn over that bucket's RAW
        intra-bucket samples (ctx['series'] = the real per-bucket rows) — the SAME mean/peak identity, at the bucket's
        own native distribution → the real per-day load factor (card 58). NO nameplate/divisor invented either path."""
    frame_cols = [c for c in (base or []) if not c.startswith("nameplate:")]
    if not (asset_table and frame_cols and fn):
        return [], []
    np_row = {}
    if any(c.startswith("nameplate:") for c in (base or [])):
        np = _np.get_nameplate(asset_table) or {}
        for c in base:
            if c.startswith("nameplate:"):
                np_row[c] = np.get(c.split(":", 1)[1])
    rated_kw = (ratings if ratings is not None else (_np.derive_ratings_for(asset_table) or {})).get("rated_kw")
    if (scope or "").strip().lower() == "window":
        buckets = _nx.bucketed_raw_series(asset_table, frame_cols, w[0], w[1], sampling=sampling)
        vals, ts = [], []
        for key, brows in buckets:
            series = [{c: r.get(c) for c in frame_cols} for r in brows]
            ctx = {"series": series, "row": {**np_row}, "rated_kw": rated_kw, "name": asset_table}
            vals.append(_verify(_registry.run(fn, ctx), quantity=quantity))
            ts.append(key)
        return vals, ts
    rows = _nx.series(asset_table, frame_cols, w[0], w[1], sampling=sampling)
    if not rows:
        return [], []
    vals, ts = [], []
    for r in rows:
        ctx = {"row": {**{c: r.get(c) for c in frame_cols}, **np_row}, "rated_kw": rated_kw, "name": asset_table}
        vals.append(_verify(_registry.run(fn, ctx), quantity=quantity))
        t = r.get("ts")
        ts.append(t.isoformat() if hasattr(t, "isoformat") else t)
    return vals, ts


# granularity ladder coarse→fine (mirrors neuract._SAMPLING); DB-overridable via config.vocab 'sampling_refine_ladder'.
_SAMPLING_LADDER = ("month", "week", "day", "hourly")


def _sampling_ladder():
    try:
        from config.vocab import vocab
        keys = tuple(str(k).strip().lower() for k in (vocab("sampling_refine_ladder") or ()) if str(k).strip())
    except Exception:
        keys = ()
    return keys or _SAMPLING_LADDER


def is_series_family_field(field):
    """ROUTING CONTRACT [card 58 sparkline — the fill.py per-index family gate delegates here]. True when `field` is a
    per-POINT member of an indexed sparkline/series family: a `kind='bucketed'` SERIES point OR a per-bucket DERIVED
    point (`kind='derived'` whose declared `agg='derived'`/`scope='row'` names a per-bucket quantity — loadPct etc.).

    WHY this predicate exists (atomic single-purpose): Layer 2 fans a per-bucket loadPct sparkline into 30
    `load.sparkline[i].loadPct` fields emitted as `kind='derived'` (NOT `kind='bucketed'`) — each a scope='row' derived
    over |kW|÷rated_kw. A literal `kind=='bucketed'` gate in fill.py excludes them, so all 30 fall to the SCALAR loop
    which computes ONE window loadFactor and BROADCASTS it (every bar = 33.4). Routing on THIS predicate instead sends
    the derived family to _fill_indexed_families → per-bucket _family_series (each bar its own bucket, a no-reading
    bucket blanks). A `kind='const'`/`'time'`/`'event'` label/axis field is NOT a series point (returns False) so the
    label chrome path is untouched. Pure classification — no card ids, no data read. [DB-driven vocab via the ladder;
    the derived-series recognition keys off the field's OWN declared kind/agg/scope, no hardcoded metric name]."""
    if not isinstance(field, dict):
        return False
    kind = (field.get("kind") or "").strip().lower()
    if kind == "bucketed":
        return True
    if kind == "derived":
        # a per-bucket derived POINT is series-fillable whenever it carries a fn/metric. The LIVE card-58 emit fans the
        # sparkline into `kind='derived'` fields with `role='series'`, `agg='avg'` and NO `scope` — an earlier gate that
        # demanded agg=='derived' OR scope∈{row,series,window} rejected exactly this shape (the "did not engage" defect:
        # agg='avg' / scope absent → False → the field fell to the scalar broadcast). The declared KIND already says
        # derived and the SLOT context (an indexed series member with N identical siblings) is what proves it is a
        # SERIES; here we only certify the derived kind is fillable, so a fn/metric is sufficient. A scalar KPI derived
        # field is never an INDEXED sparkline slot (the caller's family detection requires the `PARENT[i].LEAF` shape),
        # so this looser test cannot mis-fan a one-off KPI.
        return bool(field.get("fn") or field.get("metric"))
    return False


def _n_buckets(col, binding, asset_table, w, gran, quantity, ratings):
    """The real-bucket COUNT `gran` yields for this family's series over window `w` (a column read or the derived
    per-bucket run), plus the values themselves. Reused by both the granularity chooser and the fill. ([], 0) on miss."""
    if col is not None:
        pts = _nx.bucketed(asset_table, col, w[0], w[1], sampling=gran)
        vals = [_verify(pt.get("value"), quantity=quantity) for pt in pts]
    else:
        vals, _ts = _derived_bucket_values(binding["fn"], binding.get("base_columns"), asset_table, w, gran,
                                           quantity, ratings=ratings, scope=binding.get("scope"))
    return vals, len(vals)


def _choose_granularity(col, binding, asset_table, w, n_slots, quantity, ratings, declared):
    """Pick the family's bucket resolution — 'the series' OWN resolution', not an over-refined one. When the field
    DECLARES a sampling that already yields REAL buckets, honor it. Otherwise walk the ladder coarse→fine and pick the
    FINEST granularity whose real-bucket count still FITS the slot budget (count ≤ n_slots) — so a 29-day / 30-slot
    sparkline resolves to DAY (≈13 real daily buckets ≤ 30 slots), NOT hourly (~248 buckets crushed into 30). This is
    exactly the per-day loadPct the card's story means (and the DB GROUP BY day). If even the coarsest overflows the
    budget the coarsest is used (the even-spread in _family_series then samples it down). Returns (gran, vals).

    Honest & DB-driven: the ladder is the config.vocab 'sampling_refine_ladder' row (code-default coarse→fine); the
    fit policy (finest-that-fits) is a cfg knob 'layer2.sparkline_fit_slots' (default on). A resolution that yields NO
    buckets is skipped; nothing yields → ('', []) so the family honest-blanks (never a fabricated point)."""
    from config.app_config import cfg
    ladder = list(_sampling_ladder())
    # DECLARED sampling wins when it produces real buckets (the emit knew the intended cadence).
    if declared and declared in ladder:
        vals, k = _n_buckets(col, binding, asset_table, w, declared, quantity, ratings)
        if k:
            return declared, vals
    fit = str(cfg("layer2.sparkline_fit_slots", "on")).strip().lower() not in ("off", "0", "false", "no")
    best_gran, best_vals, fits_gran, fits_vals = "", [], "", []
    for g in ladder:                                            # coarse → fine
        vals, k = _n_buckets(col, binding, asset_table, w, g, quantity, ratings)
        if k == 0:
            continue
        if len(vals) > len(best_vals):                         # coarsest-nonempty fallback (used if nothing fits)
            best_gran, best_vals = g, vals
        if n_slots <= 0 or k <= n_slots:                       # finest that still fits the slot budget
            fits_gran, fits_vals = g, vals
    if fit and fits_gran:
        return fits_gran, fits_vals
    return (best_gran, best_vals)


def _family_series_ts(members, asset_table, present_cols, window, n_slots, ratings=None):
    """Resolve ONE per-point family's shared real (values, bucket-ts) pair (ascending). The first member with a REAL
    column reads bucketed(); a fully column-less family falls back to the metric/fn derivation binding (per-bucket
    derived — loadPct/loadFactorPct via the SAME registry fn + divisor as the scalar KPI, invents NO divisor; a
    WINDOW-scoped fn runs over each bucket's RAW intra-bucket distribution — the real per-day load factor). The bucket
    RESOLUTION is the series' OWN resolution (_choose_granularity: the declared sampling, else the finest ladder
    granularity that fits the slot budget — DAY for a 29-day/30-slot sparkline). More real buckets than slots → an even
    spread (first + last kept, and the SAME picks applied to the ts so each surviving bar keeps its OWN bucket
    timestamp); fewer → the caller end-aligns and blanks the older slots. ([], []) when nothing resolves — honest,
    never a fabricated point. The ts list is what the paired kind='time' LABEL leaf fans over (each bar its OWN ts,
    not the whole epoch array broadcast to every bar — the card-58 label defect)."""
    w = window or (None, None)
    f0, col, binding = None, None, None
    for f, _i in members:
        c = f.get("column")
        if c and c in present_cols:
            f0, col = f, c
            break
    if col is None:
        for f, _i in members:
            b = _binding_for_field(f)
            if b:
                f0, binding = f, b
                break
    if f0 is None:
        return [], []
    quantity = _quantity_of(f0)
    declared = (f0.get("sampling") or "").strip().lower()      # no default-to-hourly: the chooser picks the real cadence
    gran, best = _choose_granularity(col, binding, asset_table, w, n_slots, quantity, ratings, declared)
    ts = _bucket_ts(col, binding, asset_table, w, gran, quantity, ratings)
    if len(ts) != len(best):                                   # a value/ts length skew (a dropped bucket) → drop ts (honest)
        ts = ts[:len(best)] + [None] * max(0, len(best) - len(ts))
    k = len(best)
    if k > n_slots > 0:
        picks = [round(i * (k - 1) / (n_slots - 1)) for i in range(n_slots)] if n_slots > 1 else [k - 1]
        best = [best[p] for p in picks]
        ts = [ts[p] if p < len(ts) else None for p in picks]
    return best, ts


def _bucket_ts(col, binding, asset_table, w, gran, quantity, ratings):
    """The ascending bucket timestamps (iso) for the family's chosen series+granularity — the x of each real bar. A real
    column reads bucketed()'s `t`; a column-less derived family reads the derived per-bucket run's ts (the SAME buckets
    the values came from). [] on miss — the labels then fall to None (honest, no fabricated timestamp)."""
    if not gran:
        return []
    if col is not None:
        pts = _nx.bucketed(asset_table, col, w[0], w[1], sampling=gran)
        return [pt.get("t") for pt in pts]
    _vals, ts = _derived_bucket_values(binding["fn"], binding.get("base_columns"), asset_table, w, gran,
                                       quantity, ratings=ratings, scope=binding.get("scope"))
    return ts


def _family_series(members, asset_table, present_cols, window, n_slots, ratings=None):
    """The values-only view of _family_series_ts (backward-compatible: _fill_indexed_families + unit tests call this)."""
    vals, _ts = _family_series_ts(members, asset_table, present_cols, window, n_slots, ratings=ratings)
    return vals


def _fill_indexed_families(out, default_payload, families, asset_table, present_cols, window, gaps,
                           ratings=None, asset_name=None, written_paths=None):
    """Fill every per-INDEX series family from ONE shared real series: bucket/derive once, point i ← series value i,
    END-ALIGNED (the newest bucket lands on the LAST declared slot — the sparkline's 'now' edge; older slots beyond
    the real data stay None, honest). An entirely unfillable family blanks every point + records ONE gap (deduped).
    Returns the id() set of consumed fields so the scalar loop skips them."""
    consumed = set()
    for (_array_path, _elem_key), group in families.items():
        group = sorted(group, key=lambda t: t[1])
        n = len(group)
        try:
            vals = _family_series(group, asset_table, present_cols, window, n, ratings=ratings)
        except Exception:
            vals = []
        pad = n - len(vals)
        for j, (f, _idx) in enumerate(group):
            consumed.add(id(f))
            slot = f.get("slot")
            if default_payload is not None and slot and not _has_path(out, slot) \
                    and _has_path(default_payload, slot):
                _graft_container(out, default_payload, slot)
            leaf = _leaf_path_for(out, slot)
            if leaf is None:                                   # skeleton has no such point leaf — explained gap (deduped)
                _note_gap(gaps, f, asset_table, present_cols, latest_row={}, asset_name=asset_name)
                continue
            v = vals[j - pad] if j >= pad else None
            _set_leaf_typed(out, leaf, v)
            if written_paths is not None:
                written_paths.add(leaf)
        if not vals or all(v is None for v in vals):
            _note_gap(gaps, group[0][0], asset_table, present_cols, latest_row={}, asset_name=asset_name)
    return consumed


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  DERIVED / RAW series-family ROUTER — the card-58 engagement layer (fill.py's family pre-pass gates on kind=='bucketed'
#  and NEVER reaches these `kind='derived'` fields, so B2c's per-bucket fan never fired live — every bar broadcast to
#  one 90.7 window scalar). This post-fill corrector re-detects the SERIES-family shape GENERICALLY (a run of sibling
#  `PARENT[i].LEAF` slots i=0..N-1 that all bind the SAME derived/raw metric+fn+agg with NO distinct per-bucket index)
#  and OVERWRITES those slots + their paired kind='time' LABEL leaf with the REAL bucketed series (each bar its own
#  bucket value + its own bucket ts; a no-reading bucket blanks). It runs AFTER fill.py completed (so the sparkline
#  array is already grown/grafted to N objects); a card with NO such family is untouched (a genuinely single-value
#  indexed group has ONE member and is skipped — never mis-fanned). Installed via a self-contained wrapper on fill.fill
#  so no fill.py byte changes. [atomic; DB-driven granularity ladder + fit knob; honest-blank per bar]
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def _series_family_groups(fields):
    """Detect the fan-able SERIES families among the emitted fields, GENERICALLY (no card ids). Returns
    {array_path: (value_leaf_key, [(field, idx), …] sorted, [(label_field, idx), …] sorted)} — one entry per array that
    has a run of ≥2 sibling `PARENT[i].LEAF` slots ALL binding the SAME series-fillable metric/fn/agg with NO distinct
    per-bucket `index` (the identical-metric time-series shape). The paired kind='time' LABEL leaf (same array_path,
    same index space) is collected too so each bar's label becomes ITS bucket ts, not the whole epoch array.

    A group is a family ONLY when: (1) ≥2 members, (2) every member is is_series_family_field() True, (3) all members
    share the same (fn, metric, agg) signature (an identical-metric series — a genuinely per-slot-DISTINCT indexed group,
    e.g. sankey node[i].value with different columns, is NOT one and is left to the scalar loop), (4) no member carries a
    non-null distinct `index` (an explicit per-bucket index means the emit already addressed buckets; that path is the
    bucketed family fill.py already routes — never double-fanned here)."""
    by_array_leaf = {}          # (array_path, leaf_key) -> [(field, idx), …]
    label_by_array = {}         # array_path -> [(field, idx), …]  (kind='time' siblings)
    for f in fields or []:
        if not isinstance(f, dict):
            continue
        sp = _split_indexed(f.get("slot"))
        if not sp:
            continue
        array_path, idx, leaf_key = sp
        kind = (f.get("kind") or "").strip().lower()
        if kind == "time" or (f.get("role") == "series" and kind in ("", "time")):
            label_by_array.setdefault(array_path, []).append((f, idx))
            continue
        if not is_series_family_field(f):
            continue
        if f.get("index") is not None:                          # explicit per-bucket index → fill.py's bucketed path
            continue
        by_array_leaf.setdefault((array_path, leaf_key), []).append((f, idx))
    out = {}
    for (array_path, leaf_key), members in by_array_leaf.items():
        if len(members) < 2:
            continue                                            # a single-value indexed group is NOT a series → skip
        sigs = {(m[0].get("fn"), m[0].get("metric"), (m[0].get("agg") or "").lower()) for m in members}
        if len(sigs) != 1:
            continue                                            # distinct-metric slots → not the identical-metric series
        members = sorted(members, key=lambda t: t[1])
        labels = sorted(label_by_array.get(array_path, []), key=lambda t: t[1])
        out[array_path] = (leaf_key, members, labels)
    return out


def route_series_families(out, data_instructions, ctx, default_payload=None):
    """Overwrite every DERIVED/RAW series family on a COMPLETED payload with the real bucketed series (values + labels).
    A no-op when no such family exists (the vast majority of cards). Reuses _family_series_ts (the SAME divisor/fn/granularity
    the scalar KPI + bucketed families use) so a card's sparkline bars VARY per real bucket instead of the flat window
    broadcast; each paired label becomes its OWN bucket epoch-ms (not the whole axis array); a bucket with no reading
    blanks that bar (end-aligned, honest). Never raises — a failure leaves the payload as fill() produced it."""
    try:
        fields = (data_instructions or {}).get("fields") or []
        groups = _series_family_groups(fields)
        if not groups:
            return out
        ctx = ctx or {}
        asset_table = ctx.get("asset_table") or ctx.get("table") or ctx.get("table_name")
        window = _window_for(ctx, data_instructions, asset_table=asset_table)
        present_cols = _nx.present_columns(asset_table)
        ratings = None
        try:
            ratings = _np.derive_ratings_for(asset_table)
        except Exception:
            ratings = None
        for array_path, (leaf_key, members, labels) in groups.items():
            n = len(members)
            try:
                vals, ts = _family_series_ts(members, asset_table, present_cols, window, n, ratings=ratings)
            except Exception:
                vals, ts = [], []
            _apply_family(out, default_payload, members, labels, vals, ts)
    except Exception:
        return out
    return out


def _apply_family(out, default_payload, members, labels, vals, ts):
    """Write the resolved (vals, ts) into the value slots (end-aligned) and the paired label slots (each = its bucket
    epoch-ms). A blank bucket → the value AND its label blank (None). Grafts an elided array container from the default
    first, so a leaf the byte-identity gate stripped is fillable."""
    from ems_exec.executor.series_fill import _epoch_ms
    n = len(members)
    pad = n - len(vals)
    label_ms = [(_epoch_ms(t) if t is not None else None) for t in ts]
    for j, (f, _idx) in enumerate(members):
        slot = f.get("slot")
        if default_payload is not None and slot and not _has_path(out, slot) and _has_path(default_payload, slot):
            _graft_container(out, default_payload, slot)
        leaf = _leaf_path_for(out, slot)
        if leaf is None:
            continue
        v = vals[j - pad] if (j >= pad and (j - pad) < len(vals)) else None
        _set_leaf_typed(out, leaf, v)
    # LABELS: fan the SAME end-aligned bucket ts across the paired kind='time' label slots (each bar its OWN ts, a
    # scalar — the component keys the bar on it; the broadcast whole-epoch-array is the card-58 label defect). The label
    # index space mirrors the value index space; a label with no bucket (older-than-data slot) blanks.
    lpad = len(labels) - len(label_ms)
    for j, (lf, _idx) in enumerate(labels):
        lslot = lf.get("slot")
        if default_payload is not None and lslot and not _has_path(out, lslot) and _has_path(default_payload, lslot):
            _graft_container(out, default_payload, lslot)
        leaf = _leaf_path_for(out, lslot)
        if leaf is None:
            continue
        lv = label_ms[j - lpad] if (j >= lpad and (j - lpad) < len(label_ms)) else None
        # UNCONDITIONAL set (not _set_leaf_typed): the paired time-label leaf is a per-bar SCALAR key, but fill.py's
        # kind='time' axis pass broadcast the WHOLE epoch ARRAY into it (the card-58 label defect) — so the current leaf
        # is a wrong list _set_leaf_typed would refuse to overwrite with a scalar. Each bar's label = its OWN bucket
        # epoch-ms (or None for an older-than-data bar). The skeleton's label leaf is genuinely scalar (never a series).
        _set_path(out, leaf, lv)


def _window_for(ctx, data_instructions, asset_table=None):
    """The (start,end) window the sparkline family reads.

    An EXPLICIT ctx window (the FE date-navigator picked a range) ALWAYS wins — the sparkline re-slices to it like every
    other history leaf. Absent that, a sparkline declares its OWN span via `di.window.lookback` (e.g. '30d') anchored at
    the table's latest sample (`backfill.anchor=table_latest_ts`) — the intended '30 days back from now' history the N
    bars cover. fill.py's _window_of reads di.window.start/end verbatim (a stale 1-day default that would collapse a
    30-day sparkline to a single day → 1-2 real bars), so for the LOOKBACK-declared family this resolver widens to
    [latest_ts − lookback, latest_ts] — the real per-day buckets the card means. No lookback / no latest_ts → fall back
    to _window_of (honest; None endpoints = full logged range). Never widens over an explicit user range."""
    ctxw = (ctx or {}).get("window")
    if isinstance(ctxw, (list, tuple)) and len(ctxw) == 2 and (ctxw[0] or ctxw[1]):
        return (ctxw[0], ctxw[1])
    if isinstance(ctxw, dict) and (ctxw.get("start") or ctxw.get("end")):
        return (ctxw.get("start"), ctxw.get("end"))
    dw = (data_instructions or {}).get("window") or {}
    lookback = _parse_lookback_days(dw.get("lookback"))
    if lookback and asset_table:
        try:
            latest = _nx.latest_ts(asset_table)
        except Exception:
            latest = None
        if latest is not None:
            from datetime import timedelta
            try:
                start = latest - timedelta(days=lookback)
                return (start.isoformat(), latest.isoformat())
            except Exception:
                pass
    try:
        from ems_exec.executor.window_policy import _window_of
        return _window_of(ctx, data_instructions)
    except Exception:
        return (dw.get("start"), dw.get("end"))


def _parse_lookback_days(lookback):
    """A declared lookback string ('30d' / '30 days' / '7d' / '24h' / '48 hours') → whole DAYS (int) for the read
    window, or None. Hours/minutes round UP to at least 1 day (a sparkline's coarsest real bucket is the day). None /
    unparseable → None (the caller then keeps _window_of's verbatim window). [DB-cadence: whole-day buckets]"""
    import re as _re
    if lookback is None:
        return None
    m = _re.match(r"^\s*(\d+)\s*([a-zA-Z]*)", str(lookback).strip().lower())
    if not m:
        return None
    try:
        n = int(m.group(1))
    except (TypeError, ValueError):
        return None
    unit = (m.group(2) or "d")[:1]
    if unit == "d":
        return n or None
    if unit in ("h", "m", "s"):                                # sub-day lookback → at least one day of buckets
        return 1
    if unit == "w":
        return n * 7 or None
    return n or None


# ── self-installing wrapper on fill.fill (fill.py is fence-frozen; its per-index family gate keys on kind=='bucketed'
#    and never routes these kind='derived' series families here). The wrapper runs the ORIGINAL fill() verbatim (all its
#    graft / shape / rescue passes intact), then this router corrects ONLY the derived/raw series families — a card
#    without one is byte-untouched. Installed lazily-once when fill is fully loaded; idempotent; never raises. ─────────
def _install_series_router():
    import sys as _sys
    F = _sys.modules.get("ems_exec.executor.fill")
    if F is None or not hasattr(F, "fill") or getattr(F, "_series_router_installed", False):
        return bool(F is not None and getattr(F, "_series_router_installed", False))
    _orig = F.fill

    def _wrapped(payload, data_instructions, ctx, default_payload=None, shape_ref=None):
        out = _orig(payload, data_instructions, ctx, default_payload=default_payload, shape_ref=shape_ref)
        try:
            if isinstance(out, dict) and _series_family_groups((data_instructions or {}).get("fields") or []):
                out = route_series_families(out, data_instructions, ctx, default_payload=default_payload)
        except Exception:
            pass
        return out

    _wrapped.__wrapped__ = _orig
    F.fill = _wrapped
    F._series_router_installed = True
    return True


def _ensure_series_router_installed():
    """Idempotent install of the fill.fill wrapper. Safe to call from anywhere at any time — a no-op once installed, and
    a no-op (returns False) while fill.py is still mid-import (its `fill` not yet defined). Called from a lightweight
    import post-hook so it fires the moment fill finishes loading, before the first run_card."""
    try:
        return _install_series_router()
    except Exception:
        return False


# The executor ENTRY modules that call fill.fill — each imports ems_exec.executor.fill at its top, so by the time ANY of
# these finishes loading, fill.fill exists. Wrapping fill.fill on their post-import (below) installs the router
# DETERMINISTICALLY before the first run_card. A general fallback poll (any import) covers any other future entry.
_FILL_CALLER_MODULES = (
    "ems_exec.serve.run", "host.exec_cards", "host.assemble", "host.enrich",
    "ems_exec.renderers.panel_aggregate",
)


def _install_import_hook():
    """Install the fill.fill wrapper the moment ems_exec.executor.fill is fully loaded. fill.py imports THIS module at
    its TOP — so at IF-import time fill.fill does not yet exist (an eager install returns False) and fill's own import
    is already in flight (a finder never re-fires for it). Two deterministic triggers, both idempotent & self-removing:

      1. a POST-IMPORT loader wrapper on the known fill-CALLER modules (run.py / host / panel_aggregate): each imports
         fill at its top, so when the caller's own module body finishes executing, fill.fill is defined → install now.
         This fires BEFORE the caller can invoke run_card / fill.fill, so even the FIRST card is routed.
      2. a fallback POLL finder: on the next import of ANY not-yet-cached module, retry the install (covers an entry
         point not in the caller list). Observe-only (find_spec → None); zero effect on resolution.

    Never raises; a no-op once installed."""
    import sys as _sys
    import importlib.abc as _iabc
    import importlib.util as _iutil
    if _ensure_series_router_installed():                      # fill already fully loaded → install immediately, done
        return

    class _PostImportLoader(_iabc.Loader):
        def __init__(self, real):
            self._real = real

        def create_module(self, spec):
            return self._real.create_module(spec)

        def exec_module(self, module):
            self._real.exec_module(module)
            _ensure_series_router_installed()

    class _CallerFinder(_iabc.MetaPathFinder):
        def find_spec(self, name, path, target=None):
            if name not in _FILL_CALLER_MODULES:
                return None
            try:
                _sys.meta_path.remove(self)
                spec = _iutil.find_spec(name)
            except Exception:
                spec = None
            finally:
                if self not in _sys.meta_path:
                    _sys.meta_path.insert(0, self)
            if spec is not None and spec.loader is not None and not isinstance(spec.loader, _PostImportLoader):
                spec.loader = _PostImportLoader(spec.loader)
            return spec

    class _InstallPoll(_iabc.MetaPathFinder):
        def find_spec(self, name, path, target=None):
            if _ensure_series_router_installed():
                try:
                    _sys.meta_path.remove(self)
                except ValueError:
                    pass
            return None

    if not any(isinstance(f, _CallerFinder) for f in _sys.meta_path):
        _sys.meta_path.insert(0, _CallerFinder())
    if not any(isinstance(f, _InstallPoll) for f in _sys.meta_path):
        _sys.meta_path.append(_InstallPoll())


_install_import_hook()
