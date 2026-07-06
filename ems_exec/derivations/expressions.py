"""derivations/expressions.py — the derivation_binding EXPRESSION-row reader (the DB row is authoritative).

Single concern: for a metric/value_key, fetch its `expression` (+ `scope`) from cmd_catalog.derivation_binding so the
registry executes the ROW-DRIVEN formula via derivations.evaluate instead of a python fn. A NULL/empty expression, a
missing row, or a DB outage all return None — the registry then falls through to the retained python fn (or honest-
degrades when the fn was collapsed). NO cache: an edited row changes behavior on the next call, like every other
config/* reader. [atomic: this file = the row read, evaluate.py = the interpreter, registry.py = the dispatch]
"""
from __future__ import annotations

from data.db_client import q


def _esc(s):
    return str(s).replace("'", "''")


def expression_row(metric):
    """{expression, scope} for a metric, or None (no row / NULL expression / DB unreachable — honest fall-through)."""
    try:
        rows = q("cmd_catalog",
                 f"SELECT expression, scope FROM derivation_binding WHERE metric='{_esc(metric)}'")
    except Exception:
        return None
    if not rows:
        return None
    expr = (rows[0][0] or "").strip()
    if not expr:
        return None
    scope = (rows[0][1] or "row").strip() if len(rows[0]) > 1 else "row"
    return {"expression": expr, "scope": scope or "row"}


def expression_of(metric):
    """Just the expression text for a metric, or None."""
    row = expression_row(metric)
    return row["expression"] if row else None
