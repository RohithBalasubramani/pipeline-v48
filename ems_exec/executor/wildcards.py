"""ems_exec/executor/wildcards.py — WILDCARD ARRAY-GROW: a `points[*].<key>` slot family fanned into an N-element
OBJECT array (composite cards 56/59).

Layer 2 emits per-point series fields as WILDCARD slots — composite.points[*].readiness / [*].inputCurrentA / … —
one field per element KEY. The main field loop cannot resolve the '*' token (it is neither a dict key nor a list
index), so every [*] field was skipped and composite.points stayed the typed-empty []. This grows the array ONCE
across the SHARED bucket axis: each field's column is bucketed over the window, and every bucket becomes one element
cloned from the default's element skeleton (chrome kept, unbound data keys blanked) with each field's _verify'd value
in its own element key + the bucket timestamp in a label/time key. Generic — the array_path/element_key/value-key all
come from the slot + the default skeleton, zero card knowledge. One concern; fill.py re-exports byte-compatibly.
[atomic]
"""
from __future__ import annotations

import copy
import re

from ems_exec.data import neuract as _nx
from ems_exec.executor.paths import _leaf_at, _has_path, _set_leaf_typed, _leaf_path_for
from ems_exec.executor.verify import _verify, _quantity_of
from ems_exec.executor.series_fill import _element_time_key, _epoch_ms, _is_time_field
from ems_exec.executor.graft import _graft_container, _graft_seedfree
from ems_exec.executor.gaps import _note_gap
from ems_exec.executor.indexed_families import _binding_for_field, _derived_bucket_values


def _wildcard_time_value(iso, elem_key, skel):
    """The per-bucket TIME value shaped to the element's OWN time slot: a numeric epoch key (…Ms / …EpochMs) or a numeric
    skeleton default → epoch ms; else a display-clock STRING formatted from the ISO bucket (HH:MM, or HH:MM:SS when the
    skeleton default carries seconds). Honest None on an unparseable bucket. Reuses bindings.format_ts (the shared token
    table); a card whose label default is a clock string ('00:00') keeps that shape, never an epoch integer."""
    key = (elem_key or "").lower()
    dflt = skel.get(elem_key) if isinstance(skel, dict) else None
    if key.endswith(("ms", "epochms")) or isinstance(dflt, (int, float)):
        return _epoch_ms(iso)
    fmt = "HH:MM:SS" if (isinstance(dflt, str) and dflt.count(":") >= 2) else "HH:MM"
    try:
        from ems_exec.executor.bindings import format_ts
        return format_ts(iso, fmt)
    except Exception:
        return _epoch_ms(iso)


def _split_wildcard(slot):
    """('composite.points', 'readiness') for 'composite.points[*].readiness' (or the '.' form composite.points.*.key).
    None when the slot carries no wildcard marker. The array_path is everything before the FIRST wildcard; the element
    key is the SINGLE token after it (a nested wildcard-into-wildcard is not a shape the AI emits — honest None)."""
    if not slot:
        return None
    m = re.search(r"(.*?)(?:\[\*\]|\.\*)\.(.+)$", str(slot))
    if not m:
        return None
    array_path, elem_key = m.group(1), m.group(2)
    if not array_path or not elem_key or "*" in elem_key:
        return None
    return array_path, elem_key


def _fill_wildcard_arrays(out, default_payload, wild_fields, asset_table, present_cols, window, gaps,
                          asset_name=None):
    """Grow every `<array>[*].<key>` wildcard-slot family into a real N-element OBJECT array from the SHARED bucket axis.

    `wild_fields` = [(field, array_path, elem_key)]. Fields are grouped by array_path; each group grows its array once so
    every element key aligns index-for-index over ONE axis (the anchor bucket timestamps). Each element clones the
    default array's element[0] skeleton (chrome kept, data-leaves blanked) so the component's per-point contract holds.
    A value field's column is bucketed over the window and _verify'd per bucket; a TIME field ([*].label / a ts-metric)
    gets the bucket timestamp formatted into that same element key. A field whose column is absent honest-blanks THAT
    element key only (never fabricates) and records a gap. Returns the set of array_paths it filled (so the caller skips
    those fields in the main loop). Never raises — a broken group degrades to the typed-empty array + a gap."""
    filled_paths = set()
    by_array: dict = {}
    for f, array_path, elem_key in wild_fields:
        by_array.setdefault(array_path, []).append((f, elem_key))
    for array_path, members in by_array.items():
        try:
            _grow_one_wildcard_array(out, default_payload, array_path, members, asset_table, present_cols, window,
                                     gaps, asset_name=asset_name)
        except Exception:
            pass
        filled_paths.add(array_path)
    return filled_paths


