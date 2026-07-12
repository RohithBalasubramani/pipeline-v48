"""validation/report_json.py — the DETERMINISTIC MACHINE-READABLE REPORT: one report.json per session that a CI
diff / regression detector can compare byte-for-byte across runs. WHY a separate composer: manifest / metrics /
coverage / failures are each written by their own single-concern module; this file only ASSEMBLES them into the one
stable summary shape — it never re-analyzes. Determinism rules: `generated_at` comes from the manifest's
`finished_at` (NEVER wall-clock, or every rebuild would be a spurious diff), json.dump uses sort_keys=True indent=1,
and every list is sorted. Honesty rules: a missing sibling artifact is first rebuilt via that module's builder
(metrics.compute / coverage.analyze / failures.collect); if the builder itself is absent or fails we degrade to
counting directly from the per-case records and note the gap in `sources` — build() never raises."""
from __future__ import annotations

import json
import os

from validation import config
from validation.response import ascii_safe


# ---------------------------------------------------------------- artifact loading (read file, else build, else {})

def _read_json(path: str):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def _load_or_build(sdir: str, name: str, module: str, fn: str, session_id: str, sources: dict):
    """sessions/<sid>/<name>.json if present; else call validation.<module>.<fn>(session_id) and re-read/use it."""
    path = os.path.join(sdir, f"{name}.json")
    data = _read_json(path)
    if data is not None:
        sources[name] = "ok"                          # one token whether pre-existing or freshly built: rebuilds
        return data                                   # of the same session must be byte-identical
    try:
        import importlib
        mod = importlib.import_module(f"validation.{module}")
        out = getattr(mod, fn)(session_id)
        data = _read_json(path)                       # builders persist to the session dir; prefer the file
        if data is None and isinstance(out, dict):
            data = out
        if data is not None:
            sources[name] = "ok"
            return data
    except Exception as e:
        sources[name] = f"unavailable ({ascii_safe(e)[:80]})"
        return {}
    sources[name] = "unavailable (builder returned nothing)"
    return {}


def _cases(sdir: str) -> list[dict]:
    """Fallback ground truth: the per-case records themselves (runner.py contract), sorted by case id."""
    cdir = os.path.join(sdir, "cases")
    out = []
    try:
        for fn in sorted(os.listdir(cdir)):
            if fn.endswith(".json"):
                rec = _read_json(os.path.join(cdir, fn))
                if isinstance(rec, dict):
                    out.append(rec)
    except Exception:
        pass
    return out


# ---------------------------------------------------------------- defensive extraction

def _pick(d, *keys, default=None):
    """First present key, searching top level then one level of nesting (sibling shapes may nest under a header)."""
    if not isinstance(d, dict):
        return default
    for k in keys:
        if k in d:
            return d[k]
    for v in d.values():
        if isinstance(v, dict):
            for k in keys:
                if k in v:
                    return v[k]
    return default


def _percentile(sorted_vals: list[float], p: float):
    if not sorted_vals:
        return None
    i = max(0, min(len(sorted_vals) - 1, int(round(p / 100.0 * (len(sorted_vals) - 1)))))
    return sorted_vals[i]


def _latency_from_cases(cases: list[dict]) -> dict:
    vals = sorted(float(r["elapsed_s"]) for r in cases
                  if isinstance(r.get("elapsed_s"), (int, float)))
    if not vals:
        return {"mean": None, "p50": None, "p95": None, "p99": None}
    return {"mean": round(sum(vals) / len(vals), 3),
            "p50": round(_percentile(vals, 50), 3),
            "p95": round(_percentile(vals, 95), 3),
            "p99": round(_percentile(vals, 99), 3)}


def _latency(metrics: dict, cases: list[dict]) -> dict:
    lat = _pick(metrics, "latency", "latency_s", default=None)
    if isinstance(lat, dict) and any(k in lat for k in ("mean", "p50", "p95", "p99")):
        return {k: lat.get(k) for k in ("mean", "p50", "p95", "p99")}
    return _latency_from_cases(cases)


def _int_or(v, fallback: int) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return fallback


# ---------------------------------------------------------------- public API

def build(session_id: str) -> str:
    """Compose sessions/<sid>/report.json from the session's artifacts and return its path. Never raises."""
    sdir = config.session_dir(session_id)
    sources: dict = {}

    manifest = _read_json(os.path.join(sdir, "manifest.json")) or {}
    sources["manifest"] = "ok" if manifest else "missing"
    metrics = _load_or_build(sdir, "metrics", "metrics", "compute", session_id, sources)
    coverage = _load_or_build(sdir, "coverage", "coverage", "analyze", session_id, sources)
    failures = _load_or_build(sdir, "failures", "failures", "collect", session_id, sources)

    cases = _cases(sdir)                              # fallback ground truth for anything a sibling did not supply

    degraded = _pick(metrics, "degraded", "n_degraded", default=None)
    if degraded is None:
        degraded = sum(1 for r in cases if (r.get("judgment") or {}).get("degraded"))

    by_stage = _pick(failures, "by_stage", "stages", default=None)
    if not isinstance(by_stage, dict):
        by_stage = {}
        for r in cases:
            j = r.get("judgment") or {}
            if not j.get("pass"):
                s = str(j.get("stage") or "unknown")
                by_stage[s] = by_stage.get(s, 0) + 1
    else:                                             # counts only — a stage may carry a list of failure records
        by_stage = {str(k): (len(v) if isinstance(v, list) else _int_or(v, 0))
                    for k, v in by_stage.items()}
    by_stage = dict(sorted(by_stage.items()))

    n_failures = _pick(failures, "n_failures", "total", default=None)
    if n_failures is None:
        n_failures = sum(by_stage.values())

    uncovered = _pick(coverage, "uncovered", "uncovered_paths", default=None)
    if not isinstance(uncovered, list):
        uncovered = []
    uncovered = sorted(ascii_safe(u) if not isinstance(u, (dict, list)) else
                       json.dumps(u, sort_keys=True) for u in uncovered)

    report = {
        "session": session_id,
        "generated_at": manifest.get("finished_at"),   # manifest time, NOT wall-clock: rebuilds stay byte-identical
        "summary": {
            "total": _int_or(manifest.get("total"), len(cases)),
            "passed": _int_or(manifest.get("passed"),
                              sum(1 for r in cases if (r.get("judgment") or {}).get("pass"))),
            "failed": _int_or(manifest.get("failed"),
                              sum(1 for r in cases if not (r.get("judgment") or {}).get("pass"))),
            "degraded": _int_or(degraded, 0),
            "latency": _latency(metrics, cases),
        },
        "coverage": {
            "pct": _pick(coverage, "pct", "coverage_pct", default=None),
            "uncovered": uncovered,
        },
        "failures": {
            "n_failures": _int_or(n_failures, 0),
            "by_stage": by_stage,
        },
        "sources": dict(sorted(sources.items())),
    }
    determinism = _read_json(os.path.join(sdir, "determinism.json"))
    if determinism is not None:
        report["determinism"] = determinism

    path = os.path.join(sdir, "report.json")
    try:
        with open(path, "w") as f:
            json.dump(report, f, sort_keys=True, indent=1)
    except Exception as e:                            # disk trouble: still return the path, print the honest reason
        print(f"[report_json] write failed: {ascii_safe(e)[:120]}")
    return path
