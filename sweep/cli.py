"""validation/cli.py — the ONE entrypoint (python -m validation.cli ...). WHY: every workflow of the framework
(generate corpus, run sweep, rebuild reports, replay a case, coverage, determinism) must be reachable from a single
stdlib-argparse command so operators and cron jobs never import framework internals directly. main() is DISPATCH ONLY:
each subcommand is its own small function; sibling analyzers (metrics/coverage/failures/reports/replay/determinism)
are imported LAZILY and called through a flexible-signature shim, so a missing or drifting sibling degrades to an
honest printed note — the CLI never crashes out on bad/missing data. All printing goes through
validation.response.ascii_safe (neuract strings can carry surrogates that kill the harness)."""
from __future__ import annotations

import argparse
import glob
import json
import os
import time

from validation import config
from validation.response import ascii_safe


# ---------------------------------------------------------------- helpers

def _say(*parts) -> None:
    print(" ".join(ascii_safe(p) for p in parts), flush=True)


def _call_flex(mod_name: str, fn_name: str, shapes: list[tuple]) -> tuple:
    """Import mod_name lazily and call fn(*args) trying each arg shape in order.
    Returns (ok, value_or_reason). Never raises — a missing/drifted sibling is an honest note, not a crash."""
    try:
        mod = __import__(mod_name, fromlist=[fn_name])
        fn = getattr(mod, fn_name)
    except Exception as e:
        return False, f"{mod_name}.{fn_name} unavailable ({type(e).__name__}: {ascii_safe(e)[:120]})"
    last = "no call shape accepted"
    for args in shapes:
        try:
            return True, fn(*args)
        except TypeError as e:
            last = f"TypeError: {ascii_safe(e)[:120]}"
            continue
        except Exception as e:
            return False, f"{mod_name}.{fn_name} failed ({type(e).__name__}: {ascii_safe(e)[:160]})"
    return False, f"{mod_name}.{fn_name} signature mismatch ({last})"


def _latest_session() -> str | None:
    root = os.path.join(config.OUT_DIR, "sessions")
    try:
        dirs = sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)))
    except OSError:
        return None
    return dirs[-1] if dirs else None


def _resolve_session(args) -> str | None:
    sid = getattr(args, "session", None) or _latest_session()
    if not sid:
        _say("no session found under", os.path.join(config.OUT_DIR, "sessions"), "- run `run` first")
    return sid


def _load_corpus() -> list[dict]:
    cases: list[dict] = []
    try:
        with open(config.CORPUS_PATH) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        cases.append(json.loads(line))
                    except ValueError:
                        pass
    except OSError:
        _say("corpus missing at", config.CORPUS_PATH, "- run `generate` first")
    return cases


def _filter_cases(cases: list[dict], categories: list[str] | None, limit: int | None) -> list[dict]:
    """Category filter + DETERMINISTIC STRATIFIED limit: `--limit N` round-robins one case per category per pass
    (each category's pool id-sorted), so a small smoke still touches EVERY workflow — a head-slice of the
    category-sorted corpus would spend the whole budget on the alphabetically-first categories."""
    if categories:
        want = set(categories)
        cases = [c for c in cases if c.get("category") in want]
    cases = sorted(cases, key=lambda c: (c.get("category") or "", c.get("id") or ""))
    if not limit or len(cases) <= limit:
        return cases
    by_cat: dict[str, list[dict]] = {}
    for c in cases:
        by_cat.setdefault(c.get("category") or "?", []).append(c)
    out: list[dict] = []
    i = 0
    while len(out) < limit and any(len(v) > i for v in by_cat.values()):
        for cat in sorted(by_cat):
            if i < len(by_cat[cat]) and len(out) < limit:
                out.append(by_cat[cat][i])
        i += 1
    return sorted(out, key=lambda c: (c.get("category") or "", c.get("id") or ""))


def _load_results(sdir: str) -> list[dict]:
    """Load every per-case record of a session (deterministic order by case id)."""
    out: list[dict] = []
    for p in sorted(glob.glob(os.path.join(sdir, "cases", "*.json"))):
        try:
            with open(p) as f:
                out.append(json.load(f))
        except (OSError, ValueError):
            pass
    return out


def _analyze_and_report(session_id: str) -> None:
    """The shared post-run pipeline: metrics + coverage + failures -> json + html reports (all best-effort)."""
    sdir = config.session_dir(session_id)
    results = _load_results(sdir)
    if not results:
        _say("session", session_id, "has no case records - nothing to analyze")
        return
    bundle: dict = {"session": session_id, "n_cases": len(results)}
    for mod, fn, key in (("validation.metrics", "compute", "metrics"),
                         ("validation.coverage", "analyze", "coverage"),
                         ("validation.failures", "collect", "failures")):
        ok, val = _call_flex(mod, fn, [(results,), (results, sdir), (sdir,)])
        if ok:
            bundle[key] = val
        else:
            _say("note:", val)
    for mod, name in (("validation.report_json", "report.json"), ("validation.report_html", "report.html")):
        ok, val = _call_flex(mod, "build", [(sdir, bundle), (results, sdir), (sdir,), (bundle,)])
        if ok:
            _say("report:", val if isinstance(val, str) else os.path.join(sdir, name))
        else:
            _say("note:", val)
    passed = sum(1 for r in results if (r.get("judgment") or {}).get("pass"))
    degraded = sum(1 for r in results if (r.get("judgment") or {}).get("degraded"))
    _say(f"summary: {passed}/{len(results)} pass ({degraded} degraded) failed={len(results) - passed}",
         "session=" + session_id, "dir=" + sdir)


