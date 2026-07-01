"""External-DB query helpers for the `assets` app.

Direct port of `lt_panels/services.py` with one rename: the per-row filter
column is **`asset_id`** (not `panel_id`). Each Asset holds a ``db_link``
(libpq connection string) and a ``table_name``; these helpers open a pooled
psycopg connection and read the latest row / a time window / a trailing
history. We never write — this module is a pure read broker.

Timezone contract
-----------------
Every connection runs `SET TIME ZONE 'UTC'` immediately after opening, so
the driver returns UTC-aware datetimes. Combined with the `_to_dt` check in
`consumers/_base.py` this gives consistent rolling-window math regardless of
server local time or the column being TIMESTAMPTZ vs TIMESTAMP.

NOTE — the timeseries row filter is the column ``panel_id`` and the
timestamp column is ``ts`` (the UPS tables, e.g. ``mfm_ups_047``, are each
single-asset so the filter is technically redundant but kept for safety and
multi-asset tables). If other asset tables you wire in differ, change
`_FILTER_COLUMN` / the `ts` references here in one place.
"""

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import psycopg
from psycopg_pool import ConnectionPool


logger = logging.getLogger(__name__)


# Row-filter column in the timeseries tables. The UPS asset tables
# (mfm_ups_*) carry a `panel_id` column (e.g. 'MFM-UPS-047'), same as the
# lt_panels timeseries tables — assets read from the same DB.
_FILTER_COLUMN = 'panel_id'

# Local timezone the frontend operates in — drives human-meaningful range
# presets and bucket edges (added when history pages are built). Wire +
# storage stay UTC.
LOCAL_TZ = ZoneInfo('Asia/Kolkata')
_LOCAL_TZ_NAME = 'Asia/Kolkata'


# ─── Connection pool ──────────────────────────────────────────────────────
# One shared `ConnectionPool` per distinct `db_link`, persisting for the
# process lifetime (Daphne workers are long-lived). Each connection's session
# TZ is pinned to UTC via `configure=`.
_POOLS: dict[str, ConnectionPool] = {}
_POOLS_LOCK = threading.Lock()

_POOL_MIN_SIZE = 4
_POOL_MAX_SIZE = 60
_POOL_TIMEOUT_SEC = 30


def _configure_connection(conn: psycopg.Connection) -> None:
    try:
        with conn.cursor() as cur:
            cur.execute("SET TIME ZONE 'UTC'")
        conn.commit()
    except Exception as exc:
        logger.warning('failed to SET TIME ZONE UTC on pooled conn: %s', exc)


def _get_pool(db_link: str) -> ConnectionPool:
    """Return (creating if needed) the shared pool for this `db_link`."""
    pool = _POOLS.get(db_link)
    if pool is not None:
        return pool
    with _POOLS_LOCK:
        pool = _POOLS.get(db_link)
        if pool is None:
            pool = ConnectionPool(
                conninfo=db_link,
                min_size=_POOL_MIN_SIZE,
                max_size=_POOL_MAX_SIZE,
                timeout=_POOL_TIMEOUT_SEC,
                configure=_configure_connection,
                open=True,
            )
            _POOLS[db_link] = pool
            logger.info(
                'opened psycopg pool for %s (min=%d max=%d)',
                db_link, _POOL_MIN_SIZE, _POOL_MAX_SIZE,
            )
    return pool


def _connect(db_link: str):
    """Borrow a pooled connection (returned to the pool on context exit)."""
    return _get_pool(db_link).connection()


def _row_to_dict(cursor, row) -> dict[str, Any]:
    cols = [c.name for c in cursor.description]
    return {col: val for col, val in zip(cols, row)}


# ─── Column introspection cache ────────────────────────────────────────────
# Strategies declare columns optimistically; the real table may not carry
# every column yet. Introspect once per (db_link, table) and intersect —
# missing columns are padded with None so widgets keep their full shape.

_TABLE_COLUMNS_CACHE: dict[tuple[str, str], set[str]] = {}


