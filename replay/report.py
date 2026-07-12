"""replay/report.py — comparison dict → (a) a compact terminal summary, (b) a self-contained side-by-side HTML
report (original left, replay right, per-section severity chips, changed paths highlighted). No external assets."""
import html
import json

_SEV_COLOR = {"identical": "#2da44e", "drift": "#d4a72c", "missing": "#a475f9", "diverged": "#f85149"}
_SEV_LABEL = {"identical": "IDENTICAL", "drift": "DRIFT", "missing": "MISSING", "diverged": "DIVERGED"}


def terminal_summary(cmp):
    lines = []
    o, r = cmp.get("original") or {}, cmp.get("replay") or {}
    lines.append(f"REPLAY {r.get('trace_id')}  of  {o.get('trace_id')}   overall: {cmp.get('overall', '?').upper()}")
    if o.get("prompt"):
        lines.append(f'prompt: "{str(o["prompt"])[:100]}"')
    tape = cmp.get("tape") or {}
    if tape:
        st = tape.get("stats") or {}
        lines.append(f"mode={tape.get('mode')} pins={','.join(tape.get('pins') or [])} "
                     f"tape: {st.get('hits', 0)} hits / {st.get('repeats', 0)} repeats / "
                     f"{st.get('fuzzy', 0)} fuzzy / {st.get('misses', 0)} misses"
                     + (f" / {len(tape.get('unconsumed_llm') or [])} original llm calls never replayed"
                        if tape.get("unconsumed_llm") else ""))
    lines.append(f"{'section':<18} {'severity':<10} detail")
    for name, sec in (cmp.get("sections") or {}).items():
        sev = sec.get("severity", "?")
        detail = ""
        if name == "ai_calls":
            detail = f"{sec.get('n_differing', 0)}/{max((sec.get('n_calls') or {}).get('original', 0), (sec.get('n_calls') or {}).get('replay', 0))} calls differ"
        elif name == "sql":
            detail = (f"{len(sec.get('changed_results') or [])} changed, {len(sec.get('only_original') or [])}+"
                      f"{len(sec.get('only_replay') or [])} unmatched, {len(sec.get('tape_misses') or [])} tape misses")
        elif name == "page_selection" and sec.get("original_page"):
            detail = (sec["original_page"] if sec["original_page"] == sec.get("replay_page")
                      else f"{sec['original_page']} → {sec.get('replay_page')}")
        elif name == "executor":
            detail = f"{sum(1 for c in sec.get('cards') or [] if c.get('severity') != 'identical')} card(s) differ"
        elif name == "rendering":
            detail = f"{len(sec.get('cards_differing') or [])} card(s) differ"
        elif name == "timing":
            detail = (f"orig {((sec.get('original') or {}).get('elapsed_ms') or 0) / 1000:.1f}s → "
                      f"replay {((sec.get('replay') or {}).get('elapsed_ms') or 0) / 1000:.1f}s (informational)")
        elif sec.get("n_diffs") is not None:
            detail = f"{sec['n_diffs']} diff(s)"
        lines.append(f"{name:<18} {sev:<10} {detail}")
    return "\n".join(lines)


def render_html(cmp):
    o, r = cmp.get("original") or {}, cmp.get("replay") or {}
    parts = [_HEAD, "<body><main>"]
    parts.append(f"<h1>V48 replay comparison <span class='chip' style='background:{_SEV_COLOR.get(cmp.get('overall'), '#888')}'>"
                 f"{_SEV_LABEL.get(cmp.get('overall'), '?')}</span></h1>")
    parts.append("<table class='meta'><tr><th></th><th>original</th><th>replay</th></tr>")
    for label, key in (("trace", "trace_id"), ("started", "started_at"), ("git", "git_sha")):
        parts.append(f"<tr><td>{label}</td><td>{_e(o.get(key))}</td><td>{_e(r.get(key))}</td></tr>")
    parts.append(f"<tr><td>prompt</td><td colspan=2 class='prompt'>{_e(o.get('prompt'))}</td></tr></table>")
    tape = cmp.get("tape") or {}
    if tape:
        st = tape.get("stats") or {}
        parts.append(f"<p class='tape'>mode <b>{_e(tape.get('mode'))}</b> · pins {_e(','.join(tape.get('pins') or []) or '—')} · "
                     f"tape {st.get('hits', 0)} hits / {st.get('repeats', 0)} repeats / <b>{st.get('fuzzy', 0)} fuzzy</b> / "
                     f"<b>{st.get('misses', 0)} misses</b> · {len(tape.get('unconsumed_llm') or [])} original LLM calls never replayed</p>")
    for name, sec in (cmp.get("sections") or {}).items():
        parts.append(_section_html(name, sec))
    parts.append("</main></body>")
    return "\n".join(parts)


def _section_html(name, sec):
    sev = sec.get("severity", "?")
    open_attr = "" if sev == "identical" or sec.get("informational") else " open"
    h = [f"<details{open_attr}><summary><span class='chip' style='background:{_SEV_COLOR.get(sev, '#888')}'>"
         f"{_SEV_LABEL.get(sev, sev)}</span> <b>{_e(name)}</b></summary><div class='body'>"]
    if name == "ai_calls":
        h.append(_ai_html(sec))
    elif name == "sql":
        h.append(_sql_html(sec))
    elif name in ("executor",):
        h.append(_cards_html(sec.get("cards") or [], id_key="card_id"))
    elif name == "rendering":
        h.append(_diff_table(sec.get("flag_diff") or []))
        h.append(_cards_html(sec.get("cards_differing") or [], id_key="card"))
    elif name == "timing":
        h.append("<table class='diff'><tr><th></th><th>original</th><th>replay</th></tr>" +
                 "".join(f"<tr><td>{k}</td><td>{_e((sec.get('original') or {}).get(k))}</td>"
                         f"<td>{_e((sec.get('replay') or {}).get(k))}</td></tr>"
                         for k in ("elapsed_ms", "llm_ms", "sql_ms", "n_events")) + "</table>")
    else:
        for extra in ("lanes_only_original", "lanes_only_replay"):
            if sec.get(extra):
                h.append(f"<p class='warn'>{extra}: {_e(sec[extra])}</p>")
        h.append(_diff_table(sec.get("diffs") or []))
    h.append("</div></details>")
    return "".join(h)


