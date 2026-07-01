"""Connection-pool + row-mapping helpers for the lt_panels services layer.

One shared ``ConnectionPool`` per distinct ``db_link``. Pools persist for the
lifetime of the process; we never call ``pool.close()`` because Daphne workers
are long-lived. Each connection has its session timezone pinned to UTC via
``configure=`` so callers always see UTC-aware datetimes.

The lock guards the dict against concurrent first-use creation.
"""

import logging
import threading
from typing import Any

import psycopg
from psycopg_pool import ConnectionPool


logger = logging.getLogger(__name__)


_POOLS: dict[str, ConnectionPool] = {}
_POOLS_LOCK = threading.Lock()

_POOL_MIN_SIZE = 4
# Sized for: PCC aggregate page fans out across 4 outgoings × 3 parallel
# queries = 12 connections per open WS. Two tabs / two sockets opening
# simultaneously = 24. Tripling the old 20 limit to 60 gives the aggregate
# page comfortable headroom without exhausting Postgres's default 100
# max_connections cap (room left for other dispatchers + admin sessions).
_POOL_MAX_SIZE = 60
_POOL_TIMEOUT_SEC = 30   # how long a waiter blocks for a free conn


def _configure_connection(conn: psycopg.Connection) -> None:
    """Per-connection setup — runs once when the pool checks the conn out
    of the kernel and into the pool's idle set. SET TIME ZONE 'UTC' ensures
    timeseries queries return tz-aware UTC datetimes regardless of column
    type or server local time. See `_to_dt` in consumers/_base.py for the
    matching receiver-side enforcement.
    """
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
        # Re-check inside the lock to avoid race on first use
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
    """Borrow a pooled connection.

    Caller uses it as a context manager:
        with _connect(db_link) as conn, conn.cursor() as cur:
            cur.execute(...)
    On context exit the connection returns to the pool (it is NOT closed).
    The configured session TZ persists across check-out cycles.
    """
    return _get_pool(db_link).connection()


def _row_to_dict(cursor, row) -> dict[str, Any]:
    cols = [c.name for c in cursor.description]
    return {col: val for col, val in zip(cols, row)}
