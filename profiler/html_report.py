"""profiler/html_report.py — self-contained HTML latency dashboard from summary.json.

Emits outputs/latency/dashboard.html: KPI tiles, SVG range/stacked/histogram charts
with a hover layer, worst-case and full-stats tables. No external assets (inline
CSS/JS only), light+dark via CSS tokens (prefers-color-scheme + data-theme override).
Charts follow the dataviz reference palette; ordered percentile dots use the ordinal
blue steps, the live breakdown uses categorical slots 1-6 in fixed order.
"""
import html
import json
import math
import os

from profiler.report import STAGE_LABEL, STAGE_ORDER

LO, HI = 1.0, 320_000.0          # log-x domain, ms
TICKS = [(1, "1ms"), (10, "10ms"), (100, "100ms"), (1000, "1s"),
         (10_000, "10s"), (60_000, "1m"), (300_000, "5m")]


def _fmt(ms):
    if ms >= 60_000:
        return f"{ms / 60000:.1f}m"
    if ms >= 10_000:
        return f"{ms / 1000:.0f}s"
    if ms >= 1000:
        return f"{ms / 1000:.1f}s"
    if ms >= 100:
        return f"{ms:.0f}ms"
    return f"{ms:.1f}ms"


def _x(ms, x0, x1):
    v = min(max(ms, LO), HI)
    return x0 + (math.log10(v) - math.log10(LO)) / (math.log10(HI) - math.log10(LO)) * (x1 - x0)


def _esc(s):
    return html.escape(str(s), quote=True)


def _ordered(stats, skip=()):
    keys = [k for k in STAGE_ORDER if k in stats and k not in skip]
    keys += sorted(k for k in stats if k not in STAGE_ORDER and k not in skip)
    return keys


