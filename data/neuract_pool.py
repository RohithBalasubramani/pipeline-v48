"""data/neuract_pool.py — THE pooled psycopg2 door to neuract (dedup D1, refactor campaign 2026-07-12).

One concern: the pooled-connection lifecycle both neuract doors used to copy wholesale — `ems_exec/data/neuract.py`
(the time-series facade) and `data/neuract_live/_db.py` (the metadata facade) each carried byte-identical
`_key()/_conn()` + the execute→fetchall→pop-broken-conn read, so every tunnel-flap/lifecycle fix (connect timeouts,
keepalives, never-cache-empty) had to land twice or drift. The facades keep their public APIs, their obs/replay
seams (per-door tape kinds + sql_trace) and their own semantics; THIS module owns the pool.

Also THE home of the shared schema probe cache (`present_columns(table, runner)`) — TTLCache + never-cache-empty,
so a flap during introspection can never pin an empty column set for the process life. NOTE this deliberately
UPGRADES the registries door, whose plain-dict cache could still poison (the 2026-07-09 member-cache-poison class;
audit H2 — the fix had reached only the ems_exec copy). The `runner` parameter keeps the actual read flowing
through each facade's own traced/replayed read fn, so tapes and telemetry stay per-door.

DB-driven: connection solely from config/neuract_dsn.conn_kwargs() (connect_timeout + keepalives ride along).
Honest-degrade: conn() → None on failure; run_read() raises NeuractReadError (after dropping the broken pooled
conn) so each facade applies its own []-degrade + telemetry.
"""
from __future__ import annotations

import os
import threading

from config import neuract_dsn as _dsn
from data.ttl_cache import TTLCache

# THE pool [EXEC-1/DB-3, latency pass 2026-07-14]. Was a SINGLE persistent psycopg2 connection per key: because a
# psycopg2 connection serialises concurrent cursors behind its own lock, the 8-way executor card fan-out (and every
# /api/frame burst) queued ENTIRELY behind that one connection — a proven serialisation (a 4-panel page's summed card
# walls equalled its summed query latency). This is now a checkout/checkin pool of N connections (one thread uses one
# connection at a time), mirroring the proven cmd_catalog pool in data/db_client.py: idle connections are kept per
# (readonly, kwargs) key up to V48_DB_POOL_N; a burst may open more, and the excess closes on checkin (never blocks,
# never raises PoolError). The healthy-path RESULT is byte-identical — only the wait for the shared lock is gone.
_LOCK = threading.Lock()
_IDLE: dict = {}               # (readonly, frozen conn kwargs) -> [idle psycopg2 connections]
_POOL_MAX_IDLE = max(1, int(os.environ.get("V48_DB_POOL_N", "8")))   # idle kept per key; excess closes on checkin
_COLS_CACHE = TTLCache()       # table -> frozenset(present columns); never caches empty (see present_columns)
_TYPES_CACHE = TTLCache()      # table -> {column: data_type}; never caches empty (see column_types)


class NeuractReadError(Exception):
    """A pooled read failed (no connection / execute error). The broken conn is already dropped from the pool."""


def _key(readonly=False):
    kw = _dsn.conn_kwargs()
    return (bool(readonly),) + tuple(sorted((k, str(v)) for k, v in kw.items()))


def _new(readonly):
    """A fresh autocommit psycopg2 connection to neuract (readonly session when asked); None on any connect failure."""
    import psycopg2
    try:
        from data.connect_retry import with_retry              # bounded outage-retry (db.connect_retry_s) [audit 01 F3]
        c = with_retry(lambda: psycopg2.connect(**_dsn.conn_kwargs()), "neuract")
        c.autocommit = True
        if readonly:
            try:
                c.set_session(readonly=True)
            except Exception:
                pass
        return c
    except Exception:
        return None


def _checkout(readonly):
    """A live connection for this thread: an idle pooled one (dropping any that died while idle), else a fresh one."""
    key = _key(readonly)
    with _LOCK:
        idle = _IDLE.get(key)
        while idle:
            c = idle.pop()
            if not getattr(c, "closed", 1):
                return c
            _close(c)
    return _new(readonly)


def _checkin(readonly, c):
    """Return a still-healthy connection to the idle set (bounded by V48_DB_POOL_N); close the excess / the dead."""
    try:
        if getattr(c, "closed", 1):
            return
        key = _key(readonly)
        with _LOCK:
            idle = _IDLE.setdefault(key, [])
            if len(idle) < _POOL_MAX_IDLE:
                idle.append(c)
                return
    except Exception:
        pass
    _close(c)


def _close(c):
    try:
        c.close()
    except Exception:
        pass


def conn(readonly=False):
    """A live psycopg2 connection to neuract from the pool (compat shim; the hot path is run_read). None on failure.
    NOTE: this checks a connection OUT — the historical single-conn callers are all internal to run_read now, so this
    remains only for backward compatibility."""
    return _checkout(readonly)


def drop(readonly=False):
    """Discard every idle pooled connection for the key (a flap must not leave a half-dead conn to be reused). Open
    checked-out connections are dropped by run_read on their own read failure."""
    key = _key(readonly)
    with _LOCK:
        idle = _IDLE.pop(key, None) or []
    for c in idle:
        _close(c)


def run_read(sql, params=None, *, readonly=False, dict_rows=False):
    """Execute a read on a POOLED connection → list-of-tuples (or list-of-dicts keyed by the SELECT columns when
    `dict_rows`). Checks a connection out, runs, checks it back in; on failure the broken conn is discarded (not
    returned to the pool) and NeuractReadError is raised — the caller owns the honest-degrade ([] + its own telemetry).
    Concurrent callers each get their own connection, so the executor fan-out no longer serialises behind one socket."""
    c = _checkout(readonly)
    if c is None:
        raise NeuractReadError("no connection")
    try:
        with c.cursor() as cur:
            cur.execute(sql, params or ())
            if dict_rows:
                cols = [d[0] for d in (cur.description or [])]
                out = [dict(zip(cols, r)) for r in cur.fetchall()]
            else:
                out = cur.fetchall()
    except Exception as e:
        _close(c)
        raise NeuractReadError(str(e)[:300]) from e
    _checkin(readonly, c)
    return out


def present_columns(table, runner):
    """The frozenset of columns that PHYSICALLY exist on `table` in the neuract schema — shared cache, never-cache-
    empty (a real table always has columns, so [] means the read failed: re-check next call instead of pinning empty).
    `runner(sql, params)` is the calling facade's OWN read fn, so the probe rides that door's replay tape + trace."""
    if not table:
        return frozenset()
    hit = _COLS_CACHE.get(table)
    if hit is not None:
        return hit
    rows = runner(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s",
        (_dsn.schema(), table),
    )
    cols = frozenset(r[0] for r in rows)
    if cols:
        _COLS_CACHE[table] = cols
    return cols


def column_types(table, runner):
    """{column: information_schema data_type} for `table` — shared cache, never-cache-empty (same rule as
    present_columns: a real table always has columns, so {} means the read failed — re-check next call instead of
    pinning). Lets numeric SQL builders cast type-aware: a BOOLEAN flag column needs ::int before ::double
    precision (aux_hsd_plc_feedbacks bt_*_high — 62 'cannot cast type boolean' errors, console_validation/sql.md
    2026-07-12)."""
    if not table:
        return {}
    hit = _TYPES_CACHE.get(table)
    if hit is not None:
        return hit
    rows = runner(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s",
        (_dsn.schema(), table),
    )
    types = {r[0]: r[1] for r in rows}
    if types:
        _TYPES_CACHE[table] = types
    return types
