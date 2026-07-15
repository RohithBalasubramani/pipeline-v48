"""obs/sink_jsonl.py — the per-trace replayable file: outputs/logs/trace_<trace_id>.jsonl, one canonical event per
line (same envelope the pg sink stores). This is the always-works fallback when Postgres is unreachable and the
grep-able artifact a sweep/debug session reads straight off disk (sibling of pipeline_<run_id>.jsonl)."""
import json
import os
import threading

from obs.paths import logs_dir as _logs_dir     # the ONE writer-dir door (V48_OBS_DIR-aware) [audit 03]
_LOCK = threading.Lock()


def write(event):
    tid = event.get("trace_id") or "orphan"
    line = json.dumps(event, default=str)
    _d = _logs_dir()
    os.makedirs(_d, exist_ok=True)
    with _LOCK:                                                # threads share one trace file — keep lines whole
        with open(os.path.join(_d, f"trace_{tid}.jsonl"), "a") as f:
            f.write(line + "\n")
