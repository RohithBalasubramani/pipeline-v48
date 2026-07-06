"""registries/neuract/_db.py — the ONE read door for the NEURACT metadata tables (framework-light, pooled, READ-ONLY).

Single concern: hand every registry accessor in this package a parameterized SELECT against the `neuract` schema and give
back list-of-dicts (or [] on any failure — honest-degrade, never raise, never fabricate). This is the metadata twin of
ems_exec/data/neuract.py (which reads the time-series gic_* tables); THIS one reads the METADATA tables (lt_mfm, the
lt_mfm_* edge tables, lt_parameter/lt_config_*, asset/asset_type, the 3d tables).

DB-driven: the connection comes solely from config/neuract_dsn.conn_kwargs() (a cmd_catalog knob with a code-default
fallback) — nothing here hard-codes a host/port/db/schema. A tiny thread-safe process pool keyed by the frozen conn
kwargs means repeated metadata reads reuse one connection; a DSN edit rotates to a fresh pool. autocommit + read-only.
[atomic; DB-driven; honest-degrade]
"""
from __future__ import annotations

import threading

from config import neuract_dsn as _dsn

_LOCK = threading.Lock()
_POOL: dict = {}          # frozen-kwargs key -> psycopg2 connection
_COLS_CACHE: dict = {}    # table -> frozenset(present columns) (schema is stable per process)


def _key():
    kw = _dsn.conn_kwargs()
    return tuple(sorted((k, str(v)) for k, v in kw.items()))


def _conn():
    """A live psycopg2 connection to neuract from the pool (reconnect if the pooled one died). None on any failure."""
    import psycopg2
    key = _key()
    with _LOCK:
        c = _POOL.get(key)
        if c is not None and not getattr(c, "closed", 1):
            return c
        try:
            c = psycopg2.connect(**_dsn.conn_kwargs())
            c.autocommit = True
            try:
                c.set_session(readonly=True)          # belt-and-braces: this package NEVER writes
            except Exception:
                pass
            _POOL[key] = c
            return c
        except Exception:
            return None


def rows(sql, params=None):
    """Run a read → list-of-tuples ([] on any error / dead connection — honest-degrade, never raise)."""
    c = _conn()
    if c is None:
        return []
    try:
        with c.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()
    except Exception:
        with _LOCK:
            try:
                _POOL.pop(_key(), None)               # drop a broken pooled conn; next call reconnects
            except Exception:
                pass
        return []


def dicts(sql, params=None):
    """Run a read → list-of-dicts keyed by the SELECT column names ([] on any error — honest-degrade, never raise)."""
    c = _conn()
    if c is None:
        return []
    try:
        with c.cursor() as cur:
            cur.execute(sql, params or ())
            cols = [d[0] for d in (cur.description or [])]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
    except Exception:
        with _LOCK:
            try:
                _POOL.pop(_key(), None)
            except Exception:
                pass
        return []


def one(sql, params=None):
    """Run a read expecting a single row → dict (or None if no row / error — honest-degrade)."""
    got = dicts(sql, params)
    return got[0] if got else None


def present_columns(table):
    """The frozenset of columns that PHYSICALLY exist on `table` in the neuract schema (cached). frozenset() on error."""
    if not table:
        return frozenset()
    hit = _COLS_CACHE.get(table)
    if hit is not None:
        return hit
    got = rows(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s",
        (_dsn.schema(), table),
    )
    cols = frozenset(r[0] for r in got)
    _COLS_CACHE[table] = cols
    return cols


def has_column(table, col):
    return bool(col) and col in present_columns(table)


def table_exists(table):
    """True if `table` exists in the neuract schema (empty tables count as existing — honest-degrade uses this)."""
    return bool(present_columns(table))
