"""replay/tape.py — the recorded-events lookup used during replay. Events are keyed by CONTENT (sha256 of the
inputs that determine the result); identical inputs recurring within a run are served FIFO, a drained queue repeats
its last value (idempotent reads), and an unmatched LLM call falls back to the next unconsumed event of the SAME
stage (fuzzy — the prompt drifted; the drift itself is the finding). Every miss/fuzzy is a first-class record the
compare surfaces — nothing is served silently."""
import hashlib
import json
import threading


class TapeMiss(Exception):
    """Raised on a tape miss in --strict replay (lenient replay falls back live and records the miss)."""


def content_key(*parts):
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:24]


class Tape:
    """pins = the event kinds to inject ({'llm','sql','frame','insight'}); strict = raise TapeMiss instead of
    falling back live. Events not in pins are ignored (recorded live behavior)."""

    def __init__(self, events, *, pins=("llm", "sql", "frame", "insight"), strict=False):
        self.pins = set(pins or ())
        self.strict = strict
        self._lock = threading.Lock()
        self._queues = {}                                      # (kind, key) -> [event, ...] FIFO
        self._last = {}                                        # (kind, key) -> last event (drained-queue repeat)
        self._by_stage = {}                                    # llm fuzzy fallback: stage -> [event, ...]
        self.stats = {"hits": 0, "repeats": 0, "fuzzy": 0, "misses": 0}
        for e in events or []:
            k = e.get("kind")
            if k in ("llm", "sql.q", "sql.reg", "sql.regd", "sql.nx", "frame_probe", "insight") and e.get("key"):
                self._queues.setdefault((k, e["key"]), []).append(e)
                if k == "llm":
                    self._by_stage.setdefault(e.get("stage") or "-", []).append(e)

    def pinned(self, group):
        return group in self.pins

    def lookup(self, kind, key):
        """(event, how) — how in hit|repeat; (None, 'miss') when nothing matches. FIFO per content key."""
        with self._lock:
            q = self._queues.get((kind, key))
            if q:
                e = q.pop(0)
                if not q:
                    self._last[(kind, key)] = e
                self._mark_consumed(kind, e)
                self.stats["hits"] += 1
                return e, "hit"
            e = self._last.get((kind, key))
            if e is not None:
                self.stats["repeats"] += 1
                return e, "repeat"
            self.stats["misses"] += 1
            return None, "miss"

    def llm_fuzzy(self, stage):
        """The next UNCONSUMED llm event of this stage (prompt drifted; serve in original order)."""
        with self._lock:
            q = self._by_stage.get(stage or "-") or []
            while q:
                e = q.pop(0)
                if not e.get("_consumed"):
                    e["_consumed"] = True
                    exact = self._queues.get(("llm", e["key"]))
                    if exact and e in exact:
                        exact.remove(e)
                    self.stats["fuzzy"] += 1
                    return e
            return None

    def _mark_consumed(self, kind, e):
        if kind == "llm":
            e["_consumed"] = True

    def unconsumed_llm(self):
        """LLM events never served — original calls the replay didn't make (a divergence signal for compare)."""
        out = []
        for stage, q in self._by_stage.items():
            out.extend(e for e in q if not e.get("_consumed"))
        return out
