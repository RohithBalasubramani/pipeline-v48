"""validation/failures.py — the FAILURE COLLECTOR: turn a session's per-case records into one deterministic,
debuggable failure inventory. WHY: after a big sweep the question is never "how many failed" (the manifest says that)
but "WHICH stage owns each failure and where are its artifacts" — so every failure record carries stage attribution
(judgment.stage), the honest outcome/why, and the correlation handles a human or replay tool needs next: the raw
response path and the pipeline's own per-run log (globbed by run_id under config.PIPELINE_LOG_DIR — may be absent,
recorded as None, never guessed). DEGRADED cases (pass=true, degraded=true — honest infra/fill flakes) are collected
separately and grouped by why, so a rash of environmental flakes is visible without polluting the failure list.
Output is fully sorted (case_id order everywhere, sorted group keys) and mirrored to sessions/<sid>/failures.json.
Never raises on bad/missing/corrupt case files — a session with no cases dir just yields zero failures."""
from __future__ import annotations

import glob
import json
import os

from validation import config
from validation.response import ascii_safe

_MISSING = "(none)"   # deterministic bucket for absent grouping keys


def _load_cases(sdir: str) -> list[dict]:
    """Read every cases/*.json record, skipping unreadable/corrupt files (they cannot be judged, only ignored)."""
    out = []
    for path in sorted(glob.glob(os.path.join(sdir, "cases", "*.json"))):
        try:
            with open(path) as f:
                rec = json.load(f)
            if isinstance(rec, dict):
                out.append(rec)
        except Exception:
            continue
    return out


def _pipeline_log(run_id) -> str | None:
    """Best-effort correlate a case to the pipeline's own per-run artifact (glob *<run_id>*; absent -> None)."""
    if not run_id:
        return None
    try:
        hits = sorted(glob.glob(os.path.join(config.PIPELINE_LOG_DIR, f"*{run_id}*")))
        return hits[0] if hits else None
    except Exception:
        return None


def _failure_record(rec: dict) -> dict:
    case = rec.get("case") or {}
    parsed = rec.get("parsed") or {}
    judgment = rec.get("judgment") or {}
    run_id = parsed.get("run_id")
    return {
        "case_id": ascii_safe(case.get("id")) or _MISSING,
        "category": ascii_safe(case.get("category")) or _MISSING,
        "prompt": ascii_safe(case.get("prompt")),
        "stage": ascii_safe(judgment.get("stage")) or "unknown",
        "why": ascii_safe(judgment.get("why")),
        "asset_how": parsed.get("asset_how"),
        "outcome": parsed.get("outcome"),
        "payload_errors": int(parsed.get("payload_errors") or 0),
        "transport_error": ascii_safe(rec.get("transport_error")) if rec.get("transport_error") else None,
        "run_id": run_id,
        "pipeline_log": _pipeline_log(run_id),
        "raw_path": rec.get("raw_path"),
        # grouping-only context (kept on the record so groups are self-explaining)
        "asset_class": ascii_safe(parsed.get("asset_class")) or None,
        "page_key": ascii_safe(parsed.get("page_key")) or None,
    }


def _group(records: list[dict], key: str) -> dict:
    """{key_value: [case_ids]} with sorted keys and sorted, stable id lists; None keys bucket under _MISSING."""
    groups: dict[str, list[str]] = {}
    for r in records:
        k = r.get(key) or _MISSING
        groups.setdefault(str(k), []).append(r["case_id"])
    return {k: sorted(groups[k]) for k in sorted(groups)}


def collect(session_id: str) -> dict:
    """Collect failures + degraded cases for one session -> the summary dict (also written to failures.json)."""
    sdir = os.path.join(config.OUT_DIR, "sessions", str(session_id))
    failures: list[dict] = []
    degraded: list[dict] = []
    for rec in _load_cases(sdir):
        judgment = rec.get("judgment") or {}
        if not judgment.get("pass"):
            failures.append(_failure_record(rec))
        elif judgment.get("degraded"):
            degraded.append(_failure_record(rec))
    failures.sort(key=lambda r: r["case_id"])
    degraded.sort(key=lambda r: r["case_id"])

    out = {
        "session": str(session_id),
        "n_failures": len(failures),
        "n_degraded": len(degraded),
        "failures": failures,
        "by_stage": _group(failures, "stage"),
        "by_category": _group(failures, "category"),
        "by_class": _group(failures, "asset_class"),
        "by_page": _group(failures, "page_key"),
        "degraded": degraded,
        "degraded_by_why": _group(degraded, "why"),
    }
    try:
        os.makedirs(sdir, exist_ok=True)
        with open(os.path.join(sdir, "failures.json"), "w") as f:
            json.dump(out, f, indent=1, sort_keys=True)
    except Exception:
        pass   # report the collection even if the mirror write fails (read-only disk etc.)
    return out
