"""profiler/report.py — render latency stats to a markdown report.

Input is the {stage: stats} dict from stats.summarize plus context about the run
(source, sample counts, date range). Output is one self-contained .md file.
"""

# display order: pipeline order first, cross-cutting last
STAGE_ORDER = [
    "knowledge_gate", "route_resolve_wall", "page_selection", "asset_resolution",
    "story_selection", "validation", "asset_gate", "layer2", "layer2_card",
    "executor", "executor_card", "executor_core", "validation_verdict",
    "rendering", "rendering_card", "assembly_total", "pipeline_total",
    "e2e", "e2e_multi", "database", "ai", "ai_other",
]

STAGE_LABEL = {
    "knowledge_gate": "Knowledge Gate",
    "route_resolve_wall": "Route ∥ Resolve wall (1a ∥ 1b join)",
    "page_selection": "Page Selection (1a)",
    "asset_resolution": "Asset Resolution (1b)",
    "story_selection": "Story Selection",
    "validation": "Validation (pipeline)",
    "asset_gate": "Asset gate",
    "layer2": "Layer 2 (all cards)",
    "layer2_card": "Layer 2 (per card)",
    "executor": "Executor (all cards)",
    "executor_card": "Executor (per card)",
    "executor_core": "Executor core (run_card)",
    "validation_verdict": "Validation (render verdict, per card)",
    "rendering": "Rendering (frame assembly)",
    "rendering_card": "Rendering (per card enrich)",
    "assembly_total": "Assembly total (executor + rendering)",
    "pipeline_total": "Pipeline total (run_pipeline)",
    "e2e": "End-to-end (prompt → response)",
    "e2e_multi": "End-to-end (multi-asset compare)",
    "database": "Database (cross-cutting)",
    "ai": "AI / LLM (cross-cutting)",
    "ai_other": "AI (narrator / other)",
}


def _fmt(ms):
    if ms >= 10000:
        return f"{ms / 1000:.1f}s"
    if ms >= 100:
        return f"{ms:.0f}ms"
    return f"{ms:.1f}ms"


def _ordered(stats):
    keys = [k for k in STAGE_ORDER if k in stats]
    keys += sorted(k for k in stats if k not in STAGE_ORDER)
    return keys


def render(stats, *, title, context_lines=(), worst_note=None):
    """-> markdown string."""
    lines = [f"# {title}", ""]
    lines += list(context_lines)
    lines += ["", "## Latency by stage", "",
              "| Stage | n | avg | median | p95 | p99 | min | max |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for k in _ordered(stats):
        s = stats[k]
        lines.append(
            f"| {STAGE_LABEL.get(k, k)} | {s['n']} | {_fmt(s['avg'])} | {_fmt(s['median'])} "
            f"| {_fmt(s['p95'])} | {_fmt(s['p99'])} | {_fmt(s['min'])} | {_fmt(s['max'])} |")
    lines += ["", "## Worst cases", ""]
    if worst_note:
        lines += [worst_note, ""]
    for k in _ordered(stats):
        s = stats[k]
        if not s.get("worst"):
            continue
        lines.append(f"### {STAGE_LABEL.get(k, k)}")
        lines.append("")
        for w in s["worst"]:
            bits = [f"**{_fmt(w['ms'])}**"]
            if w.get("run_id"):
                bits.append(f"run `{w['run_id']}`")
            if w.get("prompt"):
                p = str(w["prompt"]).strip().strip("'\"")
                bits.append(f"“{p[:90]}”")
            meta = w.get("meta") or {}
            extra = ", ".join(f"{mk}={mv}" for mk, mv in meta.items() if mv not in (None, ""))
            if extra:
                bits.append(f"({extra})")
            lines.append(f"- {' — '.join(bits)}")
        lines.append("")
    return "\n".join(lines) + "\n"