def get_table_columns(db_link: str, table: str) -> set[str]:
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

    `existing` always includes the implicit `ts` and the row-filter column;
    `missing` is the subset of `requested` absent from the table.
    """
    if not requested:
        return ['ts', _FILTER_COLUMN], []
    available = get_table_columns(db_link, table)
    existing = ['ts', _FILTER_COLUMN]
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


def fetch_live(
    db_link: str,
    table: str,
    asset_id: str,
    columns: list[str] | None = None,
) -> dict[str, Any] | None:
    """Return the latest row for the given asset_id, or None.

    Columns absent from the table are dropped from the SQL and added back as
    None in the returned dict, so widget strategies keep their column shape.
    """
    if not columns:
        select_cols = '*'
        missing: list[str] = []
    else:
        existing, missing = _select_existing(db_link, table, columns)
        select_cols = ', '.join(f'"{c}"' for c in existing)
    sql = (
        f'SELECT {select_cols} FROM "{table}" '
        f'WHERE "{_FILTER_COLUMN}" = %s ORDER BY ts DESC LIMIT 1'
    )
    with _connect(db_link) as conn, conn.cursor() as cur:
        cur.execute(sql, (asset_id,))
        row = cur.fetchone()
        return _pad_missing(_row_to_dict(cur, row) if row else None, missing)


def fetch_window(
    db_link: str,
    table: str,
    asset_id: str,
    seconds: int = 30,
    columns: list[str] | None = None,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    """Return rows from the last ``seconds`` seconds, oldest-first."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=seconds)
    if not columns:
        select_cols = '*'
        missing: list[str] = []
    else:
        existing, missing = _select_existing(db_link, table, columns)
        select_cols = ', '.join(f'"{c}"' for c in existing)
    sql = (
        f'SELECT {select_cols} FROM "{table}" '
        f'WHERE "{_FILTER_COLUMN}" = %s AND ts >= %s '
        f'ORDER BY ts ASC LIMIT %s'
    )
    with _connect(db_link) as conn, conn.cursor() as cur:
        cur.execute(sql, (asset_id, cutoff, limit))
        rows = cur.fetchall()
        return [_pad_missing(_row_to_dict(cur, r), missing) for r in rows]