def _range_svg(stats, keys, label_fn=None):
    """Dot-range rows (p50→p99) on a log axis, with ≥24px hover targets."""
    label_fn = label_fn or (lambda k: STAGE_LABEL.get(k, k))
    row_h, x0, x1, top = 34, 295, 870, 26
    h = top + row_h * len(keys) + 34
    parts = [f'<svg viewBox="0 0 900 {h}" role="img" aria-label="latency range chart">']
    for v, lbl in TICKS:
        x = _x(v, x0, x1)
        parts.append(f'<line x1="{x:.1f}" y1="{top - 10}" x2="{x:.1f}" y2="{h - 30}" class="grid"/>')
        parts.append(f'<text x="{x:.1f}" y="{h - 12}" class="tick" text-anchor="middle">{lbl}</text>')
    for i, k in enumerate(keys):
        s, y = stats[k], top + row_h * i + row_h / 2
        xm, x95, x99 = (_x(s[q], x0, x1) for q in ("median", "p95", "p99"))
        name = label_fn(k)
        parts.append(f'<text x="{x0 - 14}" y="{y + 4}" class="rowlabel" text-anchor="end">{_esc(name)}'
                     f'<tspan class="n"> n={s["n"]}</tspan></text>')
        parts.append(f'<line x1="{xm:.1f}" y1="{y}" x2="{x99:.1f}" y2="{y}" class="range"/>')
        tip = (f'{_esc(name)} — median {_fmt(s["median"])} · p95 {_fmt(s["p95"])} · '
               f'p99 {_fmt(s["p99"])} · max {_fmt(s["max"])} · n={s["n"]}')
        for cx, cls in ((xm, "p50"), (x95, "p95"), (x99, "p99")):
            parts.append(f'<circle cx="{cx:.1f}" cy="{y}" r="5.5" class="dot {cls}"/>')
        parts.append(f'<rect x="{min(xm, x99) - 12:.1f}" y="{y - 12}" width="{abs(x99 - xm) + 24:.1f}" '
                     f'height="24" class="hit" data-tip="{tip}" tabindex="0"/>')
        parts.append(f'<text x="{xm:.1f}" y="{y - 10}" class="vlabel" text-anchor="middle">{_fmt(s["median"])}</text>')
        parts.append(f'<text x="{x99 + 10:.1f}" y="{y + 4}" class="vlabel">{_fmt(s["p99"])}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _hist_svg(vals_s, bins=40):
    if len(vals_s) < 5:
        return ""
    hi = max(vals_s)
    step = hi / bins
    counts = [0] * bins
    for v in vals_s:
        counts[min(int(v / step), bins - 1)] += 1
    peak = max(counts)
    x0, x1, y0, y1 = 60, 880, 208, 16
    bw = (x1 - x0) / bins
    parts = [f'<svg viewBox="0 0 900 240" role="img" aria-label="end-to-end histogram">']
    for frac in (0.25, 0.5, 0.75, 1.0):
        y = y0 - frac * (y0 - y1)
        parts.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" class="grid"/>')
        parts.append(f'<text x="{x0 - 8}" y="{y + 4:.1f}" class="tick" text-anchor="end">{int(peak * frac)}</text>')
    for i, c in enumerate(counts):
        if not c:
            continue
        bh = (y0 - y1) * c / peak
        x = x0 + i * bw
        tip = f"{i * step:.0f}–{(i + 1) * step:.0f}s: {c} runs"
        parts.append(f'<rect x="{x + 1:.1f}" y="{y0 - bh:.1f}" width="{bw - 2:.1f}" height="{bh:.1f}" '
                     f'class="bar" data-tip="{tip}" tabindex="0"/>')
    for t in range(0, int(hi) + 1, 60):
        x = x0 + (t / hi) * (x1 - x0) if hi else x0
        parts.append(f'<text x="{x:.1f}" y="228" class="tick" text-anchor="middle">{t}s</text>')
    parts.append(f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y0}" class="axis"/></svg>')
    return "".join(parts)


BREAKDOWN_SEGS = [("knowledge gate", "c1"), ("route+resolve+validate", "c2"), ("layer 2", "c3"),
                  ("executor", "c4"), ("rendering", "c5"), ("other", "c6")]


def _breakdown_rows(live_samples):
    runs = {}
    for s in live_samples:
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
        ex, rend = tot.get("executor", 0.0), tot.get("rendering", 0.0)
        other = max(tot["e2e"] - kg - route - l2 - ex - rend, 0.0)
        rows.append((tag, [kg, route, l2, ex, rend, other]))
    rows.sort(key=lambda r: sum(r[1]), reverse=True)
    return rows


def _breakdown_svg(rows):
    if not rows:
        return ""
    row_h, x0, x1, top = 30, 150, 870, 14
    hi = max(sum(r[1]) for r in rows)
    h = top + row_h * len(rows) + 30
    parts = [f'<svg viewBox="0 0 900 {h}" role="img" aria-label="per-prompt breakdown">']
    for i, (tag, segs) in enumerate(rows):
        y = top + row_h * i
        parts.append(f'<text x="{x0 - 12}" y="{y + row_h / 2 + 4}" class="rowlabel" text-anchor="end">{_esc(tag)}</text>')
        acc = 0.0
        for (name, cls), ms in zip(BREAKDOWN_SEGS, segs):
            if ms <= 0:
                continue
            w = (ms / hi) * (x1 - x0)
            x = x0 + (acc / hi) * (x1 - x0)
            tip = f"{_esc(tag)} — {name}: {_fmt(ms)} ({100 * ms / sum(segs):.0f}%)"
            parts.append(f'<rect x="{x:.1f}" y="{y + 4}" width="{max(w - 2, 1):.1f}" height="{row_h - 10}" '
                         f'class="seg {cls}" data-tip="{tip}" tabindex="0"/>')
            acc += ms
        parts.append(f'<text x="{x0 + (acc / hi) * (x1 - x0) + 8:.1f}" y="{y + row_h / 2 + 4}" '
                     f'class="vlabel">{_fmt(sum(segs))}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _kpis(m):
    e = m.get("e2e") or {}
    if not e:
        return ""
    worst = (e.get("worst") or [{}])[0]
    tiles = [
        ("Median end-to-end", _fmt(e["median"]), f"n={e['n']} runs"),
        ("p95", _fmt(e["p95"]), "95% of runs finish under this"),
        ("p99", _fmt(e["p99"]), "tail — reflect loops + 8-card pages"),
        ("Worst run", _fmt(e["max"]), (worst.get("prompt") or "")[:46]),
    ]
    cells = "".join(
        f'<div class="tile"><div class="tlabel">{_esc(a)}</div>'
        f'<div class="tval">{_esc(b)}</div><div class="tsub">{_esc(c)}</div></div>'
        for a, b, c in tiles)
    return f'<div class="kpis">{cells}</div>'


def _stats_table(stats, skip=()):
    rows = "".join(
        f"<tr><td>{_esc(STAGE_LABEL.get(k, k))}</td><td>{stats[k]['n']}</td>"
        + "".join(f"<td>{_fmt(stats[k][q])}</td>" for q in ("avg", "median", "p95", "p99", "min", "max"))
        + "</tr>"
        for k in _ordered(stats, skip))
    return ('<div class="tablewrap"><table><thead><tr><th>Stage</th><th>n</th><th>avg</th>'
            '<th>median</th><th>p95</th><th>p99</th><th>min</th><th>max</th></tr></thead>'
            f"<tbody>{rows}</tbody></table></div>")


def _worst_list(stats, stage_keys, per=3):
    items = []
    for k in stage_keys:
        s = stats.get(k)
        if not s or not s.get("worst"):
            continue
        for w in s["worst"][:per]:
            p = (w.get("prompt") or "").strip()
            meta = w.get("meta") or {}
            extra = ", ".join(f"{mk}={mv}" for mk, mv in meta.items()
                              if mv not in (None, "", False) and mk != "quantized_s")
            items.append(f'<tr><td>{_esc(STAGE_LABEL.get(k, k))}</td>'
                         f'<td class="num">{_fmt(w["ms"])}</td>'
                         f'<td><code>{_esc(w.get("run_id") or "—")}</code></td>'
                         f'<td>{_esc(p[:80] or "—")}</td><td class="dim">{_esc(extra)}</td></tr>')
    return ('<div class="tablewrap"><table><thead><tr><th>Stage</th><th>latency</th><th>run</th>'
            '<th>prompt</th><th>context</th></tr></thead><tbody>' + "".join(items) + "</tbody></table></div>")


CSS_JS = """
<style>
:root{
  --page:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --baseline:#c3c2b7; --accent:#2a78d6; --ring:rgba(11,11,11,.10);
  --p50:#86b6ef; --p95:#2a78d6; --p99:#0d366b;
  --c1:#2a78d6; --c2:#1baf7a; --c3:#eda100; --c4:#008300; --c5:#4a3aa7; --c6:#c3c2b7;
}
@media (prefers-color-scheme: dark){:root{
  --page:#0d0d0d; --surface:#1a1a19; --ink:#fff; --ink2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --baseline:#383835; --accent:#3987e5; --ring:rgba(255,255,255,.10);
  --p50:#86b6ef; --p95:#3987e5; --p99:#7fa8dd;
  --c1:#3987e5; --c2:#199e70; --c3:#c98500; --c4:#008300; --c5:#9085e9; --c6:#52514e;
}}
:root[data-theme="dark"]{
  --page:#0d0d0d; --surface:#1a1a19; --ink:#fff; --ink2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --baseline:#383835; --accent:#3987e5; --ring:rgba(255,255,255,.10);
  --p50:#86b6ef; --p95:#3987e5; --p99:#7fa8dd;
  --c1:#3987e5; --c2:#199e70; --c3:#c98500; --c4:#008300; --c5:#9085e9; --c6:#52514e;
}
:root[data-theme="light"]{
  --page:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --baseline:#c3c2b7; --accent:#2a78d6; --ring:rgba(11,11,11,.10);
  --p50:#86b6ef; --p95:#2a78d6; --p99:#0d366b;
  --c1:#2a78d6; --c2:#1baf7a; --c3:#eda100; --c4:#008300; --c5:#4a3aa7; --c6:#c3c2b7;
}
body{background:var(--page);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;margin:0}
.wrap{max-width:980px;margin:0 auto;padding:36px 22px 60px}
h1{font-size:26px;font-weight:650;margin:0 0 4px;text-wrap:balance}
h2{font-size:17px;font-weight:650;margin:38px 0 4px}
.sub{color:var(--ink2);margin:0 0 8px;max-width:72ch}
.note{color:var(--muted);font-size:13px;max-width:78ch}
.card{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:18px 20px;margin-top:12px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-top:18px}
.tile{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:14px 16px}
.tlabel{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.tval{font-size:32px;font-weight:650;margin:2px 0}
.tsub{font-size:12px;color:var(--ink2)}
svg{width:100%;height:auto;display:block}
.grid{stroke:var(--grid);stroke-width:1}
.axis{stroke:var(--baseline);stroke-width:1}
.tick{fill:var(--muted);font-size:11px}
.rowlabel{fill:var(--ink);font-size:12px}
.rowlabel .n{fill:var(--muted);font-size:10px}
.vlabel{fill:var(--ink2);font-size:10.5px}
.range{stroke:var(--grid);stroke-width:2.5}
.dot{stroke:var(--surface);stroke-width:1.5}
.dot.p50{fill:var(--p50)} .dot.p95{fill:var(--p95)} .dot.p99{fill:var(--p99)}
.bar{fill:var(--p95)} .bar:hover,.bar:focus{fill:var(--p99);outline:none}
.seg{stroke:var(--surface);stroke-width:1.5}
.seg.c1{fill:var(--c1)}.seg.c2{fill:var(--c2)}.seg.c3{fill:var(--c3)}
.seg.c4{fill:var(--c4)}.seg.c5{fill:var(--c5)}.seg.c6{fill:var(--c6)}
.seg:hover,.seg:focus{filter:brightness(1.15);outline:none}
.hit{fill:transparent;cursor:default}
.hit:focus{outline:1.5px solid var(--accent);outline-offset:2px}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;color:var(--ink2);margin-top:8px}
.legend span{display:inline-flex;align-items:center;gap:6px}
.sw{width:10px;height:10px;border-radius:50%;display:inline-block}
.swq{border-radius:2px}
.tablewrap{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13px;margin-top:6px}
th{color:var(--muted);font-weight:600;text-align:left;padding:6px 10px;border-bottom:1px solid var(--baseline);white-space:nowrap}
td{padding:6px 10px;border-bottom:1px solid var(--grid);font-variant-numeric:tabular-nums}
td.num{font-weight:650;white-space:nowrap}
td.dim,code{color:var(--ink2)}
code{font-size:12px}
#tip{position:fixed;pointer-events:none;background:var(--ink);color:var(--page);padding:6px 10px;
     border-radius:6px;font-size:12px;max-width:340px;opacity:0;transition:opacity .08s;z-index:9}
@media (prefers-reduced-motion: reduce){#tip{transition:none}}
</style>
<div id="tip" role="status"></div>
<script>
(function(){
  var tip=document.getElementById('tip');
  function show(e,t){tip.textContent=t;tip.style.opacity=1;
    var x=Math.min(e.clientX+14,innerWidth-tip.offsetWidth-8),y=e.clientY+14;
    if(y+tip.offsetHeight>innerHeight-8)y=e.clientY-tip.offsetHeight-10;
    tip.style.left=x+'px';tip.style.top=y+'px';}
  document.addEventListener('mousemove',function(e){
    var el=e.target.closest&&e.target.closest('[data-tip]');
    if(el)show(e,el.getAttribute('data-tip'));else tip.style.opacity=0;});
  document.addEventListener('focusin',function(e){
    var el=e.target.closest&&e.target.closest('[data-tip]');
    if(!el)return;var r=el.getBoundingClientRect();
    tip.textContent=el.getAttribute('data-tip');tip.style.opacity=1;
    tip.style.left=(r.left+8)+'px';tip.style.top=(r.top-34)+'px';});
  document.addEventListener('focusout',function(){tip.style.opacity=0;});
})();
</script>
"""

PCT_LEGEND = ('<div class="legend"><span><i class="sw" style="background:var(--p50)"></i>median</span>'
              '<span><i class="sw" style="background:var(--p95)"></i>p95</span>'
              '<span><i class="sw" style="background:var(--p99)"></i>p99</span></div>')


def render(summary, live_samples, mined_samples, out_path, generated=""):
    mined = summary.get("mined") or {}
    live = summary.get("live") or {}
    seg_legend = "".join(f'<span><i class="sw swq" style="background:var(--c{i + 1})"></i>{name}</span>'
                         for i, (name, _) in enumerate(BREAKDOWN_SEGS))
    e2e_vals = [s["ms"] / 1000 for s in mined_samples if s["stage"] == "e2e"]
    n_runs = (mined.get("e2e") or {}).get("n", 0)

    body = ['<title>V48 Pipeline Latency Profile</title>', CSS_JS, '<div class="wrap">']
    body.append('<h1>V48 pipeline latency profile</h1>')
    body.append(f'<p class="sub">Where a prompt\'s wall-clock goes, from knowledge gate to rendered cards. '
                f'Mined from {n_runs} historical runs (2026-07-06 → 07-11) plus a live instrumented sweep. {generated}</p>')
    if mined:
        body.append(_kpis(mined))
    if live_samples:
        rows = _breakdown_rows(live_samples)
        body.append('<h2>Live runs — where the wall-clock went</h2>')
        body.append('<p class="sub">One instrumented in-process run per prompt, sequential. Segments are '
                    'non-overlapping wall-clock components of each response.</p>')
        body.append(f'<div class="card">{_breakdown_svg(rows)}<div class="legend">{seg_legend}</div></div>')
    if mined:
        body.append('<h2>Stage latency — mined baseline</h2>')
        body.append('<p class="sub">Median → p99 per stage. 1a ∥ 1b run in parallel — their joint wall-clock is the '
                    '"Route ∥ Resolve wall" row; per-layer numbers come from AI-call records. Log scale.</p>')
        body.append(f'<div class="card">{_range_svg(mined, _ordered(mined, skip=("ai_other", "asset_gate", "e2e_multi")))}'
                    f'{PCT_LEGEND}</div>')
        if e2e_vals:
            body.append('<h2>End-to-end distribution</h2>')
            body.append('<p class="sub">Bimodal: early exits (ambiguous asset / knowledge answers) under 10s; '
                        'full card pages 25–75s; reflect-loop and 8-card-page tails to 5 minutes.</p>')
            body.append(f'<div class="card">{_hist_svg(e2e_vals)}</div>')
    if live:
        body.append('<h2>Stage latency — live instrumented</h2>')
        body.append('<p class="sub">perf_counter-exact spans, including cross-cutting database and AI time '
                    '(not measurable from historical logs). Per-card rows overlap their stage wall — don\'t sum rows.</p>')
        body.append(f'<div class="card">{_range_svg(live, _ordered(live, skip=("ai_other", "asset_gate")))}'
                    f'{PCT_LEGEND}</div>')
    worst_src = mined or live
    if worst_src:
        body.append('<h2>Worst cases</h2>')
        body.append(_worst_list(worst_src, ["e2e", "layer2", "layer2_card", "executor", "validation"]))
    for name, st in (("mined", mined), ("live", live)):
        if st:
            body.append(f'<h2>Full statistics — {name}</h2>')
            body.append(_stats_table(st))
    body.append('<p class="note">Method: mined boundaries are timestamp deltas between pipeline stage records '
                '(coarse); mined AI durations are ±1s quantized (log ts − response.created). Live spans wrap the '
                'real stage functions via profiler/attach.py. Mined and live samples are never pooled. '
                'Regenerate: <code>python3 -m profiler.cli mine · live · report</code>.</p>')
    body.append('</div>')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    # pure-ASCII output: non-ASCII → numeric entities, so the page renders
    # correctly regardless of whether the serving layer declares a charset
    doc = "\n".join(body).encode("ascii", "xmlcharrefreplace").decode("ascii")
    with open(out_path, "w") as f:
        f.write(doc)
    return out_path


def main(out_dir):
    with open(os.path.join(out_dir, "summary.json")) as f:
        summary = json.load(f)

    def load(name):
        p = os.path.join(out_dir, name)
        if not os.path.exists(p):
            return []
        with open(p) as f:
            d = json.load(f)
        return d["samples"] if isinstance(d, dict) else d

    return render(summary, load("live_samples.json"), load("mined_samples.json"),
                  os.path.join(out_dir, "dashboard.html"))
