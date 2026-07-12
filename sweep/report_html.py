"""validation/report_html.py — the HUMAN DASHBOARD: render one session's already-computed artifacts (report.json,
failures.json, coverage.json) into a single self-contained HTML file a human opens after a sweep. WHY a separate
module: the JSON reports are the machine truth and must stay diff-stable; HTML is presentation only — this file
computes NOTHING new (no re-judging, no re-aggregation beyond display grouping), so a disagreement between the page
and the JSON is impossible by construction. Zero external assets (inline <style>, no scripts, no CDN) so the file can
be attached to a bug report or opened over sshfs years later. Deterministic: same session artifacts -> byte-identical
HTML (the only timestamp shown is the manifest's own finished_at). Missing/corrupt inputs degrade to honest
'(unavailable)' sections — build() never raises."""
from __future__ import annotations

import html
import json
import os

from sweep import config
from sweep.response import ascii_safe

_MISSING = "(none)"


# ---------------------------------------------------------------- input loading (all best-effort, never raises)

def _read_json(path: str):
    try:
        with open(path) as f:
            v = json.load(f)
        return v if isinstance(v, dict) else None
    except Exception:
        return None


def _load_report(sdir: str, session_id: str) -> dict:
    rep = _read_json(os.path.join(sdir, "report.json"))
    if rep is not None:
        return rep
    try:                                   # build it if the machine report was never generated
        from sweep import report_json
        report_json.build(session_id)
    except Exception:
        pass
    rep = _read_json(os.path.join(sdir, "report.json"))
    if rep is not None:
        return rep
    # last resort: stitch a minimal summary from the per-concern artifacts so the page is still honest
    out: dict = {}
    m = _read_json(os.path.join(sdir, "metrics.json"))
    if m is None:
        try:
            from sweep import metrics
            m = metrics.compute(session_id)
        except Exception:
            m = None
    if m:
        out["metrics"] = m
    mf = _read_json(os.path.join(sdir, "manifest.json"))
    if mf:
        out["manifest"] = mf
    return out


def _load_failures(sdir: str, session_id: str) -> dict:
    f = _read_json(os.path.join(sdir, "failures.json"))
    if f is not None:
        return f
    try:
        from sweep import failures
        return failures.collect(session_id) or {}
    except Exception:
        return {}


def _load_coverage(sdir: str, session_id: str) -> dict:
    c = _read_json(os.path.join(sdir, "coverage.json"))
    if c is not None:
        return c
    try:                                   # coverage module may compute+mirror on demand
        from sweep import coverage
        for fn_name in ("compute", "build", "report"):
            fn = getattr(coverage, fn_name, None)
            if callable(fn):
                v = fn(session_id)
                return v if isinstance(v, dict) else {}
    except Exception:
        pass
    return _read_json(os.path.join(sdir, "coverage.json")) or {}


# ---------------------------------------------------------------- normalization (shape-tolerant, display-only)

