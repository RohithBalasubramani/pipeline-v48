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

import threading

from config import neuract_dsn as _dsn
from data.ttl_cache import TTLCache

_LOCK = threading.Lock()
_POOL: dict = {}               # (readonly, frozen conn kwargs) -> psycopg2 connection
_COLS_CACHE = TTLCache()       # table -> frozenset(present columns); never caches empty (see present_columns)


class NeuractReadError(Exception):
    """A pooled read failed (no connection / execute error). The broken conn is already dropped from the pool."""


def _key(readonly=False):
    kw = _dsn.conn_kwargs()
    return (bool(readonly),) + tuple(sorted((k, str(v)) for k, v in kw.items()))


def conn(readonly=False):
    """A live psycopg2 connection to neuract from the pool (reconnect if the pooled one died). None on any failure.
    `readonly=True` marks the session read-only (the registries door's belt-and-braces — that package never writes)."""
    import psycopg2
    key = _key(readonly)
    with _LOCK:
        c = _POOL.get(key)
        if c is not None and not getattr(c, "closed", 1):
            return c
        try:
            c = psycopg2.connect(**_dsn.conn_kwargs())
            c.autocommit = True
            if readonly:
                try:
                    c.set_session(readonly=True)
                except Exception:
                    pass
            _POOL[key] = c
            return c
        except Exception:
            return None


def drop(readonly=False):
    """Forget the pooled connection (a broken conn must not be reused); the next conn() call reconnects. The popped
    conn is closed (outside the lock) so its FD is released now, not whenever GC gets to it."""
    c = None
    with _LOCK:
        try:
            c = _POOL.pop(_key(readonly), None)
        except Exception:
            pass
    if c is not None:
        try:
            c.close()
        except Exception:
            pass


def run_read(sql, params=None, *, readonly=False, dict_rows=False):
    """Execute a read on the pooled connection → list-of-tuples (or list-of-dicts keyed by the SELECT columns when
    `dict_rows`). Raises NeuractReadError on no-connection/execute failure — the caller owns the honest-degrade
    ([] + its own telemetry); the broken pooled conn is dropped here so the next call reconnects."""
    c = conn(readonly)
    if c is None:
        raise NeuractReadError("no connection")
    try:
        with c.cursor() as cur:
            cur.execute(sql, params or ())
            if dict_rows:
                cols = [d[0] for d in (cur.description or [])]
                return [dict(zip(cols, r)) for r in cur.fetchall()]
            return cur.fetchall()
    except Exception as e:
        drop(readonly)
        raise NeuractReadError(str(e)[:300]) from e


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