def _grow_one_wildcard_array(out, default_payload, array_path, members, asset_table, present_cols, window, gaps,
                             asset_name=None):
    """Grow ONE `<array_path>` into a real per-bucket object array from its member [*] fields. Bucket axis = the anchor
    of the member fields (their FIRST real-column series). Each bucket → one element cloned from the default skeleton,
    every member field's value written into its own element key. Honest-degrade: no real column on any member → the
    array stays the typed-empty [] (never a fabricated element) and each member field is gapped."""
    # graft the array container back from the default so the element skeleton is available (the gate elided it to None).
    leaf = _leaf_path_for(out, array_path)
    if leaf is None and default_payload is not None and _has_path(default_payload, array_path):
        _graft_container(out, default_payload, array_path)
        leaf = _leaf_path_for(out, array_path)
    if leaf is None:
        leaf = array_path if _has_path(out, array_path) else None
    # the element skeleton comes from the DEFAULT array's first element (chrome + key shape); else the current leaf's.
    skel = None
    for src in (default_payload, out):
        arr = _leaf_at(src, array_path) if src is not None else None
        if isinstance(arr, list) and arr and isinstance(arr[0], dict):
            skel = arr[0]
            break
    member_fields = [f for (f, _k) in members]
    # ONE shared bucket axis for every member field (index-for-index alignment) — the raw [{t, value?}] anchor series.
    anchor, anchor_sampling = None, "hourly"
    for f in member_fields:
        col = f.get("column")
        if col and col in present_cols:
            w = window or (None, None)
            s = _nx.bucketed(asset_table, col, w[0], w[1], sampling=f.get("sampling") or "hourly")
            if s:
                anchor = s
                anchor_sampling = f.get("sampling") or "hourly"
                break
    if not anchor:
        # no real column on ANY member → honest typed-empty array + gap each member field (never a fabricated element).
        if leaf is not None:
            _set_leaf_typed(out, leaf, [])
        for f in member_fields:
            _note_gap(gaps, f, asset_table, present_cols, latest_row={}, asset_name=asset_name)
        return
    n = len(anchor)
    tkey = _element_time_key(skel) if isinstance(skel, dict) else None
    # per-member bucketed value lists aligned to the anchor length (None-padded); a time member fills from the anchor ts.
    per_member = []
    for f, elem_key in members:
        col = f.get("column")
        quantity = _quantity_of(f)
        if _is_time_field(f, elem_key):
            # a ts-metric [*] field → the bucket timestamps. Match the element's OWN time shape: a numeric epoch key
            # (…Ms) or a numeric skeleton default → epoch ms; a display-clock key (skeleton value is a time STRING like
            # '00:00') → the timestamp formatted per that string's token width (HH:MM / HH:MM:SS), so the axis reads the
            # same shape the component expects (never epoch ms in a label slot, never a clock string in an …Ms slot).
            vals = [_wildcard_time_value(pt.get("t"), elem_key, skel) for pt in anchor]
            is_time = True
        elif col and col in present_cols:
            s = _nx.bucketed(asset_table, col, (window or (None, None))[0], (window or (None, None))[1],
                             sampling=f.get("sampling") or "hourly")
            vlist = [_verify(pt.get("value"), quantity=quantity) for pt in s]
            vals = (vlist + [None] * n)[:n]                     # align to the shared axis length (honest None-pad)
            is_time = False
            if not s or all(v is None for v in vlist):
                _note_gap(gaps, f, asset_table, present_cols, latest_row={}, asset_name=asset_name)
        elif _binding_for_field(f):
            # COLUMN-LESS member whose metric/fn has a derivation_binding row → per-bucket DERIVED series over the
            # anchor's granularity, TIMESTAMP-aligned to the shared axis (never positional: series() drops fully-dead
            # buckets, bucketed() doesn't). Same registry fn as the scalar KPI — honest None per unfillable bucket.
            b = _binding_for_field(f)
            dvals, dts = _derived_bucket_values(b["fn"], b.get("base_columns"), asset_table,
                                                (window or (None, None)), anchor_sampling, quantity)
            by_ts = {t: v for t, v in zip(dts, dvals)}
            vals = [by_ts.get(pt.get("t")) for pt in anchor]
            is_time = False
            if all(v is None for v in vals):
                _note_gap(gaps, f, asset_table, present_cols, latest_row={}, asset_name=asset_name)
        else:
            vals = [None] * n                                  # absent column → this element key blanks, others fill
            is_time = False
            _note_gap(gaps, f, asset_table, present_cols, latest_row={}, asset_name=asset_name)
        per_member.append((elem_key, vals, is_time))
    # ELEMENT BASE: skeleton chrome kept, data leaves blanked, and every UNDECLARED SCALAR data leaf NULLED — the fill
    # for this array completes RIGHT HERE, so a data key no [*] field declares can never fill later; shipping its
    # numeric 0.0 placeholder would render a MEASURED zero (card-59 bypassVoltageV). Declared member keys are written
    # below (a real 0.0 reading still lands); string/array chrome stays. [placeholder-null]
    el_base = _graft_seedfree(skel) if isinstance(skel, dict) else None
    if isinstance(el_base, dict):
        try:
            from grounding.default_assemble import null_scalar_data_leaves
            el_base = null_scalar_data_leaves(el_base) or el_base
        except Exception:
            pass
    # build the array: one element per bucket, cloned from the skeleton (data-blanked), each member key written in.
    grown = []
    for i in range(n):
        el = copy.deepcopy(el_base) if isinstance(el_base, dict) else {}
        if not isinstance(el, dict):
            el = {}
        for elem_key, vals, _is_time in per_member:
            el[elem_key] = vals[i] if i < len(vals) else None
        # a skeleton time key not covered by a [*] field still gets the bucket ts so the component's x-axis aligns.
        if tkey and tkey not in {k for (k, _v, _t) in per_member}:
            el[tkey] = _epoch_ms(anchor[i].get("t"))
        grown.append(el)
    if leaf is not None:
        _set_leaf_typed(out, leaf, grown)
