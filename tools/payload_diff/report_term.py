"""tools/payload_diff/report_term.py — the terminal rendering of a compare() report: one line per dimension, honest
about degraded dimensions, REAL→EMPTY regressions called out loudly. ANSI color only when stdout is a tty."""
import sys


def _c(code, s):
    return f"\033[{code}m{s}\033[0m" if sys.stdout.isatty() else str(s)


def _status(same, detail=""):
    if same:
        return _c(32, "SAME")
    return _c(33, "CHANGED") + (f"  {detail}" if detail else "")


def _fmt(v, n=60):
    s = repr(v) if not isinstance(v, str) else v
    return s if len(s) <= n else s[: n - 1] + "…"


def render(report):
    lines = []
    pa, pb = report["provenance"]["a"], report["provenance"]["b"]
    lines.append(_c(1, "payload_diff"))
    for side, p in (("A", pa), ("B", pb)):
        git = p.get("git") or {}
        dirty = "+dirty" if git.get("dirty") else ""
        lines.append(f"  {side}: {_fmt(p.get('prompt'), 70)}  [{p.get('run_id')}@{p.get('occurrence')}"
                     f" {p.get('source')} git {git.get('sha')}{dirty}"
                     + (f" label={p['label']}" if p.get("label") else "") + "]")

    def dim(name, r, detail=""):
        if "unavailable" in r:
            lines.append(f"  {name:<10} {_c(90, 'n/a')}      {r['unavailable']}")
        else:
            lines.append(f"  {name:<10} {_status(r.get('same'), detail)}")

    page = report["page"]
    dim("page", page, "" if "unavailable" in page else
        "; ".join(f"{ch['field']}: {_fmt(ch['a'], 24)} → {_fmt(ch['b'], 24)}" for ch in page.get("changes", [])[:4]))

    for name in ("cards", "metadata", "bindings"):
        r = report[name]
        if "unavailable" not in r:
            parts = []
            if r["only_b"]:
                parts.append(f"+{len(r['only_b'])} added")
            if r["only_a"]:
                parts.append(f"-{len(r['only_a'])} removed")
            if r["n_changed"]:
                parts.append(f"{r['n_changed']}/{r['n_paired']} cards changed")
            dim(name, r, ", ".join(parts))
        else:
            dim(name, r)

    sql = report["sql"]
    dim("sql", sql, "" if "unavailable" in sql else
        f"+{len(sql.get('added', []))} / -{len(sql.get('removed', []))} statements, "
        f"{len(sql.get('recount', []))} recounts ({sql.get('n_a')} → {sql.get('n_b')} reads)"
        + (f"\n             {_c(33, '⚠ ' + sql['note'])}" if sql.get("note") else ""))

    val = report["validation"]
    if "unavailable" in val:
        dim("validation", val)
    else:
        regr = val.get("regressions", 0)
        detail = f"{len(val.get('cards', []))} card verdict/leaf changes, {len(val.get('page', []))} page changes"
        if regr:
            detail += "  " + _c(31, f"⚠ {regr} REAL→EMPTY regression(s)")
        dim("validation", val, detail)

    pay = report["payload"]
    if "unavailable" not in pay:
        t = pay["totals"]
        added_removed = "".join([f"+{len(pay['only_b'])} added, " if pay["only_b"] else "",
                                 f"-{len(pay['only_a'])} removed, " if pay["only_a"] else ""])
        detail = (f"{added_removed}{pay['n_changed']}/{pay['n_paired']} paired cards: "
                  f"{t['structural']} structural, {t['value']} value")
        if t["emptied"]:
            detail += "  " + _c(31, f"⚠ {t['emptied']} emptied leaf/series")
        if t["filled"]:
            detail += "  " + _c(32, f"+{t['filled']} filled")
        dim("payload", pay, detail)
    else:
        dim("payload", pay)

    cfgd = report["config"]
    dim("config", cfgd, "" if "unavailable" in cfgd else
        "; ".join(f"{ch['key']}: {_fmt(ch['a'], 16)} → {_fmt(ch['b'], 16)}" for ch in cfgd.get("changes", [])[:4]))

    return "\n".join(lines)
