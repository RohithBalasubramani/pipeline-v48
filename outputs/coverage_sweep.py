"""outputs/coverage_sweep.py — COMPREHENSIVE render-coverage sweep, PACED + RESILIENT (serial, gentle on the archbox
tunnel — a concurrent flood is what dropped it). For one data-bearing asset per CLASS x its applicable pages, run the
full host pipeline and record per page: cards present (NO-DROP vs the layout count), cards filled (has_payload),
frames fetched (DATA), validate verdict + whether the chilled gate blocked, and the BASKET COLUMNS (for column coverage).

Writes outputs/coverage_sweep.jsonl (one row per asset x page). Re-runnable: appends; analyze.py reads the jsonl.

Usage:
  python3 outputs/coverage_sweep.py [classes=AHU,UPS,...] [pages=feeder|panel|all] [per_class=1] [sleep=4]
"""
import os, sys, json, time, traceback
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)

FEEDER = {
    "individual-feeder-meter-shell/real-time-monitoring": "real time monitoring",
    "individual-feeder-meter-shell/voltage-current": "voltage and current health",
    "individual-feeder-meter-shell/energy-power": "today's energy and power",
    "individual-feeder-meter-shell/power-quality": "power quality and harmonics",
}
PANEL = {
    "panel-overview-shell/real-time-monitoring": "real time monitoring for the panel",
    "panel-overview-shell/energy-power": "energy and power for the panel",
    "panel-overview-shell/energy-distribution": "energy distribution and flow for the panel",
    "panel-overview-shell/voltage-current": "voltage and current events for the panel",
    "panel-overview-shell/harmonics-pq": "harmonics and power quality for the panel",
}


def _layout_counts():
    from data.db_client import q
    from config.databases import CMD_CATALOG
    out = {}
    for r in q(CMD_CATALOG, "SELECT page_key, count(*) FROM page_layout_cards GROUP BY page_key"):
        out[r[0]] = int(r[1])
    return out


def _kv(args, key, default):
    for a in args:
        if a.startswith(key + "="):
            return a.split("=", 1)[1]
    return default


def run_one(asset_id, cls, name, page, prompt, layout_n):
    os.environ["V48_AVAILABLE_PAGES"] = page
    from host.server import build_response
    t0 = time.time()
    r = build_response(prompt, asset_id=asset_id)
    cards = r.get("cards") or []
    frames = r.get("frames") or {}
    val = r.get("validation") or {}
    basket_cols = sorted({c.get("column") for c in (((r.get("asset") or {}).get("basket") or {}).get("columns") or [])}) \
        if False else None  # basket not in response; pulled from data_instructions below
    # collect the data columns each card binds (from data_instructions.fields[].column / target_column)
    cols = set()
    for c in cards:
        di = c.get("data_instructions") or {}
        for f in (di.get("fields") or []):
            for k in ("column", "target_column", "source_column"):
                if isinstance(f, dict) and f.get(k):
                    cols.add(f[k])
    data_cards = [c for c in cards if c.get("endpoint")]
    return {
        "page": page, "asset_id": asset_id, "class": cls, "asset": name,
        "how": (r.get("asset") or {}).get("how"),
        "verdict": val.get("verdict"), "blocked": r.get("validation_blocked"), "pending": r.get("asset_pending"),
        "layout_cards": layout_n, "n_cards": len(cards),
        "dropped": max(0, (layout_n or 0) - len(cards)),                 # cards in layout but absent from the run
        "filled": sum(1 for c in cards if c.get("has_payload")),         # has exact_metadata (renderable)
        "data_cards": len(data_cards),
        "with_frame": sum(1 for c in data_cards if c.get("endpoint") in frames),
        "frames": sorted(frames.keys()),
        "n_columns": ((val.get("data") or {}).get("summary") or {}).get("n_columns"),
        "bound_columns": sorted(cols),                                   # columns the cards' data_instructions touch
        "elapsed_s": round(time.time() - t0, 1),
    }


def main():
    args = sys.argv[1:]
    which = _kv(args, "pages", "feeder")
    per_class = int(_kv(args, "per_class", "1"))
    sleep_s = float(_kv(args, "sleep", "4"))
    cls_filter = set(filter(None, _kv(args, "classes", "").split(",")))

    from layer1b.resolve.asset_candidates import asset_candidates
    cands = asset_candidates()
    layout = _layout_counts()

    # one (or per_class) data-bearing asset per class
    byclass = {}
    for x in cands:
        if not x[6]:
            continue
        byclass.setdefault(x[5], []).append((int(x[0]), x[1]))
    targets = []
    for cls, lst in byclass.items():
        if cls_filter and cls not in cls_filter:
            continue
        for aid, nm in lst[:per_class]:
            targets.append((aid, cls, nm))

    pages = {}
    if which in ("feeder", "all"):
        pages.update(FEEDER)
    if which in ("panel", "all"):
        pages.update(PANEL)
    # panels only make sense for PCC panels; feeder pages for everything else
    out_path = os.path.join(HERE, "coverage_sweep.jsonl")
    n = 0
    with open(out_path, "a") as f:
        for aid, cls, nm in targets:
            use_pages = PANEL if (which == "all" and nm.lower().startswith("pcc-panel")) else \
                        (FEEDER if which != "panel" else PANEL)
            for page, prompt in use_pages.items():
                try:
                    row = run_one(aid, cls, nm, page, prompt, layout.get(page))
                except Exception as e:
                    row = {"page": page, "asset_id": aid, "class": cls, "asset": nm,
                           "ERROR": f"{type(e).__name__}: {str(e)[:140]}"}
                f.write(json.dumps(row) + "\n"); f.flush()
                n += 1
                if "ERROR" in row:
                    print(f"[{n}] {cls:<12} {nm[:22]:<22} {page.split('/')[-1]:<22} ERROR {row['ERROR'][:60]}")
                else:
                    print(f"[{n}] {cls:<12} {nm[:22]:<22} {page.split('/')[-1]:<22} "
                          f"cards={row['n_cards']}/{row['layout_cards']} filled={row['filled']} "
                          f"frame={row['with_frame']}/{row['data_cards']} verdict={row['verdict']} "
                          f"blocked={row['blocked']} {row['elapsed_s']}s")
                time.sleep(sleep_s)                                       # PACE: protect the tunnel
    print(f"\nwrote {out_path} ({n} runs)")


if __name__ == "__main__":
    main()
