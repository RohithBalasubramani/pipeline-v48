"""tools/payload_diff/report_html.py — the visual rendering of a compare() report: ONE self-contained HTML file
(inline CSS, no external assets, dark + light via prefers-color-scheme). Layout: A/B provenance header → per-dimension
summary chips → a section per dimension with side-by-side A→B rows. Color language: green added / red removed /
amber changed / bold red for REAL→EMPTY regressions. Value-drift lists collapse by default (live data always drifts);
structural + emptied/filled entries stay expanded — they are the before/after signal."""
import html
import json


def _esc(v, n=160):
    if isinstance(v, (dict, list)):
        s = json.dumps(v, ensure_ascii=False)
    elif v is None:
        s = "∅"
    else:
        s = str(v)
    if len(s) > n:
        s = s[: n - 1] + "…"
    return html.escape(s)


_CSS = """
:root{--bg:#f7f7f8;--panel:#fff;--ink:#1a1a24;--muted:#6b6b76;--line:#e3e3e8;--add:#0a7d33;--add-bg:#e3f5e9;
--rem:#b42318;--rem-bg:#fbeae8;--chg:#8a5a00;--chg-bg:#fdf3dd;--accent:#3b5bdb;--mono:ui-monospace,SFMono-Regular,Menlo,monospace}
@media(prefers-color-scheme:dark){:root{--bg:#101014;--panel:#1a1a21;--ink:#e8e8ee;--muted:#8f8f9c;--line:#2a2a33;
--add:#4ade80;--add-bg:#12331d;--rem:#f87171;--rem-bg:#3a1512;--chg:#fbbf24;--chg-bg:#332708;--accent:#8da2fb}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;padding:24px}
h1{font-size:19px;margin:0 0 4px}h2{font-size:15px;margin:0 0 10px}
.sub{color:var(--muted);font-size:12px;margin-bottom:18px}
.prov{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px;overflow-x:auto}
.side{font-weight:700;font-size:11px;letter-spacing:.08em;color:var(--accent)}
.prompt{font-weight:600;margin:2px 0 6px;word-break:break-word}
.meta{color:var(--muted);font-size:12px;font-family:var(--mono)}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px}
.chip{border:1px solid var(--line);background:var(--panel);border-radius:999px;padding:4px 12px;font-size:12px}
.chip b{font-weight:600}.ok{color:var(--add)}.warn{color:var(--chg)}.bad{color:var(--rem);font-weight:700}.na{color:var(--muted)}
section{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin-bottom:14px;overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13px}
th{color:var(--muted);text-align:left;font-weight:500;font-size:11px;letter-spacing:.05em;text-transform:uppercase;
padding:4px 10px 6px 0;border-bottom:1px solid var(--line)}
td{padding:5px 10px 5px 0;border-bottom:1px solid var(--line);vertical-align:top;word-break:break-word}
tr:last-child td{border-bottom:none}
.path,.mono{font-family:var(--mono);font-size:12px}
.pill{display:inline-block;border-radius:5px;padding:1px 7px;font-size:11px;font-weight:600}
.p-add{background:var(--add-bg);color:var(--add)}.p-rem{background:var(--rem-bg);color:var(--rem)}
.p-chg{background:var(--chg-bg);color:var(--chg)}.p-reg{background:var(--rem-bg);color:var(--rem);border:1px solid var(--rem)}
.a{color:var(--rem)}.b{color:var(--add)}.arrow{color:var(--muted);padding:0 4px}
details{margin:6px 0}summary{cursor:pointer;color:var(--muted);font-size:13px}
summary b{color:var(--ink)}.empty{color:var(--muted);font-style:italic}
.sqlbox{font-family:var(--mono);font-size:12px;white-space:pre-wrap;word-break:break-word;padding:6px 8px;
border-radius:6px;margin:4px 0}
.sql-add{background:var(--add-bg)}.sql-rem{background:var(--rem-bg)}
"""


def _prov(report):
    cells = []
    for side in ("a", "b"):
        p = report["provenance"][side]
        git = p.get("git") or {}
        unav = p.get("unavailable") or {}
        unav_s = f"<div class='meta'>degraded: {_esc('; '.join(f'{k}: {v}' for k, v in unav.items()), 300)}</div>" if unav else ""
        cells.append(
            f"<div class='card'><div class='side'>{side.upper()}"
            + (f" · {_esc(p.get('label'))}" if p.get("label") else "") + "</div>"
            f"<div class='prompt'>{_esc(p.get('prompt'), 300)}</div>"
            f"<div class='meta'>{_esc(p.get('run_id'))}@{_esc(p.get('occurrence'))} · {_esc(p.get('source'))}"
            f" · git {_esc(git.get('sha'))}{'+dirty' if git.get('dirty') else ''}"
            f" · {_esc(p.get('captured_at'))}"
            + (f" · {p.get('elapsed_ms')} ms" if p.get("elapsed_ms") else "") + f"</div>{unav_s}</div>")
    return f"<div class='prov'>{''.join(cells)}</div>"


