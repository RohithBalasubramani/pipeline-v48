"""validation/replay.py — the REPLAY RUNNER: re-run any saved case with IDENTICAL inputs, for debugging.

WHY: a sweep failure is only actionable if it can be reproduced on demand. Every case the runner executes leaves
its exact request body on disk (sessions/<sid>/cases/<id>.json); replay re-POSTs that SAME body to /api/run, parses
and judges it with the SAME case dict, and prints an original-vs-replay side-by-side — so 'still failing' (real
defect) separates from 'passes now' (environmental flake, e.g. the :5433 tunnel or vLLM contention) in one command.
The replay's raw response is saved next to the original (raw/<id>.replay.json), never overwriting it, so both full
payloads remain diffable. `replay_failed` sweeps every failed case of a session SEQUENTIALLY (concurrency 1 — a
replay must never manufacture its own contention failures). Never raises on bad/missing data: degrades to an honest
error record. All printing goes through ascii_safe (neuract strings can carry surrogates)."""
from __future__ import annotations

import json
import os
import time
import urllib.request

from validation import config
from validation.response import parse, ascii_safe
from validation.checks.expectations import judge


def _load_json(path: str):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def _post_run(body: dict, timeout: float | None = None) -> tuple[dict | None, str | None]:
    """POST body to /api/run (runner.py pattern). Returns (raw, transport_error)."""
    try:
        req = urllib.request.Request(config.BASE_URL + "/api/run", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout or config.RUN_TIMEOUT_S) as r:
            return json.loads(r.read().decode("utf-8", "replace")), None
    except Exception as e:
        return None, f"{type(e).__name__}: {ascii_safe(e)[:200]}"


def _summ(judgment: dict | None, parsed: dict | None) -> dict:
    j = judgment or {}
    p = parsed or {}
    return {
        "outcome": p.get("outcome"),
        "pass": bool(j.get("pass")),
        "degraded": bool(j.get("degraded")),
        "stage": j.get("stage"),
        "why": ascii_safe(j.get("why"))[:200] or None,
        "n_cards": p.get("n_cards"),
        "payload_errors": p.get("payload_errors"),
    }


def replay(case_id: str, session_id: str, quiet: bool = False) -> dict:
    """Re-run one saved case with its identical request body; print original-vs-replay; return the comparison dict."""
    sdir = config.session_dir(session_id)
    case_path = os.path.join(sdir, "cases", f"{case_id}.json")
    rec = _load_json(case_path)
    if not isinstance(rec, dict) or not isinstance(rec.get("case"), dict):
        out = {"case_id": case_id, "session": session_id, "error": f"no saved case record at {case_path}"}
        if not quiet:
            print(ascii_safe(f"[replay] {out['error']}"))
        return out

    case = rec["case"]
    body = rec.get("request") or {"prompt": case.get("prompt", "")}

    t0 = time.time()
    raw, transport_error = _post_run(body, config.timeout_for(case))
    elapsed_s = round(time.time() - t0, 2)

    replay_raw_path = None
    if raw is not None:
        os.makedirs(os.path.join(sdir, "raw"), exist_ok=True)
        replay_raw_path = os.path.join(sdir, "raw", f"{case_id}.replay.json")
        try:
            with open(replay_raw_path, "w") as f:
                json.dump(raw, f)
        except Exception:
            replay_raw_path = None
        parsed = parse(raw)
        judgment = judge(case, parsed)
    else:
        parsed = None
        judgment = {"pass": False, "degraded": False, "stage": "transport",
                    "why": transport_error or "no response"}

    orig = _summ(rec.get("judgment"), rec.get("parsed"))
    new = _summ(judgment, parsed)
    out = {
        "case_id": case_id,
        "session": session_id,
        "category": case.get("category"),
        "prompt": ascii_safe(case.get("prompt"))[:200],
        "original": dict(orig, raw_path=rec.get("raw_path")),
        "replay": dict(new, raw_path=replay_raw_path, elapsed_s=elapsed_s),
        "changed": orig != new,
        "still_failing": (not orig["pass"]) and (not new["pass"]),
    }

    if not quiet:
        print(ascii_safe(f"[replay] case {case_id} ({out['category']}): {out['prompt']}"))
        print(ascii_safe(f"  {'':10} {'original':<40} {'replay':<40}"))
        for k in ("outcome", "pass", "degraded", "stage", "why"):
            print(ascii_safe(f"  {k:10} {str(orig.get(k)):<40.40} {str(new.get(k)):<40.40}"))
        print(ascii_safe(f"  {'raw':10} {str(rec.get('raw_path')):<40.40} {str(replay_raw_path):<40.40}"))
        print(ascii_safe(f"  => {'UNCHANGED' if not out['changed'] else 'CHANGED'}"
                         f"{' | STILL FAILING' if out['still_failing'] else ''}"))
    return out


def replay_failed(session_id: str) -> list:
    """Sequentially re-run every failed case of a session. Returns sorted [{case_id, was, now, still_failing}]."""
    sdir = config.session_dir(session_id)
    cases_dir = os.path.join(sdir, "cases")
    try:
        names = sorted(n for n in os.listdir(cases_dir) if n.endswith(".json"))
    except Exception:
        print(ascii_safe(f"[replay] no cases dir at {cases_dir}"))
        return []

    failed_ids = []
    for n in names:
        rec = _load_json(os.path.join(cases_dir, n))
        if isinstance(rec, dict) and not (rec.get("judgment") or {}).get("pass"):
            failed_ids.append(n[:-len(".json")])
    failed_ids.sort()

    print(ascii_safe(f"[replay] session {session_id}: replaying {len(failed_ids)} failed case(s) sequentially"))
    results = []
    for cid in failed_ids:
        r = replay(cid, session_id)
        results.append({
            "case_id": cid,
            "was": r.get("original") or {"pass": False},
            "now": r.get("replay") or {"pass": False, "why": r.get("error")},
            "still_failing": bool(r.get("still_failing", True)),
        })
    still = sum(1 for r in results if r["still_failing"])
    print(ascii_safe(f"[replay] done: {len(results)} replayed, {still} still failing, "
                     f"{len(results) - still} recovered (flakes)"))
    return results
