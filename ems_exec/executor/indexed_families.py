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
from ems_exec.executor.paths import _leaf_at, _has_path, _set_leaf_typed, _leaf_path_for
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



# The DERIVED/RAW series-family ROUTER moved to ems_exec/executor/series_router.py (monoliths F4, 2026-07-12) and is
# WIRED EXPLICITLY as fill()'s last pass — the old self-installing sys.meta_path import-hook that monkey-patched
# fill.fill is deleted (fill.py stopped being fence-frozen long ago; interpreter-global machinery does not belong in
# a data-fill module). This module keeps ONE concern: the per-index family machinery + the is_series_family_field
# routing contract (which the router imports from here).
