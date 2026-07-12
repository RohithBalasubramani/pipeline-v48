"""tools/payload_diff/logs.py — locate + segment the per-run artifacts under outputs/logs. One concern: raw file access.

A run_id keys three files: pipeline_<rid>.jsonl (stage records, APPENDED across re-runs of the same prompt),
sql_<rid>.jsonl (data reads, appended), response_<rid>.json (the full /api/run response, OVERWRITTEN — latest only).
Re-running the same prompt appends to the jsonl files, so an EXECUTION is a segment of the stage log: records from one
stage=="PROMPT" up to (not including) the next. SQL records carry no run marker — they are joined by time window."""
import hashlib
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_DIR = os.path.join(ROOT, "outputs", "logs")
DIFF_DIR = os.path.join(ROOT, "outputs", "diffs")


def make_run_id(prompt, salt=""):
    """Mirror of run/run_id.py (kept import-free so the tool works even when pipeline imports are broken)."""
    return "r_" + hashlib.sha1((salt + "|" + (prompt or "")).encode()).hexdigest()[:10]


def read_jsonl(path):
    """Parsed records of a .jsonl file; [] when absent. Bad lines are skipped (a crash mid-write is not a tool crash)."""
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def stage_log(run_id):
    return read_jsonl(os.path.join(LOG_DIR, f"pipeline_{run_id}.jsonl"))


def sql_log(run_id):
    return read_jsonl(os.path.join(LOG_DIR, f"sql_{run_id}.jsonl"))


def response_json(run_id):
    """The persisted /api/run response (LATEST execution only — host overwrites it), or None."""
    path = os.path.join(LOG_DIR, f"response_{run_id}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def segment_executions(stage_records):
    """Split an appended stage log into per-execution segments. A segment starts at each stage=='PROMPT' record;
    records before the first PROMPT (e.g. a multi-asset RESPONSE_MULTI logged under the parent rid) form a leading
    segment of their own. No PROMPT at all → the whole log is one segment. Never returns empty segments."""
    segments, current = [], []
    for rec in stage_records:
        if rec.get("stage") == "PROMPT" and current:
            segments.append(current)
            current = []
        current.append(rec)
    if current:
        segments.append(current)
    return segments


def segment_time_window(segment, pad_s=2.0):
    """(t_start, t_end) covering the segment's records, padded — the join key for run-marker-less sql_<rid>.jsonl."""
    ts = [r.get("ts") for r in segment if isinstance(r.get("ts"), (int, float))]
    if not ts:
        return None
    return min(ts) - pad_s, max(ts) + pad_s


def sql_for_segment(run_id, segment):
    """The SQL records that fall inside this execution's time window ([] when the trace file is absent)."""
    window = segment_time_window(segment)
    records = sql_log(run_id)
    if not records or window is None:
        return []
    lo, hi = window
    return [r for r in records if isinstance(r.get("ts"), (int, float)) and lo <= r["ts"] <= hi]


def list_runs():
    """All run_ids present under outputs/logs with their prompt + execution count + last ts (newest last)."""
    runs = {}
    for name in sorted(os.listdir(LOG_DIR)) if os.path.isdir(LOG_DIR) else []:
        if name.startswith("pipeline_r_") and name.endswith(".jsonl"):
            rid = name[len("pipeline_"):-len(".jsonl")]
            segs = segment_executions(stage_log(rid))
            prompt, last_ts = None, None
            for seg in segs:
                for rec in seg:
                    if rec.get("stage") == "PROMPT" and rec.get("text"):
                        prompt = rec["text"]
                    if isinstance(rec.get("ts"), (int, float)):
                        last_ts = rec["ts"] if last_ts is None else max(last_ts, rec["ts"])
            runs[rid] = {"run_id": rid, "prompt": prompt, "executions": len(segs), "last_ts": last_ts,
                         "has_response": response_json(rid) is not None}
    return sorted(runs.values(), key=lambda r: r["last_ts"] or 0)
