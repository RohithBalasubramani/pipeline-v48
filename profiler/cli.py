"""profiler/cli.py — entry point.

    python3 -m profiler.cli mine     # historical logs -> stats + report + charts
    python3 -m profiler.cli live     # instrumented in-process sweep (needs services)
    python3 -m profiler.cli report   # re-render report + charts from saved samples

Mined and live samples are NEVER pooled: mined boundaries are coarse ts deltas and
AI durations are ±1s quantized, while live spans are perf_counter-exact — pooling
them would corrupt the percentiles. The report shows both, side by side.
"""
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

OUT_DIR = os.path.join(_ROOT, "outputs", "latency")


def _trim(samples):
    for s in samples:
        if s.get("prompt"):
            s["prompt"] = str(s["prompt"])[:120]
    return samples


def cmd_mine():
    from profiler import logmine
    samples = _trim(logmine.mine())
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "mined_samples.json"), "w") as f:
        json.dump(samples, f)
    print(f"mined {len(samples)} samples -> {OUT_DIR}/mined_samples.json")
    cmd_report()


def cmd_live():
    from profiler import live
    live.run(os.path.join(OUT_DIR, "live_samples.json"))
    cmd_report()


def _load(name):
    p = os.path.join(OUT_DIR, name)
    if not os.path.exists(p):
        return []
    with open(p) as f:
        data = json.load(f)
    return data["samples"] if isinstance(data, dict) else data


def cmd_report():
    from profiler import charts, report, stats
    mined = _load("mined_samples.json")
    live_data = _load("live_samples.json")
    summary = {}
    if mined:
        summary["mined"] = stats.summarize(mined)
    if live_data:
        summary["live"] = stats.summarize(live_data)
    if not summary:
        print("no samples yet — run `mine` and/or `live` first")
        return
    with open(os.path.join(OUT_DIR, "summary.json"), "w") as f:
        json.dump(summary, f, indent=1)

    parts = []
    if "mined" in summary:
        n_runs = summary["mined"].get("e2e", {}).get("n", 0)
        parts.append(report.render(
            summary["mined"], title="V48 latency — mined from historical logs",
            context_lines=[
                f"Source: `outputs/logs/pipeline_*.jsonl` + `ai_*.jsonl` ({n_runs} closed single-asset runs).",
                "Boundary stages (route_resolve_wall/validation/layer2/executor/rendering) are coarse",
                "ts-deltas between stage records; AI-call durations are ±1s quantized (`ts − response.created`).",
                "1a∥1b run in parallel — route_resolve_wall is their joint wall-clock; the per-layer split",
                "comes from the AI-call rows (page_selection / asset_resolution / story_selection).",
                "Database time does not exist in historical logs — see the live section.",
            ]))
    if "live" in summary:
        parts.append(report.render(
            summary["live"], title="V48 latency — live instrumented sweep",
            context_lines=[
                "Source: `python3 -m profiler.cli live` — perf_counter spans via profiler/attach.py,",
                f"{len({s.get('run_id') for s in live_data})} sequential prompts (profiler/live.py CORPUS), full request path",
                "(knowledge gate → pipeline → executor → assembly) plus cross-cutting database/ai spans.",
                "story_selection runs INSIDE page_selection; layer2_card sums exceed the layer2 wall",
                "(fan-out, cap 4); executor_card sums exceed executor wall (ThreadPool ≤8). database/ai",
                "rows count every call — their totals overlap the stage rows, don't add them.",
            ]))
    md = "\n\n---\n\n".join(parts)
    with open(os.path.join(OUT_DIR, "report.md"), "w") as f:
        f.write(md)
    chart_files = charts.render_all(summary, {"mined": mined, "live": live_data},
                                    os.path.join(OUT_DIR, "charts"))
    with open(os.path.join(OUT_DIR, "report.md"), "a") as f:
        f.write("\n\n## Charts\n\n")
        for c in chart_files:
            f.write(f"![{os.path.basename(c)}](charts/{os.path.basename(c)})\n\n")
    from profiler import html_report
    dash = html_report.main(OUT_DIR)
    print(f"report -> {OUT_DIR}/report.md  charts -> {OUT_DIR}/charts/ ({len(chart_files)} files)  dashboard -> {dash}")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    {"mine": cmd_mine, "live": cmd_live, "report": cmd_report}[cmd]()


if __name__ == "__main__":
    main()
