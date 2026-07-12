"""obs/sink_pg.py — the QUERYABLE store: a buffered background writer into cmd_catalog obs_* tables
(db/obs_schema.sql). write(event) only enqueues (bounded queue — overflow DROPS and counts, it never blocks the
pipeline); one daemon thread batches INSERTs on a flush interval. First start executes db/obs_schema.sql
(all IF NOT EXISTS — zero-ops bootstrap); any DB failure backs the sink off for 30s and the events degrade to the
jsonl/console sinks that already got them. Uses its OWN psycopg2 connection — never data.db_client.q — so the
db_tap can never see (and re-log) the sink's own writes."""
import json
import os
import queue
import threading
import time

_Q = None                                                     # bounded event queue (created on first write)
_LOCK = threading.Lock()
_STARTED = False
_DOWN_UNTIL = 0.0                                             # backoff: sink disabled until this epoch after a failure
DROPPED = 0                                                   # overflow/backoff drop counter (telemetry)

_SCHEMA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "db", "obs_schema.sql")


from config.failopen import cfg_safe as _cfg   # THE guarded cfg reader (D3)


def write(event):
    """Enqueue one canonical event; never blocks, never raises."""
    global _Q, _STARTED, DROPPED
    if time.time() < _DOWN_UNTIL:
        DROPPED += 1
        return
    with _LOCK:
        if _Q is None:
            _Q = queue.Queue(maxsize=int(_cfg("obs.buffer_max", 5000) or 5000))
        if not _STARTED:
            threading.Thread(target=_writer_loop, name="obs-pg-writer", daemon=True).start()
            _STARTED = True
    try:
        _Q.put_nowait(event)
    except queue.Full:
        DROPPED += 1


def flush(timeout=5.0):
    """Best-effort drain (tests / process exit): wait until the queue is empty or the timeout passes."""
    t0 = time.time()
    while _Q is not None and not _Q.empty() and time.time() - t0 < timeout:
        time.sleep(0.05)


def _connect():
    from data.db_client import pg_connect
    from config.databases import CMD_CATALOG
    conn = pg_connect(CMD_CATALOG)
    conn.autocommit = False
    return conn


def _bootstrap(conn):
    """Apply db/obs_schema.sql (idempotent: IF NOT EXISTS / CREATE OR REPLACE VIEW). Missing file → tables must
    already exist; a failure here just surfaces on the first INSERT and triggers the normal backoff."""
    try:
        with open(_SCHEMA_FILE, encoding="utf-8") as f:
            ddl = f.read()
        with conn.cursor() as cur:
            cur.execute(ddl)
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass


_LAST_PURGE = 0.0


def _purge(conn):
    """RETENTION [obs.retention_days, default 30; 0 = keep forever]: drop obs_* rows older than the window, at most
    once per writer-day. Zero-ops (no cron): the long-running host's own sink keeps the store bounded. Fail-open —
    a purge failure never affects the write path (rolled back, retried next window)."""
    global _LAST_PURGE
    days = int(_cfg("obs.retention_days", 30) or 0)
    if days <= 0 or time.time() - _LAST_PURGE < 86400:
        return
    _LAST_PURGE = time.time()
    try:
        with conn.cursor() as cur:
            for table, ts_col in (("obs_stage_events", "ts_start"), ("obs_llm_calls", "ts"),
                                  ("obs_db_queries", "ts"), ("obs_traces", "started_at")):
                cur.execute(f"DELETE FROM {table} WHERE {ts_col} < now() - %s * interval '1 day'", (days,))
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass


def _writer_loop():
    global _DOWN_UNTIL, DROPPED
    conn = None
    flush_s = float(_cfg("obs.flush_interval_s", 2.0) or 2.0)
    while True:
        try:
            batch = [_Q.get(timeout=flush_s)]
        except queue.Empty:
            continue
        try:
            while len(batch) < 500:
                batch.append(_Q.get_nowait())
        except queue.Empty:
            pass
        try:
            if conn is None or getattr(conn, "closed", 1):
                conn = _connect()
                _bootstrap(conn)
            _insert_batch(conn, batch)
            conn.commit()
            _purge(conn)                                       # retention window (daily, fail-open)
        except Exception:
            DROPPED += len(batch)
            _DOWN_UNTIL = time.time() + 30.0                   # back off; jsonl/console still have every event
            try:
                if conn is not None:
                    conn.rollback()
                    conn.close()
            except Exception:
                pass
            conn = None


def _j(x):
    return json.dumps(x, default=str) if x is not None else None