def _num(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _summary(report: dict, failures_doc: dict) -> dict:
    """total/passed/failed/degraded/p95 — probed from the report's likely homes, falling back to failures.json."""
    metrics = report.get("metrics") if isinstance(report.get("metrics"), dict) else report
    totals = metrics.get("totals") if isinstance(metrics.get("totals"), dict) else {}
    manifest = report.get("manifest") if isinstance(report.get("manifest"), dict) else {}
    lat = metrics.get("latency_s") if isinstance(metrics.get("latency_s"), dict) else {}
    overall = lat.get("overall") if isinstance(lat.get("overall"), dict) else {}

    passed = _num(totals.get("passed"), _num(manifest.get("passed")))
    failed = _num(totals.get("failed"), _num(manifest.get("failed"), _num(failures_doc.get("n_failures"))))
    degraded = _num(totals.get("degraded"), _num(failures_doc.get("n_degraded")))
    total = _num(metrics.get("cases"), _num(manifest.get("total")))
    if total is None and passed is not None and failed is not None:
        total = passed + failed
    return {
        "total": total, "passed": passed, "failed": failed, "degraded": degraded,
        "p95": _num(overall.get("p95")),
        "finished_at": ascii_safe(manifest.get("finished_at")) or None,
    }


def _coverage_rows(cov: dict) -> list[dict]:
    """[{dimension, covered, universe, pct, uncovered:[...]}] sorted by dimension — tolerant of several shapes."""
    dims = None
    for key in ("dimensions", "coverage", "by_dimension"):
        if isinstance(cov.get(key), dict):
            dims = cov[key]
            break
    if dims is None:      # maybe the top level IS the dimension map
        dims = {k: v for k, v in cov.items()
                if isinstance(v, dict) and ("universe" in v or "covered" in v or "uncovered" in v)}
    rows = []
    for name in sorted(dims):
        e = dims[name]
        if not isinstance(e, dict):
            continue
        covered = e.get("covered")
        n_cov = len(covered) if isinstance(covered, (list, set)) else _num(covered, 0) or 0
        universe = e.get("universe")
        n_uni = len(universe) if isinstance(universe, (list, set)) else _num(universe, 0) or 0
        uncovered = e.get("uncovered") if isinstance(e.get("uncovered"), list) else []
        if not n_uni:
            n_uni = n_cov + len(uncovered)
        pct = _num(e.get("pct"))
        if pct is None:
            pct = (100.0 * n_cov / n_uni) if n_uni else 0.0
        rows.append({"dimension": ascii_safe(name), "covered": int(n_cov), "universe": int(n_uni),
                     "pct": round(pct, 1), "uncovered": sorted(ascii_safe(u) for u in uncovered)})
    return rows


# ---------------------------------------------------------------- html helpers

def _e(s) -> str:
    return html.escape(ascii_safe(s))


def _fmt(v, suffix: str = "") -> str:
    if v is None:
        return "-"
    f = float(v)
    return (str(int(f)) if f == int(f) else f"{f:g}") + suffix


_STYLE = """
:root { color-scheme: dark light; }
body { background:#16181d; color:#d6d9de; font:14px/1.5 -apple-system,'Segoe UI',sans-serif; margin:0; padding:24px; }
h1 { font-size:19px; margin:0 0 4px; color:#eceef1; }
h2 { font-size:15px; margin:28px 0 8px; color:#eceef1; border-bottom:1px solid #2d3138; padding-bottom:4px; }
.meta { color:#8a8f98; font-size:12px; margin-bottom:14px; }
.strip { display:flex; gap:10px; flex-wrap:wrap; margin:14px 0; }
.stat { background:#1e2128; border:1px solid #2d3138; border-radius:6px; padding:8px 16px; min-width:90px; }
.stat .k { color:#8a8f98; font-size:11px; text-transform:uppercase; letter-spacing:.05em; }
.stat .v { font-size:20px; font-family:ui-monospace,Menlo,Consolas,monospace; }
.stat.bad .v { color:#e5737a; } .stat.warn .v { color:#d9a05b; } .stat.good .v { color:#7fb98a; }
table { border-collapse:collapse; width:100%; font-family:ui-monospace,Menlo,Consolas,monospace; font-size:12.5px; }
th { text-align:left; color:#8a8f98; font-weight:600; }
th, td { border:1px solid #2d3138; padding:5px 10px; vertical-align:top; }
tr.low td { background:rgba(196,72,80,.14); }
tr.low td.pct { color:#e5737a; font-weight:700; }
details { margin:8px 0; border:1px solid #2d3138; border-radius:6px; background:#1a1d23; }
summary { cursor:pointer; padding:7px 12px; color:#c9cdd3; font-family:ui-monospace,Menlo,Consolas,monospace; font-size:13px; }
summary .n { color:#8a8f98; }
details > div, details > table { margin:0 12px 12px; width:auto; }
.uncov { color:#a7abb3; font-size:12px; word-break:break-word; }
.empty { color:#8a8f98; font-style:italic; }
td.why { color:#a7abb3; max-width:520px; }
.tablewrap { overflow-x:auto; }
"""


def _stat(k: str, v: str, cls: str = "") -> str:
    return f'<div class="stat {cls}"><div class="k">{_e(k)}</div><div class="v">{_e(v)}</div></div>'


def _fail_table(rows: list[dict]) -> str:
    body = "".join(
        f'<tr><td>{_e(r.get("case_id") or _MISSING)}</td><td>{_e(r.get("category") or _MISSING)}</td>'
        f'<td>{_e(r.get("prompt"))}</td><td class="why">{_e(r.get("why"))}</td></tr>'
        for r in rows)
    return ('<div class="tablewrap"><table><tr><th>case_id</th><th>category</th><th>prompt</th><th>why</th></tr>'
            f"{body}</table></div>")


# ---------------------------------------------------------------- public API

def build(session_id: str) -> str:
    """Render sessions/<sid>/report.html from the session's JSON artifacts; returns the html path. Never raises —
    missing inputs render as honest '(unavailable)' sections."""
    sid = ascii_safe(session_id)
    sdir = os.path.join(config.OUT_DIR, "sessions", sid)
    report = _load_report(sdir, session_id)
    fdoc = _load_failures(sdir, session_id)
    cov_rows = _coverage_rows(_load_coverage(sdir, session_id))
    s = _summary(report, fdoc)

    parts: list[str] = [f"<style>{_STYLE}</style>",
                        f"<h1>V48 validation session {_e(sid)}</h1>"]
    if s["finished_at"]:
        parts.append(f'<div class="meta">finished {_e(s["finished_at"])}</div>')

    failed = s["failed"] or 0
    degraded = s["degraded"] or 0
    parts.append('<div class="strip">'
                 + _stat("total", _fmt(s["total"]))
                 + _stat("passed", _fmt(s["passed"]), "good")
                 + _stat("failed", _fmt(s["failed"]), "bad" if failed else "good")
                 + _stat("degraded", _fmt(s["degraded"]), "warn" if degraded else "")
                 + _stat("p95 latency", _fmt(s["p95"], "s"))
                 + "</div>")

    # ---- coverage table -------------------------------------------------
    parts.append("<h2>Coverage</h2>")
    if cov_rows:
        rows_html = "".join(
            f'<tr class="{"low" if r["pct"] < 80.0 else ""}"><td>{_e(r["dimension"])}</td>'
            f'<td>{r["covered"]}</td><td>{r["universe"]}</td><td class="pct">{r["pct"]:.1f}%</td></tr>'
            for r in cov_rows)
        parts.append('<div class="tablewrap"><table><tr><th>dimension</th><th>covered</th><th>universe</th>'
                     f"<th>pct</th></tr>{rows_html}</table></div>")
        # uncovered details
        parts.append("<h2>Uncovered</h2>")
        any_uncov = False
        for r in cov_rows:
            if not r["uncovered"]:
                continue
            any_uncov = True
            items = ", ".join(_e(u) for u in r["uncovered"])
            parts.append(f'<details><summary>{_e(r["dimension"])} <span class="n">'
                         f'({len(r["uncovered"])} uncovered)</span></summary>'
                         f'<div class="uncov">{items}</div></details>')
        if not any_uncov:
            parts.append('<div class="empty">every dimension fully covered</div>')
    else:
        parts.append('<div class="empty">coverage.json unavailable</div>')

    # ---- failure dashboard ----------------------------------------------
    parts.append("<h2>Failure dashboard</h2>")
    fails = [f for f in (fdoc.get("failures") or []) if isinstance(f, dict)]
    if fails:
        by_stage: dict[str, list[dict]] = {}
        for f in fails:
            by_stage.setdefault(ascii_safe(f.get("stage")) or "unknown", []).append(f)
        for stage in sorted(by_stage):
            rows = sorted(by_stage[stage], key=lambda r: ascii_safe(r.get("case_id")))
            parts.append(f'<details open><summary>stage: {_e(stage)} <span class="n">({len(rows)})</span></summary>'
                         + _fail_table(rows) + "</details>")
    elif fdoc:
        parts.append('<div class="empty">no failures</div>')
    else:
        parts.append('<div class="empty">failures.json unavailable</div>')

    # ---- degraded --------------------------------------------------------
    parts.append("<h2>Degraded (honest passes worth watching)</h2>")
    degs = [d for d in (fdoc.get("degraded") or []) if isinstance(d, dict)]
    if degs:
        by_why: dict[str, list[dict]] = {}
        for d in degs:
            by_why.setdefault(ascii_safe(d.get("why")) or _MISSING, []).append(d)
        for why in sorted(by_why):
            rows = sorted(by_why[why], key=lambda r: ascii_safe(r.get("case_id")))
            parts.append(f'<details><summary>{_e(why)} <span class="n">({len(rows)})</span></summary>'
                         + _fail_table(rows) + "</details>")
    elif fdoc:
        parts.append('<div class="empty">no degraded cases</div>')
    else:
        parts.append('<div class="empty">failures.json unavailable</div>')

    doc = ('<!doctype html><html><head><meta charset="utf-8">'
           f"<title>V48 validation {_e(sid)}</title></head><body>"
           + "".join(parts) + "</body></html>")

    path = os.path.join(sdir, "report.html")
    try:
        os.makedirs(sdir, exist_ok=True)
        with open(path, "w", encoding="ascii", errors="replace") as f:
            f.write(doc)
    except Exception:
        pass   # the path is still the contract; a read-only disk must not crash a report run
    return path
