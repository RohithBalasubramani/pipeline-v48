"""Time-bucketed aggregation + energy-delta fetchers.

``fetch_bucketed`` rolls columns into avg/min/max per time bucket;
``fetch_energy_delta`` returns consumption over a window as the difference of
the two boundary readings (robust to non-monotonic meter data).
"""

from datetime import datetime
from typing import Any

from .config import _TSQ, _PANEL_POS
from .connection import _connect
from .columns import get_table_columns, _columns_in_expr
from .timeutils import VALID_SAMPLINGS, _bucket_expr


def fetch_bucketed(
    db_link: str,
    table: str,
    panel_id: str,
    columns: list[str],
    start: datetime,
    end: datetime,
    sampling: str = 'hour',
    extra_aggregates: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Aggregate columns into time buckets, returning avg/min/max per bucket.

    ``extra_aggregates`` is a dict of {output_alias: SQL fragment} for things
    like ``SUM(sag_events_24h)`` that don't fit the avg/min/max pattern.

    Columns and extra-aggregate fragments referencing columns that don't exist
    on the table are silently dropped from the SQL — the corresponding output
    aliases are simply absent from the result rows (frontend treats missing keys
    as None).
    """
    if sampling not in VALID_SAMPLINGS:
        raise ValueError(f'Invalid sampling: {sampling}')
    bucket_expr = _bucket_expr(sampling)

    available = get_table_columns(db_link, table) if columns or extra_aggregates else set()

    agg_parts = []
    for c in columns:
        if c not in available:
            continue
        agg_parts.append(f'AVG("{c}") AS "{c}_avg"')
        agg_parts.append(f'MIN("{c}") AS "{c}_min"')
        agg_parts.append(f'MAX("{c}") AS "{c}_max"')
    if extra_aggregates:
        for alias, expr in extra_aggregates.items():
            referenced = _columns_in_expr(expr)
            if referenced and not referenced.issubset(available):
                continue
            agg_parts.append(f'{expr} AS "{alias}"')
    if not agg_parts:
        # Nothing to aggregate — still emit bucket + samples so client gets shape
        agg_parts = ['NULL AS _placeholder']
    agg_sql = ', '.join(agg_parts)

    sql = f'''
        SELECT
            {bucket_expr} AS bucket,
            {agg_sql},
            COUNT(*) AS samples
        FROM "{table}"
        WHERE {_PANEL_POS} AND {_TSQ} >= %s AND {_TSQ} <= %s
        GROUP BY bucket
        ORDER BY bucket ASC
    '''
    with _connect(db_link) as conn, conn.cursor() as cur:
        cur.execute(sql, (panel_id, start, end))
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def fetch_energy_delta(
    db_link: str,
    table: str,
    panel_id: str,
    column: str,
    start: datetime,
    end: datetime,
) -> float | None:
    """Return energy consumed during ``[start, end]`` as

        (latest value at-or-before end) − (latest value at-or-before start)

    This is robust to non-monotonic meter data (e.g. the simulator writing
    historical hourly snapshots alongside live sub-second samples) — we
    don't rely on MAX/MIN, just on what the meter SAID at those two moments.

    Returns None if the column doesn't exist on the table or either bound
    has no row.
    """
    available = get_table_columns(db_link, table)
    if column not in available:
        return None
    # Two single-row probes: the most recent reading at-or-before each bound.
    sql = (
        f'SELECT "{column}" FROM "{table}" '
        f'WHERE {_PANEL_POS} AND {_TSQ} <= %s '
        f'ORDER BY {_TSQ} DESC LIMIT 1'
    )
    with _connect(db_link) as conn, conn.cursor() as cur:
        cur.execute(sql, (panel_id, start))
        s_row = cur.fetchone()
        cur.execute(sql, (panel_id, end))
        e_row = cur.fetchone()
    if not s_row or not e_row or s_row[0] is None or e_row[0] is None:
        return None
    return float(e_row[0]) - float(s_row[0])
