"""replay/hooks.py — THE choke-point API. Each I/O seam calls ONE hook that (a) passes straight through when no
capture session is active (the common case — one dict lookup of overhead), (b) records the call full-fidelity into
the active Recorder, and (c) during replay serves the recorded outcome from the Tape instead of touching the live
world. Recording internals are fail-open — a broken recorder can never affect a request; the ONLY deliberate raises
are re-raising the pipeline's own recorded errors (so degrade-gate fingerprint branches reproduce) and TapeMiss
under --strict. During replay every call is ALSO recorded into the replay bundle (with a `served` marker), so the
compare engine aligns original vs replay events symmetrically."""
import time

from replay import coding
from replay.recorder import active as _active
from replay.tape import TapeMiss, content_key

_MISS = object()


def _tape_for(rec, group):
    t = rec.tape if rec else None
    return t if (t is not None and t.pinned(group)) else None


# ── LLM (llm/client.call_qwen outer boundary) ────────────────────────────────────────────────────────────────────────

def llm(raw, system, user, *, timeout=None, stage=None, schema=None, json_schema=None, on_error="empty"):
    rec = _active()
    if rec is None:
        return raw(system, user, timeout=timeout, stage=stage, schema=schema, json_schema=json_schema,
                   on_error=on_error)
    key = content_key("llm", stage, system, user, schema, json_schema)
    tape = _tape_for(rec, "llm")
    if tape is not None:
        served = _llm_from_tape(rec, tape, key, stage, system, user, on_error)
        if served is not _MISS:
            return served
    t0 = time.time()
    try:
        val = raw(system, user, timeout=timeout, stage=stage, schema=schema, json_schema=json_schema,
                  on_error=on_error)
    except Exception as e:                                     # LlmError under on_error='raise' — record + re-raise
        _safe_event(rec, "llm", key=key, stage=stage, system=system, user=user, on_error=on_error,
                    outcome="raise", error={"kind": getattr(e, "kind", type(e).__name__),
                                            "detail": getattr(e, "detail", str(e))},
                    ms=int((time.time() - t0) * 1000), served=(tape is not None and "miss_live") or None)
        raise
    _safe_event(rec, "llm", key=key, stage=stage, system=system, user=user, on_error=on_error,
                outcome="return", value=coding.encode(val), ms=int((time.time() - t0) * 1000),
                served=(tape is not None and "miss_live") or None)
    return val


def _llm_from_tape(rec, tape, key, stage, system, user, on_error):
    e, how = tape.lookup("llm", key)
    if e is None:
        e = tape.llm_fuzzy(stage)
        how = "fuzzy" if e is not None else "miss"
    if e is None:
        _safe_event(rec, "tape_miss", group="llm", stage=stage, key=key)
        if tape.strict:
            raise TapeMiss(f"llm stage={stage}: no recorded call matches (strict)")
        return _MISS
    if how == "fuzzy":
        _safe_event(rec, "tape_fuzzy", group="llm", stage=stage, key=key, orig_key=e.get("key"),
                    orig_seq=e.get("seq"))
    _safe_event(rec, "llm", key=key, stage=stage, system=system, user=user, on_error=on_error,
                outcome=e.get("outcome"), value=e.get("value"), error=e.get("error"),
                ms=0, served=how)
    if e.get("outcome") == "raise":
        from llm.client import LlmError                        # lazy: llm.client imports this module's caller
        err = e.get("error") or {}
        raise LlmError(err.get("kind", "replayed"), err.get("detail", ""))
    return coding.decode(e.get("value"))


# ── catalog/registry SQL via psql (data/db_client.q) ─────────────────────────────────────────────────────────────────

def db_q(raw, db, sql):
    rec = _active()
    if rec is None:
        return raw(db, sql)
    key = content_key("sql.q", db, sql)
    tape = _tape_for(rec, "sql")
    if tape is not None:
        e, how = tape.lookup("sql.q", key)
        if e is None:
            _safe_event(rec, "tape_miss", group="sql", door="sql.q", db=db, sql=sql, key=key)
            if tape.strict:
                raise TapeMiss(f"sql.q {db}: not on tape (strict): {sql[:120]}")
        else:
            _safe_event(rec, "sql.q", key=key, db=db, sql=sql, outcome=e.get("outcome"),
                        n_rows=e.get("n_rows"), rows=e.get("rows"), error=e.get("error"), ms=0, served=how)
            if e.get("outcome") == "raise":
                raise RuntimeError(e.get("error") or f"DB error ({db}): replayed failure")
            return coding.decode(e.get("rows"))
    t0 = time.time()
    try:
        rows = raw(db, sql)
    except RuntimeError as e:
        _safe_event(rec, "sql.q", key=key, db=db, sql=sql, outcome="raise", error=str(e),
                    ms=int((time.time() - t0) * 1000), served=(tape is not None and "miss_live") or None)
        raise
    _safe_event(rec, "sql.q", key=key, db=db, sql=sql, outcome="return", n_rows=len(rows),
                rows=coding.encode(rows), ms=int((time.time() - t0) * 1000),
                served=(tape is not None and "miss_live") or None)
    return rows


# ── psycopg2 read doors (data/neuract_live/_db.rows + ems_exec/data/neuract._run) ───────────────────────────────────