# ---------------------------------------------------------------- subcommands

def cmd_generate(args) -> int:
    ok, val = _call_flex("validation.corpus.generate", "write", [(config.CORPUS_PATH,)])
    if not ok:
        _say("generate failed:", val)
        return 1
    _say(f"generated {val} cases ->", config.CORPUS_PATH)
    return 0


def cmd_stats(args) -> int:
    """Per-category corpus counts vs prompt_category budgets — shortfalls are REPORTED, never silently padded."""
    cases = _load_corpus()
    if not cases:
        return 1
    by_cat: dict[str, int] = {}
    mutated = 0
    for c in cases:
        by_cat[c.get("category") or "?"] = by_cat.get(c.get("category") or "?", 0) + 1
        if (c.get("meta") or {}).get("mutation"):
            mutated += 1
    ok, s = _call_flex("validation.corpus.store", "store", [()])
    budgets = (s or {}).get("categories", {}) if ok and isinstance(s, dict) else {}
    for cat in sorted(by_cat):
        b = (budgets.get(cat) or {}).get("budget")
        short = f"  (short of budget {b})" if isinstance(b, int) and by_cat[cat] < b else ""
        _say(f"  {cat:16s} {by_cat[cat]:6d}{short}")
    _say(f"total {len(cases)} cases ({mutated} mutation variants) source={((s or {}).get('source') if ok else '?')}")
    return 0


def cmd_run(args) -> int:
    cases = _filter_cases(_load_corpus(), args.category, args.limit)
    if not cases:
        _say("no cases to run (empty corpus or over-narrow filter)")
        return 1
    session_id = args.session or time.strftime("%Y%m%d_%H%M%S")

    def progress(done: int, total: int, rec: dict) -> None:
        j = rec.get("judgment") or {}
        case = rec.get("case") or {}
        status = "PASS" if j.get("pass") else "FAIL"
        if j.get("pass") and j.get("degraded"):
            status = "PASS(degraded)"
        _say(f"{done}/{total} {status} {case.get('category', '?')} :: {ascii_safe(case.get('prompt'))[:70]}")

    from validation.runner import run_cases
    manifest = run_cases(cases, session_id, concurrency=args.concurrency, progress=progress)
    _say(f"run done: {manifest.get('passed')}/{manifest.get('total')} pass, {manifest.get('failed')} fail")
    _analyze_and_report(session_id)
    return 0


def cmd_report(args) -> int:
    sid = _resolve_session(args)
    if not sid:
        return 1
    _analyze_and_report(sid)
    return 0


def cmd_replay(args) -> int:
    sid = _resolve_session(args)
    if not sid:
        return 1
    sdir = config.session_dir(sid)
    ok, val = _call_flex("validation.replay", "replay",
                         [(args.case_id, sid), (args.case_id, sdir), (args.case_id,)])
    if not ok:
        _say("replay failed:", val)
        return 1
    try:
        _say(json.dumps(val, sort_keys=True, indent=1, default=str).encode("ascii", "replace").decode("ascii"))
    except (TypeError, ValueError):
        _say("replay result:", val)
    return 0


def cmd_coverage(args) -> int:
    sid = _resolve_session(args)
    if not sid:
        return 1
    results = _load_results(config.session_dir(sid))
    ok, cov = _call_flex("validation.coverage", "analyze", [(results,), (results, config.session_dir(sid))])
    if not ok or not isinstance(cov, dict):
        _say("coverage failed:", cov if not ok else "analyzer returned non-dict")
        return 1
    pct = cov.get("pct", cov.get("coverage_pct", cov.get("percent")))
    _say(f"session {sid}: coverage {pct if pct is not None else 'unknown'}%")
    unc = cov.get("uncovered")
    if isinstance(unc, dict):
        for dim in sorted(unc):
            v = unc[dim]
            _say(f"  uncovered {dim}: {len(v) if isinstance(v, (list, dict)) else v}")
    elif isinstance(unc, list):
        _say(f"  uncovered paths: {len(unc)}")
    return 0


