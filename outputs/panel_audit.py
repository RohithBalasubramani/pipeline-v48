"""outputs/panel_audit.py — PER-CARD audit of the 5 panel-overview pages for a given PCC panel asset_id. For each card:
endpoint, frame-fetched?, payload?, handling_class (from cmd_catalog), and a verdict explaining any missing frame
(NO-ENDPOINT-by-design narrative/control card vs FRAME-FAIL data card). Also runs the validate layer + prints its verdict.

Usage: python3 outputs/panel_audit.py <asset_id>   (default 317 = PCC-Panel-1)
"""
import os, sys, json, time
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); sys.path.insert(0, ROOT)

PANEL_PAGES = [
    "panel-overview-shell/real-time-monitoring",
    "panel-overview-shell/energy-power",
    "panel-overview-shell/energy-distribution",
    "panel-overview-shell/voltage-current",
    "panel-overview-shell/harmonics-pq",
]
PROMPTS = {
    "panel-overview-shell/real-time-monitoring": "real time monitoring for the panel",
    "panel-overview-shell/energy-power": "energy and power for the panel",
    "panel-overview-shell/energy-distribution": "energy distribution and flow for the panel",
    "panel-overview-shell/voltage-current": "voltage and current events for the panel",
    "panel-overview-shell/harmonics-pq": "harmonics and power quality for the panel",
}


def _handling():
    from data.db_client import q
    from config.databases import CMD_CATALOG
    out = {}
    for r in q(CMD_CATALOG, "SELECT card_id, handling_class FROM card_handling"):
        out[int(r[0])] = r[1]
    return out


def audit(asset_id):
    from host.server import build_response
    from validate.build import run_validate
    HAND = _handling()
    for pg in PANEL_PAGES:
        os.environ["V48_AVAILABLE_PAGES"] = pg
        t0 = time.time()
        try:
            r = build_response(PROMPTS[pg], asset_id=asset_id)
        except Exception as e:
            print(f"\n### {pg}\n  ERROR {type(e).__name__}: {e}"); continue
        frames = r.get("frames") or {}
        cards = r.get("cards") or []
        asset = (r.get("asset") or {}).get("asset") or {}
        how = (r.get("asset") or {}).get("how")
        # validate layer verdict
        val = (r.get("validation") or {})
        print(f"\n### {pg}   asset={asset.get('name')}  how={how}  frames={sorted(frames.keys())}  "
              f"validate={val.get('verdict')}  ({round(time.time()-t0,1)}s)")
        for c in cards:
            cid = c.get("card_id"); ep = c.get("endpoint"); inf = ep in frames
            hc = HAND.get(cid, "?")
            data_card = hc in ("single_asset_series", "single_asset_derived", "panel_aggregate")
            if not ep:
                verdict = "no-endpoint (narrative/control — by design)" if hc in ("narrative_ai", "nav") or not data_card else f"!! DATA CARD ({hc}) but NO ENDPOINT emitted"
            elif inf:
                verdict = "OK"
            else:
                verdict = f"!! FRAME-FAIL (ep={ep}, data card {hc})"
            print(f"   #{cid:<3} {('R' if c.get('has_payload') else '-')}{('F' if inf else ' ')}  "
                  f"hc={hc:<22} ep={str(ep):<22} {verdict}")


if __name__ == "__main__":
    audit(int(sys.argv[1]) if len(sys.argv) > 1 else 317)
