#!/usr/bin/env python3
"""tools/fab_guards_shadow_replay.py — THE FLEET-AUDIT ACCEPTANCE INSTRUMENT for the fab_guards rework.

WHAT IT IS
  With `fab_guards.mode='report'` set live, every card's served payload is UNMUTATED but carries the would-blank
  "shadow" gap records the guards WOULD have blanked in 'enforce' mode. This tool drives the whole fleet (the 19
  page-shells), collects those per-card gap records, and produces a verdict table = the before/after acceptance
  artifact for judging the guard rework.

WHERE THE GAPS LIVE  (interface — confirmed against real saved responses, trusted)
  A run response (POST /api/run) has top-level `cards` (list). Each card carries `card_id` (int), `title`, `payload`,
  and `render`. The per-leaf honest-gap records are attached by the host at the serve boundary to:
        cards[i].render.gaps      -> [{slot, cause, metric, column, fn, reason, card_id?, shadow?}, ...]
  In report/shadow mode a card's payload may instead still carry the raw records under the GAPS_KEY:
        cards[i].payload._blank_gaps
  This tool reads BOTH (render.gaps first, then _blank_gaps) so it works in enforce AND report mode, before OR after
  the rework. Cause is OPEN VOCABULARY (no_reading / column_absent / structurally_null / derivation_unbound /
  no_nameplate / unbound_by_emit / quantity_mismatch, plus the rework's CLASS causes epoch_ms_leak /
  null_column_reading / no_source_value / unstripped_seed) — the tool never hardcodes the set, it tallies whatever
  cause string each record carries.

MODES  (argparse)
  --render                POST every fleet prompt (throttled, max --concurrency=3, vLLM-contention-safe), saving each
                          response to <out>/renders/<stem>.json.
  --analyze <dir>         Read saved responses from <dir> (and <dir>/renders/), extract every card's guard gaps, emit
                          <out>/VERDICTS.md + <out>/verdicts.json.
  (no mode)               render THEN analyze.
  --diff <base> <cand>    Diff two verdicts.json files by (card_id, cause, slot): NEW gaps (cand has, base lacks) and
                          DROPPED gaps (base has, cand lacks) — how a rework's effect is judged.

  --prompts <file>        Override the built-in fleet list. One case per line:  stem|prompt        (asset pin optional)
                                                                                stem|prompt|asset_id
  --out <dir>             Output root (default outputs/fab_guards_audit_<YYYYMMDD>).
  --host <url>            Run endpoint (default http://127.0.0.1:8770/api/run).
  --concurrency <n>       Max concurrent renders (default 3).
  --timeout <s>           Per-request timeout seconds (default 300).

SAFETY
  Pure stdlib (json/os/argparse/urllib/concurrent.futures). Imports NO heavy pipeline module. Never raises on a bad
  response file (skips + counts). ASCII-SAFE printing throughout: neuract label strings carry lone surrogates, so any
  label that is printed OR written to markdown is run through .encode('ascii','replace').decode() first.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import Counter, defaultdict, OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# ── interface constants (mirror ems_exec/executor/gaps.py) ───────────────────────────────────────────────────────
GAPS_KEY = "_blank_gaps"            # raw record home inside an unmutated (report-mode) payload
DEFAULT_HOST = "http://127.0.0.1:8770/api/run"

# ── the fleet: the 19 page-shells (exact prompts from render_pages.sh), with the asset_id:171 pin on every
#    "Transformer 01" case (it now resolves AMBIGUOUS and would otherwise bounce to the AssetPicker with no cards). ──
_TX = 171
PROMPTS = [
    # (stem, prompt, asset_id | None)
    ("feeder_rtm",              "real-time monitoring for Transformer 01",            _TX),
    ("feeder_energy_power",     "energy and power for Transformer 01",                _TX),
    ("feeder_voltage_current",  "voltage and current for Transformer 01",             _TX),
    ("feeder_power_quality",    "power quality for Transformer 01",                   _TX),
    ("transformer_thermal_life","winding temperature and life for Transformer 01",   _TX),
    ("transformer_tap_rtcc",    "tap changer position and rtcc for Transformer 01",  _TX),
    ("ups_battery_autonomy",    "battery autonomy for GIC-01-N3-UPS-01",              None),
    ("ups_output_load",         "output load and capacity for GIC-01-N3-UPS-01",      None),
    ("ups_source_transfer",     "source transfer for GIC-01-N3-UPS-01",               None),
    ("dg_engine_cooling",       "engine cooling temperature for DG-1",                None),
    ("dg_fuel_efficiency",      "fuel efficiency for DG-1",                           None),
    ("dg_operations_runtime",   "operations and runtime hours for DG-1",             None),
    ("dg_voltage_current",      "voltage and current for DG-1",                       None),
    ("panel_energy_distribution","energy distribution for PCC-1A",                    None),
    ("panel_energy_power",      "energy and power for PCC-1A",                        None),
    ("panel_harmonics_pq",      "harmonics and power quality for PCC-1A",             None),
    ("panel_rtm",               "real-time monitoring for PCC-1A",                    None),
    ("panel_voltage_current",   "voltage and current for PCC-1A",                     None),
    ("asset_overview",          "overview of Transformer 01",                         _TX),
]


# ── ascii-safe helpers ───────────────────────────────────────────────────────────────────────────────────────────
def A(s) -> str:
    """ASCII-fold any value for safe printing / markdown. Lone surrogates in neuract names never reach a terminal."""
    if s is None:
        return ""
    try:
        return str(s).encode("ascii", "replace").decode("ascii")
    except Exception:
        return repr(s)


def _cell(s) -> str:
    """ASCII cell safe to drop into a markdown table (escape the pipe, collapse newlines)."""
    return A(s).replace("|", "\\|").replace("\n", " ").strip()


# ── extraction ───────────────────────────────────────────────────────────────────────────────────────────────────
def _gaps_of_card(card) -> list:
    """Every gap record for one card: the fab_guards SHADOW channel (payload._shadow_gaps — report-mode would-blanks
    that survive the stale-gap prune) UNION render.gaps / payload._blank_gaps (enforce-mode + roster/emit gaps). The
    shadow channel is the fab_guards audit substrate; the others carry the non-guard reason causes for context."""
    if not isinstance(card, dict):
        return []
    out = []
    p = card.get("payload")
    if isinstance(p, dict):
        sg = p.get("_shadow_gaps")           # fab_guards report-mode would-blanks (un-pruned dedicated channel)
        if isinstance(sg, list):
            out.extend(x for x in sg if isinstance(x, dict))
    r = card.get("render")
    if isinstance(r, dict):
        g = r.get("gaps")
        if isinstance(g, list):
            out.extend(x for x in g if isinstance(x, dict))
    if isinstance(p, dict):
        g = p.get(GAPS_KEY)
        if isinstance(g, list):
            out.extend(x for x in g if isinstance(x, dict))
    return out


def _rows_from_response(stem: str, resp) -> list:
    """Flat gap rows for one saved response. Never raises. page = the file stem (page-shell/tab identity)."""
    rows = []
    if not isinstance(resp, dict):
        return rows
    cards = resp.get("cards")
    if not isinstance(cards, list):
        return rows
    page_key = ((resp.get("page") or {}) if isinstance(resp.get("page"), dict) else {}).get("page_key")
    for c in cards:
        if not isinstance(c, dict):
            continue
        cid = c.get("card_id")
        title = c.get("title")
        for g in _gaps_of_card(c):
            # per-gap card_id (rework) overrides the card's id when present; else fall back to the card object's id
            gcid = g.get("card_id", cid)
            rows.append({
                "page": stem,
                "page_key": page_key,
                "card_id": gcid,
                "title": title,
                "cause": g.get("cause"),
                "slot": g.get("slot"),
                "column": g.get("column"),
                "metric": g.get("metric"),
                "fn": g.get("fn"),
                "shadow": bool(g.get("shadow", False)),
            })
    return rows


def _iter_response_files(d: str):
    """Response JSON files under <d> and <d>/renders/, excluding our own verdicts.json output. De-duped, sorted."""
    seen = OrderedDict()
    for pat in (os.path.join(d, "*.json"), os.path.join(d, "renders", "*.json")):
        for f in sorted(glob.glob(pat)):
            base = os.path.basename(f)
            if base == "verdicts.json":
                continue
            seen.setdefault(os.path.abspath(f), f)
    return list(seen.values())


def analyze_dir(d: str):
    """Read every response under <d>, return (rows, stats). Bad/irrelevant files are skipped + counted, never fatal."""
    rows = []
    stats = {"files": 0, "parsed": 0, "skipped": 0, "no_cards": 0}
    for f in _iter_response_files(d):
        stats["files"] += 1
        stem = os.path.splitext(os.path.basename(f))[0]
        try:
            with open(f, "r", encoding="utf-8", errors="replace") as fh:
                resp = json.load(fh)
        except Exception:
            stats["skipped"] += 1
            continue
        if not (isinstance(resp, dict) and isinstance(resp.get("cards"), list)):
            stats["no_cards"] += 1
            continue
        stats["parsed"] += 1
        rows.extend(_rows_from_response(stem, resp))
    return rows, stats


# ── verdict artifacts ────────────────────────────────────────────────────────────────────────────────────────────
def write_verdicts(rows: list, stats: dict, out_dir: str, src_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, "verdicts.json")
    md_path = os.path.join(out_dir, "VERDICTS.md")

    # machine-readable flat rows (one per gap record) — the diff substrate
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump([{k: r[k] for k in ("page", "page_key", "card_id", "title", "cause",
                                       "slot", "column", "metric", "fn", "shadow")} for r in rows],
                  fh, ensure_ascii=True, indent=2)

    # rollups
    per_cause = Counter(r["cause"] for r in rows)
    shadow_n = sum(1 for r in rows if r["shadow"])
    enforce_n = len(rows) - shadow_n

    # (card_id, cause) aggregate with an example slot/column, plus a clean ascii title
    agg = defaultdict(lambda: {"count": 0, "title": "", "page": "", "slot": "", "column": ""})
    for r in rows:
        k = (r["card_id"], r["cause"])
        a = agg[k]
        a["count"] += 1
        if not a["title"] and r["title"]:
            a["title"] = r["title"]
        if not a["page"]:
            a["page"] = r["page"]
        if not a["slot"] and r["slot"]:
            a["slot"] = r["slot"]
        if not a["column"] and r["column"]:
            a["column"] = r["column"]
    agg_sorted = sorted(agg.items(), key=lambda kv: (-kv[1]["count"], str(kv[0][0]), str(kv[0][1])))

    # per-page rollup
    per_page = defaultdict(lambda: defaultdict(Counter))   # page -> card_id -> cause -> count
    page_title = {}
    for r in rows:
        per_page[r["page"]][r["card_id"]][r["cause"]] += 1
        page_title.setdefault(r["page"], r["page_key"])

    L = []
    L.append("# fab_guards SHADOW-REPLAY VERDICTS")
    L.append("")
    L.append(f"- generated: {datetime.now().isoformat(timespec='seconds')}")
    L.append(f"- source: `{A(src_dir)}`")
    L.append(f"- response files: {stats['files']}  (parsed {stats['parsed']}, "
             f"skipped {stats['skipped']}, no-cards {stats['no_cards']})")
    L.append(f"- total gap records: {len(rows)}  (shadow {shadow_n} / enforce {enforce_n})")
    L.append(f"- distinct (card, cause) pairs: {len(agg)}")
    L.append("")

    L.append("## Per-cause rollup")
    L.append("")
    L.append("| cause | count |")
    L.append("| --- | ---: |")
    for cause, n in sorted(per_cause.items(), key=lambda kv: (-kv[1], str(kv[0]))):
        L.append(f"| {_cell(cause)} | {n} |")
    L.append("")

    L.append("## Verdict table  (card x cause, by count desc)")
    L.append("")
    L.append("| card_id | title | cause | count | example slot | example column |")
    L.append("| ---: | --- | --- | ---: | --- | --- |")
    for (cid, cause), a in agg_sorted:
        L.append(f"| {_cell(cid)} | {_cell(a['title'])} | {_cell(cause)} | {a['count']} "
                 f"| {_cell(a['slot'])} | {_cell(a['column'])} |")
    L.append("")

    L.append("## Per-page sections")
    L.append("")
    for page in sorted(per_page):
        pk = page_title.get(page)
        L.append(f"### {_cell(page)}" + (f"  ({_cell(pk)})" if pk else ""))
        L.append("")
        L.append("| card_id | cause | count |")
        L.append("| ---: | --- | ---: |")
        for cid in sorted(per_page[page], key=lambda x: str(x)):
            for cause, n in sorted(per_page[page][cid].items(), key=lambda kv: (-kv[1], str(kv[0]))):
                L.append(f"| {_cell(cid)} | {_cell(cause)} | {n} |")
        L.append("")

    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    return md_path, json_path, agg_sorted, per_cause, (len(rows), shadow_n, enforce_n)


def print_verdict_table(agg_sorted, per_cause, totals, limit=40):
    total, shadow_n, enforce_n = totals
    print(f"\nTOTAL gap records: {total}  (shadow {shadow_n} / enforce {enforce_n})")
    print("\nPer-cause rollup:")
    for cause, n in sorted(per_cause.items(), key=lambda kv: (-kv[1], str(kv[0]))):
        print(f"  {A(cause):24s} {n:5d}")
    print(f"\nVerdict table (top {limit} of {len(agg_sorted)} card x cause pairs):")
    hdr = f"  {'card':>5}  {'cause':22}  {'cnt':>4}  {'title':30}  example_slot"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for (cid, cause), a in agg_sorted[:limit]:
        print(f"  {A(cid):>5}  {A(cause):22.22}  {a['count']:>4}  {A(a['title']):30.30}  {A(a['slot'])}")
    if len(agg_sorted) > limit:
        print(f"  ... {len(agg_sorted) - limit} more pairs (see VERDICTS.md)")


# ── render (drive the fleet) ─────────────────────────────────────────────────────────────────────────────────────
def _post(host: str, prompt: str, asset_id, timeout: float):
    """POST one run. Returns (http_code:int, body:bytes|None, err:str|None). urllib only."""
    import urllib.request
    import urllib.error
    body = {"prompt": prompt}
    if asset_id is not None:
        body["asset_id"] = int(asset_id)
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(host, data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode(), resp.read(), None
    except urllib.error.HTTPError as e:
        try:
            payload = e.read()
        except Exception:
            payload = None
        return e.code, payload, f"HTTP {e.code}"
    except Exception as e:
        return 0, None, f"{type(e).__name__}: {A(e)}"


def _summary_of(resp) -> str:
    if not isinstance(resp, dict):
        return "non-dict response"
    a = resp.get("asset") or {}
    cards = resp.get("cards") or []
    gapn = sum(len(_gaps_of_card(c)) for c in cards if isinstance(c, dict))
    pend = " ASSET_PENDING" if resp.get("asset_pending") else ""
    pk = (resp.get("page") or {}).get("page_key") if isinstance(resp.get("page"), dict) else None
    return (f"asset={A(a.get('name'))} mfm={A(a.get('mfm_id'))} page={A(pk)} "
            f"cards={len(cards)} gaps={gapn}{pend}")


def render_fleet(prompts, host: str, out_dir: str, concurrency: int, timeout: float) -> str:
    renders_dir = os.path.join(out_dir, "renders")
    os.makedirs(renders_dir, exist_ok=True)

    def one(entry):
        stem, prompt, asset_id = entry
        code, body, err = _post(host, prompt, asset_id, timeout)
        path = os.path.join(renders_dir, f"{stem}.json")
        info = err or ""
        if body is not None:
            try:
                with open(path, "wb") as fh:
                    fh.write(body)
            except Exception as e:
                info = f"write-fail {A(e)}"
            try:
                info = _summary_of(json.loads(body.decode("utf-8", "replace")))
            except Exception as e:
                info = info or f"parse-fail {A(e)}"
        return stem, code, info

    print(f"Rendering {len(prompts)} pages -> {renders_dir}  (host={host}, concurrency={concurrency})")
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as ex:
        futs = {ex.submit(one, e): e[0] for e in prompts}
        for fut in as_completed(futs):
            try:
                stem, code, info = fut.result()
            except Exception as e:
                print(f"  [ERR] {A(futs[fut])} :: {A(e)}")
                continue
            print(f"  [{code}] {A(stem):26.26} :: {info}")
    print(f"=== RENDER COMPLETE -> {renders_dir} ===")
    return renders_dir


# ── diff (baseline vs candidate verdicts.json) ───────────────────────────────────────────────────────────────────
def _load_verdicts_json(path: str) -> list:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        data = json.load(fh)
    return data if isinstance(data, list) else []


def _diff_key(r):
    return (r.get("card_id"), r.get("cause"), r.get("slot"))


def run_diff(baseline_path: str, candidate_path: str) -> int:
    try:
        base = _load_verdicts_json(baseline_path)
        cand = _load_verdicts_json(candidate_path)
    except Exception as e:
        print(f"diff load error: {A(e)}")
        return 2
    base_map = {_diff_key(r): r for r in base}
    cand_map = {_diff_key(r): r for r in cand}
    new_keys = [k for k in cand_map if k not in base_map]
    dropped_keys = [k for k in base_map if k not in cand_map]

    def _fmt(k, r):
        cid, cause, slot = k
        return f"  card {A(cid):>5}  {A(cause):22.22}  slot={A(slot)}  metric={A(r.get('metric'))}"

    print(f"\nDIFF  baseline={A(baseline_path)}  candidate={A(candidate_path)}")
    print(f"  baseline gaps: {len(base)}   candidate gaps: {len(cand)}")
    print(f"\nNEW gaps (candidate has, baseline lacks) = {len(new_keys)}   << INVESTIGATE each")
    for k in sorted(new_keys, key=lambda x: (str(x[0]), str(x[1]), str(x[2]))):
        print(_fmt(k, cand_map[k]))
    print(f"\nDROPPED gaps (baseline has, candidate lacks) = {len(dropped_keys)}   << false-positive fixed / leaf now real")
    for k in sorted(dropped_keys, key=lambda x: (str(x[0]), str(x[1]), str(x[2]))):
        print(_fmt(k, base_map[k]))
    print("")
    # exit 2 signals "there are NEW gaps to investigate" — useful in a CI gate for the rework
    return 2 if new_keys else 0


# ── prompt-file override ─────────────────────────────────────────────────────────────────────────────────────────
def load_prompts_file(path: str) -> list:
    out = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            parts = ln.split("|")
            if len(parts) < 2:
                continue
            stem, prompt = parts[0].strip(), parts[1].strip()
            asset_id = None
            if len(parts) >= 3 and parts[2].strip():
                try:
                    asset_id = int(parts[2].strip())
                except Exception:
                    asset_id = None
            out.append((stem, prompt, asset_id))
    return out


# ── CLI ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="fab_guards shadow-replay: fleet-audit acceptance instrument for the guard rework.")
    ap.add_argument("--render", action="store_true", help="POST every fleet prompt, save responses (throttled)")
    ap.add_argument("--analyze", metavar="DIR", help="analyze saved responses in DIR (+ DIR/renders)")
    ap.add_argument("--diff", nargs=2, metavar=("BASELINE", "CANDIDATE"),
                    help="diff two verdicts.json by (card_id,cause,slot)")
    ap.add_argument("--prompts", metavar="FILE", help="override the fleet list (lines: stem|prompt[|asset_id])")
    ap.add_argument("--out", metavar="DIR", default=None, help="output root (default outputs/fab_guards_audit_<date>)")
    ap.add_argument("--host", default=DEFAULT_HOST, help=f"run endpoint (default {DEFAULT_HOST})")
    ap.add_argument("--concurrency", type=int, default=3, help="max concurrent renders (default 3)")
    ap.add_argument("--timeout", type=float, default=300.0, help="per-request timeout seconds (default 300)")
    args = ap.parse_args(argv)

    if args.diff:
        return run_diff(args.diff[0], args.diff[1])

    out_dir = args.out or os.path.join("outputs", f"fab_guards_audit_{datetime.now():%Y%m%d}")

    # DEFAULT (no explicit mode) = render then analyze. --analyze-only skips rendering.
    do_render = args.render or (not args.analyze and not args.render)
    analyze_src = args.analyze

    if do_render:
        prompts = load_prompts_file(args.prompts) if args.prompts else PROMPTS
        if not prompts:
            print("no prompts to render", file=sys.stderr)
            return 1
        renders_dir = render_fleet(prompts, args.host, out_dir, args.concurrency, args.timeout)
        analyze_src = analyze_src or renders_dir

    if not analyze_src:
        return 0

    rows, stats = analyze_dir(analyze_src)
    md_path, json_path, agg_sorted, per_cause, totals = write_verdicts(rows, stats, out_dir, analyze_src)
    print(f"\nAnalyzed {stats['parsed']} responses from {A(analyze_src)} "
          f"(skipped {stats['skipped']}, no-cards {stats['no_cards']}).")
    print(f"  -> {A(md_path)}")
    print(f"  -> {A(json_path)}")
    print_verdict_table(agg_sorted, per_cause, totals)
    return 0


if __name__ == "__main__":
    sys.exit(main())