def fetch_history(
    db_link: str,
    table: str,
    asset_id: str,
    minutes: int = 60,
    columns: list[str] | None = None,
    limit: int = 20000,
) -> list[dict[str, Any]]:
    """Return raw rows over the trailing ``minutes`` minutes, oldest-first."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    if not columns:
        select_cols = '*'
        missing: list[str] = []
    else:
        existing, missing = _select_existing(db_link, table, columns)
        select_cols = ', '.join(f'"{c}"' for c in existing)
    sql = (
        f'SELECT {select_cols} FROM "{table}" '
        f'WHERE "{_FILTER_COLUMN}" = %s AND ts >= %s '
        f'ORDER BY ts ASC LIMIT %s'
    )
    with _connect(db_link) as conn, conn.cursor() as cur:
        cur.execute(sql, (asset_id, cutoff, limit))
        rows = cur.fetchall()
        return [_pad_missing(_row_to_dict(cur, r), missing) for r in rows]


# ─── Range presets + period aggregates (Overview WindowedKpi support) ───────

def _local_midnight(dt_local: datetime) -> datetime:
    return dt_local.replace(hour=0, minute=0, second=0, microsecond=0)


def _parse_boundary(value: str) -> datetime:
    """ISO 8601 datetime, or bare YYYY-MM-DD anchored to IST midnight → UTC."""
    v = value.strip()
    if 'T' in v or ' ' in v:
        return datetime.fromisoformat(v.replace('Z', '+00:00'))
    d = datetime.fromisoformat(v + 'T00:00:00')
    return d.replace(tzinfo=LOCAL_TZ).astimezone(timezone.utc)


def resolve_range(preset: str | None, start: str | None = None,
                  end: str | None = None) -> tuple[datetime, datetime]:
    """Resolve a window from explicit start/end or a named preset → (start_utc, end_utc).

    Presets (IST-anchored): today, yesterday, week/this-week, month/this-month,
    last-month, last-7-days, last-30-days, last-24h. `week`/`month` are the
    Overview Energy-filter aliases for this-week/this-month. Explicit start+end
    accept ISO datetimes or bare YYYY-MM-DD (IST midnight). All returns are
    tz-aware UTC for the TIMESTAMPTZ `ts` column.
    """
    if start and end:
        return _parse_boundary(start), _parse_boundary(end)

    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(LOCAL_TZ)
    p = (preset or 'today').strip().lower()

    if p == 'today':
        return _local_midnight(now_local).astimezone(timezone.utc), now_utc
    if p == 'yesterday':
        end_local = _local_midnight(now_local)
        return (end_local - timedelta(days=1)).astimezone(timezone.utc), end_local.astimezone(timezone.utc)
    if p in ('week', 'this_week', 'this-week'):
        start_local = _local_midnight(now_local) - timedelta(days=now_local.weekday())
        return start_local.astimezone(timezone.utc), now_utc
    if p in ('month', 'this_month', 'this-month'):
        return _local_midnight(now_local).replace(day=1).astimezone(timezone.utc), now_utc
    if p in ('last_month', 'last-month'):
        this_month_start = _local_midnight(now_local).replace(day=1)
        prev_month_start = (this_month_start - timedelta(days=1)).replace(day=1)
        return prev_month_start.astimezone(timezone.utc), this_month_start.astimezone(timezone.utc)
    if p == 'last-7-days':
        return (_local_midnight(now_local) - timedelta(days=6)).astimezone(timezone.utc), now_utc
    if p == 'last-30-days':
        return (_local_midnight(now_local) - timedelta(days=29)).astimezone(timezone.utc), now_utc
    if p in ('last-90-days', '3m', '3M'):
        return (_local_midnight(now_local) - timedelta(days=89)).astimezone(timezone.utc), now_utc
    if p in ('last-365-days', '1y', '1Y'):
        return (_local_midnight(now_local) - timedelta(days=364)).astimezone(timezone.utc), now_utc
    if p in ('last_24h', 'last-24h'):
        return now_utc - timedelta(hours=24), now_utc
    # Unknown → today
    return _local_midnight(now_local).astimezone(timezone.utc), now_utc


# Sampling → bucket width. `hourly` = 3-hour blocks (the design's 00-03…21-24
# columns); `shift` = 8-hour IST shifts; daily/weekly as named.
VALID_SAMPLINGS = {'hourly', 'shift', 'daily', 'weekly', 'hour', 'day'}
_BUCKET_SECONDS = {
    'hourly': 3 * 3600, 'shift': 8 * 3600, 'daily': 86_400, 'weekly': 7 * 86_400,
    'hour': 3600, 'day': 86_400,
}


def _bucket_expr(sampling: str) -> str:
    """SQL expression bucketing `ts` by `sampling`, edges anchored to IST.

    Uses epoch-floor for sub-day/odd widths (hourly=3h, shift=8h) and
    date_trunc for daily/weekly. Mirrors the lt_panels bucketing so the two
    apps' history charts can't drift.
    """
    tz = f"'{_LOCAL_TZ_NAME}'"
    if sampling in ('daily', 'day'):
        return f"date_trunc('day', ts AT TIME ZONE {tz}) AT TIME ZONE {tz}"
    if sampling == 'weekly':
        return f"date_trunc('week', ts AT TIME ZONE {tz}) AT TIME ZONE {tz}"
    if sampling == 'hour':
        return f"date_trunc('hour', ts AT TIME ZONE {tz}) AT TIME ZONE {tz}"
    seconds = _BUCKET_SECONDS.get(sampling)
    if seconds is None:
        raise ValueError(f'Invalid sampling: {sampling}')
    return (f"((to_timestamp(floor(extract(epoch from ts AT TIME ZONE {tz}) "
            f"/ {seconds}) * {seconds}) AT TIME ZONE 'UTC') AT TIME ZONE {tz})")


def _columns_in_expr(expr: str) -> set[str]:
    import re
    keywords = {'AVG', 'MIN', 'MAX', 'SUM', 'COUNT', 'COALESCE', 'NULLIF',
                'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'AS', 'AND', 'OR',
                'NOT', 'NULL', 'TRUE', 'FALSE', 'CAST'}
    tokens = set(re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', expr))
    return {t for t in tokens if t.upper() not in keywords}


def fetch_bucketed(
    db_link: str, table: str, asset_id: str, columns: list[str],
    start: datetime, end: datetime, sampling: str = 'hourly',
    extra_aggregates: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """AVG/MIN/MAX per time bucket over [start, end]. Columns absent from the
    table are silently dropped (their aliases just won't appear). Each row:
    {bucket, <col>_avg, <col>_min, <col>_max, ..., samples}."""
    if sampling not in VALID_SAMPLINGS:
        raise ValueError(f'Invalid sampling: {sampling}')
    bucket_expr = _bucket_expr(sampling)
    available = get_table_columns(db_link, table) if (columns or extra_aggregates) else set()

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
        agg_parts = ['NULL AS _placeholder']
    agg_sql = ', '.join(agg_parts)

    sql = f'''
        SELECT {bucket_expr} AS bucket, {agg_sql}, COUNT(*) AS samples
        FROM "{table}"
        WHERE "{_FILTER_COLUMN}" = %s AND ts >= %s AND ts <= %s
        GROUP BY bucket ORDER BY bucket ASC
    '''
    with _connect(db_link) as conn, conn.cursor() as cur:
        cur.execute(sql, (asset_id, start, end))
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def fetch_tod_peaks(
    db_link: str, table: str, asset_id: str, columns: list[str],
    start: datetime, end: datetime, slot_hours: int = 3,
) -> dict[int, dict[str, float]]:
    """MAX per time-of-day slot over [start, end] — powers the Peak Temperature
    Heatmap. Slots are `slot_hours`-wide IST blocks (3h → slots 0..7 = 00-03…
    21-24). For multi-day windows this is the worst same-slot value across days.

    Returns {slot_index: {column: max_value}}.
    """
    available = get_table_columns(db_link, table)
    cols = [c for c in columns if c in available]
    if not cols:
        return {}
    tz = f"'{_LOCAL_TZ_NAME}'"
    slot_expr = f"floor(extract(hour from ts AT TIME ZONE {tz}) / {slot_hours})::int"
    max_parts = ', '.join(f'MAX("{c}") AS "{c}"' for c in cols)
    sql = f'''
        SELECT {slot_expr} AS slot, {max_parts}
        FROM "{table}"
        WHERE "{_FILTER_COLUMN}" = %s AND ts >= %s AND ts <= %s
        GROUP BY slot ORDER BY slot ASC
    '''
    with _connect(db_link) as conn, conn.cursor() as cur:
        cur.execute(sql, (asset_id, start, end))
        names = [c.name for c in cur.description]
        out = {}
        for r in cur.fetchall():
            row = dict(zip(names, r))
            slot = row.pop('slot')
            out[int(slot)] = {k: v for k, v in row.items()}
        return out


def fetch_window_stats(
    db_link: str, table: str, asset_id: str, column: str,
    start: datetime, end: datetime,
) -> dict | None:
    """MIN / MAX / AVG of a column over [start, end] (e.g. a 24h score
    envelope). None if the column is absent or the window has no rows."""
    if column not in get_table_columns(db_link, table):
        return None
    sql = (
        f'SELECT MIN("{column}"), MAX("{column}"), AVG("{column}") FROM "{table}" '
        f'WHERE "{_FILTER_COLUMN}" = %s AND ts BETWEEN %s AND %s'
    )
    with _connect(db_link) as conn, conn.cursor() as cur:
        cur.execute(sql, (asset_id, start, end))
        r = cur.fetchone()
        if not r or r[0] is None:
            return None
        return {'min': float(r[0]), 'max': float(r[1]), 'avg': float(r[2])}


def fetch_bucket_last(
    db_link: str, table: str, asset_id: str, column: str,
    start: datetime, end: datetime, sampling: str = 'hourly',
) -> dict[datetime, Any]:
    """Last value of `column` per time bucket — for categorical state timelines
    (e.g. UPS operating mode per bucket). Returns {bucket_start: value}."""
    if column not in get_table_columns(db_link, table):
        return {}
    bucket_expr = _bucket_expr(sampling)
    sql = f'''
        SELECT DISTINCT ON (bucket) bucket, val FROM (
            SELECT {bucket_expr} AS bucket, "{column}" AS val, ts
            FROM "{table}"
            WHERE "{_FILTER_COLUMN}" = %s AND ts BETWEEN %s AND %s
        ) q
        ORDER BY bucket, ts DESC
    '''
    with _connect(db_link) as conn, conn.cursor() as cur:
        cur.execute(sql, (asset_id, start, end))
        return {row[0]: row[1] for row in cur.fetchall()}


def fetch_period_delta(
    db_link: str, table: str, asset_id: str, column: str,
    start: datetime, end: datetime,
) -> float | None:
    """MAX-MIN of a monotonic counter column over [start, end] — i.e. the
    energy consumed in the window. Returns None if the column doesn't exist
    or the window has no rows. Column is validated against the real table
    schema (introspection set) before reaching SQL.
    """
    if column not in get_table_columns(db_link, table):
        return None
    sql = (
        f'SELECT MAX("{column}") - MIN("{column}") FROM "{table}" '
        f'WHERE "{_FILTER_COLUMN}" = %s AND ts BETWEEN %s AND %s'
    )
    with _connect(db_link) as conn, conn.cursor() as cur:
        cur.execute(sql, (asset_id, start, end))
        r = cur.fetchone()
        return float(r[0]) if r and r[0] is not None else None


def fetch_config_row(db_link: str, table: str, asset_id: str) -> dict[str, Any] | None:
    """Return the per-asset static config/nameplate row (e.g. transformer_config),
    filtered by panel_id. None if the table or row is absent."""
    with _connect(db_link) as conn, conn.cursor() as cur:
        try:
            cur.execute(
                f'SELECT * FROM "{table}" WHERE "{_FILTER_COLUMN}" = %s LIMIT 1',
                (asset_id,),
            )
        except Exception:
            return None
        row = cur.fetchone()
        return _row_to_dict(cur, row) if row else None
