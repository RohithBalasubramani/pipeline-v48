"""replay/cli.py — the operator surface.

    python3 -m replay.cli list [n]                     newest bundles (trace_id · kind · prompt · when)
    python3 -m replay.cli show <trace|run_id|last>     one bundle's manifest + event counts
    python3 -m replay.cli replay <trace|run_id|last>   re-run + compare (default --mode pinned)
                          [--mode pinned|live] [--pin llm,sql,frame,insight,cfg] [--strict] [--tol 0.02]
    python3 -m replay.cli compare <trace_a> <trace_b>  diff any two bundles (no re-run)

Run from the pipeline_v48 root (or anywhere — the repo root is put on sys.path)."""
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _flag(args, name, default=None):
    if name in args:
        i = args.index(name)
        v = args[i + 1] if i + 1 < len(args) else default
        del args[i:i + 2]
        return v
    return default


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    cmd = args.pop(0) if args else "list"
    if cmd == "list":
        from replay.ids import bundles_newest_first
        n = int(args[0]) if args else 25
        rows = bundles_newest_first()[:n]
        for d, m in rows:
            kind = m.get("kind") or "?"
            extra = f" replay_of={m.get('replay_of')}" if kind == "replay" else ""
            print(f"{m['trace_id']}  {kind:<7} {m.get('started_at_iso', '')[:19]:<20} "
                  f"{(m.get('prompt') or '')[:60]!r}{extra}")
        if not rows:
            print("no trace bundles yet (outputs/traces/)")
        return 0
    if cmd == "show":
        from replay.ids import resolve
        d, m = resolve(args[0] if args else "last")
        print(json.dumps(m, indent=1, default=str))
        return 0
    if cmd == "compare":
        from replay.ids import resolve
        from replay import store
        from replay.compare import compare_bundles
        from replay.report import terminal_summary, render_html
        a, _ = resolve(args[0]); b, _ = resolve(args[1])
        cmp = compare_bundles(store.load_bundle(a), store.load_bundle(b), tol=float(_flag(args, "--tol", 0) or 0))
        out = os.path.join(b, "replay")
        os.makedirs(out, exist_ok=True)
        json.dump(cmp, open(os.path.join(out, "comparison.json"), "w"), default=str, indent=1)
        open(os.path.join(out, "report.html"), "w").write(render_html(cmp))
        print(terminal_summary(cmp))
        print(f"\nreport: {os.path.join(out, 'report.html')}")
        return 0
    if cmd == "replay":
        mode = _flag(args, "--mode", "pinned")
        pins = _flag(args, "--pin")
        strict = "--strict" in args and (args.remove("--strict") or True)
        _flag(args, "--tol")                                   # accepted for symmetry; compare uses exact by default
        ref = args[0] if args else "last"
        from replay.engine import replay as run_replay
        from replay.report import terminal_summary
        rdir, cmp = run_replay(ref, mode=mode, strict=bool(strict),
                               pins=([p.strip() for p in pins.split(",") if p.strip()] if pins else None))
        print(terminal_summary(cmp))
        print(f"\nreplay bundle: {rdir}\nreport:        {os.path.join(rdir, 'replay', 'report.html')}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
