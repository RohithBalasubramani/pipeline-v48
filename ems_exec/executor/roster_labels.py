"""ems_exec/executor/roster_labels.py — the per-series LABEL alignment post-pass (c73/c53 swap label-morph
gap) [monoliths F8, 2026-07-12]. Extracted from roster.py into its own sibling (the roster_modes_*/roster_stats
pattern roster.py's docstring documents); roster.py re-exports byte-compatibly and calls _align_series_labels after
the roster fills. One concern: rename a per-series LABEL leaf to the metric its OWN values leaf was actually bound
to — only when the seed label does not already name that quantity. [atomic; DB-driven leaf-token vocab]"""
from __future__ import annotations

from config.failopen import cfg_safe as _cfg
from ems_exec.executor.roster_paths import _targets, values_at

# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# SWAP LABEL-MORPH GAP [DEFECT c73/c53]: a swapped-in card renders its swap-TARGET's payload shape (card 53
# backupHistory.series[i]) but the slot's story bound a DIFFERENT metric family (a DG power/frequency trend). Layer 2's
# DATA fields correctly bind each `series[i].values` to a real column WITH a declared label ('Active Power (kW)', …),
# and the real (all-zero-but-honest) power series fills — yet the sibling `series[i].label` kept the swap-target SEED
# ('Autonomy index' / 'Backup time score' / 'Load Pressure score') the recipe never morphed. Real data plotted under a
# label that names a quantity this meter does not even measure = a misleading leaf (the card's own data_note declares
# those score series omitted). The FIX: after the roster fills, align each per-series LABEL to the metric its OWN values
# leaf was bound to (the emitted field's declared label / humanized metric) — ONLY when the seed label does NOT already
# name that metric (over-reach-safe: a label that already matches, or a series with no real fill and no bound field, is
# untouched). Generic — no card ids, no key literals; driven off the emitted fields + the payload's own shape.

# the leaf token a per-series VALUE array carries, and the sibling LABEL leaf token — DB-driven, code-default. A field
# whose slot ends in a value token has a sibling label at the same series element under the label token.
_SERIES_VALUE_LEAF_DEFAULT = ["values", "value", "data", "points", "series_data"]
_SERIES_LABEL_LEAF_DEFAULT = ["label", "name", "legendLabel", "seriesLabel", "title"]
# tokens dropped when comparing a label to a metric quantity (units / stats / filler) — a label that already NAMES the
# bound metric's quantity is left alone; only a STALE label naming a different quantity is renamed.
_LABEL_MATCH_STOP = {"the", "of", "and", "per", "avg", "average", "mean", "max", "min", "peak", "total", "kw", "kwh",
                     "kva", "kvar", "kvarh", "kvah", "hz", "pct", "percent", "score", "index", "a", "v"}


def _series_value_leaves():
    v = _cfg("roster.series_value_leaf_tokens", _SERIES_VALUE_LEAF_DEFAULT)
    return [str(t).lower() for t in v] if isinstance(v, (list, tuple)) and v else _SERIES_VALUE_LEAF_DEFAULT


def _series_label_leaves():
    v = _cfg("roster.series_label_leaf_tokens", _SERIES_LABEL_LEAF_DEFAULT)
    return [str(t).lower() for t in v] if isinstance(v, (list, tuple)) and v else _SERIES_LABEL_LEAF_DEFAULT


def _label_tokens(text):
    """Lowercase content tokens of a label / metric (camelCase + snake_case split, units/stats/filler dropped)."""
    if not text:
        return set()
    import re
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(text)).replace("_", " ").replace("-", " ")
    return {t for t in re.split(r"[^a-z0-9]+", s.lower()) if t and t not in _LABEL_MATCH_STOP and not t.isdigit()}


