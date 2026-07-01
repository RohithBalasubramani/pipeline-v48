"""outputs/prompt_check.py — drive a VARIETY of prompts through the LIVE host server (POST /api/run, like the manual
curl), PACED + resilient, and report per prompt the end-to-end backend outcome: routed page, resolved asset + how,
gate (blocked / pending / no_data), cards filled vs total, frames fetched, validation verdict. Flags anything off.
Browser render-crashes aren't visible here (no Playwright) — this is the backend truth the frontend renders from.

Usage: python3 outputs/prompt_check.py [host=http://127.0.0.1:8770] [sleep=4]
"""
import sys, json, time, urllib.request

PROMPTS = [
    # feeder pages × classes
    "real time monitoring for AHU-5",
    "voltage and current health for GIC-03-N6-AHU-5",
    "today's energy and power for MLDB",
    "power quality and harmonics for UPS-01",
    "voltage and current for DG-1 MFM",
    "real time monitoring for Utility Panel-1",
    # panel-overview (PCC aggregate) × 5 pages
    "real time monitoring for PCC Panel 1",
    "energy and power for PCC Panel 2",
    "energy distribution and flow for PCC Panel 1",
    "voltage and current events for PCC Panel 3",
    "harmonics and power quality for PCC Panel 4",
    # metric diversity
    "THD and harmonic distortion for AHU-8",
    "daily power demand by feeder for PCC Panel 1",
    "load anomalies for AHU-5",
    # resolution flows (expected to NOT render → picker)
    "battery health and backup autonomy",          # ambiguous → picker
    "voltage and current for Transformer-01",       # no_data / silent → picker
    "energy and power",                             # no asset → picker
]


def run(host, prompt):
    body = json.dumps({"prompt": prompt}).encode()
    req = urllib.request.Request(host + "/api/run", data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=180) as resp:
        r = json.load(resp)
    cards = r.get("cards") or []
    frames = r.get("frames") or {}
    data_cards = [c for c in cards if c.get("endpoint")]
    asset = (r.get("asset") or {}).get("asset") or {}
    return {
        "prompt": prompt,
        "page": (r.get("page") or {}).get("page_key"),
        "asset": asset.get("name"), "how": (r.get("asset") or {}).get("how"),
        "blocked": r.get("validation_blocked"), "pending": r.get("asset_pending"), "no_data": r.get("asset_no_data"),
        "verdict": (r.get("validation") or {}).get("verdict"),
        "cards": len(cards), "filled": sum(1 for c in cards if c.get("has_payload")),
        "data_cards": len(data_cards), "with_frame": sum(1 for c in data_cards if c.get("endpoint") in frames),
        "frames": sorted(frames.keys()),
        "errors": r.get("errors") or {},
        "elapsed_s": round(time.time() - t0, 1),
    }


def main():
    host = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("host=")), "http://127.0.0.1:8770")
    sleep_s = float(next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("sleep=")), "4"))
    print(f"checking {len(PROMPTS)} prompts on {host}\n")
    for i, p in enumerate(PROMPTS, 1):
        try:
            r = run(host, p)
        except Exception as e:
            print(f"[{i:>2}] ERROR  {p[:46]:<46} {type(e).__name__}: {str(e)[:50]}")
            time.sleep(sleep_s); continue
        # classify outcome
        if r["pending"] or r["no_data"] or r["blocked"]:
            why = "no_data→picker" if r["no_data"] else ("blocked→picker" if r["blocked"] else "ambiguous/empty→picker")
            tag = "PICKER"
        elif r["filled"] == r["cards"] and r["with_frame"] == r["data_cards"]:
            tag, why = "OK", f"{r['filled']}/{r['cards']} cards · {r['with_frame']}/{r['data_cards']} framed"
        else:
            tag, why = "PARTIAL", f"filled {r['filled']}/{r['cards']} · framed {r['with_frame']}/{r['data_cards']}"
        flag = "  <<<" if (tag == "PARTIAL" or r["errors"]) else ""
        print(f"[{i:>2}] {tag:<7} {p[:44]:<44} → {str(r['page']).split('/')[-1][:20]:<20} {str(r['asset'])[:18]:<18} "
              f"how={r['how']} verdict={r['verdict']} | {why}{flag}")
        if r["errors"]:
            print(f"       errors: {r['errors']}")
        time.sleep(sleep_s)
    print("\ndone")


if __name__ == "__main__":
    main()
