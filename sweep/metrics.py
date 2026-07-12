"""validation/metrics.py — the METRICS COLLECTOR: turn a finished session's per-case records into the small set of
numbers a human (or a regression diff) actually reads — latency percentiles per workflow category and honest totals
(passed / failed / degraded / transport / fabrication / leaf-fill). WHY a separate module: the runner must stay a dumb
executor and the reports must stay renderers; the single place that defines "what p95 means" and "what counts as a
transport error" lives here, so every report and every cross-session diff agrees byte-for-byte. Percentiles are
nearest-rank on the sorted list (no numpy, no interpolation — deterministic and defensible on tiny samples), every
float is rounded to 3 decimals, and every dict/list is emitted in sorted order so metrics.json is diffable across
sessions. Bad/missing data degrades honestly (an unreadable case file is counted, never raised)."""
from __future__ import annotations

import json
import math
import os

from validation import config
from validation.response import ascii_safe


def _round3(x) -> float:
    try:
        return round(float(x), 3)
    except (TypeError, ValueError):
        return 0.0


def _nearest_rank(sorted_vals: list[float], pct: float) -> float:
    """Nearest-rank percentile: value at ceil(pct/100 * n), 1-indexed, on an ascending list."""
    n = len(sorted_vals)
    if n == 0:
        return 0.0
    rank = max(1, min(n, math.ceil(pct / 100.0 * n)))
    return sorted_vals[rank - 1]


def _latency_stats(values: list[float]) -> dict:
    vals = sorted(v for v in values if isinstance(v, (int, float)))
    n = len(vals)
    if n == 0:
        return {"count": 0, "mean": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "min": 0.0, "max": 0.0}
    return {
        "count": n,
        "mean": _round3(sum(vals) / n),
        "p50": _round3(_nearest_rank(vals, 50)),
        "p95": _round3(_nearest_rank(vals, 95)),
        "p99": _round3(_nearest_rank(vals, 99)),
        "min": _round3(vals[0]),
        "max": _round3(vals[-1]),
    }


def _load_cases(sdir: str) -> tuple[list[dict], int]:
    """Read every cases/*.json record; return (records, unreadable_count). Never raises."""
    cdir = os.path.join(sdir, "cases")
    recs: list[dict] = []
    unreadable = 0
    try:
        names = sorted(f for f in os.listdir(cdir) if f.endswith(".json"))
    except OSError:
        return [], 0
    for name in names:
        try:
            with open(os.path.join(cdir, name)) as f:
                rec = json.load(f)
            if isinstance(rec, dict):
                recs.append(rec)
            else:
                unreadable += 1
        except (OSError, ValueError):
            unreadable += 1
    return recs, unreadable


def compute(session_id: str) -> dict:
    """Compute latency + outcome metrics over sessions/<session_id>/cases/*.json; also writes metrics.json there."""
    sdir = os.path.join(config.OUT_DIR, "sessions", ascii_safe(session_id))
    recs, unreadable = _load_cases(sdir)

    all_lat: list[float] = []
    by_cat_lat: dict[str, list[float]] = {}
    passed = failed = degraded = transport_errors = fabrication = 0
    real_leaves = data_leaves = 0

    for rec in recs:
        case = rec.get("case") or {}
        judgment = rec.get("judgment") or {}
        parsed = rec.get("parsed") or {}
        cat = str(case.get("category") or "unknown")

        el = rec.get("elapsed_s")
        if isinstance(el, (int, float)):
            all_lat.append(float(el))
            by_cat_lat.setdefault(cat, []).append(float(el))

        if judgment.get("pass"):
            passed += 1
            if judgment.get("degraded"):
                degraded += 1
        else:
            failed += 1
        if judgment.get("stage") == "transport" or rec.get("transport_error"):
            transport_errors += 1
        if isinstance(parsed, dict):
            fabrication += int(parsed.get("payload_errors") or 0)
            real_leaves += int(parsed.get("real_leaves") or 0)
            data_leaves += int(parsed.get("data_leaves") or 0)

    metrics = {
        "session": ascii_safe(session_id),
        "cases": len(recs),
        "unreadable_case_files": unreadable,
        "latency_s": {
            "overall": _latency_stats(all_lat),
            "by_category": {cat: _latency_stats(vals) for cat, vals in sorted(by_cat_lat.items())},
        },
        "totals": {
            "passed": passed,
            "failed": failed,
            "degraded": degraded,
            "transport_errors": transport_errors,
            "fabrication": fabrication,
            "real_leaves": real_leaves,
            "data_leaves": data_leaves,
            "fill_pct": _round3(100.0 * real_leaves / data_leaves) if data_leaves else 0.0,
        },
    }

    try:
        os.makedirs(sdir, exist_ok=True)
        with open(os.path.join(sdir, "metrics.json"), "w") as f:
            json.dump(metrics, f, indent=1, sort_keys=True)
    except OSError:
        pass  # metrics are still returned; persistence failure must not crash a report run
    return metrics
