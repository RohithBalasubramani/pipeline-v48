"""obs/sql_trace.py — append every neuract DATA read to outputs/logs/sql_<run_id>.jsonl (the SQL leg of a run's
observability triple: pipeline_<rid>.jsonl stages + ai_<rid>.jsonl LLM calls + sql_<rid>.jsonl data reads). Keyed by
the SAME process-wide run id obs.ai_log tracks, so tools/payload_diff can join all three per execution. Records the
statement + params + rowcount + elapsed — never the row data (payloads already ride on the response). Telemetry only:
never raises, never alters the read. Disable with V48_SQL_TRACE=0."""
import json
import os
import time

import obs.ai_log as _ai_log

_OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "logs")
_ENABLED = os.environ.get("V48_SQL_TRACE", "1") != "0"


def record(db, sql, params=None, rows=None, ms=None, err=None):
    # TRACE LEG [obs/db_tap]: mirror every DB read into the trace-linked store (obs_db_queries + per-stage span
    # rollups) — data/db_client.q AND ems_exec/data/neuract._run both funnel through here, so this ONE forward
    # covers the whole pipeline's query surface. Fail-open, no-op outside a trace.
    try:
        from obs import db_tap
        db_tap.record(db=db, sql=sql, rows_returned=rows, latency_s=(ms or 0) / 1000.0, error=err)
    except Exception:
        pass
    if not _ENABLED:
        return
    try:
        rid = getattr(_ai_log, "_RUN_ID", "default") or "default"
        rec = {"ts": time.time(), "db": db, "sql": sql, "rows": rows, "ms": ms}
        if params:
            rec["params"] = [str(p) for p in (params if isinstance(params, (list, tuple)) else [params])]
        if err:
            rec["err"] = str(err)[:200]
        os.makedirs(_OUT, exist_ok=True)
        with open(os.path.join(_OUT, f"sql_{rid}.jsonl"), "a") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception:
        pass