def _insert_batch(conn, batch):
    stages, llms, dbs, traces = [], [], [], []
    for e in batch:
        k = e.get("kind")
        if k in ("stage", "legacy"):
            stages.append(e)
        elif k == "llm":
            llms.append(e)
        elif k == "db":
            dbs.append(e)
        elif k == "trace":
            traces.append(e)
    with conn.cursor() as cur:
        if stages:
            cur.executemany(
                """INSERT INTO obs_stage_events
                   (trace_id, run_id, span_id, parent_span_id, seq, kind, stage, card_id,
                    ts_start, ts_end, latency_ms, status, confidence, inputs, outputs,
                    n_llm_calls, tokens_prompt, tokens_completion, n_db_queries, rows_returned,
                    validation, degradation, warnings, errors, attrs)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s, to_timestamp(%s), to_timestamp(%s), %s,%s,
                           %s::jsonb,%s::jsonb,%s::jsonb, %s,%s,%s,%s,%s,
                           %s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb)""",
                [(e.get("trace_id"), e.get("run_id"), e.get("span_id"), e.get("parent_span_id"),
                  e.get("seq"), e.get("kind"), e.get("stage"), e.get("card_id"),
                  e.get("ts_start"), e.get("ts_end"), e.get("latency_ms"), e.get("status"),
                  _j(e.get("confidence")), _j(e.get("inputs")), _j(e.get("outputs")),
                  (e.get("ai") or {}).get("n_calls"), (e.get("ai") or {}).get("tokens_prompt"),
                  (e.get("ai") or {}).get("tokens_completion"),
                  (e.get("db") or {}).get("n_queries"), (e.get("db") or {}).get("rows_returned"),
                  _j(e.get("validation")), _j(e.get("degradation")),
                  _j(e.get("warnings")), _j(e.get("errors")), _j(e.get("attrs"))) for e in stages])
        if llms:
            cur.executemany(
                """INSERT INTO obs_llm_calls
                   (trace_id, run_id, span_id, parent_span_id, stage, card_id, ts, latency_ms, model,
                    prompt_system, prompt_user, response, tokens_prompt, tokens_completion,
                    finish_reason, attempt, error_kind, params, decision)
                   VALUES (%s,%s,%s,%s,%s,%s, to_timestamp(%s), %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)""",
                [(e.get("trace_id"), e.get("run_id"), e.get("span_id"), e.get("parent_span_id"),
                  e.get("stage"), e.get("card_id"), e.get("ts_start"), e.get("latency_ms"),
                  (e.get("ai") or {}).get("model"),
                  (e.get("ai") or {}).get("prompt_system"), (e.get("ai") or {}).get("prompt_user"),
                  (e.get("ai") or {}).get("response"),
                  (e.get("ai") or {}).get("tokens_prompt"), (e.get("ai") or {}).get("tokens_completion"),
                  (e.get("ai") or {}).get("finish_reason"), (e.get("ai") or {}).get("attempt"),
                  (e.get("ai") or {}).get("error_kind"),
                  _j((e.get("ai") or {}).get("params")), _j((e.get("ai") or {}).get("decision"))) for e in llms])
        if dbs:
            cur.executemany(
                """INSERT INTO obs_db_queries
                   (trace_id, run_id, span_id, parent_span_id, stage, card_id, ts, latency_ms,
                    db_name, sql_text, rows_returned, error)
                   VALUES (%s,%s,%s,%s,%s,%s, to_timestamp(%s), %s,%s,%s,%s,%s)""",
                [(e.get("trace_id"), e.get("run_id"), e.get("span_id"), e.get("parent_span_id"),
                  e.get("stage"), e.get("card_id"), e.get("ts_start"), e.get("latency_ms"),
                  (e.get("db") or {}).get("database"), (e.get("db") or {}).get("sql"),
                  (e.get("db") or {}).get("rows_returned"),
                  (e.get("errors") or [None])[0]) for e in dbs])
        if traces:
            cur.executemany(
                """INSERT INTO obs_traces
                   (trace_id, kind, prompt, asset_id, run_ids, started_at, ended_at, latency_ms, status,
                    n_stages, n_llm_calls, tokens_prompt, tokens_completion, n_db_queries, rows_returned,
                    degradation, warnings, errors, response_summary)
                   VALUES (%s,%s,%s,%s,%s::jsonb, to_timestamp(%s), to_timestamp(%s), %s,%s,
                           %s,%s,%s,%s,%s,%s, %s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb)
                   ON CONFLICT (trace_id) DO UPDATE SET
                     ended_at = EXCLUDED.ended_at, latency_ms = EXCLUDED.latency_ms,
                     status = EXCLUDED.status, n_stages = EXCLUDED.n_stages,
                     n_llm_calls = EXCLUDED.n_llm_calls, tokens_prompt = EXCLUDED.tokens_prompt,
                     tokens_completion = EXCLUDED.tokens_completion, n_db_queries = EXCLUDED.n_db_queries,
                     rows_returned = EXCLUDED.rows_returned, degradation = EXCLUDED.degradation,
                     warnings = EXCLUDED.warnings, errors = EXCLUDED.errors,
                     response_summary = EXCLUDED.response_summary, run_ids = EXCLUDED.run_ids""",
                [(e.get("trace_id"), (e.get("inputs") or {}).get("kind"),
                  (e.get("inputs") or {}).get("prompt"), (e.get("inputs") or {}).get("asset_id"),
                  _j((e.get("attrs") or {}).get("run_ids")), e.get("ts_start"), e.get("ts_end"),
                  e.get("latency_ms"), e.get("status"), (e.get("attrs") or {}).get("n_stages"),
                  (e.get("ai") or {}).get("n_calls"), (e.get("ai") or {}).get("tokens_prompt"),
                  (e.get("ai") or {}).get("tokens_completion"),
                  (e.get("db") or {}).get("n_queries"), (e.get("db") or {}).get("rows_returned"),
                  _j(e.get("degradation")), _j(e.get("warnings")), _j(e.get("errors")),
                  _j(e.get("outputs"))) for e in traces])
