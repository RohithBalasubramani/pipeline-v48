"""run/layer_diag.py — per-LAYER end-to-end diagnostic for ONE prompt. Runs the full pipeline and dumps a compact
per-layer summary (1a / 1b / validate / asset_gate / Layer 2 / frames) so an audit can judge whether each layer worked.

    python run/layer_diag.py "<prompt>" [asset_id]
"""
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from run.harness import run_pipeline              # noqa: E402
from host.server import _card_frames              # noqa: E402


def _hasdata(fr):
    s = json.dumps(fr, default=str)
    return any(k in s for k in ("queue", "buckets", "widgets", "outgoings", "feeders", "kpis"))


def main(prompt, asset_id=None):
    out = run_pipeline(prompt, asset_id=int(asset_id) if asset_id else None)
    l1a = out.get("layer1a") or {}
    l1b = out.get("layer1b") or {}
    val = out.get("validation") or {}
    l2 = out.get("layer2") or {}
    how = l1b.get("how")
    asset = l1b.get("asset") or {}
    frames = _card_frames(l2, run_id=out.get("run_id")) if l2 else {}
    summary = {
        "prompt": prompt,
        "asset_id_in": asset_id,
        "1a": {"page": l1a.get("page_key"),
               "n_cards": len(l1a.get("cards") or []),
               "primitive": (l1a.get("layout") or {}).get("layout_primitive"),
               "ok": bool(l1a.get("page_key") and (l1a.get("cards") or []))},
        "1b": {"asset": asset.get("name"), "mfm_id": asset.get("mfm_id"), "how": how,
               "has_feeders": asset.get("has_feeders"),
               "n_candidates": len(l1b.get("candidate_list") or []),
               "basket_cols": (l1b.get("column_basket") or {}).get("n_columns"),
               "ok": how in ("AI", "user-choice", "ambiguous", "empty", "no_data")},
        "validate": {"verdict": val.get("verdict")},
        "asset_gate": {"pinned": how in ("AI", "user-choice"),
                       "pending": out.get("asset_pending"),
                       "no_data": out.get("asset_no_data")},
        "layer2": {"ran": bool(l2),
                   "n_cards": len(l2),
                   "n_conform": sum(1 for o in l2.values() if (o or {}).get("conforms")),
                   "n_gap": sum(1 for o in l2.values() if (o or {}).get("gap"))},
        "frames": {ep: _hasdata(fr) for ep, fr in frames.items()},
        "errors": out.get("errors") or {},
    }
    print(json.dumps(summary, indent=1, default=str))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