def _ai_html(sec):
    h = ["<table class='diff'><tr><th>stage</th><th>#</th><th>status</th><th>served</th><th>detail</th></tr>"]
    for c in sec.get("calls") or []:
        detail = ""
        if c.get("prompt_diff"):
            for part, d in c["prompt_diff"].items():
                detail += (f"<div class='pd'><b>{part}</b> len {d['len'][0]}→{d['len'][1]}, first diff @{d['first_diff_at']}"
                           f"<div class='sxs'><pre>{_e(d['original_excerpt'])}</pre><pre>{_e(d['replay_excerpt'])}</pre></div></div>")
        if c.get("value_diff"):
            detail += _diff_table(c["value_diff"])
        color = _SEV_COLOR.get(c.get("severity"), "#888")
        h.append(f"<tr><td>{_e(c.get('stage'))}</td><td>{c.get('n')}</td>"
                 f"<td style='color:{color}'>{_e(c.get('status'))}</td><td>{_e(c.get('served') or '—')}</td>"
                 f"<td>{detail or '—'}</td></tr>")
    h.append("</table>")
    return "".join(h)


def _sql_html(sec):
    h = []
    for label, rows in (("changed results", sec.get("changed_results")), ("only in original", sec.get("only_original")),
                        ("only in replay", sec.get("only_replay")), ("tape misses", sec.get("tape_misses"))):
        if rows:
            h.append(f"<p class='warn'>{label} ({len(rows)})</p><table class='diff'>")
            for e in rows[:100]:
                h.append(f"<tr><td class='sql'>{_e(str(e.get('sql') or e))[:400]}</td>"
                         f"<td>{_e(e.get('n_rows'))}</td></tr>")
            if len(rows) > 100:
                h.append(f"<tr><td colspan=2>… {len(rows) - 100} more (see comparison.json)</td></tr>")
            h.append("</table>")
    return "".join(h) or "<p>all recorded queries matched with identical results</p>"


def _cards_html(cards, id_key):
    if not cards:
        return "<p>no per-card differences</p>"
    h = []
    for c in cards:
        sev = c.get("severity", "?")
        h.append(f"<details><summary><span class='chip' style='background:{_SEV_COLOR.get(sev, '#888')}'>{_SEV_LABEL.get(sev, sev)}</span> "
                 f"card {_e(c.get(id_key))} {_e(c.get('title') or '')} {_e(c.get('status') or '')}</summary>")
        h.append(_diff_table(c.get("diffs") or []))
        h.append("</details>")
    return "".join(h)


def _diff_table(entries):
    if not entries:
        return "<p>—</p>"
    h = ["<table class='diff'><tr><th>path</th><th>kind</th><th>original</th><th>replay</th></tr>"]
    for e in entries:
        cls = "structural" if e.get("cls") == "structural" else ("emptied" if e.get("sub") == "emptied" else "value")
        h.append(f"<tr class='{cls}'><td>{_e(e.get('path'))}</td><td>{_e(e.get('kind'))}"
                 f"{('/' + e['sub']) if e.get('sub') else ''}</td>"
                 f"<td>{_v(e.get('a'))}</td><td>{_v(e.get('b'))}</td></tr>")
    h.append("</table>")
    return "".join(h)


def _v(x):
    s = x if isinstance(x, str) else json.dumps(x, default=str)
    return f"<pre>{_e(s[:600])}{'…' if len(s) > 600 else ''}</pre>"


def _e(x):
    return html.escape("" if x is None else str(x))


_HEAD = """<meta charset="utf-8"><title>V48 replay comparison</title><style>
:root{color-scheme:light dark}body{font:14px/1.5 system-ui,sans-serif;margin:0;background:Canvas;color:CanvasText}
main{max-width:1200px;margin:0 auto;padding:24px}h1{font-size:20px}
.chip{color:#fff;border-radius:10px;padding:2px 10px;font-size:12px;font-weight:600;vertical-align:middle}
table.meta,table.diff{border-collapse:collapse;width:100%;margin:8px 0}
table td,table th{border:1px solid color-mix(in srgb,CanvasText 18%,transparent);padding:4px 8px;text-align:left;vertical-align:top}
th{font-size:12px;opacity:.75}pre{margin:0;white-space:pre-wrap;word-break:break-word;font-size:12px;max-height:220px;overflow:auto}
details{border:1px solid color-mix(in srgb,CanvasText 15%,transparent);border-radius:8px;margin:10px 0;padding:2px 10px}
summary{cursor:pointer;padding:8px 0;font-size:15px}.body{padding:4px 0 12px}
tr.structural td{background:color-mix(in srgb,#f85149 12%,transparent)}
tr.emptied td{background:color-mix(in srgb,#a475f9 12%,transparent)}
.warn{color:#d4a72c;font-weight:600}.prompt{font-style:italic}.tape{opacity:.85}
.sxs{display:grid;grid-template-columns:1fr 1fr;gap:6px}.sxs pre{border:1px solid color-mix(in srgb,CanvasText 15%,transparent);padding:4px}
td.sql{font-family:ui-monospace,monospace;font-size:12px}.pd{margin:4px 0}
</style>"""
