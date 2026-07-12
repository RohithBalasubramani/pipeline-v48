"""ems_exec/executor/series_router.py — the DERIVED/RAW series-family ROUTER (the card-58 engagement layer).

fill.py's family pre-pass gates on kind=='bucketed' and never reaches `kind='derived'` per-index families, so B2c's
per-bucket fan never fired live — every bar broadcast to one 90.7 window scalar. This post-fill corrector re-detects
the SERIES-family shape GENERICALLY (a run of sibling `PARENT[i].LEAF` slots i=0..N-1 that all bind the SAME
derived/raw metric+fn+agg with NO distinct per-bucket index) and OVERWRITES those slots + their paired kind='time'
LABEL leaf with the REAL bucketed series (each bar its own bucket value + its own bucket ts; a no-reading bucket
blanks). It runs AFTER fill() completed (so the sparkline array is already grown/grafted to N objects); a card with
NO such family is untouched (a genuinely single-value indexed group has ONE member and is skipped — never mis-fanned).

HOME + WIRING [monoliths F4, 2026-07-12]: extracted from indexed_families.py (which keeps the per-index family
machinery and the is_series_family_field routing contract this router reuses). The old sys.meta_path import-hook that
monkey-patched fill.fill (built when fill.py was fence-frozen) is DELETED — fill() now calls route_series_families
explicitly as its LAST pass, identical order to the wrapper (whole original body, then the router) with the same
groups guard + never-raise contract. [atomic; DB-driven granularity ladder + fit knob; honest-blank per bar]
"""
from __future__ import annotations

from ems_exec.data import neuract as _nx
from config import nameplates as _np
from ems_exec.executor.paths import _has_path, _set_leaf_typed, _set_path, _leaf_path_for
from ems_exec.executor.graft import _graft_container
from ems_exec.executor.indexed_families import _split_indexed, is_series_family_field, _family_series_ts


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
