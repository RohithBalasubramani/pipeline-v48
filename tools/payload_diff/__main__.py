"""tools/payload_diff/__main__.py — the CLI (dispatch only; every concern lives in its sibling module).

    python3 -m tools.payload_diff capture "<prompt>" [--asset-id N] [--label before]
    python3 -m tools.payload_diff snapshot <ref> [--out FILE]
    python3 -m tools.payload_diff diff <refA> <refB> [--tol 0.02] [--html FILE] [--expand-values]
    python3 -m tools.payload_diff rerun "<prompt>" [--asset-id N]
    python3 -m tools.payload_diff list [--grep S] [-n 20]

<ref> grammar: snapshot file | saved label | run id | prompt text — each with optional @occurrence (see refs.py).
Exit codes: 0 clean · 2 the diff found REAL→EMPTY regressions (scriptable as a cert gate)."""
import argparse
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from tools.payload_diff import logs as L                    # noqa: E402
from tools.payload_diff import snapshot as S                # noqa: E402
from tools.payload_diff import refs as R                    # noqa: E402
from tools.payload_diff.capture import capture, DEFAULT_HOST  # noqa: E402
from tools.payload_diff.diff import compare                 # noqa: E402
from tools.payload_diff import report_term, report_html     # noqa: E402


def _write_report(report, snap_a, snap_b, html_path=None, expand_values=False):
    print(report_term.render(report))
    ma, mb = snap_a["meta"], snap_b["meta"]
    if html_path is None:
        os.makedirs(L.DIFF_DIR, exist_ok=True)
        name = (f"{ma.get('label') or ma['run_id']}_occ{ma.get('occurrence')}"
                f"__vs__{mb.get('label') or mb['run_id']}_occ{mb.get('occurrence')}.html")
        html_path = os.path.join(L.DIFF_DIR, name)
    title = f"payload diff — {ma['run_id']}@{ma.get('occurrence')} vs {mb['run_id']}@{mb.get('occurrence')}"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(report_html.render(report, title=title, expand_values=expand_values))
    print(f"\n  report: {html_path}")
    regressions = (report["validation"].get("regressions", 0) if "unavailable" not in report["validation"] else 0)
    emptied = (report["payload"]["totals"]["emptied"] if "unavailable" not in report["payload"] else 0)
    return 2 if (regressions or emptied) else 0


def cmd_capture(args):
    snap, path = capture(args.prompt, asset_id=args.asset_id, host=args.host, label=args.label)
    m = snap["meta"]
    resp = snap.get("response") or {}
    print(f"captured {m['run_id']}@{m.get('occurrence')} — {len(resp.get('cards') or [])} cards, "
          f"{len(snap.get('sql') or [])} SQL reads, {resp.get('elapsed_ms')} ms\n  snapshot: {path}")
    return 0


def cmd_snapshot(args):
    snap = R.resolve(args.ref)
    path = S.save(snap, out=args.out)
    unav = snap.get("unavailable") or {}
    print(f"snapshot {snap['meta']['run_id']}@{snap['meta'].get('occurrence')} → {path}")
    for k, why in unav.items():
        print(f"  degraded [{k}]: {why}")
    return 0


def cmd_diff(args):
    snap_a, snap_b = R.resolve_pair(args.ref_a, args.ref_b)
    report = compare(snap_a, snap_b, tol=args.tol, max_entries=args.max_entries)
    return _write_report(report, snap_a, snap_b, html_path=args.html, expand_values=args.expand_values)


def cmd_rerun(args):
    """Same-prompt comparison in one shot: freeze the previous execution FROM LOGS (before the fresh run overwrites
    response_<rid>.json), run it again live, diff old vs new. No prior execution → run twice back-to-back."""
    rid = L.make_run_id(args.prompt)
    had_prior = bool(L.segment_executions(L.stage_log(rid))) and L.response_json(rid) is not None
    if had_prior:
        snap_a = S.build(rid, occurrence=-1, prompt=args.prompt)
        snap_a["meta"]["label"] = "prior"
        S.save(snap_a)
        print(f"froze prior execution {rid}@{snap_a['meta'].get('occurrence')}")
    else:
        print("no prior execution on record — running the prompt twice back-to-back")
        snap_a, _ = capture(args.prompt, asset_id=args.asset_id, host=args.host, label="rerun-1")
        time.sleep(1)
    snap_b, _ = capture(args.prompt, asset_id=args.asset_id, host=args.host,
                        label="rerun-2" if not had_prior else "rerun")
    report = compare(snap_a, snap_b, tol=args.tol, max_entries=args.max_entries)
    return _write_report(report, snap_a, snap_b, html_path=args.html)


def cmd_list(args):
    runs = L.list_runs()
    if args.grep:
        runs = [r for r in runs if args.grep.lower() in (r.get("prompt") or "").lower()]
    for r in runs[-args.n:]:
        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(r["last_ts"])) if r.get("last_ts") else "?"
        resp = "resp" if r["has_response"] else "  — "
        print(f"  {r['run_id']}  ×{r['executions']:<3} {resp}  {ts}  {(r.get('prompt') or '')[:80]}")
    print(f"  ({len(runs)} run(s); ×N = logged executions; 'resp' = latest response on disk)")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="payload_diff", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common_diff(p):
        p.add_argument("--tol", type=float, default=0.0, help="relative numeric tolerance, e.g. 0.02 = ±2%%")
        p.add_argument("--max-entries", type=int, default=400, help="per-card deep-diff entry cap")
        p.add_argument("--html", default=None, help="report path (default outputs/diffs/<A>__vs__<B>.html)")

    def common_capture(p):
        p.add_argument("--asset-id", type=int, default=None, help="pin the asset (skips 1b ambiguity/picker)")
        p.add_argument("--host", default=DEFAULT_HOST)

    p = sub.add_parser("capture", help="run a prompt through the live host and freeze the execution")
    p.add_argument("prompt")
    p.add_argument("--label", default=None, help="snapshot label, e.g. 'before' — later usable as a diff ref")
    common_capture(p)
    p.set_defaults(fn=cmd_capture)

    p = sub.add_parser("snapshot", help="freeze an already-logged execution (ref = run id | prompt | @occurrence)")
    p.add_argument("ref")
    p.add_argument("--out", default=None)
    p.set_defaults(fn=cmd_snapshot)

    p = sub.add_parser("diff", help="compare two executions (refs: file | label | run id | prompt, each @occ)")
    p.add_argument("ref_a")
    p.add_argument("ref_b")
    p.add_argument("--expand-values", action="store_true", help="expand live-data value drift in the HTML too")
    common_diff(p)
    p.set_defaults(fn=cmd_diff)

    p = sub.add_parser("rerun", help="re-run a prompt now and diff against its previous execution")
    p.add_argument("prompt")
    common_capture(p)
    common_diff(p)
    p.set_defaults(fn=cmd_rerun)

    p = sub.add_parser("list", help="known runs under outputs/logs")
    p.add_argument("--grep", default=None)
    p.add_argument("-n", type=int, default=20)
    p.set_defaults(fn=cmd_list)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
