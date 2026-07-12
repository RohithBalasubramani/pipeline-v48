"""profiler/logmine.py — mine historical outputs/logs into latency samples.

Two sources, both replayable without any live service:

pipeline_r_*.jsonl  per-stage event records with float-epoch ts. A file appends
                    MULTIPLE runs (up to 24); a run = PROMPT ... RESPONSE|RESPONSE_MULTI,
                    paired sequentially within the file. Stage-boundary deltas give
                    coarse wall times; 1a+1b flush together at their parallel join, and
                    all L2.card records flush at the layer2 join, so per-card L2 and the
                    1a-vs-1b split come from the AI log instead.
ai_r_*.jsonl        one self-contained record per LLM call (request + full response).
                    duration = local_ts − response.created (server receipt, integer
                    seconds → ±1s quantization; validated non-negative on all records).
                    Kind/stage via aikinds.classify. Failed LLM calls never appear here.

DB time is NOT minable (no records exist) — that comes from live instrumentation only.
"""
import datetime
import json
import os

from profiler.aikinds import classify

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "logs")


def _lines(path):
    """Yield parsed JSON records, skipping NUL-corrupted / partial lines."""
    with open(path, "r", errors="replace") as f:
        for line in f:
            line = line.strip().lstrip("\x00")
            if not line:
                continue
            try:
                yield json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue


def _split_runs(records):
    """Sequential PROMPT→RESPONSE|RESPONSE_MULTI pairing within one file."""
    runs, cur = [], None
    for r in records:
        st = r.get("stage")
        if st == "PROMPT":
            if cur is not None:
                runs.append(cur)          # orphan PROMPT (no response) — kept, marked open
            cur = {"records": [r], "closed": False}
        elif cur is not None:
            cur["records"].append(r)
            if st in ("RESPONSE", "RESPONSE_MULTI"):
                cur["closed"] = True
                runs.append(cur)
                cur = None
    if cur is not None:
        runs.append(cur)
    return runs


def _first(records, stage):
    return next((r for r in records if r.get("stage") == stage), None)


def _boundary_samples(run, run_id, prompt):
    """Coarse stage wall times from consecutive record ts within one closed run."""
    recs = run["records"]
    out = []
    p = recs[0]
    resp = recs[-1]
    meta_end = {"page": (resp.get("page") if resp.get("stage") == "RESPONSE" else None)}

    def add(stage, t_from, t_to, **meta):
        if t_from is not None and t_to is not None and t_to >= t_from:
            out.append({"stage": stage, "ms": (t_to - t_from) * 1000.0, "run_id": run_id,
                        "prompt": prompt, "source": "mined", "meta": meta})

    r1a = _first(recs, "1a")
    val = _first(recs, "validate")
    gate = _first(recs, "asset_gate")
    l2 = _first(recs, "layer2")
    execs = [r for r in recs if r.get("stage") == "exec"]
    notes = _first(recs, "notes")

    # 1a & 1b log together at their parallel join → wall time of route∥resolve
    # (includes stories + column basket; the split lives in the AI-log samples)
    add("route_resolve_wall", p["ts"], r1a["ts"] if r1a else None)
    if r1a and val:
        add("validation", r1a["ts"], val["ts"])
    if val and gate:
        add("asset_gate", val["ts"], gate["ts"])
    if gate and l2:
        add("layer2", gate["ts"], l2["ts"], n_cards=l2.get("cards"))
    if execs:
        t_start = (notes or l2 or gate or r1a or p)["ts"]
        add("executor", t_start, max(e["ts"] for e in execs), n_cards=len(execs))
        add("rendering", max(e["ts"] for e in execs), resp["ts"])

    if resp.get("stage") == "RESPONSE" and resp.get("elapsed_ms") is not None:
        out.append({"stage": "e2e", "ms": float(resp["elapsed_ms"]), "run_id": run_id,
                    "prompt": prompt, "source": "mined",
                    "meta": {**meta_end, "asset_pending": resp.get("asset_pending"),
                             "rendered": resp.get("rendered"), "n_cards": resp.get("cards")}})
    # RESPONSE_MULTI is handled at file level in mine_pipeline: a multi run's inner
    # per-class RESPONSE closes the paired run first, so the RESPONSE_MULTI record
    # usually arrives outside any open run and would be dropped here.
    return out


def mine_pipeline(log_dir=LOG_DIR):
    """-> (samples, run_windows) where run_windows = {run_id: [(t0, t1, prompt), ...]}
    for attributing AI-log records to the run active at their timestamp."""
    samples, windows = [], {}
    for name in sorted(os.listdir(log_dir)):
        if not (name.startswith("pipeline_") and name.endswith(".jsonl")):
            continue
        run_id = name[len("pipeline_"):-len(".jsonl")]
        records = list(_lines(os.path.join(log_dir, name)))
        for r in records:
            if r.get("stage") == "RESPONSE_MULTI" and r.get("elapsed_ms") is not None:
                samples.append({"stage": "e2e_multi", "ms": float(r["elapsed_ms"]),
                                "run_id": run_id, "prompt": None, "source": "mined",
                                "meta": {"assets": r.get("assets"), "n_cards": r.get("cards"),
                                         "data_unavailable": r.get("data_unavailable")}})
        for run in _split_runs(records):
            recs = run["records"]
            prompt = (recs[0].get("text") or "").strip().strip("'\"")
            if run["closed"]:
                samples.extend(_boundary_samples(run, run_id, prompt))
            windows.setdefault(run_id, []).append((recs[0]["ts"], recs[-1]["ts"], prompt))
    return samples, windows


def mine_ai(run_windows, log_dir=LOG_DIR):
    """Stream ai_*.jsonl -> per-LLM-call samples, each emitted twice: once under its
    pipeline stage (page_selection / asset_resolution / ...) and once under the
    cross-cutting 'ai' stage."""
    samples = []
    for name in sorted(os.listdir(log_dir)):
        if not (name.startswith("ai_") and name.endswith(".jsonl")):
            continue
        if name in ("ai_pytest.jsonl", "ai_pytest_log.jsonl"):
            continue  # test-suite traffic, not user runs
        for rec in _lines(os.path.join(log_dir, name)):
            try:
                t_done = datetime.datetime.fromisoformat(rec["ts"]).timestamp()
                created = rec["response"]["created"]           # server receipt, int seconds
                ms = (t_done - created) * 1000.0
                if ms < 0:
                    continue
                sys_content = rec["request"]["messages"][0]["content"]
            except (KeyError, TypeError, ValueError, IndexError):
                continue
            kind, stage = classify(sys_content)
            run_id = rec.get("run_id") or "?"
            prompt = None
            for (t0, t1, p) in run_windows.get(run_id, ()):
                if t0 - 5 <= t_done <= t1 + 5:
                    prompt = p
                    break
            base = {"ms": ms, "run_id": run_id, "prompt": prompt, "source": "mined",
                    "meta": {"kind": kind, "quantized_s": True}}
            samples.append({"stage": stage, **base})
            samples.append({"stage": "ai", **base})
    return samples


def mine(log_dir=LOG_DIR):
    pipeline_samples, windows = mine_pipeline(log_dir)
    return pipeline_samples + mine_ai(windows, log_dir)