def cmd_determinism(args) -> int:
    all_cases = _load_corpus()
    if not all_cases:
        return 1
    by_cat: dict[str, list[dict]] = {}
    for c in sorted(all_cases, key=lambda c: (c.get("category") or "", c.get("id") or "")):
        by_cat.setdefault(c.get("category") or "?", []).append(c)
    sample: list[dict] = []
    i = 0
    while len(sample) < args.limit and any(len(v) > i for v in by_cat.values()):
        for cat in sorted(by_cat):                      # round-robin across categories, deterministic
            if len(by_cat[cat]) > i and len(sample) < args.limit:
                sample.append(by_cat[cat][i])
        i += 1
    sid = args.session or time.strftime("determinism_%Y%m%d_%H%M%S")
    ok, val = _call_flex("validation.checks.determinism", "run_determinism",
                         [(sample, sid, args.repeats), (sample, args.repeats), (sample,)])
    if not ok:
        _say("determinism failed:", val)
        return 1
    try:
        _say(json.dumps(val, sort_keys=True, indent=1, default=str).encode("ascii", "replace").decode("ascii"))
    except (TypeError, ValueError):
        _say("determinism result:", val)
    return 0


def cmd_datesync(args) -> int:
    """Interactive date-sync coverage over a session's SAVED raw responses (checks/datesync.py): every is_history card
    must reslice (or be an honest RC9 as-of-latest scalar), no snapshot card may carry a refetch bundle. /api/frame is
    NO-LLM, so this sweep is cheap and vLLM-safe; --limit caps how many responses are driven (newest-id-first stable)."""
    sid = _resolve_session(args)
    if not sid:
        return 1
    sdir = config.session_dir(sid)
    raws = sorted(glob.glob(os.path.join(sdir, "raw", "*.json")))
    raws = [p for p in raws if not p.endswith(".replay.json")][: args.limit or None]
    if not raws:
        _say("session", sid, "has no raw responses")
        return 1
    ok, _mod = _call_flex("validation.checks.datesync", "check_response", [({},)])  # probe availability only
    totals = {"responses": 0, "n_history": 0, "reslices": 0, "as_of_latest": 0, "failures": [], "snapshot_violations": []}
    from validation.checks.datesync import check_response
    for p in raws:
        try:
            with open(p) as f:
                raw = json.load(f)
        except (OSError, ValueError):
            continue
        if not (raw.get("cards") or []):
            continue
        r = check_response(raw)
        totals["responses"] += 1
        totals["n_history"] += r["n_history"]
        totals["reslices"] += r["reslices"]
        totals["as_of_latest"] += r["as_of_latest"]
        cid = os.path.basename(p)[:-5]
        totals["failures"].extend({**f, "case": cid} for f in r["failures"])
        totals["snapshot_violations"].extend({"case": cid, "card_id": c} for c in r["snapshot_violations"])
        _say(f"  {cid}: history={r['n_history']} reslice={r['reslices']} as_of_latest={r['as_of_latest']} "
             f"fail={len(r['failures'])} snapshot_violations={len(r['snapshot_violations'])}")
    with open(os.path.join(sdir, "datesync.json"), "w") as f:
        json.dump(totals, f, sort_keys=True, indent=1)
    _say(f"datesync: {totals['responses']} responses, {totals['n_history']} history cards -> "
         f"{totals['reslices']} reslice + {totals['as_of_latest']} as-of-latest, "
         f"{len(totals['failures'])} failures, {len(totals['snapshot_violations'])} snapshot violations")
    return 0 if not totals["failures"] and not totals["snapshot_violations"] else 1


# ---------------------------------------------------------------- dispatch

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="validation.cli", description="V48 pipeline validation framework")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("generate", help="build corpus -> config.CORPUS_PATH").set_defaults(func=cmd_generate)
    sub.add_parser("stats", help="per-category corpus counts vs budgets").set_defaults(func=cmd_stats)

    r = sub.add_parser("run", help="execute corpus cases and build reports")
    r.add_argument("--limit", type=int, default=None)
    r.add_argument("--concurrency", type=int, default=None)
    r.add_argument("--category", action="append", default=None)
    r.add_argument("--session", default=None)
    r.set_defaults(func=cmd_run)

    for name, func, hlp in (("report", cmd_report, "rebuild reports for an existing session"),
                            ("coverage", cmd_coverage, "print coverage pct + uncovered counts")):
        s = sub.add_parser(name, help=hlp)
        s.add_argument("--session", default=None)
        s.set_defaults(func=func)

    rp = sub.add_parser("replay", help="re-run one saved case")
    rp.add_argument("case_id")
    rp.add_argument("--session", default=None)
    rp.set_defaults(func=cmd_replay)

    d = sub.add_parser("determinism", help="repeat-run a category-spread sample")
    d.add_argument("--session", default=None)
    d.add_argument("--limit", type=int, default=10)
    d.add_argument("--repeats", type=int, default=3)
    d.set_defaults(func=cmd_determinism)

    ds = sub.add_parser("datesync", help="interactive date-sync checks over a session's saved responses")
    ds.add_argument("--session", default=None)
    ds.add_argument("--limit", type=int, default=None)
    ds.set_defaults(func=cmd_datesync)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
