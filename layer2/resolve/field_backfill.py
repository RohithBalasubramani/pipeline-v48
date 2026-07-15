"""layer2/resolve/field_backfill.py — deterministic completion of slim fields[] emissions
[decode-wall Stage 6, flag emit.diet.fields, 2026-07-15].

fields[] was ~55% of every emit's completion tokens, and most of each ~180-byte field record RESTATES context the
pipeline already owns: `label`/`unit` are the slot's own payload chrome (slot catalog ctx) and the bound column's
dictionary entry (the basket — layer1b describe()), `metric` is the bound column, `role`/`agg` are functions of
`kind`. Under the slim contract the model emits only its DECISIONS ({slot, kind, column | fn/base_columns |
value+metric | edge, sampling}); this pass fills the ABSENT keys — and ONLY absent keys: a value the model DID emit
(an R7 proxy override, a legacy full retype) passes through byte-identically, so flag-off traffic and full retypes
are untouched no-ops.

TRUTHFULNESS: the backfilled metric/unit/label feed the executor's quantity-honesty verify (`ems_exec/executor/
verify.py`) and the unit-compat override (`layer2/resolve/column_override.py`) — sourcing them from the basket
dictionary + slot ctx is the SAME truth those gates enforce, i.e. strictly more honest than a model retype.
Wired in build._finalize_inner BEFORE override_columns so every gate sees completed fields. Never raises. [atomic]
"""
from layer2.emit.diet import fields_slim as _flag


_ROLE_BY_KIND = {"bucketed": "series", "time": "series"}
_AGG_BY_KIND = {"raw": "last", "bucketed": "avg", "event": "count", "derived": "derived"}


def _slot_ctx_map(dp, basket):
    """{slot: ctx{label,unit,section}} from the SAME slot catalog the prompt showed. {} on any failure (fail-open)."""
    try:
        if not dp or not dp.get("payload"):
            return {}
        from layer2.emit.slot_catalog import build_slot_catalog
        return {e.get("slot"): (e.get("ctx") or {}) for e in build_slot_catalog(dp["payload"], basket) or []}
    except Exception:
        return {}


def apply(di, basket, dp):
    """Fill ONLY-absent display/context keys on every fields[] record, in place; returns di. No-op when the flag is
    off, fields is empty, or a record already carries the key (present-but-empty values are the model's own choice
    and pass through untouched — 'fills ONLY absent keys' is the whole safety contract)."""
    if not _flag():
        return di
    fields = (di or {}).get("fields")
    if not isinstance(fields, list) or not fields:
        return di
    by_col = {}
    for c in (basket or {}).get("columns") or []:
        if isinstance(c, dict) and c.get("column"):
            by_col[c["column"]] = c
    ctx_by_slot = None                                         # lazy — most cards need it, but never pay on empty
    for f in fields:
        if not isinstance(f, dict):
            continue
        kind = str(f.get("kind") or "raw").strip().lower()
        col = f.get("column")
        b = by_col.get(col) or {}
        if "source" not in f:
            f["source"] = "const" if kind == "const" else "live"
        if "metric" not in f and col and kind != "const":      # const metric is the AI's nameplate-row key (R10) — never invented
            f["metric"] = col
        if "unit" not in f and b.get("unit"):
            f["unit"] = b["unit"]
        if "label" not in f:
            if ctx_by_slot is None:
                ctx_by_slot = _slot_ctx_map(dp, basket)
            lab = (ctx_by_slot.get(f.get("slot")) or {}).get("label") or b.get("label")
            if lab:
                f["label"] = lab
        if "role" not in f:
            f["role"] = _ROLE_BY_KIND.get(kind, "kpi")
        if "agg" not in f and kind in _AGG_BY_KIND:
            f["agg"] = _AGG_BY_KIND[kind]
    return di
