"""replay/capture.py — the request-boundary concern: open a Recorder session for one request, snapshot the resolved
config + filtered environment, run the handler, then persist the whole bundle ONCE (buffered — the request hot path
never touches the trace dir). Sits INSIDE obs.middleware.run_traced so it inherits the obs trace_id; if obs is
absent/disabled it mints its own trace. Fail-open end to end: any capture failure leaves the request byte-identical
(the bundle is simply not written, with one stderr line saying so)."""
import os
import sys
import time
import uuid

from replay import store
from replay.recorder import Recorder, attach

ENV_PREFIXES = ("V48_", "LLM_", "EMS_", "PG", "CATALOG_", "PIPELINE_ASSET_ID", "STORYBOOK_URL")
ENV_REDACTED = "__redacted__"                                  # never persist credentials; replay leaves these as-is
_SENSITIVE = ("PASSWORD", "SECRET", "TOKEN", "APIKEY", "API_KEY")


def _cfg(key, default):
    try:
        from config.app_config import cfg
        return cfg(key, default)
    except Exception:
        return default


def env_snapshot():
    return {k: (ENV_REDACTED if any(s in k.upper() for s in _SENSITIVE) else v)
            for k, v in os.environ.items() if k.startswith(ENV_PREFIXES)}


def cfg_snapshot():
    """The app_config rows this process is actually running on (config/app_config._load is process-cached)."""
    try:
        from config.app_config import _load
        return {k: list(v) for k, v in _load().items()}
    except Exception:
        return {}


def captured(kind, request, fn, *, tape=None, replay_of=None, mode=None, path=None, trace_id=None):
    """Run fn() under a fresh capture session; persist outputs/traces/<trace_id>/ afterwards. Returns fn()'s result
    (and re-raises its exception AFTER persisting what was captured — a crashed request is still replayable).
    trace_id: engine-only override (the replay bundle dir is minted BEFORE the run so legacy writers can be
    redirected into it); normally the obs trace_id is the bundle identity."""
    if tape is None and not _truthy(_cfg("replay.capture", True)):
        return fn()
    rec = None
    try:
        t = _obs_trace(kind, request)
        trace_id = trace_id or (t or {}).get("trace_id") or f"t_{uuid.uuid4().hex}"
        rec = Recorder(trace_id, tape=tape)
        attach(t, rec)
        rec.artifact("_cfg_snapshot", cfg_snapshot())          # stashed on the recorder; written as its own file below
    except Exception:
        rec = None
    if rec is None:
        return fn()
    err = None
    try:
        resp = fn()
    except Exception as e:
        err = e
        resp = None
    try:
        rec.artifact("response", resp if isinstance(resp, (dict, list)) else {"_error": repr(err) if err else None})
        cfg_snap = rec.artifacts.pop("_cfg_snapshot", {})
        manifest = {
            "trace_id": rec.trace_id, "kind": kind, "path": path,
            "replay_of": replay_of, "mode": mode,
            "ts_start": rec.ts_start, "ts_end": time.time(),
            "started_at_iso": _iso(rec.ts_start),
            "prompt": (request or {}).get("prompt"),
            "run_ids": _run_ids(rec, resp),
            "git_sha": store.git_sha(),
            "status": "error" if err else "ok",
            "error": repr(err) if err else None,
            "counts": _counts(rec),
            "tape_stats": (tape.stats if tape is not None else None),
        }
        store.write_bundle(rec.trace_id, manifest=manifest, request={"path": path, "body": request},
                           cfg_snapshot=cfg_snap, env_snapshot=env_snapshot(),
                           events=rec.events, artifacts=rec.artifacts)
    except Exception as e:
        sys.stderr.write(f"[replay] capture persist failed (request unaffected): {type(e).__name__}: {e}\n")
    if err is not None:
        raise err
    return resp


def _obs_trace(kind, request):
    """The active obs trace dict (opened by obs.middleware), or a fresh one if obs isn't wrapping this request."""
    try:
        from obs import trace as _trace
        t = _trace.current()
        if t is None:
            t = _trace.new_trace(kind=kind, prompt=(request or {}).get("prompt"),
                                 asset_id=(request or {}).get("asset_id"))
        return t
    except Exception:
        return None


def _run_ids(rec, resp):
    ids = []
    try:
        for name in rec.artifacts:
            if name.startswith("pipeline_out_"):
                ids.append(name[len("pipeline_out_"):])
        rid = (resp or {}).get("run_id") if isinstance(resp, dict) else None
        if rid and rid not in ids:
            ids.append(rid)
    except Exception:
        pass
    return ids


def _counts(rec):
    c = {}
    for e in rec.events:
        c[e["kind"]] = c.get(e["kind"], 0) + 1
    return c


def _iso(ts):
    import datetime
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).isoformat()


def _truthy(v):
    return str(v).strip().lower() in ("1", "true", "yes", "t", "on")