def _leaf_slot_swap(slot, want_value_leaves, new_leaf):
    """Given a field slot whose LAST path segment is one of `want_value_leaves` AND whose value leaf is the child of an
    ARRAY ELEMENT (a per-series element: '…series[0].values' / '…points[*].values' — an indexed or [*] segment
    immediately precedes the leaf), return the sibling slot with that last segment replaced by `new_leaf`
    ('…series[0].label'), else None. The array-element requirement is the OVER-REACH GUARD: a bare scalar
    '<tile>.value' (no array index parent) is NOT a per-series value and is never touched — only a genuine SERIES
    element's label is aligned. Preserves every earlier segment/index verbatim (surgery on the final '.<leaf>' only)."""
    import re
    s = str(slot or "")
    m = re.search(r"\.([A-Za-z_][A-Za-z0-9_]*)$", s)
    if not m or m.group(1).lower() not in want_value_leaves:
        return None
    parent = s[:m.start()]                                       # the value leaf's parent path
    # parent must END in a SPECIFIC INDEXED array element ('…[<int>]') — a per-series element addressed 1:1 by the
    # field. A bare scalar ('<tile>.value', no array parent) is skipped, AND a wildcard '…[*].values' is skipped too:
    # a [*] field would smear ONE label onto EVERY series element (the c53 fix binds each series by its own INDEX, so
    # the per-index path is the only one that carries a distinct metric identity). Over-reach guard.
    if not re.search(r"\[-?\d+\]$", parent):
        return None
    return parent + "." + new_leaf


def _humanize_metric(metric):
    """A readable label for a raw metric/column name when the field declared no label ('active_power_total_kw' →
    'Active Power Total Kw'). Title-cased content of the split tokens; empty → None."""
    import re
    if not metric:
        return None
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(metric)).replace("_", " ").replace("-", " ")
    words = [w for w in re.split(r"\s+", s.strip()) if w]
    return " ".join(w.capitalize() for w in words) or None


def _align_series_labels(payload, state, default_payload):
    """For each emitted DATA field that binds a per-SERIES value leaf ('…series[i].values') which actually FILLED with
    real data, rename the sibling '…series[i].label' to the field's declared label (or humanized metric) — but ONLY
    when the current label is a STALE seed that does NOT already name the bound metric's quantity. Fixes the c73/c53
    swap label-morph gap (real power/frequency series plotted under stale 'Autonomy index' seeds). Over-reach-safe: a
    series with no real fill, or a label already naming the bound quantity, or a field with no usable label, is left
    untouched; never fabricates a label for a genuinely-blank series. Never raises (each field independent)."""
    if not isinstance(payload, dict):
        return
    fields = state.get("emitted_fields") or []
    if not fields:
        return
    value_leaves = _series_value_leaves()
    label_leaf = (_series_label_leaves() or ["label"])[0]
    for f in fields:
        if not isinstance(f, dict):
            continue
        slot = f.get("slot")
        # the metric identity this field bound — its declared label wins, else a humanized metric/column.
        want_label = (f.get("label") or "").strip() or _humanize_metric(f.get("metric") or f.get("column"))
        if not want_label:
            continue
        label_slot = _leaf_slot_swap(slot, value_leaves, label_leaf)
        if not label_slot:
            continue
        # only rename when the field's OWN value leaf actually holds real data (an honest-blank series is not relabeled)
        vals = values_at(payload, slot)
        real = any((isinstance(v, list) and any(x is not None for x in v)) or
                   (not isinstance(v, list) and v not in (None, "", "—")) for v in vals)
        if not real:
            continue
        want_toks = _label_tokens(want_label)
        for container, key, _marker in _targets(payload, default_payload, label_slot):
            cur = container.get(key)
            # untouched when: no current label (nothing to correct) OR it already names the bound metric's quantity.
            if not isinstance(cur, str) or not cur.strip():
                continue
            cur_toks = _label_tokens(cur)
            if want_toks and cur_toks and want_toks.issubset(cur_toks):
                continue                                        # the label already names this quantity — leave it
            container[key] = want_label                          # align the label to the metric its values bound


