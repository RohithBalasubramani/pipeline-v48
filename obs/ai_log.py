"""obs/ai_log.py — monkeypatch urllib.urlopen -> log every LLM-endpoint call to outputs/logs/ai_<run_id>.jsonl.
Import FIRST. The match token derives from llm/config.LLM_URL's netloc (fallback ':8200') so relocating vLLM via
env doesn't silently blind the run-audit/replay tooling that mines these logs.

Run-id attribution is contextvar-backed [OBS-1]: two concurrent /api/run requests each bind their own run id, so
the ai_/sql_/failures_ jsonl legs no longer cross-label under concurrency. Resolution order in run_id():
this context's binding → the active obs trace's last-bound run_id → the legacy process-global (plain threads /
external setattr callers). Legacy readers doing getattr(ai_log, "_RUN_ID", ...) resolve through the same accessor
via the module __getattr__ below — no call-site churn."""
import contextvars
import io
import json
import os
import urllib.request
from datetime import datetime
from urllib.parse import urlsplit

_RUN_ID_VAR = contextvars.ContextVar("obs_ai_log_run_id", default=None)   # per-request/context binding [OBS-1]
_RUN_ID_LEGACY = "default"                                                # process-global fallback (plain threads)
_OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "logs")
_orig = urllib.request.urlopen

try:
    from llm import config as _llm_config
    _split = urlsplit(_llm_config.LLM_URL)
    # Match on ':port' (byte-identical to the old ':8200' check in a default env — host-agnostic), else the netloc.
    _MATCH = f":{_split.port}" if _split.port else (_split.netloc or ":8200")
except Exception:  # pragma: no cover — observer must never break the import chain
    _MATCH = ":8200"


def set_run_id(rid):
    """Bind the run id for THIS context (and refresh the process-global fallback for plain threads)."""
    global _RUN_ID_LEGACY
    _RUN_ID_LEGACY = rid or "default"
    _RUN_ID_VAR.set(rid or "default")


def set_context_run_id(rid):
    """Bind a run id to THIS context ONLY — no global-fallback mutation. For process-internal service threads
    (obs/sink_pg's writer pins 'obs_sink') so their self-telemetry never labels a live run's jsonl [OBS-5]."""
    _RUN_ID_VAR.set(rid or "default")


def run_id():
    """The current run id: this context's binding, else the active trace's last-bound run_id, else the legacy
    global. Concurrency-safe attribution for every jsonl telemetry leg [OBS-1]."""
    rid = _RUN_ID_VAR.get()
    if rid:
        return rid
    try:
        from obs import trace as _trace
        rid = _trace.current_run_id()
    except Exception:                                          # telemetry only — never break a caller
        rid = None
    return rid or _RUN_ID_LEGACY or "default"


def __getattr__(name):
    # Legacy readers (obs/sql_trace, llm/client, config/reason_templates, layer1a/story_builder, tests) do
    # getattr(ai_log, "_RUN_ID", ...) — route them through run_id() with zero call-site edits [OBS-1].
    # A direct setattr (tests' monkeypatch) still wins: a real module attribute shadows this hook.
    if name == "_RUN_ID":
        return run_id()
    raise AttributeError(name)


class _Tee:
    def __init__(self, data):
        self._b = io.BytesIO(data)

    def read(self, *a):
        return self._b.read(*a)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _logged(req, *a, **kw):
    resp = _orig(req, *a, **kw)
    try:
        url = getattr(req, "full_url", "")
        if _MATCH not in url:
            return resp
        data = resp.read()
        os.makedirs(_OUT, exist_ok=True)
        rid = run_id()                                         # resolve ONCE — record and filename must agree
        rec = {"ts": datetime.now().isoformat(), "run_id": rid, "url": url}
        try:
            rec["request"] = json.loads(req.data) if getattr(req, "data", None) else None
        except Exception:
            rec["request"] = None
        try:
            rec["response"] = json.loads(data)
        except Exception:
            rec["response"] = None
        with open(os.path.join(_OUT, f"ai_{rid}.jsonl"), "a") as f:
            f.write(json.dumps(rec) + "\n")
        return _Tee(data)
    except Exception:
        return resp


urllib.request.urlopen = _logged
