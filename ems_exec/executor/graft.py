"""ems_exec/executor/graft.py — default-payload grafting + placeholder honesty: the seed-free graft of gate-elided
containers, the untouched-placeholder null pass and the FE-safety typed-empty array restore. One concern; fill.py
re-exports byte-compatibly. [atomic]
"""
from __future__ import annotations

import copy

from config import quality_policy as _qp
from ems_exec.executor.paths import _toks, _leaf_at, _set_path, _has_path


def _graft_seedfree(subtree):
    """A DEEP COPY of a default subtree with every DATA leaf reset to its typed placeholder — the ONLY thing a graft
    may import. Grafting the raw default verbatim re-imported the Storybook seed: only the ONE declared leaf was then
    overwritten and every sibling seed number (a heatmap section's feeders grid) rendered as if live. Uses the MINIMAL
    data-leaf blank (grounding.default_assemble.blank_data_leaves — one leaf_classify pass, scalar→0/array→[]/series
    per-element, NO narrative scrub: a data container carries no prose), NOT the full build-time strip. On any failure
    the graft is REFUSED (None — the leaf honest-blanks) rather than seeded."""
    try:
        from grounding.default_assemble import blank_data_leaves
        stripped = blank_data_leaves(copy.deepcopy(subtree))
        return stripped if isinstance(stripped, (dict, list)) else copy.deepcopy(subtree)
    except Exception:
        return None if isinstance(subtree, (dict, list)) else copy.deepcopy(subtree)


def _graft_container(out, default_payload, slot):
    """Ensure the leaf `slot` HAS A CONTAINER to fill by grafting it from the DEFAULT payload.

    The Layer-2 byte-identity gate ELIDES the whole DATA tier (a `series`/`history`/`nodes` roster → None), so the
    exact_metadata the executor receives has NO `history.data.series[0].values` container at all — a declared series
    field then resolves to nothing and the leaf can never fill. This grafts the elided container back from the harvested
    DEFAULT payload (which still carries the placeholder skeleton, e.g. series[i].values=[…]) so the executor has a real
    array/object leaf to overwrite. It ONLY creates ancestors that already exist in the default (never invents a path);
    the placeholder numbers it grafts are OVERWRITTEN by the real fill (or honest-blanked) immediately after, so no seed
    survives. Returns True if the slot is now present (grafted or already there)."""
    if default_payload is None or _has_path(out, slot):
        return _has_path(out, slot)
    toks = _toks(slot)
    if not toks:
        return False
    # walk the two trees in lock-step; where `out` is missing a child that the DEFAULT has, deep-copy the default subtree.
    node, dnode = out, default_payload
    for i, t in enumerate(toks):
        key = int(t) if t.isdigit() else t
        dchild = None
        try:
            dchild = dnode[key]
        except (KeyError, IndexError, TypeError):
            return False                                        # the default has no such path → cannot graft (honest)
        present = False
        try:
            present = node[key] is not None                    # a key present-but-None (gate-elided) counts as MISSING
        except (KeyError, IndexError, TypeError):
            present = False
        if not present:
            # graft the DEFAULT's subtree SEED-FREE (typed placeholders only) IF the parent container can hold this
            # key (dict key / valid list index). A raw-default graft would re-import Storybook numbers the declared
            # fields never overwrite — a graft that cannot be stripped is refused (honest-blank beats seed).
            graft = _graft_seedfree(dchild)
            if graft is None and isinstance(dchild, (dict, list)):
                return False
            if isinstance(node, dict):
                node[key] = graft
            elif isinstance(node, list) and isinstance(key, int) and 0 <= key <= len(node):
                if key == len(node):
                    node.append(graft)
                else:
                    node[key] = graft
            else:
                return False
        if i < len(toks) - 1:
            node = node[key]
            dnode = dchild
    return _has_path(out, slot)