def _chip(name, r, extra=""):
    if "unavailable" in r:
        return f"<span class='chip'>{name}: <b class='na'>n/a</b></span>"
    cls = "ok" if r.get("same") else "warn"
    label = "same" if r.get("same") else "changed"
    return f"<span class='chip'>{name}: <b class='{cls}'>{label}</b>{extra}</span>"


def _ab_row(cols):
    return "<tr>" + "".join(f"<td>{c}</td>" for c in cols) + "</tr>"


def _field_table(changes, key_name="field"):
    if not changes:
        return "<div class='empty'>identical</div>"
    rows = "".join(_ab_row([f"<span class='path'>{_esc(c[key_name])}</span>",
                            f"<span class='a'>{_esc(c['a'])}</span>",
                            f"<span class='b'>{_esc(c['b'])}</span>"]) for c in changes)
    return f"<table><tr><th>{key_name}</th><th>A</th><th>B</th></tr>{rows}</table>"


def _entry_rows(entries):
    rows = []
    for e in entries:
        kind = e["kind"]
        pill = ("<span class='pill p-add'>added</span>" if kind == "added" else
                "<span class='pill p-rem'>removed</span>" if kind == "removed" else
                f"<span class='pill p-reg'>{e['sub']}</span>" if e.get("sub") == "emptied" else
                f"<span class='pill p-add'>{e['sub']}</span>" if e.get("sub") == "filled" else
                f"<span class='pill p-chg'>{_esc(kind)}</span>")
        note = f" <span class='meta'>{_esc(e['note'])}</span>" if e.get("note") else ""
        rows.append(_ab_row([f"<span class='path'>{_esc(e['path'], 90)}</span>", pill,
                             f"<span class='a'>{_esc(e.get('a'))}</span>",
                             f"<span class='b'>{_esc(e.get('b'))}</span>" + note]))
    return "".join(rows)


def _per_card_section(name, r, expand_value=False):
    if "unavailable" in r:
        return f"<section><h2>{name}</h2><div class='empty'>{_esc(r['unavailable'], 400)}</div></section>"
    parts = [f"<section><h2>{name}</h2>"]
    if r["only_b"]:
        parts.append("<div>" + " ".join(f"<span class='pill p-add'>+ {_esc(k)}</span>" for k in r["only_b"])
                     + " <span class='meta'>only in B</span></div>")
    if r["only_a"]:
        parts.append("<div>" + " ".join(f"<span class='pill p-rem'>− {_esc(k)}</span>" for k in r["only_a"])
                     + " <span class='meta'>only in A</span></div>")
    if not r["cards"]:
        parts.append(f"<div class='empty'>all {r['n_paired']} paired cards identical</div>")
    for c in r["cards"]:
        entries = c["entries"]
        headline = [e for e in entries if e["cls"] == "structural" or e.get("sub")]
        drift = [e for e in entries if e["cls"] == "value" and not e.get("sub")]
        badges = []
        if c.get("emptied"):
            badges.append(f"<span class='pill p-reg'>⚠ {c['emptied']} emptied</span>")
        if c.get("filled"):
            badges.append(f"<span class='pill p-add'>{c['filled']} filled</span>")
        if c.get("structural"):
            badges.append(f"<span class='pill p-chg'>{c['structural']} structural</span>")
        if drift:
            badges.append(f"<span class='pill p-chg'>{len(drift)} value</span>")
        parts.append(f"<details {'open' if headline else ''}><summary><b>{_esc(c['key'])}</b> {' '.join(badges)}</summary>")
        if headline:
            parts.append(f"<table><tr><th>path</th><th></th><th>A</th><th>B</th></tr>{_entry_rows(headline)}</table>")
        if drift:
            if expand_value:
                parts.append(f"<table><tr><th>path</th><th></th><th>A</th><th>B</th></tr>{_entry_rows(drift)}</table>")
            else:
                parts.append(f"<details><summary>{len(drift)} value change(s) — live-data drift</summary>"
                             f"<table><tr><th>path</th><th></th><th>A</th><th>B</th></tr>{_entry_rows(drift)}</table></details>")
        parts.append("</details>")
    parts.append("</section>")
    return "".join(parts)


