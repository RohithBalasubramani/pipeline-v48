"""obs/db_tap.py — the ONE DB-query recorder. data/db_client.py (the single query convention) reports each q()
here: database, SQL, rows returned, latency, error. Attributed to the active stage span (counts/rows ride the
stage event); the full record ships as a kind='db' event → obs_db_queries. Reentrancy-guarded: the first cfg()
lookup inside the obs path itself runs a q() — the guard breaks that loop. Fail-open, no-op outside a trace."""
import contextvars
import time
import uuid

_IN_TAP = contextvars.ContextVar("obs_in_db_tap", default=False)


def _cfg(key, default):
    try:
        from config.app_config import cfg
        return cfg(key, default)
    except Exception:
        return default


def record(*, db=None, sql=None, rows_returned=None, latency_s=None, error=None):
    """Report ONE DB query (success or failure). Never raises; never re-enters itself."""
    if _IN_TAP.get():
        return
    token = _IN_TAP.set(True)
    try:
        from obs import trace as _trace, span as _span, event, bus
        t = _trace.current()
        if t is None:
            return
        now = time.time()
        rec = {
            "span_id": uuid.uuid4().hex[:12],
            "ts_start": now - (latency_s or 0.0),
            "ts_end": now,
            "db": db,
            "sql": str(sql or "")[: int(_cfg("obs.max_field_bytes", 16384) or 16384)],
            "rows_returned": rows_returned,
            "error": (str(error)[:500] if error else None),
        }
        sp = _span.attribute_db(rec)
        bus.emit(event.db_event(t, sp, rec))
    except Exception:
        pass
    finally:
        _IN_TAP.reset(token)