def _null_untouched_placeholders(out, input_payload, written_paths):
    """FILL-COMPLETION HONESTY [card-59 bypassVoltageV family]: a SCALAR data leaf the fill never touched (no field
    declared it, no graft/axis/family/wildcard wrote it) still holds the build-time numeric placeholder
    (quality_policy placeholder.scalar, 0.0) — shipped as-is it renders a MEASURED zero. Null it so host/display_dash
    dashes it ('—'). GENERIC and safe by three fences:
      (a) leaves = validate.leaf_classify SCALAR data leaves of the INPUT skeleton — chrome is untouchable by
          construction (classify never lists it);
      (b) 'untouched' = not in written_paths AND still byte-equal to the input — a REAL measured 0.0 the executor
          wrote is in written_paths and stays 0.0;
      (c) only the exact PLACEHOLDER value is nulled — an AI-morphed numeric or any surviving non-placeholder value is
          never erased.
    Runs BEFORE the roster seam, so a roster-filled real zero lands after this pass and survives. Never raises."""
    try:
        from validate.leaf_classify import classify
        leaves = classify(input_payload).get("data_leaves") or []
    except Exception:
        return
    try:
        ph = float(_qp.txt("placeholder.scalar", "0"))
    except (TypeError, ValueError):
        ph = 0.0
    written = {tuple(_toks(p)) for p in (written_paths or ())}

    def _exempt(toks):
        # PREFIX exemption: a leaf under ANY written path (a series array the executor replaced wholesale, a wildcard-
        # grown roster) was produced by the fill — its zeros are REAL readings, never placeholder residue.
        return any(toks[:j] in written for j in range(1, len(toks) + 1))

    def _is_ph_pair(ov, iv):
        return (isinstance(ov, (int, float)) and not isinstance(ov, bool)
                and isinstance(iv, (int, float)) and not isinstance(iv, bool)
                and ov == iv == ph)

    def _null_in_elements(oe, ie, toks):
        # lock-step walk of ONE series element (out vs input): an element numeric STILL byte-equal to the input
        # placeholder is untouched residue (kpiCells[1].value=0.0 shipped as a measured average) → None.
        if isinstance(oe, dict) and isinstance(ie, dict):
            for k, ivv in ie.items():
                t = toks + (str(k),)
                if _exempt(t):
                    continue
                ovv = oe.get(k)
                if _is_ph_pair(ovv, ivv):
                    oe[k] = None
                elif isinstance(ovv, (dict, list)) and isinstance(ivv, (dict, list)):
                    _null_in_elements(ovv, ivv, t)
        elif isinstance(oe, list) and isinstance(ie, list):
            for i, (o2, i2) in enumerate(zip(oe, ie)):
                _null_in_elements(o2, i2, toks + (str(i),))

    for d in leaves:
        kind = d.get("kind")
        path = d.get("path") or ""
        if not path:
            continue
        toks = tuple(_toks(path))
        if _exempt(toks):
            continue
        iv = _leaf_at(input_payload, path)
        ov = _leaf_at(out, path)
        if kind == "scalar":
            if _is_ph_pair(ov, iv):
                _set_path(out, path, None)
        elif kind == "series" and isinstance(ov, list) and isinstance(iv, list):
            # a series-of-OBJECTS is classified as ONE leaf (no per-element scalars listed) — walk its elements so an
            # untouched per-element numeric placeholder (kpiCells[1].value) nulls too. A series the fill REPLACED is
            # exempt above; inside a kept container, only input-identical placeholder values null (real zeros differ
            # from the input or live under a written path).
            _null_in_elements(ov, iv, toks)


def _restore_array_containers(out, default):
    """Walk the DEFAULT payload; wherever it holds a LIST but `out` holds None (gate-elided) or lacks the key, set the
    typed-empty [] so the FE always mounts an iterable — never a null roster. [] only; never the default's seed rows."""
    if isinstance(default, dict) and isinstance(out, dict):
        for k, dv in default.items():
            if isinstance(dv, list):
                if out.get(k) is None:                          # missing key OR present-but-None → typed-empty
                    out[k] = []
                elif isinstance(out.get(k), list):
                    _restore_array_containers(out[k], dv)
            elif isinstance(dv, dict):
                ov = out.get(k)
                if isinstance(ov, dict):
                    _restore_array_containers(ov, dv)
    elif isinstance(default, list) and isinstance(out, list):
        for ov, dv in zip(out, default):
            if isinstance(dv, (dict, list)) and isinstance(ov, (dict, list)):
                _restore_array_containers(ov, dv)
