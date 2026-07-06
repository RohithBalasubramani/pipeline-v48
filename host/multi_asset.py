"""host/multi_asset.py — the /api/run MULTI-ASSET response: compare 1+ assets in ONE run. [author-once-per-class]

Resolve the picker's asset_ids → run_pipeline_multi (1a routes ONCE; Layer 2 authors the recipe ONCE PER CLASS) → for
each asset reuse ITS class recipe (rebind_consumer) + fill from ITS OWN neuract table (host/assemble.assemble_cards) +
TAG every card by asset → concat into ONE response the FE groups by `card.asset`. The single-asset build_response is
NEVER touched: N==1 stays on that path byte-for-byte; this file is only reached when the picker returns 2+ ids. [atomic]
"""
import time

from config.app_config import cfg
from run.harness import run_pipeline_multi
from host.assemble import assemble_cards
from host.rebind_consumer import rebind_consumer
from host.asset_lanes import resolve_assets


def build_response_multi(prompt, asset_ids, date_window=None):
    """Compare the resolved `asset_ids` in one run and return the merged /api/run response (cards tagged `card.asset`,
    page from the shared template). The number of assets is capped by the DB knob multi_asset.max_assets (code default 6)."""
    from host.server import _attach_l2_notes, SB_BASE       # lazy: server imports this module — break the cycle
    from obs.stage import stage
    t0 = time.time()
    cap = max(1, int(cfg("multi_asset.max_assets", 6)))
    assets = resolve_assets(asset_ids)[:cap]
    multi = run_pipeline_multi(prompt, assets)
    groups = multi.get("groups") or []
    shared_1a = multi.get("layer1a") or {}
    lane0 = (groups[0]["lane"] if groups else {}) or {}

    all_cards = []
    for group in groups:
        lane = group.get("lane") or {}
        recipe = lane.get("layer2") or {}                    # the class recipe (authored ONCE for this class)
        for asset in (group.get("assets") or []):
            lane_i = {**lane, "layer2": rebind_consumer(recipe, asset)}   # point the recipe at THIS asset's meter
            cards_i = assemble_cards(lane_i, asset, date_window)          # fill from THIS asset's own neuract table
            _attach_l2_notes(cards_i, lane_i["layer2"])                   # B1 disclosures per card (same as single path)
            tag = {"id": asset.get("mfm_id"), "name": asset.get("name"), "class": asset.get("class")}
            for c in cards_i:
                c["asset"] = tag                                          # FE groups + labels by this (additive)
            all_cards.extend(cards_i)

    val = lane0.get("validation") or {}
    # OUTAGE PROPAGATION [honest-terminal parity with build_response]: if any lane hit the data_unavailable terminal
    # (e.g. the neuract tunnel dropped mid-run), surface it so the FE shows the degrade notice — NOT a silent blank grid.
    unavail = next((g.get("lane") or {} for g in groups if (g.get("lane") or {}).get("data_unavailable")), None)
    stage(multi.get("run_id") or "-", "RESPONSE_MULTI", assets=len(assets), groups=len(groups),
          cards=len(all_cards), data_unavailable=bool(unavail), elapsed_ms=int((time.time() - t0) * 1000))
    return {
        "ok": bool(all_cards) or bool(shared_1a.get("cards")),
        "prompt": prompt,
        "run_id": multi.get("run_id"),
        "elapsed_ms": int((time.time() - t0) * 1000),
        "sb_base": SB_BASE,
        "multi_asset": True,                                  # FE: render the grouped (per-asset) grid
        "assets": [{"mfm_id": a.get("mfm_id"), "name": a.get("name"), "class": a.get("class"),
                    "table": a.get("table")} for a in assets],
        "page": {
            "page_key": shared_1a.get("page_key"),
            "page_title": shared_1a.get("page_title"),
            "shell": shared_1a.get("shell"),
            "metric": shared_1a.get("metric"),
            "intent": shared_1a.get("intent"),
            "story": shared_1a.get("story"),
            "layout": shared_1a.get("layout") or {},
            "groups": shared_1a.get("interdependency_groups") or [],
        },
        "asset_pending": False,                              # every id is already pinned (the picker resolved them)
        "asset_no_data": False,
        "validation_blocked": False,
        "data_unavailable": bool(unavail),                   # a lane's outage → honest page-level terminal (FE notice)
        "degrade": (unavail or {}).get("degrade") if unavail else None,
        "asset": {                                           # back-compat single-asset FE fields = the FIRST asset
            "asset": (assets[0] if assets else None),
            "how": "user-choice",
            "candidates": [],
            "n_columns": None,
        },
        "validation": {
            "verdict": val.get("verdict"),
            "how": val.get("how"),
            "policy": val.get("policy"),
            "data_summary": (val.get("data") or {}).get("summary"),
            "payload_summary": (val.get("payload") or {}).get("summary"),
        },
        "cards": all_cards,
        "frames": {},
        "frame_status": {},
        "live_frame": None,
        "date_window": date_window,
        "notes": lane0.get("notes") or {"loop1": [], "loop2": None},
        "errors": lane0.get("errors") or {},
    }
