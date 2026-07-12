"""admin/replay.py — replay launcher: re-run a past prompt through the LIVE host API, tracked in-memory.

Replay in V48 = re-POST the same prompt (+asset_id/asset_ids to pin a picker choice) to host /api/run — the
deterministic run id (run/run_id.make_run_id) means the new execution APPENDS to the same trace files, so the
predicted run_id links to the trace viewer IMMEDIATELY, while the run is still going. Launches run in daemon
threads (a page run is LLM-bound, up to ~5 min); keep concurrency low — vLLM contention manufactures fake
timeouts (memory: l2-fanout-concurrency-cap). Registry is process-lifetime, capped at the last 100 launches."""
import itertools
import json
import threading
import time
import urllib.request

from admin.config import HOST_API, iso

_LOCK = threading.Lock()
_REGISTRY = {}                      # replay_id -> row (insertion-ordered)
_SEQ = itertools.count(1)
_CAP = 100
TIMEOUT_S = 540
MAX_ACTIVE = 2                      # vLLM contention guard


def _predict_run_id(prompt):
    try:
        from run.run_id import make_run_id
        return make_run_id(prompt)
    except Exception:
        return None


def active_count():
    with _LOCK:
        return sum(1 for r in _REGISTRY.values() if r["status"] in ("queued", "running"))


def launch(prompt, asset_id=None, asset_ids=None, date_window=None):
    """Fire one replay. Returns the registry row (status=queued) or an error dict when at capacity."""
    prompt = (prompt or "").strip()
    if not prompt:
        return {"launched": False, "error": "prompt required"}
    if active_count() >= MAX_ACTIVE:
        return {"launched": False, "error": f"replay concurrency cap ({MAX_ACTIVE}) reached — wait for active runs"}
    rid = f"rp_{next(_SEQ)}_{int(time.time())}"
    row = {"replay_id": rid, "run_id": _predict_run_id(prompt), "prompt": prompt,
           "asset_id": asset_id, "asset_ids": asset_ids, "status": "queued",
           "started": iso(time.time()), "finished": None, "elapsed_ms": None, "ok": None, "error": None,
           "response_run_id": None, "cards": None, "asset_pending": None}
    with _LOCK:
        _REGISTRY[rid] = row
        while len(_REGISTRY) > _CAP:
            _REGISTRY.pop(next(iter(_REGISTRY)))
    threading.Thread(target=_worker, args=(rid, prompt, asset_id, asset_ids, date_window), daemon=True).start()
    # NOTE: row carries its own `ok` (the PIPELINE result, null until done) — the launch flag must not collide with it
    return {**row, "launched": True}


def _worker(rid, prompt, asset_id, asset_ids, date_window):
    with _LOCK:
        row = _REGISTRY.get(rid)
        if not row:
            return
        row["status"] = "running"
    t0 = time.time()
    try:
        body = {"prompt": prompt, "asset_id": asset_id, "asset_ids": asset_ids, "date_window": date_window}
        req = urllib.request.Request(f"{HOST_API}/api/run", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            d = json.load(resp)
        with _LOCK:
            row.update(status="done", ok=d.get("ok"), response_run_id=d.get("run_id"),
                       cards=len(d.get("cards") or []), asset_pending=d.get("asset_pending"),
                       finished=iso(time.time()), elapsed_ms=int((time.time() - t0) * 1000))
            if d.get("run_id"):
                row["run_id"] = d["run_id"]
    except Exception as e:
        with _LOCK:
            row.update(status="error", error=str(e)[:300],
                       finished=iso(time.time()), elapsed_ms=int((time.time() - t0) * 1000))


def listing():
    with _LOCK:
        return list(reversed(list(_REGISTRY.values())))
