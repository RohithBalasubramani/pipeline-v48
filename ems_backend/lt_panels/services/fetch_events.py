"""Boolean event-flag fetchers (rising-edge FALSE→TRUE detection).

The simulator emits ``sag_event_active`` / ``swell_event_active`` etc as
boolean columns that flip TRUE while an event is in progress. Counting raw TRUE
rows over-reports (one event spans many samples), so these helpers use LAG to
count only the rising edges — "one event = one count". The single- and
combo-column variants share their crossing detector so counts and record lists
stay consistent on the same window.
"""

from datetime import datetime
from typing import Any

from .config import _TSQ, _PANEL_NAMED, _LOCAL_TZ_NAME
from .connection import _connect
from .columns import get_table_columns, _VALID_BOOL_COL


def fetch_bool_event_counts_per_bucket(
    db_link: str,
    table: str,
    panel_id: str,
    column: str,
    start: datetime,
    end: datetime,
    bucket_seconds: int,
) -> dict[datetime, int]:
    """Count FALSE→TRUE transitions of a boolean event-flag column, bucketed.

    The simulator emits ``sag_event_active`` / ``swell_event_active`` etc as
    BOOLEAN columns that flip TRUE while an event is in progress. Counting
    raw TRUE rows over-reports (one event spans many samples), so we use
    LAG to count only the rising edges — that's "one event = one count".

    Returns ``{bucket_start_ts (UTC tz-aware): count}``. Same crossing
    detector used elsewhere — keeps counts consistent with
    ``fetch_bool_event_records`` if both run on the same window.
    """
    if not _VALID_BOOL_COL.match(column):
        raise ValueError(f'unsafe column name: {column!r}')
    if column not in get_table_columns(db_link, table):
        return {}
    sql = f"""
        WITH samples AS (
            SELECT {_TSQ} AS ts, ("{column}" != 0) AS active,
                   LAG(("{column}" != 0)) OVER (ORDER BY {_TSQ}) AS prev_active
            FROM "{table}"
            WHERE {_PANEL_NAMED} AND {_TSQ} BETWEEN %(start)s AND %(end)s
        ), edges AS (
            SELECT ts
            FROM samples
            WHERE active = TRUE
              AND (prev_active IS NULL OR prev_active = FALSE)
        )
        SELECT to_timestamp(floor(extract(epoch FROM ts) / %(bucket)s) * %(bucket)s) AS bucket_ts,
               COUNT(*) AS n
        FROM edges
        GROUP BY bucket_ts
        ORDER BY bucket_ts
    """
    params = {'panel_id': panel_id, 'start': start, 'end': end,
              'bucket': bucket_seconds}
    out: dict[datetime, int] = {}
    with _connect(db_link) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        for bucket_ts, n in cur.fetchall():
            if bucket_ts is not None:
                out[bucket_ts] = int(n)
    return out


def fetch_bool_event_records(
    db_link: str,
    table: str,
    panel_id: str,
    column: str,
    start: datetime,
    end: datetime,
    max_events: int = 100,
) -> list[dict[str, Any]]:
    """Discrete FALSE→TRUE transition records for a boolean event-flag column.

    Returns ``[{'ts': datetime}]`` capped at ``max_events`` (oldest first).
    Use alongside ``fetch_bool_event_counts_per_bucket`` for the wire-frame
    events list — the counts query gives the authoritative total, this one
    gives a representative sample of timestamps for the timeline chart.
    """
    if not _VALID_BOOL_COL.match(column):
        raise ValueError(f'unsafe column name: {column!r}')
    if column not in get_table_columns(db_link, table):
        return []
    sql = f"""
        WITH samples AS (
            SELECT {_TSQ} AS ts, ("{column}" != 0) AS active,
                   LAG(("{column}" != 0)) OVER (ORDER BY {_TSQ}) AS prev_active
            FROM "{table}"
            WHERE {_PANEL_NAMED} AND {_TSQ} BETWEEN %(start)s AND %(end)s
        )
        SELECT ts FROM samples
        WHERE active = TRUE AND (prev_active IS NULL OR prev_active = FALSE)
        ORDER BY ts
        LIMIT %(max_events)s
    """
    params = {'panel_id': panel_id, 'start': start, 'end': end,
              'max_events': max_events}
    with _connect(db_link) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return [{'ts': r[0]} for r in cur.fetchall()]


