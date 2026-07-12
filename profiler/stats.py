"""profiler/stats.py — descriptive statistics over latency samples.

A sample is a dict: {"stage": str, "ms": float, "run_id": str, "prompt": str|None,
"source": "live"|"mined", "meta": dict}. Stats are computed per stage.
Percentiles use linear interpolation (numpy default), so p95/p99 on small n are
still defined; n is always reported so the reader can judge confidence.
"""
from collections import defaultdict


def percentile(sorted_vals, q):
    """Linear-interpolated percentile, q in [0,100]. sorted_vals must be non-empty and ascending."""
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    pos = (q / 100.0) * (n - 1)
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def summarize(samples, worst_n=5):
    """samples -> {stage: {n, avg, median, p95, p99, min, max, total_ms, worst: [...]}}.

    worst is the worst_n highest-latency samples for the stage, each with run_id/prompt
    so the pathological inputs are identifiable, not just the number.
    """
    by_stage = defaultdict(list)
    for s in samples:
        by_stage[s["stage"]].append(s)
    out = {}
    for stage, group in by_stage.items():
        vals = sorted(x["ms"] for x in group)
        worst = sorted(group, key=lambda x: x["ms"], reverse=True)[:worst_n]
        out[stage] = {
            "n": len(vals),
            "avg": sum(vals) / len(vals),
            "median": percentile(vals, 50),
            "p95": percentile(vals, 95),
            "p99": percentile(vals, 99),
            "min": vals[0],
            "max": vals[-1],
            "total_ms": sum(vals),
            "worst": [
                {"ms": w["ms"], "run_id": w.get("run_id"), "prompt": w.get("prompt"),
                 "meta": {k: v for k, v in (w.get("meta") or {}).items() if k in
                          ("page", "card", "kind", "url", "stage_at_call", "n_cards", "note")}}
                for w in worst
            ],
        }
    return out
