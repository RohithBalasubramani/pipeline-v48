"""run/card_diag.py — per-card render diagnostic for ONE page. Runs the full pipeline for a (prompt, asset_id), then
dumps per-card facts (L2 emit conforms / fill / endpoint / payload / gap) + the fetched frame state + the card's
card_feasibility (required_topology). Used by the 9/10-page render-bottleneck audit.

    python run/card_diag.py "<prompt>" <asset_id>
"""
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from host.server import build_response          # noqa: E402
from data.db_client import q                    # noqa: E402


def _feas(cid):
    try:
        r = q("cmd_catalog", f"SELECT family, verdict, required_topology, required_mesh FROM card_feasibility WHERE card_id={int(cid)}")
        if r and r[0]:
            return {"family": r[0][0], "verdict": r[0][1], "required_topology": r[0][2] == "t", "required_mesh": r[0][3] == "t"}
    except Exception:
        pass
    return {}


def main(prompt, asset_id):
    r = build_response(prompt, asset_id=int(asset_id) if asset_id else None)
    frames = r.get("frames") or {}
    out = {
        "prompt": prompt,
        "page": (r.get("page") or {}).get("page_key"),
        "asset": ((r.get("asset") or {}).get("asset") or {}).get("name"),
        "asset_pending": r.get("asset_pending"),
        "asset_no_data": r.get("asset_no_data"),
        "frames": {ep: {"bytes": len(json.dumps(fr)),
                        "hasData": any(k in json.dumps(fr) for k in ("queue", "buckets", "widgets", "outgoings", "feeders"))}
                   for ep, fr in frames.items()},
        "cards": [],
    }
    for c in (r.get("cards") or []):
        cid = c.get("card_id")
        ep = c.get("endpoint")
        fr = frames.get(ep)
        out["cards"].append({
            "card_id": cid,
            "title": c.get("title"),
            "endpoint": ep,
            "conforms": c.get("conforms"),
            "has_payload": c.get("has_payload"),
            "fill_ok": c.get("fill_ok"),
            "fill_why": c.get("fill_why"),
            "payload_error": c.get("payload_error"),
            "frame_present": ep in frames if ep else False,
            "frame_hasData": bool(fr and any(k in json.dumps(fr) for k in ("queue", "buckets", "widgets", "outgoings", "feeders"))),
            "feasibility": _feas(cid),
        })
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
