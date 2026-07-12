"""profiler/charts.py — matplotlib PNG charts over the latency summary.

Follows the dataviz reference palette (validated): categorical slots in fixed
order, ordinal blue steps for the ordered p50/p95/p99 stats, hairline solid
grid, thin marks, light surface. Latency spans ~4ms → ~300s, so range plots use
a log x-axis (labeled in human units).
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, NullLocator

from profiler.report import STAGE_LABEL, STAGE_ORDER

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
# ordinal blue steps (ordered stats: lighter = lower percentile)
P50, P95, P99 = "#86b6ef", "#2a78d6", "#0d366b"
# categorical slots 1..6 (fixed order, never cycled)
CAT = ["#2a78d6", "#1baf7a", "#eda100", "#008300", "#4a3aa7", "#e34948"]

_TICKS = [1, 10, 100, 1000, 10_000, 60_000, 300_000]
_TICK_LABELS = ["1ms", "10ms", "100ms", "1s", "10s", "1m", "5m"]


def _style_axes(ax, log_x=False):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.tick_params(colors=MUTED, labelsize=9, length=0)
    if log_x:
        ax.set_xscale("log")
        ax.xaxis.set_major_locator(FixedLocator(_TICKS))
        ax.xaxis.set_minor_locator(NullLocator())
        ax.set_xticklabels(_TICK_LABELS)
    ax.grid(axis="x", color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)


def _fmt(ms):
    if ms >= 60_000:
        return f"{ms / 60000:.1f}m"
    if ms >= 1000:
        return f"{ms / 1000:.1f}s"
    return f"{ms:.0f}ms"


def _ordered_stages(stats, skip=()):
    keys = [k for k in STAGE_ORDER if k in stats and k not in skip]
    keys += sorted(k for k in stats if k not in STAGE_ORDER and k not in skip)
    return keys


def stage_range(stats, title, path, skip=()):
    """Horizontal p50→p99 range per stage; dots at p50/p95/p99, p50 & p99 direct-labeled."""
    keys = _ordered_stages(stats, skip)
    if not keys:
        return None
    fig, ax = plt.subplots(figsize=(9, 0.52 * len(keys) + 1.6), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    _style_axes(ax, log_x=True)
    ys = range(len(keys), 0, -1)
    for y, k in zip(ys, keys):
        s = stats[k]
        ax.hlines(y, s["median"], s["p99"], color=GRID, linewidth=2, zorder=1)
        ax.plot(s["median"], y, "o", ms=7, color=P50, zorder=3)
        ax.plot(s["p95"], y, "o", ms=7, color=P95, zorder=3)
        ax.plot(s["p99"], y, "o", ms=7, color=P99, zorder=3)
        ax.annotate(_fmt(s["median"]), (s["median"], y), textcoords="offset points",
                    xytext=(0, 9), ha="center", fontsize=8, color=INK2)
        ax.annotate(_fmt(s["p99"]), (s["p99"], y), textcoords="offset points",
                    xytext=(10, -3), ha="left", fontsize=8, color=INK2)
    ax.set_yticks(list(ys))
    ax.set_yticklabels([f"{STAGE_LABEL.get(k, k)}  (n={stats[k]['n']})" for k in keys],
                       fontsize=9, color=INK)
    ax.set_title(title, loc="left", fontsize=12, color=INK, pad=14)
    for color, label in ((P50, "median"), (P95, "p95"), (P99, "p99")):
        ax.plot([], [], "o", ms=7, color=color, label=label)
    fig.legend(loc="upper right", frameon=False, fontsize=8, labelcolor=INK2, ncol=3)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return path


def e2e_hist(samples, title, path):
    vals = [s["ms"] / 1000.0 for s in samples if s["stage"] == "e2e"]
    if len(vals) < 5:
        return None
    fig, ax = plt.subplots(figsize=(9, 3.4), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    _style_axes(ax)
    ax.hist(vals, bins=40, color=P95, edgecolor=SURFACE, linewidth=1.2)
    ax.grid(axis="x", visible=False)
    ax.grid(axis="y", color=GRID, linewidth=0.7)
    ax.set_xlabel("end-to-end seconds", fontsize=9, color=INK2)
    ax.set_ylabel("runs", fontsize=9, color=INK2)
    ax.set_title(title, loc="left", fontsize=12, color=INK, pad=12)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return path


def ai_kind_range(samples, title, path):
    """p50→p99 range per AI-call kind (from cross-cutting 'ai' samples)."""
    from profiler.stats import summarize
    by_kind = {}
    for s in samples:
        if s["stage"] == "ai":
            k = (s.get("meta") or {}).get("kind") or "unknown"
            by_kind.setdefault(k, []).append({**s, "stage": k})
    flat = [x for grp in by_kind.values() for x in grp]
    if not flat:
        return None
    st = summarize(flat)
    order = sorted(st, key=lambda k: st[k]["median"], reverse=True)
    fig, ax = plt.subplots(figsize=(9, 0.52 * len(order) + 1.6), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    _style_axes(ax, log_x=True)
    ys = range(len(order), 0, -1)
    for y, k in zip(ys, order):
        s = st[k]
        ax.hlines(y, s["median"], s["p99"], color=GRID, linewidth=2, zorder=1)
        ax.plot(s["median"], y, "o", ms=7, color=P50, zorder=3)
        ax.plot(s["p95"], y, "o", ms=7, color=P95, zorder=3)
        ax.plot(s["p99"], y, "o", ms=7, color=P99, zorder=3)
        ax.annotate(_fmt(s["median"]), (s["median"], y), textcoords="offset points",
                    xytext=(0, 9), ha="center", fontsize=8, color=INK2)
    ax.set_yticks(list(ys))
    ax.set_yticklabels([f"{k}  (n={st[k]['n']})" for k in order], fontsize=9, color=INK)
    ax.set_title(title, loc="left", fontsize=12, color=INK, pad=14)
    for color, label in ((P50, "median"), (P95, "p95"), (P99, "p99")):
        ax.plot([], [], "o", ms=7, color=color, label=label)
    fig.legend(loc="upper right", frameon=False, fontsize=8, labelcolor=INK2, ncol=3)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return path


def live_breakdown(samples, title, path):
    """Stacked horizontal bar per live prompt: where its wall-clock went.
    Segments are non-overlapping wall-clock components (fixed categorical order)."""
    runs = {}
    for s in samples:
        runs.setdefault(s.get("run_id"), []).append(s)
    rows = []
    for rid, grp in runs.items():
        tot = {}
        for s in grp:
            tot[s["stage"]] = tot.get(s["stage"], 0.0) + s["ms"]
        if "e2e" not in tot:
            continue
        tag = next(((s.get("meta") or {}).get("tag") for s in grp
                    if s["stage"] == "e2e" and (s.get("meta") or {}).get("tag")), rid)
        kg = tot.get("knowledge_gate", 0.0)
        l2 = tot.get("layer2", 0.0)
        route = max(tot.get("pipeline_total", 0.0) - l2, 0.0)
        ex = tot.get("executor", 0.0)
        rend = tot.get("rendering", 0.0)
        other = max(tot["e2e"] - kg - route - l2 - ex - rend, 0.0)
        rows.append((tag, [kg, route, l2, ex, rend, other]))
    if not rows:
        return None
    rows.sort(key=lambda r: sum(r[1]), reverse=True)
    labels = ["knowledge gate", "route+resolve+validate", "layer 2", "executor", "rendering", "other"]
    fig, ax = plt.subplots(figsize=(9, 0.5 * len(rows) + 1.9), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    _style_axes(ax)
    ys = range(len(rows), 0, -1)
    left = [0.0] * len(rows)
    for i, seg_label in enumerate(labels):
        widths = [r[1][i] / 1000.0 for r in rows]
        ax.barh(list(ys), widths, left=left, height=0.6, color=CAT[i],
                edgecolor=SURFACE, linewidth=1.2, label=seg_label)
        left = [a + b for a, b in zip(left, widths)]
    ax.set_yticks(list(ys))
    ax.set_yticklabels([r[0] for r in rows], fontsize=9, color=INK)
    ax.set_xlabel("seconds", fontsize=9, color=INK2)
    ax.set_title(title, loc="left", fontsize=12, color=INK, pad=12)
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right", frameon=False, fontsize=8, ncol=3, labelcolor=INK2)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return path


def render_all(summary, samples_by_source, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    made = []
    if "mined" in summary:
        mined = samples_by_source.get("mined") or []
        made.append(stage_range(summary["mined"], "Mined stage latency — median / p95 / p99 (log scale)",
                                os.path.join(out_dir, "mined_stage_range.png"),
                                skip=("ai_other", "asset_gate")))
        made.append(e2e_hist(mined, "Mined end-to-end latency distribution",
                             os.path.join(out_dir, "mined_e2e_hist.png")))
        made.append(ai_kind_range(mined, "AI call latency by kind — median / p95 / p99 (log scale)",
                                  os.path.join(out_dir, "mined_ai_kinds.png")))
    if "live" in summary:
        live = samples_by_source.get("live") or []
        made.append(stage_range(summary["live"], "Live stage latency — median / p95 / p99 (log scale)",
                                os.path.join(out_dir, "live_stage_range.png"),
                                skip=("ai_other", "asset_gate")))
        made.append(live_breakdown(live, "Live runs — where the wall-clock went",
                                   os.path.join(out_dir, "live_breakdown.png")))
    return [m for m in made if m]
