"""outputs/verify_pages.py — coverage audit: for each of the 9 routable pages, FORCE routing to that page, run the FULL
host pipeline (build_response = run_pipeline + per-card ems_backend frame fetch), and report PER CARD whether it is
RENDERABLE (has_payload) and has PROPER DATA (its endpoint frame fetched + non-empty). Backend-only (no Playwright).

Usage:
  python3 outputs/verify_pages.py                 # all 9 pages
  python3 outputs/verify_pages.py <page_key>      # one page

Writes outputs/verify_pages.jsonl (one JSON object per page) and prints a compact matrix.
"""
import os, sys, json, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

# (page_key, forcing prompt, asset_id-or-None). Feeder pages pin a real data-bearing single asset (GIC-03-N6-AHU-5=36);
# panel pages name a PCC panel and let 1b resolve the panel-aggregate.
PAGES = [
    ("individual-feeder-meter-shell/real-time-monitoring", "real time monitoring for AHU-5", 36),
    ("individual-feeder-meter-shell/voltage-current",      "voltage and current health for AHU-5", 36),
    ("individual-feeder-meter-shell/energy-power",         "today's energy and power analysis for AHU-5", 36),
    ("individual-feeder-meter-shell/power-quality",        "power quality and harmonics for AHU-5", 36),
    ("panel-overview-shell/real-time-monitoring",          "real time monitoring for PCC Panel 1A", None),
    ("panel-overview-shell/energy-power",                  "energy and power for PCC Panel 1A", None),
    ("panel-overview-shell/energy-distribution",           "energy input and distribution for PCC Panel 1A", None),
    ("panel-overview-shell/voltage-current",               "voltage and current events for PCC Panel 1A", None),
    ("panel-overview-shell/harmonics-pq",                  "harmonics and power quality for PCC Panel 1A", None),
]


def _frame_nonempty(frame):
    """A fetched ems_backend frame counts as REAL data if it carries any non-empty shape (widgets / queue / buckets / rows)."""
    if not isinstance(frame, dict):
        return bool(frame)
    for k in ("widgets", "queue", "buckets", "rows", "series", "feeders", "data", "points"):
        v = frame.get(k)
        if isinstance(v, (list, dict)) and len(v) > 0:
            return True
    # any non-trivial scalar/array payload beyond bookkeeping keys
    meat = {k: v for k, v in frame.items() if k not in ("endpoint", "ok", "why", "range", "start", "end", "sampling", "ts")}
    return any(isinstance(v, (list, dict)) and len(v) > 0 for v in meat.values()) or len(meat) > 3


def audit_page(page_key, prompt, asset_id):
    os.environ["V48_AVAILABLE_PAGES"] = page_key            # FORCE 1a to route to exactly this page
    from host.server import build_response
    t0 = time.time()
    try:
        resp = build_response(prompt, asset_id=asset_id)
    except Exception as e:
        return {"page_key": page_key, "prompt": prompt, "ERROR": f"{type(e).__name__}: {e}"}
    frames = resp.get("frames") or {}
    routed = (resp.get("page") or {}).get("page_key")
    cards = []
    for c in resp.get("cards") or []:
        ep = c.get("endpoint")
        in_frames = ep in frames
        cards.append({
            "card_id": c.get("card_id"),
            "render_card_id": c.get("render_card_id"),
            "title": (c.get("title") or "")[:40],
            "has_payload": bool(c.get("has_payload")),     # RENDERABLE
            "endpoint": ep,
            "in_frames": in_frames,                        # frame fetched for its endpoint
            "frame_nonempty": bool(in_frames and _frame_nonempty(frames.get(ep))),  # PROPER DATA
            "conforms": c.get("conforms"),
            "payload_error": c.get("payload_error"),
        })
    return {
        "page_key": page_key, "routed_to": routed, "matched": routed == page_key,
        "prompt": prompt, "asset_id": asset_id,
        "how": (resp.get("asset") or {}).get("how"),
        "asset": ((resp.get("asset") or {}).get("asset") or {}).get("name"),
        "asset_pending": resp.get("asset_pending"), "asset_no_data": resp.get("asset_no_data"),
        "n_cards": len(cards),
        "frames_fetched": sorted(frames.keys()),
        "cards": cards,
        "elapsed_s": round(time.time() - t0, 1),
        "errors": resp.get("errors") or {},
    }


def main():
    sel = sys.argv[1] if len(sys.argv) > 1 else None
    pages = [p for p in PAGES if (not sel or p[0] == sel)]
    out_path = os.path.join(HERE, "verify_pages.jsonl")
    results = []
    with open(out_path, "a") as f:
        for page_key, prompt, asset_id in pages:
            r = audit_page(page_key, prompt, asset_id)
            results.append(r)
            f.write(json.dumps(r) + "\n"); f.flush()
            # compact line per page
            if "ERROR" in r:
                print(f"\n### {page_key}\n  ERROR: {r['ERROR']}")
                continue
            ok_render = sum(1 for c in r["cards"] if c["has_payload"])
            ok_data = sum(1 for c in r["cards"] if c["frame_nonempty"])
            print(f"\n### {page_key}  (routed={r['routed_to']} match={r['matched']} how={r['how']} asset={r['asset']} {r['elapsed_s']}s)")
            print(f"  cards={r['n_cards']}  renderable={ok_render}  with_data={ok_data}  frames={r['frames_fetched']}")
            for c in r["cards"]:
                flag = "R" if c["has_payload"] else "-"
                flag += "D" if c["frame_nonempty"] else ("d" if c["in_frames"] else ".")
                print(f"    [{flag:2}] #{c['card_id']:<3} ep={str(c['endpoint']):<26} {c['title']}")
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
