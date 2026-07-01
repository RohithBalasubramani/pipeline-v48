"""Column-introspection cache + column-list helpers.

Strategies declare columns optimistically; the underlying timeseries table may
not actually carry every column yet. We introspect once per (db_link, table)
and intersect — missing columns are padded with None in the response so widgets
still get their full shape.
"""

import re
from typing import Any

from .connection import _connect


_TABLE_COLUMNS_CACHE: dict[tuple[str, str], set[str]] = {}

# Guards raw-SQL boolean-event column names against injection (used by the
# fetch_bool_* helpers, which interpolate the column name straight into SQL).
_VALID_BOOL_COL = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]{0,62}$')


def get_table_columns(db_link: str, table: str) -> set[str]:
    """Return the set of column names that actually exist on ``table``.

    Cached per (db_link, table) for the lifetime of the process. Call
    ``invalidate_table_columns()`` if the schema changes at runtime.
    """
    key = (db_link, table)
    cached = _TABLE_COLUMNS_CACHE.get(key)
    if cached is not None:
        return cached
    sql = (
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = %s"
    )
    with _connect(db_link) as conn, conn.cursor() as cur:
        cur.execute(sql, (table,))
        cols = {r[0] for r in cur.fetchall()}
    _TABLE_COLUMNS_CACHE[key] = cols
    return cols


def invalidate_table_columns(db_link: str | None = None, table: str | None = None) -> None:
    """Clear all or a subset of cached column listings."""
    if db_link is None and table is None:
        _TABLE_COLUMNS_CACHE.clear()
        return
    keys = [k for k in _TABLE_COLUMNS_CACHE
            if (db_link is None or k[0] == db_link)
            and (table is None or k[1] == table)]
    for k in keys:
        _TABLE_COLUMNS_CACHE.pop(k, None)


def _select_existing(
    db_link: str, table: str, requested: list[str] | None
) -> tuple[list[str], list[str]]:
    """Split the caller's column list into (existing, missing).

    `existing` is the subset of `requested` that exists on the table; the
    timestamp is no longer an implicit member (callers prepend the `{_TSQ} AS
    ts` alias themselves), and there is no `panel_id` column on the raw
    per-meter tables. `missing` is the subset of `requested` that doesn't
    exist on the table.
    """
    if not requested:
        return [], []
    available = get_table_columns(db_link, table)
    existing = []
    missing = []
    for c in requested:
        if c in available:
            if c not in existing:
                existing.append(c)
        else:
            missing.append(c)
    return existing, missing


def _pad_missing(row: dict[str, Any] | None, missing: list[str]) -> dict[str, Any] | None:
    if row is None or not missing:
        return row
    for c in missing:
        row.setdefault(c, None)
    return row


def _columns_in_expr(expr: str) -> set[str]:
    """Heuristic: pull bare identifiers out of a SQL fragment so we can check
    each one exists on the table. Misses quoted identifiers and table-qualified
    names; good enough for our extra_aggregates (e.g. 'MAX(sag_events_24h)')."""
    SQL_KEYWORDS = {
        'AVG', 'MIN', 'MAX', 'SUM', 'COUNT', 'COALESCE', 'NULLIF',
        'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'AS', 'AND', 'OR',
        'NOT', 'NULL', 'TRUE', 'FALSE', 'CAST',
    }
    tokens = set(re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', expr))
    return {t for t in tokens if t.upper() not in SQL_KEYWORDS}
