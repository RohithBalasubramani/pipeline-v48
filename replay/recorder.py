"""replay/recorder.py — the per-request Recorder: a thread-safe in-memory event buffer + artifact map that rides the
ACTIVE OBS TRACE DICT (obs/trace.py) so every fan-out thread that inherited the trace context reaches the same
recorder with zero extra plumbing. Buffered — nothing touches disk until capture.finish() writes the bundle once."""
import threading
import time

_ATTACH_KEY = "replay_recorder"


class Recorder:
    def __init__(self, trace_id, *, tape=None):
        self.trace_id = trace_id
        self.tape = tape                                       # a replay.tape.Tape during replay, else None
        self._lock = threading.Lock()
        self._seq = 0
        self.events = []
        self.artifacts = {}
        self.ts_start = time.time()

    def event(self, kind, **fields):
        """Append one already-JSON-safe event. Returns the event dict (callers may not mutate after append)."""
        with self._lock:
            self._seq += 1
            e = {"seq": self._seq, "t_rel": round(time.time() - self.ts_start, 4), "kind": kind, **fields}
            self.events.append(e)
            return e

    def artifact(self, name, obj):
        with self._lock:
            self.artifacts[name] = obj


def attach(trace_dict, recorder):
    if trace_dict is not None:
        trace_dict[_ATTACH_KEY] = recorder


def active():
    """The Recorder attached to the current obs trace, or None. Fail-open: never raises."""
    try:
        from obs import trace as _trace
        t = _trace.current()
        return t.get(_ATTACH_KEY) if t else None
    except Exception:
        return None


def active_tape():
    r = active()
    return r.tape if r else None
