"""tools/payload_diff/snapshot.py — assemble ONE execution into a self-contained snapshot dict (and save/load it).

A snapshot is everything the diff needs, frozen at capture time, so before/after code- or config-change comparisons
survive the host overwriting response_<rid>.json and the DB knobs moving on. Sources: the /api/run response (live wire
copy, or the persisted latest), the execution's stage-log segment, its SQL trace slice, the app_config fingerprint,
and git provenance. Per-dimension degradation: missing sources land in `unavailable` with a reason, never a crash."""
import json
import os
import subprocess
import time
from datetime import datetime

from tools.payload_diff import SNAPSHOT_VERSION
from tools.payload_diff import logs as L

SNAP_DIR = os.path.join(L.DIFF_DIR, "snapshots")


def _git_provenance():
    """{sha, dirty} of the v48 tree — the code-version stamp for before/after code-change diffs. Fail-open."""
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=L.ROOT,
                             capture_output=True, text=True, timeout=5).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain", "--", "."], cwd=L.ROOT,
                                    capture_output=True, text=True, timeout=10).stdout.strip())
        return {"sha": sha or None, "dirty": dirty}
    except Exception:
        return {"sha": None, "dirty": None}


def _app_config_fingerprint():
    """{key: value} of cmd_catalog.app_config — the DB-knob state, so a config-change diff names the exact rows that
    moved. Best-effort ({} + reason on any DB error); read via the pipeline's own db client."""
    try:
        from data.db_client import q
        from config.databases import CMD_CATALOG
        return {r[0]: r[1] for r in q(CMD_CATALOG, "SELECT key, value FROM app_config ORDER BY key")}, None
    except Exception as e:
        return {}, f"app_config not readable: {type(e).__name__}: {e}"


def build(run_id, occurrence=-1, response=None, sql=None, source="logs", label=None,
          prompt=None, asset_id=None, host=None):
    """Assemble the snapshot for `run_id` execution `occurrence` (negative = from the end, -1 latest).
    `response`/`sql` given → the live wire copies (capture path); omitted → read from outputs/logs."""
    unavailable = {}
    segments = L.segment_executions(L.stage_log(run_id))
    seg = None
    if segments:
        try:
            seg = segments[occurrence]
        except IndexError:
            unavailable["stages"] = f"occurrence {occurrence} out of range (run has {len(segments)} executions)"
    else:
        unavailable["stages"] = f"no stage log for {run_id} (outputs/logs/pipeline_{run_id}.jsonl absent)"

    n = len(segments)
    occ_index = occurrence if occurrence >= 0 else (n + occurrence if n else None)
    is_latest = (occ_index is not None and n and occ_index == n - 1)

    if response is None:
        if is_latest or not segments:
            response = L.response_json(run_id)
            if response is None:
                unavailable["response"] = f"outputs/logs/response_{run_id}.json absent"
        else:
            unavailable["response"] = (f"host keeps only the LATEST response per run_id; occurrence {occ_index} of "
                                       f"{n} predates it — page/cards/payload dims limited to stage-log facts")

    if sql is None:
        sql = L.sql_for_segment(run_id, seg) if seg else []
    if not sql:
        unavailable.setdefault("sql", (
            "no SQL trace records landed during the capture — restart host/server.py if it predates obs/sql_trace.py"
            if source == "live" else
            f"no SQL trace for this execution (outputs/logs/sql_{run_id}.jsonl empty/absent for its time window — "
            f"trace ships with obs/sql_trace.py; older runs predate it)"))

    app_config, cfg_err = _app_config_fingerprint()
    if cfg_err:
        unavailable["app_config"] = cfg_err

    if prompt is None:
        for rec in (seg or []):
            if rec.get("stage") == "PROMPT":
                prompt = rec.get("text")
                if isinstance(prompt, str) and prompt[:1] in ("'", '"'):   # stage logs repr() the prompt
                    try:
                        import ast
                        prompt = ast.literal_eval(prompt)
                    except Exception:
                        pass
                break
        if prompt is None and isinstance(response, dict):
            prompt = response.get("prompt")

    return {
        "snapshot_version": SNAPSHOT_VERSION,
        "meta": {
            "run_id": run_id, "prompt": prompt, "occurrence": occ_index, "executions_in_log": n,
            "captured_at": datetime.now().isoformat(timespec="seconds"), "source": source, "label": label,
            "asset_id": asset_id, "host": host, "git": _git_provenance(),
            "elapsed_ms": (response or {}).get("elapsed_ms"),
        },
        "response": response,
        "stages": seg or [],
        "sql": sql or [],
        "app_config": app_config,
        "unavailable": unavailable,
    }


def save(snap, out=None):
    """Persist under outputs/diffs/snapshots/ (or `out`); the filename carries label/run/occurrence for `list`/refs."""
    os.makedirs(SNAP_DIR, exist_ok=True)
    if out is None:
        label = (snap["meta"].get("label") or time.strftime("%Y%m%d_%H%M%S")).replace(os.sep, "_")
        out = os.path.join(SNAP_DIR, f"{label}_{snap['meta']['run_id']}_occ{snap['meta'].get('occurrence')}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(snap, f)
    return out


def load(path):
    with open(path, encoding="utf-8") as f:
        snap = json.load(f)
    if not isinstance(snap, dict) or "snapshot_version" not in snap:
        raise ValueError(f"{path} is not a payload_diff snapshot (missing snapshot_version)")
    return snap