def fetch_bool_event_combo_per_bucket(
    db_link: str,
    table: str,
    panel_id: str,
    columns: list[tuple[str, str]],   # [(sql_col_name, wire_type_label), ...]
    start: datetime,
    end: datetime,
    bucket_seconds: int,
) -> dict[datetime, dict[str, int]]:
    """One-shot per-bucket counts for multiple boolean event-flag columns.

    Same rising-edge detection as ``fetch_bool_event_counts_per_bucket`` but
    sweeps all 4 (sag/swell/current/neutral) flags in a single CTE — turns 4
    SQL round trips into 1. Returns ``{bucket_ts: {type_label: count, ...}}``.

    Columns that don't physically exist on the table are silently skipped
    so this also handles the transformer/UPS tables (which haven't been
    given the boolean flags yet) without erroring.
    """
    if not columns:
        return {}
    available = get_table_columns(db_link, table)
    columns = [(c, lbl) for c, lbl in columns if c in available]
    if not columns:
        return {}
    for col, _ in columns:
        if not _VALID_BOOL_COL.match(col):
            raise ValueError(f'unsafe column name: {col!r}')

    select_cols = ', '.join(f'("{c}" != 0) AS act_{i}'
                            for i, (c, _) in enumerate(columns))
    lag_cols = ', '.join(
        f'LAG(("{c}" != 0)) OVER (ORDER BY {_TSQ}) AS prev_{i}'
        for i, (c, _) in enumerate(columns)
    )
    sum_cols = ',\n        '.join(
        f'SUM(CASE WHEN act_{i} = TRUE AND (prev_{i} IS NULL OR prev_{i} = FALSE) '
        f'THEN 1 ELSE 0 END) AS n_{i}'
        for i in range(len(columns))
    )
    # IST-anchored bucket flooring (same trick as `_bucket_expr`): shift the
    # UTC ts to IST wall-clock, floor by bucket_seconds, then reinterpret
    # the floor result as IST and convert back to UTC. This keeps SQL keys
    # aligned with the IST-midnight bucket edges built in `_make_bucket_edges`
    # — without the AT TIME ZONE dance the keys would be UTC-midnight and
    # the per-bucket lookups would miss every entry.
    tz = f"'{_LOCAL_TZ_NAME}'"
    sql = f"""
        WITH samples AS (
            SELECT {_TSQ} AS ts, {select_cols}, {lag_cols}
            FROM "{table}"
            WHERE {_PANEL_NAMED} AND {_TSQ} BETWEEN %(start)s AND %(end)s
        )
        SELECT (
            (to_timestamp(floor(
                extract(epoch from ts AT TIME ZONE {tz}) / %(bucket)s
            ) * %(bucket)s) AT TIME ZONE 'UTC') AT TIME ZONE {tz}
        ) AS bucket_ts,
        {sum_cols}
        FROM samples
        GROUP BY bucket_ts
        ORDER BY bucket_ts
    """
    params = {'panel_id': panel_id, 'start': start, 'end': end,
              'bucket': bucket_seconds}
    out: dict[datetime, dict[str, int]] = {}
    with _connect(db_link) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        for row in cur.fetchall():
            bucket_ts = row[0]
            if bucket_ts is None:
                continue
            slot = {lbl: int(row[1 + i]) for i, (_, lbl) in enumerate(columns)}
            out[bucket_ts] = slot
    return out


def fetch_bool_event_combo_records(
    db_link: str,
    table: str,
    panel_id: str,
    columns: list[tuple[str, str]],
    start: datetime,
    end: datetime,
    max_events_per_type: int = 100,
) -> list[dict[str, Any]]:
    """Discrete event records across multiple boolean flags — one table scan.

    Replaces the naive N-UNION-ALL pattern (which scans the table once per
    branch) with a single CTE: the LAG sweep runs ONCE, then a lateral
    VALUES expression fans out the rising-edge detection across all 4
    flags. ROW_NUMBER() caps per-type so one stormy event-type can't crowd
    out the others. For a 27-day window on a 1Hz table this cuts records
    fetch time by ~4× (matches the number of event flags).
    """
    if not columns:
        return []
    available = get_table_columns(db_link, table)
    columns = [(c, lbl) for c, lbl in columns if c in available]
    if not columns:
        return []
    for col, _ in columns:
        if not _VALID_BOOL_COL.match(col):
            raise ValueError(f'unsafe column name: {col!r}')

    # Build the CTE selects: act_i + prev_i for each flag.
    act_cols  = ', '.join(f'("{c}" != 0) AS act_{i}'
                          for i, (c, _) in enumerate(columns))
    lag_cols  = ', '.join(
        f'LAG(("{c}" != 0)) OVER (ORDER BY {_TSQ}) AS prev_{i}'
        for i, (c, _) in enumerate(columns)
    )
    # Lateral VALUES turns "one row per sample" into "up to 4 rows per
    # sample" — one for each flag that just flipped to TRUE on this row.
    values_rows = ',\n            '.join(
        f"('{lbl}', act_{i} = TRUE AND (prev_{i} IS NULL OR prev_{i} = FALSE))"
        for i, (_, lbl) in enumerate(columns)
    )
    sql = f"""
        WITH samples AS (
            SELECT {_TSQ} AS ts, {act_cols}, {lag_cols}
            FROM "{table}"
            WHERE {_PANEL_NAMED} AND {_TSQ} BETWEEN %(start)s AND %(end)s
        ), edges AS (
            SELECT samples.ts, v.etype
            FROM samples
            CROSS JOIN LATERAL (VALUES
            {values_rows}
            ) AS v(etype, is_edge)
            WHERE v.is_edge
        ), ranked AS (
            SELECT ts, etype,
                   ROW_NUMBER() OVER (PARTITION BY etype ORDER BY ts) AS rn
            FROM edges
        )
        SELECT ts, etype FROM ranked
        WHERE rn <= %(per_type)s
        ORDER BY ts
    """
    params = {'panel_id': panel_id, 'start': start, 'end': end,
              'per_type': max_events_per_type}
    out: list[dict[str, Any]] = []
    with _connect(db_link) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        for ts, etype in cur.fetchall():
            out.append({'ts': ts, 'type': etype})
    return out