def _sql_section(r):
    if "unavailable" in r:
        return f"<section><h2>sql</h2><div class='empty'>{_esc(r['unavailable'], 400)}</div></section>"
    parts = [f"<section><h2>sql</h2><div class='meta'>{r.get('n_a')} reads in A · {r.get('n_b')} reads in B</div>"]
    if r.get("note"):
        parts.append(f"<div class='meta'>⚠ {_esc(r['note'], 300)}</div>")
    if r.get("same"):
        parts.append("<div class='empty'>identical statement set and counts</div>")
    for title, items, cls in (("only in B", r.get("added", []), "sql-add"), ("only in A", r.get("removed", []), "sql-rem")):
        if items:
            parts.append(f"<details open><summary><b>{len(items)}</b> statement(s) {title}</summary>")
            for g in items:
                parts.append(f"<div class='sqlbox {cls}'>{_esc(g['sql'], 600)}"
                             f"<div class='meta'>×{g.get('n')} · table {_esc(g.get('table'))}</div></div>")
            parts.append("</details>")
    if r.get("recount"):
        rows = "".join(_ab_row([f"<span class='mono'>{_esc(g['sql'], 110)}</span>", _esc(g["n_a"]), _esc(g["n_b"])])
                       for g in r["recount"])
        parts.append(f"<details><summary>{len(r['recount'])} statement(s) with changed execution counts</summary>"
                     f"<table><tr><th>statement</th><th>A ×</th><th>B ×</th></tr>{rows}</table></details>")
    parts.append("</section>")
    return "".join(parts)


def _validation_section(r):
    if "unavailable" in r:
        return f"<section><h2>validation</h2><div class='empty'>{_esc(r['unavailable'], 400)}</div></section>"
    parts = ["<section><h2>validation</h2>"]
    if r.get("regressions"):
        parts.append(f"<div><span class='pill p-reg'>⚠ {r['regressions']} REAL→EMPTY regression(s)</span></div>")
    if r.get("page"):
        parts.append("<h2 style='margin-top:10px'>page-level</h2>" + _field_table(r["page"]))
    if r.get("cards"):
        rows = []
        for c in r["cards"]:
            v = (f"<span class='a'>{_esc(c['verdict_a'])}</span><span class='arrow'>→</span>"
                 f"<span class='b'>{_esc(c['verdict_b'])}</span>")
            leaves = f"real {c['real_a']}→{c['real_b']}"
            reg = "<span class='pill p-reg'>regression</span>" if c.get("regression") else ""
            fields = "; ".join(f"{ch['field']}: {_esc(ch['a'], 40)}→{_esc(ch['b'], 40)}" for ch in c["changes"][:6])
            rows.append(_ab_row([f"<b>{_esc(c['key'])}</b>", v, leaves, reg, f"<span class='meta'>{fields}</span>"]))
        parts.append("<table><tr><th>card</th><th>verdict</th><th>leaves</th><th></th><th>changes</th></tr>"
                     + "".join(rows) + "</table>")
    if not r.get("page") and not r.get("cards"):
        parts.append("<div class='empty'>identical</div>")
    parts.append("</section>")
    return "".join(parts)


def render(report, title="payload diff", expand_values=False):
    page, cards, meta, bind = report["page"], report["cards"], report["metadata"], report["bindings"]
    val, pay, cfgd = report["validation"], report["payload"], report["config"]
    regr = val.get("regressions", 0) if "unavailable" not in val else 0
    emptied = pay["totals"]["emptied"] if "unavailable" not in pay else 0
    chips = [
        _chip("page", page),
        _chip("cards", cards, "" if "unavailable" in cards else
              f" <span class='meta'>+{len(cards['only_b'])}/−{len(cards['only_a'])}</span>"),
        _chip("metadata", meta), _chip("bindings", bind), _chip("sql", report["sql"]),
        _chip("validation", val, f" <b class='bad'>⚠ {regr} regr</b>" if regr else ""),
        _chip("payload", pay, f" <b class='bad'>⚠ {emptied} emptied</b>" if emptied else ""),
        _chip("config", cfgd),
    ]
    body = [
        f"<h1>{_esc(title)}</h1>",
        f"<div class='sub'>tolerance ±{report.get('tol', 0) * 100:g}% on numeric values · generated by tools/payload_diff</div>",
        _prov(report), f"<div class='chips'>{''.join(chips)}</div>",
        "<section><h2>page</h2>" + ("<div class='empty'>" + _esc(page["unavailable"], 400) + "</div>"
                                    if "unavailable" in page else _field_table(page["changes"])) + "</section>",
        _per_card_section("cards (identity / slot / swap)", cards, expand_value=True),
        _per_card_section("metadata", meta, expand_value=True),
        _per_card_section("bindings (data_instructions)", bind, expand_value=True),
        _sql_section(report["sql"]),
        _validation_section(val),
        _per_card_section("renderer payload", pay, expand_value=expand_values),
        "<section><h2>config (cmd_catalog.app_config)</h2>"
        + ("<div class='empty'>" + _esc(cfgd["unavailable"], 400) + "</div>" if "unavailable" in cfgd else
           ((f"<div class='meta'>⚠ {_esc(cfgd['note'], 300)}</div>" if cfgd.get("note") else "")
            + _field_table(cfgd["changes"], key_name="key"))) + "</section>",
    ]
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'><title>{_esc(title)}</title>"
            f"<style>{_CSS}</style></head><body>{''.join(body)}</body></html>")
