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


def natural_compare_ids(prompt):
    """NATURAL COMPARE auto-resolution [multi-asset gap fix]: a 'compare A and B' prompt that spells out 2+ SPECIFIC
    full asset names ('GIC-01-N3-UPS-01 and GIC-02-N5-UPS-04') carries no picker asset_ids, so the single-asset resolver
    sees both UPS tokens as one ambiguous set and dead-ends in the single picker (0 cards). This splits the prompt into
    per-name sub-prompts and resolves EACH through the SAME 1b resolver (layer1b.compare.resolve_compare, concurrently);
    when 2+ names pin CONFIDENTLY (exact unique meter, no picker) it returns those mfm_ids so the caller routes them
    through build_response_multi — the identical author-once-per-class compare the picker's multi-select takes.

    Returns [] (single-asset path unchanged) when: the prompt names <2 specific assets (a single full name, or bare
    homonyms like 'UPS-01' that only match a class+unit token), OR any named asset stays AMBIGUOUS on its own sub-prompt
    (that name must surface its OWN picker, not be auto-pinned to a wrong homonym). Gated by multi_asset.enabled. Purely
    additive: the single-asset branch is byte-identical whenever this returns [].

    FAIL-OPEN BOUNDARY: this is an OPTIONAL pre-flight enhancer that runs BEFORE build_response's protected layers —
    any exception here (e.g. the registry has_data probe re-raising a :5433 outage) must NOT 500 the request. It
    fail-opens to [] so the request proceeds down the single path, where the SAME outage is caught by the degrade gate
    and served as the honest data_unavailable terminal (200 + reason), never a raw error page."""
    if not bool(cfg("multi_asset.enabled", True)):
        return []
    try:
        from layer1b.compare.detect import is_natural_compare
        if not is_natural_compare(prompt):
            return []
        from layer1b.compare.resolve_names import resolve_compare
        r = resolve_compare(prompt)
        confident = r.get("confident") or []
        # EVERY named asset must pin (no ambiguous name) AND 2+ confident — otherwise the honest answer is the single
        # picker for the unresolved name, not a partial auto-compare that silently drops it.
        if r.get("ambiguous") or len(confident) < 2:
            return []
        return confident
    except Exception as e:
        import sys
        sys.stderr.write(f"[natural_compare] fail-open to single path ({type(e).__name__}: {str(e)[:120]})\n")
        return []


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
