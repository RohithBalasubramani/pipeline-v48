"""ems_exec/executor/sibling_resolve.py — SIBLING-FIELD resolution for the unbound measurable scalar leaf
(card 40) [monoliths F10, 2026-07-12]. Extracted from measurable_resolve.py (its one consumer is
scalar_mean_fill.py); re-exported byte-compatibly. [atomic; DB-driven stopword vocab]"""
from __future__ import annotations

from ems_exec.executor.measurable_resolve import _tokens, _tokset

# ── sibling-field resolution (the fields[] scalar-mean leaf, card 40) ─────────────────────────────────────────────────
# The non-content STOPWORD tokens (articles / stat words / display units) stripped before comparing a leaf's QUANTITY
# identity to a sibling field's. DB-driven (measurable.sibling_stopwords) with this code-default mirror.
_STOPWORDS_DEFAULT = ["the", "of", "and", "per", "avg", "average", "mean", "max", "min", "peak",
                      "total", "kw", "kwh", "kva", "kvar", "kvarh", "kvah", "hz", "pct", "percent"]


def _stopwords():
    return _tokset("measurable.sibling_stopwords", _STOPWORDS_DEFAULT)


def _content_tokens(*texts):
    """The content (non-stopword, non-unit, non-stat) tokens of a set of texts — the QUANTITY identity of a leaf/field
    ('activePowerAvgKw'→{active,power}; label 'Active Power' + metric 'active_power_total_kw'→{active,power})."""
    stop = _stopwords()
    out = set()
    for t in texts:
        for tok in _tokens(t):
            if tok and tok not in stop and not tok.isdigit():
                out.add(tok)
    return out


def sibling_column_for_scalar(key, fields, unit=None):
    """The (column, quantity) an UNBOUND MEASURABLE scalar leaf should reduce, taken from a SIBLING data field that
    already binds a real column of the SAME quantity (card 40: data.activePowerAvgKw is unbound, but data.bars[*].active
    already binds active_power_total_kw, unit kW). Match = the leaf key's content tokens ⊆ a series/scalar field's content
    tokens (its metric/column/label), AND the field carries a real column, AND (when both declare a unit) the units agree.
    `quantity` = the sibling field's unit-derived dimensional quantity (config.vocab unit_quantities; kW→power) so the
    caller's _verify applies the SAME negative-power abs convention the sibling series used (else the scalar mean of a
    reversed-CT feeder's negative active power would read −188 while the bars read +190). (None, None) when no matching
    sibling exists. Purely over the emitted fields (no DB) — the caller still verifies the column is present+logged before
    filling, so an over-reach is impossible. Never raises."""
    want = _content_tokens(key)
    if not want:
        return None, None
    ku = (unit or "").strip().lower()
    best = None
    for f in (fields or []):
        if not isinstance(f, dict):
            continue
        col = f.get("column")
        if not col or (f.get("kind") or "").lower() in ("const", "text"):
            continue
        have = _content_tokens(f.get("metric"), f.get("column"), f.get("label"))
        if not want.issubset(have):
            continue
        fu = str(f.get("unit") or "").strip().lower()
        if ku and fu and ku != fu:
            continue                                           # a declared unit mismatch → not the same quantity
        # prefer the tightest match (fewest extra tokens) so 'active power' does not bind a broader 'power' field
        extra = len(have - want)
        if best is None or extra < best[3]:
            best = (col, f.get("quantity"), f, extra)
    if best is None:
        return None, None
    col, q, f, _extra = best
    if q is None:
        try:
            from ems_exec.executor.verify import _quantity_of
            q = _quantity_of(f)                                # kW→power (the SAME dimensional lookup the bars used)
        except Exception:
            q = None
    return col, q
