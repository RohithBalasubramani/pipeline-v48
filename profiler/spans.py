"""profiler/spans.py — in-process span collector for live profiling.

A profiling session is opened with `session()`; instrumented code records spans via
`record(stage, ms, **meta)` or the `span(stage, **meta)` context manager. The active
session is held in a module-level slot guarded by a lock (NOT a contextvar: the
pipeline fans out through ThreadPoolExecutor workers that must all report into the
same session, and worker threads don't inherit contextvars set after pool creation).
Only one live profiling session runs per process — the harness is the only writer.

Cross-cutting stages (database / ai) additionally tag which pipeline stage was on
the "stage stack" when the call happened, so DB/AI time can be attributed. The
stack IS a contextvar copied into threads at submit time where possible, but falls
back to "?" when attribution is unknown — attribution is best-effort telemetry,
the ms numbers themselves are exact.
"""
import contextlib
import contextvars
import threading
import time

_lock = threading.Lock()
_active = None  # the one live ProfSession, or None

# which top-level pipeline stage is currently executing (per-thread/task)
current_stage = contextvars.ContextVar("prof_current_stage", default="?")


class ProfSession:
    def __init__(self, run_id, prompt=None):
        self.run_id = run_id
        self.prompt = prompt
        self.samples = []
        self._lk = threading.Lock()

    def record(self, stage, ms, **meta):
        s = {"stage": stage, "ms": float(ms), "run_id": self.run_id,
             "prompt": self.prompt, "source": "live", "meta": meta}
        with self._lk:
            self.samples.append(s)


@contextlib.contextmanager
def session(run_id, prompt=None):
    """Open the process-wide profiling session; yields the ProfSession."""
    global _active
    s = ProfSession(run_id, prompt)
    with _lock:
        _active = s
    try:
        yield s
    finally:
        with _lock:
            _active = None


def record(stage, ms, **meta):
    with _lock:
        s = _active
    if s is not None:
        s.record(stage, ms, **meta)


@contextlib.contextmanager
def span(stage, set_current=False, **meta):
    """Time a block. set_current=True marks this stage as the attribution target
    for nested database/ai spans (top-level pipeline stages only)."""
    token = current_stage.set(stage) if set_current else None
    t0 = time.perf_counter()
    try:
        yield
    finally:
        ms = (time.perf_counter() - t0) * 1000.0
        if token is not None:
            current_stage.reset(token)
        record(stage, ms, **meta)
