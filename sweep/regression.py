"""validation/regression.py — the REGRESSION DETECTOR: diff two sessions of the SAME corpus case-by-case. WHY:
report.json is diff-stable, but a byte-diff cannot tell "3 new failures + 3 fixes" from "no change" — regression truth
is a per-case JOIN on case id (ids are sha1(category|prompt), stable across sessions of one corpus, so the join needs
no fuzziness; corpus drift lands in only_in_* buckets, reported, never guessed).

Buckets: new_fail (baseline pass -> now fail: THE regression signal), fixed (fail -> pass), still_fail, still_pass,
newly_degraded / recovered_degraded (pass both sides, honesty flag moved — an infra-flake trend, not a defect count),
only_in_baseline / only_in_session (corpus changed between runs). verdict = 'regression' iff new_fail > 0 — degraded
moves and latency drift NEVER flip the verdict, they are context. Latency compares overall mean/p50/p95 from each
side's cases (same nearest-rank convention as metrics.py); coverage compares each side's coverage.json pct dims when
both exist. Output is fully sorted, mirrored to sessions/<session>/regression.json, and compare() never raises on
bad/missing data — an empty side yields honest empty buckets."""
from __future__ import annotations

import glob
import json
import math
import os

from sweep import config
from sweep.response import ascii_safe


def _cases(session_id: str) -> dict[str, dict]:
    """{case_id: record} for one session; unreadable files skipped (they cannot be judged, only ignored)."""
    out: dict[str, dict] = {}
    cdir = os.path.join(config.OUT_DIR, "sessions", ascii_safe(session_id), "cases")
    for path in sorted(glob.glob(os.path.join(cdir, "*.json"))):
        try:
            with open(path) as f:
                rec = json.load(f)
        except (OSError, ValueError):
            continue
        cid = ((rec.get("case") or {}).get("id")) if isinstance(rec, dict) else None
        if cid:
            out[ascii_safe(cid)] = rec
    return out


def _fp(rec: dict) -> dict:
    """The per-case comparison fingerprint (small on purpose: what a human reads in a regression row)."""
    j = rec.get("judgment") or {}
    p = rec.get("parsed") or {}
    return {"pass": bool(j.get("pass")), "degraded": bool(j.get("degraded")),
            "stage": ascii_safe(j.get("stage")) or None, "why": ascii_safe(j.get("why"))[:200] or None,
            "outcome": (p or {}).get("outcome"), "payload_errors": int((p or {}).get("payload_errors") or 0)}


def _latency(records: dict[str, dict]) -> dict:
    vals = sorted(float(r["elapsed_s"]) for r in records.values()
                  if isinstance(r.get("elapsed_s"), (int, float)))
    if not vals:
        return {"mean": None, "p50": None, "p95": None}

    def _rank(p: float) -> float:
        return vals[max(1, min(len(vals), math.ceil(p / 100.0 * len(vals)))) - 1]

    return {"mean": round(sum(vals) / len(vals), 3), "p50": round(_rank(50), 3), "p95": round(_rank(95), 3)}


def _coverage_pct(session_id: str):
    try:
        with open(os.path.join(config.OUT_DIR, "sessions", ascii_safe(session_id), "coverage.json")) as f:
            pct = (json.load(f) or {}).get("pct")
        return pct if isinstance(pct, dict) else None
    except Exception:
        return None


def compare(baseline_id: str, session_id: str) -> dict:
    """Diff session vs baseline; write sessions/<session_id>/regression.json; return the report. Never raises."""
    base, cur = _cases(baseline_id), _cases(session_id)
    ids_base, ids_cur = set(base), set(cur)

    buckets: dict[str, list] = {"new_fail": [], "fixed": [], "still_fail": [], "still_pass": [],
                                "newly_degraded": [], "recovered_degraded": []}
    for cid in sorted(ids_base & ids_cur):
        b, c = _fp(base[cid]), _fp(cur[cid])
        row = {"case_id": cid,
               "category": ascii_safe((cur[cid].get("case") or {}).get("category")) or None,
               "prompt": ascii_safe((cur[cid].get("case") or {}).get("prompt"))[:120],
               "baseline": b, "session": c}
        if b["pass"] and not c["pass"]:
            buckets["new_fail"].append(row)
        elif not b["pass"] and c["pass"]:
            buckets["fixed"].append(row)
        elif not b["pass"]:
            buckets["still_fail"].append(row)
        else:
            buckets["still_pass"].append({"case_id": cid})       # counts only — the interesting rows carry detail
            if c["degraded"] and not b["degraded"]:
                buckets["newly_degraded"].append(row)
            elif b["degraded"] and not c["degraded"]:
                buckets["recovered_degraded"].append(row)

    lat_b, lat_c = _latency(base), _latency(cur)
    cov_b, cov_c = _coverage_pct(baseline_id), _coverage_pct(session_id)
    report = {
        "baseline": ascii_safe(baseline_id), "session": ascii_safe(session_id),
        "verdict": "regression" if buckets["new_fail"] else "ok",
        "counts": {k: len(v) for k, v in sorted(buckets.items())} | {
            "compared": len(ids_base & ids_cur),
            "only_in_baseline": len(ids_base - ids_cur), "only_in_session": len(ids_cur - ids_base)},
        "new_fail": buckets["new_fail"], "fixed": buckets["fixed"], "still_fail": buckets["still_fail"],
        "newly_degraded": buckets["newly_degraded"], "recovered_degraded": buckets["recovered_degraded"],
        "only_in_baseline": sorted(ids_base - ids_cur), "only_in_session": sorted(ids_cur - ids_base),
        "latency_s": {"baseline": lat_b, "session": lat_c,
                      "mean_delta": (round(lat_c["mean"] - lat_b["mean"], 3)
                                     if lat_b["mean"] is not None and lat_c["mean"] is not None else None)},
        "coverage_pct": {"baseline": cov_b, "session": cov_c} if cov_b or cov_c else None,
    }
    try:
        sdir = config.session_dir(session_id)
        with open(os.path.join(sdir, "regression.json"), "w") as f:
            json.dump(report, f, indent=1, sort_keys=True)
    except Exception:
        pass                                            # the comparison is still returned; disk trouble is not analysis failure
    return report
