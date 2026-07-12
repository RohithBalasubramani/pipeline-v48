"""data/db_client.py — q(db, sql): THE catalog/registry read door; raises on failure (no silent empty).

ENGINE (V48_DB_ENGINE env): 'pool' (default) runs queries over a small process-wide pool of psycopg2 connections —
one connect per (db × pool slot) instead of one `psql` SUBPROCESS per query (the audit's hottest finding: fan-in ~70,
dozens of process spawns per page render). 'psql' is the instant rollback to the historical subprocess path.

CSV PARITY: the pool path fetches SELECT-shaped statements via `COPY (sql) TO STDOUT (FORMAT csv)` and parses with the
same csv.reader — the SERVER formats every value exactly as `psql --csv -t` did (bool t/f, NULL → '', timestamps,
jsonb, arrays), so the two engines are byte-compatible for every caller. Rows come back as lists of strings either way.

SELF-HEAL: a pooled connection that died with the tunnel (:5433 flap) is discarded and the query retried ONCE on a
fresh connect; a fresh-connection failure raises immediately (the honest outage — degrade-gate fingerprints match the
psycopg2 message shapes; see data/outage.py). [R2 pooled-engine 2026-07-12]
"""
import csv
import io
import os
import subprocess
import sys
import threading

from config.databases import PSQL_USER, conn_env


try:
    from replay import hooks as _replay_hooks                  # record/replay seam (fail-open; None → bare calls)
except Exception:
    _replay_hooks = None


_ENGINE = (os.environ.get("V48_DB_ENGINE") or "pool").strip().lower()

# ── the pool: {db: [idle psycopg2 connections]} — checkout/checkin under one lock (a connection is used by exactly
# one thread at a time; run/parallel's per-request thread pools would churn thread-locals, so pooling is global).
_POOL_LOCK = threading.Lock()
_POOL = {}
_POOL_MAX_IDLE = int(os.environ.get("V48_DB_POOL_MAX", "6"))  # idle kept per db; excess closes on checkin

# statements the server can wrap in COPY (...) TO STDOUT (FORMAT csv) — everything q() serves today. Anything else
# (should DML ever arrive) falls to a plain autocommit execute.
_COPYABLE = ("select", "with", "values", "table")


def q(db, sql):
    """The public catalog/registry read — semantics in the engine functions below. REPLAY SEAM [replay/hooks.py]:
    recorded (rows or the raised RuntimeError) during a traced request; served from the tape during a pinned replay
    (incl. re-raising a recorded failure verbatim, so degrade-gate fingerprint branches reproduce)."""
    if _replay_hooks is None:
        return _q_raw(db, sql)
    return _replay_hooks.db_q(_q_raw, db, sql)


def _q_raw(db, sql):
    if _ENGINE == "psql":
        return _q_psql(db, sql)
    return _q_pool(db, sql)


# ── pooled psycopg2 engine (default) ─────────────────────────────────────────────────────────────────────────────

def _checkout(db):
    """(conn, fresh) — an idle pooled connection, else a new pg_connect (which owns the 5s fail-fast + obs tracing)."""
    with _POOL_LOCK:
        idle = _POOL.get(db)
        if idle:
            return idle.pop(), False
    return pg_connect(db), True


def _checkin(db, conn):
    try:
        if conn.closed:
            return
        with _POOL_LOCK:
            idle = _POOL.setdefault(db, [])
            if len(idle) < _POOL_MAX_IDLE:
                idle.append(conn)
                return
    except Exception:
        pass
    _discard(conn)


def _discard(conn):
    try:
        conn.close()
    except Exception:
        pass


def _first_keyword(sql):
    """First SQL keyword, skipping whitespace and -- / block comments (enough to classify COPY-able reads)."""
    s = sql.lstrip()
    while True:
        if s.startswith("--"):
            nl = s.find("\n")
            if nl < 0:
                return ""
            s = s[nl + 1:].lstrip()
        elif s.startswith("/*"):
            end = s.find("*/")
            if end < 0:
                return ""
            s = s[end + 2:].lstrip()
        else:
            break
    tok = s.split(None, 1)[0] if s else ""
    return tok.lower().rstrip("(")


def _run_on(conn, sql):
    """Rows (lists of strings) via server-side CSV for reads; plain execute fallback otherwise."""
    import psycopg2
    conn.autocommit = True
    if _first_keyword(sql) in _COPYABLE:
        buf = io.StringIO()
        with conn.cursor() as cur:
            try:
                cur.copy_expert(f"COPY ({sql}) TO STDOUT (FORMAT csv)", buf)
                return [r for r in csv.reader(io.StringIO(buf.getvalue())) if r]
            except psycopg2.errors.FeatureNotSupported:
                pass                                           # e.g. a data-modifying CTE — plain path below
    with conn.cursor() as cur:
        cur.execute(sql)
        if cur.description is None:
            return []
        return [[_psql_str(v) for v in row] for row in cur.fetchall()]


def _psql_str(v):
    """psql-parity string for the (rare) non-COPY path: NULL → '', bool → t/f, everything else str()."""
    if v is None:
        return ""
    if v is True:
        return "t"
    if v is False:
        return "f"
    return str(v)


def _connection_dead(conn, exc):
    import psycopg2
    return bool(getattr(conn, "closed", False)) or isinstance(exc, (psycopg2.OperationalError, psycopg2.InterfaceError))


