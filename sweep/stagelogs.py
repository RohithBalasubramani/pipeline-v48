"""validation/stagelogs.py — PER-CASE STAGE-LOG CAPTURE + LOG-DERIVED FAILURE REASONS. WHY: the pipeline already
writes superb per-stage artifacts (outputs/logs/pipeline_<rid>.jsonl stage-by-stage, failures_<rid>.jsonl,
ai_<rid>.jsonl every LLM call, outputs/notes/<rid>.json reflect notes) — but run_id is DETERMINISTIC from the prompt
(sha1 prefix), so the NEXT fire of the same prompt (a replay, a determinism repeat, a resume re-POST) silently
OVERWRITES them. A failure whose stage logs are gone is not debuggable; so the runner calls capture() the moment a
case finishes, snapshotting that run's artifacts into sessions/<sid>/stagelogs/<case_id>/ where nothing overwrites
them.

SIZE POLICY: pipeline_/failures_ jsonl + notes are small and always archived; ai_<rid>.jsonl carries every full LLM
request/response (MBs on a big emit page) so it is archived per config.ARCHIVE_AI: 'fail' (default — only when the
case failed or carries payload_errors), 'all', or 'never'.

REASON MINING (the fine-grained automatic failure categorization): judge() attributes a failure to a coarse stage
(transport/routing/asset_resolution/layer2_emit/...); the pipeline's own failures_<rid>.jsonl says exactly WHY
(llm:timeout, layer1b:stage_error, exec:card_fail, reason:no_reading ...). reasons() folds those lines into a
deterministic {token: count} map (token = '<stage>:<reason>'), which failures.py/report readers group on — no
human re-greps 30k log files. Multi-asset caveat: compare lanes run under salted run_ids the response does not carry,
so lane logs are captured only when their filename globs the response run_id — best-effort, recorded, never guessed.
Never raises: a missing log file is an honest absence, not an error."""
from __future__ import annotations

import glob
import json
import os
import shutil

from sweep import config
from sweep.response import ascii_safe

_SMALL = ("pipeline_", "failures_")     # always archived (KB-scale, stage-by-stage truth)
_BIG = ("ai_",)                          # archived per config.ARCHIVE_AI (full LLM request/response bodies)


def _reason_token(line: dict) -> str:
    """One deterministic '<stage>:<reason>' token per failures_<rid>.jsonl line ('?' buckets absent fields)."""
    return f"{ascii_safe(line.get('stage')) or '?'}:{ascii_safe(line.get('reason')) or '?'}"


def reasons(run_id: str | None, log_dir: str | None = None) -> dict[str, int]:
    """Mine failures_<rid>.jsonl + pipeline_<rid>.jsonl ERROR lines -> sorted {token: count}. Never raises."""
    if not run_id:
        return {}
    d = log_dir or config.PIPELINE_LOG_DIR
    out: dict[str, int] = {}

    def _bump(tok: str) -> None:
        out[tok] = out.get(tok, 0) + 1

    for path in sorted(glob.glob(os.path.join(d, f"failures_*{run_id}*.jsonl"))):
        try:
            with open(path, errors="replace") as f:
                for raw in f:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        _bump(_reason_token(json.loads(raw)))
                    except ValueError:
                        _bump("failures_log:unparseable_line")
        except OSError:
            continue
    for path in sorted(glob.glob(os.path.join(d, f"pipeline_*{run_id}*.jsonl"))):
        try:
            with open(path, errors="replace") as f:
                for raw in f:
                    if '"ERROR"' not in raw:
                        continue
                    try:
                        line = json.loads(raw)
                    except ValueError:
                        continue
                    if "ERROR" in line:
                        _bump(f"{ascii_safe(line.get('stage')) or '?'}:stage_error")
        except OSError:
            continue
    return dict(sorted(out.items()))


def capture(session_dir: str, case_id: str, run_id: str | None, failed: bool,
            subdir: str | None = None) -> dict:
    """Snapshot this run's per-stage artifacts into <session_dir>/stagelogs/<case_id>[/<subdir>]/ and mine reasons.
    Returns {archived: [filenames], skipped: [filenames], log_reasons: {token: count}} — all sorted, never raises."""
    summary = {"archived": [], "skipped": [], "log_reasons": {}}
    if not run_id:
        return summary
    dest = os.path.join(session_dir, "stagelogs", ascii_safe(case_id) or "unknown", subdir or "")
    want_big = config.ARCHIVE_AI == "all" or (config.ARCHIVE_AI == "fail" and failed)

    for path in sorted(glob.glob(os.path.join(config.PIPELINE_LOG_DIR, f"*{run_id}*"))):
        name = os.path.basename(path)
        if name.startswith("response_"):
            continue                               # the runner already saves the full response as raw/<case_id>.json
        big = name.startswith(_BIG)
        if big and not want_big:
            summary["skipped"].append(name)
            continue
        try:
            os.makedirs(dest, exist_ok=True)
            shutil.copy2(path, os.path.join(dest, name))
            summary["archived"].append(name)
        except OSError:
            summary["skipped"].append(name)
    notes = os.path.join(config.NOTES_DIR, f"{run_id}.json")
    if os.path.isfile(notes):
        try:
            os.makedirs(dest, exist_ok=True)
            shutil.copy2(notes, os.path.join(dest, f"notes_{run_id}.json"))
            summary["archived"].append(f"notes_{run_id}.json")
        except OSError:
            summary["skipped"].append(f"notes_{run_id}.json")

    summary["archived"].sort()
    summary["skipped"].sort()
    summary["log_reasons"] = reasons(run_id)
    return summary