def db_rows(raw, door, sql, params=None):
    """door: 'sql.reg' | 'sql.nx'. Both raws honest-degrade to [] and never raise."""
    rec = _active()
    if rec is None:
        return raw(sql, params)
    key = content_key(door, sql, params)
    tape = _tape_for(rec, "sql")
    if tape is not None:
        e, how = tape.lookup(door, key)
        if e is None:
            _safe_event(rec, "tape_miss", group="sql", door=door, sql=sql, key=key)
            if tape.strict:
                raise TapeMiss(f"{door}: not on tape (strict): {sql[:120]}")
        else:
            _safe_event(rec, door, key=key, sql=sql, params=e.get("params"), n_rows=e.get("n_rows"),
                        rows=e.get("rows"), ms=0, served=how)
            return coding.decode(e.get("rows"))
    t0 = time.time()
    rows = raw(sql, params)
    _safe_event(rec, door, key=key, sql=sql, params=coding.encode(params), n_rows=len(rows or []),
                rows=coding.encode(rows), ms=int((time.time() - t0) * 1000),
                served=(tape is not None and "miss_live") or None)
    return rows


# ── validate's pandas probe (validate/data_load.load_asset_frame) ────────────────────────────────────────────────────

def frame_probe(raw, table, columns, limit):
    rec = _active()
    if rec is None:
        return raw(table, columns, limit=limit)
    key = content_key("frame_probe", table, list(columns or []), limit)
    tape = _tape_for(rec, "frame")
    if tape is not None:
        e, how = tape.lookup("frame_probe", key)
        if e is None:
            _safe_event(rec, "tape_miss", group="frame", table=table, key=key)
            if tape.strict:
                raise TapeMiss(f"frame_probe {table}: not on tape (strict)")
        else:
            _safe_event(rec, "frame_probe", key=key, table=table, columns=list(columns or []), limit=limit,
                        df=e.get("df"), cols=e.get("cols"), ordered=e.get("ordered"), ms=0, served=how)
            import pandas as pd
            df_enc = e.get("df") or {}
            df = pd.DataFrame(coding.decode(df_enc.get("records") or []), columns=df_enc.get("columns") or [])
            return df, list(e.get("cols") or []), bool(e.get("ordered"))
    t0 = time.time()
    df, cols, ordered = raw(table, columns, limit=limit)
    try:
        df_enc = {"columns": [str(c) for c in df.columns],
                  "records": coding.encode([tuple(r) for r in df.itertuples(index=False, name=None)])}
    except Exception:
        df_enc = {"columns": [], "records": []}
    _safe_event(rec, "frame_probe", key=key, table=table, columns=list(columns or []), limit=limit,
                df=df_enc, cols=list(cols or []), ordered=bool(ordered), n_rows=int(len(df)),
                ms=int((time.time() - t0) * 1000), served=(tape is not None and "miss_live") or None)
    return df, cols, ordered


# ── the UNSEEDED narrative-insight LLM (ems_exec/renderers/_insight._narrate_sync) ───────────────────────────────────

def insight(raw, story, fields, timeout):
    rec = _active()
    if rec is None:
        return raw(story, fields, timeout)
    key = content_key("insight", story, fields)
    tape = _tape_for(rec, "insight")
    if tape is not None:
        e, how = tape.lookup("insight", key)
        if e is None:
            _safe_event(rec, "tape_miss", group="insight", key=key)
            if tape.strict:
                raise TapeMiss("insight: not on tape (strict)")
        else:
            _safe_event(rec, "insight", key=key, story=story, fields=coding.encode(fields),
                        value=e.get("value"), ms=0, served=how)
            return coding.decode(e.get("value"))
    t0 = time.time()
    val = raw(story, fields, timeout)
    _safe_event(rec, "insight", key=key, story=story, fields=coding.encode(fields), value=coding.encode(val),
                ms=int((time.time() - t0) * 1000), served=(tape is not None and "miss_live") or None)
    return val


# ── record-only anchors ──────────────────────────────────────────────────────────────────────────────────────────────

def exec_card(raw, **kw):
    """Wraps host/exec_cards.fill_one_card: records the per-card OPERATIVE window + completed payload (the
    executor-stage diff anchor). Never injects — the executor re-runs on tape-fed SQL."""
    rec = _active()
    if rec is None:
        return raw(**kw)
    t0 = time.time()
    out = raw(**kw)
    _safe_event(rec, "exec_card", cid=kw.get("cid"), render_card_id=kw.get("render_card_id"),
                handling_class=kw.get("handling_class"), asset_table=kw.get("asset_table"),
                window=coding.encode(kw.get("window")), requested_window=coding.encode(kw.get("requested_window")),
                member_scope=kw.get("member_scope"), payload=coding.encode(out),
                ms=int((time.time() - t0) * 1000))
    return out


def pipeline_out(out):
    """Record run_pipeline's full out dict as a per-lane artifact (keyed by the lane's run_id)."""
    rec = _active()
    if rec is None or not isinstance(out, dict):
        return
    try:
        rec.artifact(f"pipeline_out_{out.get('run_id') or 'default'}", coding.encode(out))
    except Exception:
        pass


def _safe_event(rec, kind, **fields):
    try:
        rec.event(kind, **{k: v for k, v in fields.items() if v is not None})
    except Exception:
        pass