def _q_pool(db, sql):
    import time
    t0 = time.time()
    conn, fresh = _checkout(db)
    try:
        rows = _run_on(conn, sql)
    except Exception as e:
        _discard(conn)
        if not fresh and _connection_dead(conn, e):
            # stale pooled connection (tunnel flap while idle) — one retry on a genuinely fresh connect; a failure
            # THERE is the honest outage and raises below.
            try:
                conn2 = pg_connect(db)
            except Exception as e2:
                return _q_fail(db, sql, t0, e2)
            try:
                rows = _run_on(conn2, sql)
            except Exception as e3:
                _discard(conn2)
                return _q_fail(db, sql, t0, e3)
            _checkin(db, conn2)
            _sql_trace(db, sql, ms=int((time.time() - t0) * 1000), rows=len(rows))
            return rows
        return _q_fail(db, sql, t0, e)
    _checkin(db, conn)
    _sql_trace(db, sql, ms=int((time.time() - t0) * 1000), rows=len(rows))
    return rows


def _q_fail(db, sql, t0, exc):
    import time
    err = str(exc).strip()[:300]
    ms = int((time.time() - t0) * 1000)
    sys.stderr.write(f"[db error - {db}] {err}\n  SQL: {sql[:200]}\n")
    _sql_trace(db, sql, ms=ms, err=err)
    raise RuntimeError(f"DB error ({db}): {err}")


# ── historical psql-subprocess engine (V48_DB_ENGINE=psql rollback) ──────────────────────────────────────────────

def _q_psql(db, sql):
    import time
    t0 = time.time()
    out = subprocess.run(
        ["psql", "-U", PSQL_USER, "-d", db, "--csv", "-t", "-c", sql],
        capture_output=True, text=True,
        env={**os.environ, "PGCLIENTENCODING": "UTF8", **conn_env(db)},  # route db → tunnel/catalog endpoint
    )
    ms = int((time.time() - t0) * 1000)
    if out.returncode != 0:
        err = (out.stderr or "").strip()[:300]
        sys.stderr.write(f"[db error - {db}] {err}\n  SQL: {sql[:200]}\n")
        _sql_trace(db, sql, ms=ms, err=err)
        raise RuntimeError(f"DB error ({db}): {err}")
    rows = [r for r in csv.reader(io.StringIO(out.stdout)) if r]
    _sql_trace(db, sql, ms=ms, rows=len(rows))
    return rows


def _sql_trace(db, sql, *, ms=None, rows=None, err=None):
    """SQL telemetry (obs/sql_trace.py — the SQL leg of the run's observability triple). Fail-open: a missing/broken
    recorder must never affect a query."""
    try:
        from obs.sql_trace import record
        record(db, sql, rows=rows, ms=ms, err=err)
    except Exception:
        pass


def pg_connect(db):
    """A psycopg2 connection to `db`, ROUTED to the right endpoint (tunnel 5433 vs local catalog 5432) via conn_env —
    for callers that need a live cursor / pandas DataFrame (validate's data read), not q()'s rows; the q() pool also
    connects through here. Without this, a bare psycopg2.connect(dbname=...) defaults to the local socket and misses
    the tunneled DATA/REGISTRY DBs.

    OBS: the CONNECT phase is recorded as its own sql_trace/db_tap record (`<pg_connect>`) — a wobbling tunnel burns
    its 5s timeout per attempt invisibly otherwise (the asset_resolution 200s-vs-146ms-LLM gap). Query-time on these
    raw cursors stays untapped (the caller's stage span still owns the wall clock)."""
    import time
    import psycopg2
    ce = conn_env(db)
    t0 = time.time()
    try:
        conn = psycopg2.connect(dbname=db, user=ce["PGUSER"], host=ce["PGHOST"], port=ce["PGPORT"],
                                password=(ce["PGPASSWORD"] or None),
                                connect_timeout=int(ce.get("PGCONNECT_TIMEOUT", "5")))  # dead tunnel → fail fast, not ~2min TCP hang
    except Exception as e:
        _sql_trace(db, "<pg_connect>", ms=int((time.time() - t0) * 1000), err=e)
        raise
    _sql_trace(db, "<pg_connect>", ms=int((time.time() - t0) * 1000), rows=None)
    return conn


def pg_bool(v):
    """A psql CSV boolean cell → bool. psql --csv emits booleans as 't'/'f' (raw column) or 'true'/'false' (cast);
    '1' covers int-cast flags. THE one parser for that cell format (dedup D7, 2026-07-12) — five inline copies
    (equipment/bridge, meaningful, has_data, corpus/universe, registry/lt_mfm) repointed here. copilot/has_data.py has
    a deliberate pandas twin (copilot is zero-coupled — leave it)."""
    return str(v).strip().lower() in ("t", "true", "1")


def first_row(db, sql):
    """The first row of `sql`, or None under the catalog readers' triple guard (no rows / empty row / NULL first
    cell — a LEFT-JOIN ghost or an all-default row reads as absent). THE one home for that idiom (dedup D12,
    2026-07-12). NOT for readers whose first cell may be legitimately falsy — those keep their own double guard."""
    r = q(db, sql)
    if not r or not r[0] or not r[0][0]:
        return None
    return r[0]


def json_cell(v, raw_on_error=False):
    """A psql json/jsonb cell → the parsed value; empty → None. `raw_on_error` picks the failure semantics the two
    catalog copies deliberately differed on (D12): False → None (card_data_recipe — a corrupt recipe is absent),
    True → the raw text (card_controls — a malformed defaults blob still ships as text for the FE to ignore)."""
    import json as _json
    if not v:
        return None
    try:
        return _json.loads(v)
    except Exception:
        return (v or None) if raw_on_error else None
