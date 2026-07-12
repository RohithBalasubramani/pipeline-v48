"""validation/runner.py — the PARALLEL PROMPT EXECUTOR: run corpus cases against /api/run with per-lane concurrency,
auto-throttle, full artifact capture, and per-case judgment. Every case leaves a replayable record on disk:

  sessions/<sid>/cases/<case_id>.json   {case, request, parsed, judgment, raw_path, elapsed_s, attempt}
  sessions/<sid>/raw/<case_id>.json     the FULL /api/run response (payloads included) — the SSR/replay input
  sessions/<sid>/manifest.json          run manifest (config, clamps, throttle events, counts)

THROTTLE: vLLM contention manufactures fake 'llm timeout' failures above ~3 concurrent /api/run. The lane starts at
min(requested, RUN_CONCURRENCY_MAX); if the rolling error rate of the last THROTTLE_WINDOW calls exceeds
THROTTLE_ERROR_RATE the lane halves (floor 1) and the event is recorded in the manifest — the framework must expose
real failures, never manufacture contention ones. Nothing fails silently: every transport error/timeout becomes a
case record with stage='transport'."""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from sweep import config
from sweep.response import parse, ascii_safe
from sweep.checks.expectations import judge
from sweep.stagelogs import capture as stage_capture


def _post(path: str, body: dict, timeout: float) -> dict:
    req = urllib.request.Request(config.BASE_URL + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


class _Throttle:
    """Sliding-window error-rate governor over the /api/run lane."""

    def __init__(self, start: int):
        self.limit = max(1, start)
        self.sem = threading.Semaphore(self.limit)
        self._window: list[bool] = []
        self._lock = threading.Lock()
        self.events: list[dict] = []

    def record(self, ok: bool):
        with self._lock:
            self._window.append(ok)
            if len(self._window) > config.THROTTLE_WINDOW:
                self._window.pop(0)
            if (len(self._window) >= config.THROTTLE_WINDOW and self.limit > 1
                    and self._window.count(False) / len(self._window) > config.THROTTLE_ERROR_RATE):
                for _ in range(self.limit - max(1, self.limit // 2)):
                    self.sem.acquire()                       # shrink by holding permits (never released)
                self.events.append({"t": time.time(), "from": self.limit, "to": max(1, self.limit // 2)})
                self.limit = max(1, self.limit // 2)
                self._window.clear()


def _resume_leg(case: dict, raw: dict | None, sdir: str, throttle: "_Throttle") -> dict | None:
    """UNEXPECTED-PICKER diagnostic: the FE's real workflow after a picker is 'pick a candidate, re-POST pinned' —
    so when a cards-expecting case lands on the picker, re-POST the same prompt pinned to the first has_data candidate
    and record whether the pipeline COMPLETES after a pick (resolvable ambiguity) or fails outright. The original
    judgment STANDS — this leg is diagnostic, never a pass-rescue. Bounded: fires only on unexpected-picker failures.
    Runs inside the throttle lane (it is a full /api/run). Its stage logs land under stagelogs/<case>/resume/ —
    the re-POST reuses the same deterministic run_id, which is exactly why the first leg was captured before this."""
    cands = ((raw or {}).get("asset") or {}).get("candidates") or []
    pick = next((c for c in cands if isinstance(c, dict) and c.get("has_data")),
                cands[0] if cands and isinstance(cands[0], dict) else None)
    if not pick or pick.get("mfm_id") is None:
        return None
    out = {"asset_id": pick["mfm_id"], "asset_name": ascii_safe(pick.get("name"))[:80]}
    t0 = time.time()
    throttle.sem.acquire()
    try:
        raw2 = _post("/api/run", {"prompt": case["prompt"], "asset_id": pick["mfm_id"]}, config.timeout_for(case))
    except Exception as e:
        out["transport_error"] = f"{type(e).__name__}: {ascii_safe(e)[:200]}"
        out["elapsed_s"] = round(time.time() - t0, 2)
        return out
    finally:
        throttle.sem.release()
    out["elapsed_s"] = round(time.time() - t0, 2)
    try:
        raw_path = os.path.join(sdir, "raw", f"{case['id']}.resume.json")
        with open(raw_path, "w") as f:
            json.dump(raw2, f)
        out["raw_path"] = raw_path
    except OSError:
        pass
    out["parsed"] = parse(raw2)
    out["judgment"] = judge(case, out["parsed"])
    try:
        out["stagelogs"] = stage_capture(sdir, case["id"], out["parsed"].get("run_id"),
                                         not out["judgment"].get("pass"), subdir="resume")
    except Exception:
        out["stagelogs"] = None
    return out


def run_cases(cases: list[dict], session_id: str, concurrency: int | None = None,
              progress=None) -> dict:
    """Execute `cases` and return the manifest. `progress(done, total, case_result)` is an optional callback."""
    sdir = config.session_dir(session_id)
    os.makedirs(os.path.join(sdir, "raw"), exist_ok=True)
    requested = concurrency or config.RUN_CONCURRENCY_DEFAULT
    lane = min(requested, config.RUN_CONCURRENCY_MAX)
    throttle = _Throttle(lane)
    results: list[dict] = []
    lock = threading.Lock()
    # DEAD-SERVER CIRCUIT BREAKER [campaign2_volume post-mortem]: the target server was killed mid-run and the runner
    # burned through 745 remaining cases in minutes — each an instant Connection-refused 'failure' (garbage session,
    # wasted corpus). N CONSECUTIVE transport failures = dead-server shape (per-case flakiness resets the count) =>
    # abort the remainder: skipped cases record stage='aborted' and the manifest carries aborted=true so a report can
    # never be mistaken for a real sweep.
    breaker = {"consec": 0, "tripped": False}
    breaker_n = int(os.environ.get("V48_VALIDATE_BREAKER_N", "10"))

    def one(case: dict) -> dict:
        body = {"prompt": case["prompt"]}
        if case.get("pin") is not None:
            body["asset_id"] = case["pin"]              # pinned single-asset lane (the FE picker re-POST semantics)
        if case.get("pins"):
            body["asset_ids"] = list(case["pins"])      # pinned multi-asset compare lane
        t0 = time.time()
        rec = {"case": case, "request": body, "attempt": 1}
        if breaker["tripped"]:
            rec["parsed"] = None
            rec["judgment"] = {"pass": False, "stage": "aborted", "why": "run aborted: dead-server circuit breaker"}
            with open(os.path.join(sdir, "cases", f"{case['id']}.json"), "w") as f:
                json.dump(rec, f, sort_keys=True)
            return rec
        throttle.sem.acquire()
        try:
            raw = _post("/api/run", body, config.timeout_for(case))
            ok_transport = True
        except Exception as e:
            raw, ok_transport = None, False
            rec["transport_error"] = f"{type(e).__name__}: {ascii_safe(e)[:200]}"
        finally:
            throttle.sem.release()
        rec["elapsed_s"] = round(time.time() - t0, 2)
        throttle.record(ok_transport and bool((raw or {}).get("ok", True)))
        with lock:
            breaker["consec"] = 0 if ok_transport else breaker["consec"] + 1
            if breaker["consec"] >= breaker_n:
                breaker["tripped"] = True
        if raw is not None:
            raw_path = os.path.join(sdir, "raw", f"{case['id']}.json")
            with open(raw_path, "w") as f:
                json.dump(raw, f)
            rec["raw_path"] = raw_path
            rec["parsed"] = parse(raw)
            rec["judgment"] = judge(case, rec["parsed"])
        else:
            rec["parsed"] = None
            rec["judgment"] = {"pass": False, "stage": "transport", "why": rec.get("transport_error", "no response")}
        # snapshot this run's per-stage logs NOW — run_id is deterministic from the prompt, so any later fire of the
        # same prompt (replay / determinism repeat / the resume leg below) OVERWRITES outputs/logs/*<rid>*.
        failed = not rec["judgment"].get("pass")
        try:
            rec["stagelogs"] = stage_capture(sdir, case["id"], (rec.get("parsed") or {}).get("run_id"), failed)
        except Exception:
            rec["stagelogs"] = None
        if failed and (rec.get("parsed") or {}).get("outcome") == "picker":
            rec["resume"] = _resume_leg(case, raw, sdir, throttle)
        with open(os.path.join(sdir, "cases", f"{case['id']}.json"), "w") as f:
            json.dump(rec, f, sort_keys=True)
        return rec

    with ThreadPoolExecutor(max_workers=max(2, requested)) as ex:
        futs = {ex.submit(one, c): c for c in cases}
        for fut in as_completed(futs):
            try:
                rec = fut.result()
            except Exception as e:                            # belt-and-braces: a runner bug is itself a record
                c = futs[fut]
                rec = {"case": c, "judgment": {"pass": False, "stage": "runner", "why": ascii_safe(e)[:200]},
                       "parsed": None, "elapsed_s": None}
                with open(os.path.join(sdir, "cases", f"{c['id']}.json"), "w") as f:
                    json.dump(rec, f, sort_keys=True)
            with lock:
                results.append(rec)
                if progress:
                    progress(len(results), len(cases), rec)

    manifest = {
        "session": session_id, "total": len(cases),
        "requested_concurrency": requested, "run_lane_start": lane, "run_lane_end": throttle.limit,
        "throttle_events": throttle.events,
        "aborted": breaker["tripped"],
        "aborted_cases": sum(1 for r in results if (r.get("judgment") or {}).get("stage") == "aborted"),
        "passed": sum(1 for r in results if (r.get("judgment") or {}).get("pass")),
        "failed": sum(1 for r in results if not (r.get("judgment") or {}).get("pass")),
        "resume_legs": sum(1 for r in results if r.get("resume")),
        "resume_completed": sum(1 for r in results if ((r.get("resume") or {}).get("judgment") or {}).get("pass")),
        "config": {"base": config.BASE_URL, "run_timeout_s": config.RUN_TIMEOUT_S},
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    with open(os.path.join(sdir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1, sort_keys=True)
    return manifest
