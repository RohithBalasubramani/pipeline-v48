"""ems_exec/executor/indexed_families.py — PER-INDEX SERIES FAMILY: `<array>[i].<key>` bucketed slots, ONE field per
POINT (sparkline card 58) — filled from ONE shared real series (point i ← bucket i). Layer 2 sometimes fans a per-point
series into 30 per-INDEX fields (`load.sparkline[0].loadPct` … `[29].loadPct`) instead of the `[*]` wildcard; the
scalar loop would hand EACH slot the WHOLE series ([] when the field is column-less → the all-empty sparkline).
Generic — array/key/index all come from the slot text; no card knowledge. Also home of the column-less derivation
binding lookup + per-bucket derived series the wildcard grow reuses. One concern; fill.py re-exports byte-compatibly.
[atomic]
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
    """The derivation_binding row a COLUMN-LESS series field resolves through — keyed on the field's declared fn,
    else its METRIC name (the AI's metric vocabulary IS the binding key: metric='loadPct' → fn kpiKwLoadPctOfRated via
    the editable cmd_catalog.derivation_binding row). None when neither resolves (honest — no guess)."""
    for key in (field.get("fn"), field.get("metric")):
        if not key:
            continue
        try:
            b = _deriv.binding(key)
        except Exception:
            b = None
        if b and b.get("fn"):
            return b
    return None


def _derived_bucket_values(fn, base, asset_table, w, sampling, quantity, ratings=None):
    """A PER-BUCKET derived series: run a NAMED library fn once per time bucket over the windowed series of its base
    columns (+ the real nameplate pseudo-columns). Returns ([verified values], [bucket ts iso]) ascending. The
    per-bucket ctx mirrors _run_derived's row ctx (row + nameplate:* + rated_kw) so the SAME fn that fills a scalar
    KPI fills each point. Honest: a bucket with missing inputs yields None; NO nameplate → the nameplate-driven fn
    Nones every point (never a fabricated denominator); empty table/window → ([], [])."""
    frame_cols = [c for c in (base or []) if not c.startswith("nameplate:")]
    if not (asset_table and frame_cols and fn):
        return [], []
    rows = _nx.series(asset_table, frame_cols, w[0], w[1], sampling=sampling)
    if not rows:
        return [], []
    np_row = {}
    if any(c.startswith("nameplate:") for c in (base or [])):
        np = _np.get_nameplate(asset_table) or {}
        for c in base:
            if c.startswith("nameplate:"):
                np_row[c] = np.get(c.split(":", 1)[1])
    rated_kw = (ratings if ratings is not None else (_np.derive_ratings_for(asset_table) or {})).get("rated_kw")
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


def _family_series(members, asset_table, present_cols, window, n_slots, ratings=None):
    """Resolve ONE per-point family's shared real value series [v|None, …] (ascending). The first member with a REAL
    column reads bucketed(); a fully column-less family falls back to the metric/fn derivation binding (per-bucket
    derived — loadPct = |kW|/rated_kw via the SAME registry fn as the scalar KPI). The declared sampling is REFINED
    down the granularity ladder while it yields fewer buckets than the family has point slots (a 30-slot sparkline
    over a 24h window at sampling='day' fills 2 of 30 — hourly fills ~25); more buckets than slots → an even spread of
    REAL buckets (first + last kept). [] when nothing resolves — honest, never a fabricated point."""
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
        return []
    quantity = _quantity_of(f0)
    declared = (f0.get("sampling") or "hourly").strip().lower()
    ladder = list(_sampling_ladder())
    start = ladder.index(declared) if declared in ladder else max(len(ladder) - 1, 0)
    best = []
    for g in ladder[start:] or [declared]:
        if col is not None:
            pts = _nx.bucketed(asset_table, col, w[0], w[1], sampling=g)
            vals = [_verify(pt.get("value"), quantity=quantity) for pt in pts]
        else:
            vals, _ts = _derived_bucket_values(binding["fn"], binding.get("base_columns"), asset_table, w, g,
                                               quantity, ratings=ratings)
        if len(vals) > len(best):
            best = vals
        if len(best) >= n_slots:
            break
    k = len(best)
    if k > n_slots > 0:
        picks = [round(i * (k - 1) / (n_slots - 1)) for i in range(n_slots)] if n_slots > 1 else [k - 1]
        best = [best[p] for p in picks]
    return best


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
