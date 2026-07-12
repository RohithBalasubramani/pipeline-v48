"""admin/latency.py — latency report: per-stage duration stats + end-to-end trend + slowest runs.

Stage lines are END-markers, so a record's duration = its ts minus the previous record's ts within one execution
(runs.executions). Per-card fan-out stages (L2.card, exec) overlap in wall time — their numbers read as "event
spacing", the per-run RESPONSE elapsed_ms is the honest end-to-end figure."""
from admin import runs, store
from admin.config import in_window, iso


def _pctl(sorted_vals, p):
    if not sorted_vals:
        return None
    i = min(len(sorted_vals) - 1, max(0, int(round(p * (len(sorted_vals) - 1)))))
    return sorted_vals[i]


def report(t_from=None, t_to=None, slowest_n=15):
    durs = {}                     # stage -> [ms]
    by_day = {}                   # day -> [elapsed_ms]
    slowest = []
    for rid in store.run_ids():
        ts = store.last_ts(rid)
        if not in_window(ts, t_from, t_to):
            continue
        for sl in runs.executions(rid):
            prev = None
            for rec in sl:
                t = rec.get("ts")
                if prev is not None and t is not None:
                    durs.setdefault(rec.get("stage"), []).append((t - prev) * 1000)
                prev = t if t is not None else prev
        s = runs.summary(rid)
        if s.get("elapsed_ms"):
            by_day.setdefault((s["ts"] or "unknown")[:10], []).append(s["elapsed_ms"])
            slowest.append({"run_id": rid, "ts": s["ts"], "prompt": s["prompt"], "page_key": s["page_key"],
                            "elapsed_ms": s["elapsed_ms"], "cards": s["cards"]})
    stages = []
    for stage, vals in durs.items():
        vals.sort()
        stages.append({"stage": stage, "count": len(vals),
                       "avg_ms": int(sum(vals) / len(vals)),
                       "p50_ms": int(_pctl(vals, 0.5)), "p90_ms": int(_pctl(vals, 0.9)),
                       "max_ms": int(vals[-1])})
    stages.sort(key=lambda s: -s["avg_ms"])
    slowest.sort(key=lambda r: -(r["elapsed_ms"] or 0))
    return {
        "stages": stages,
        "by_day": [{"day": d, "runs": len(v), "avg_ms": int(sum(v) / len(v)),
                    "p90_ms": int(_pctl(sorted(v), 0.9))} for d, v in sorted(by_day.items())],
        "slowest": slowest[:slowest_n],
    }
