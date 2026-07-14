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
    from host.notes import _attach_l2_notes, SB_BASE        # shared serve-boundary home (was a lazy host.server back-import)
    from obs.stage import stage
    t0 = time.time()
    cap = max(1, int(cfg("multi_asset.max_assets", 6)))
    assets = resolve_assets(asset_ids)[:cap]
    from run.run_id import make_run_id
    # PROMPT marker parity with the single path: the multi rid's pipeline file otherwise holds ONLY RESPONSE_MULTI
    # records (lanes log under their own rids), so admin runs.executions() couldn't split appended executions and
    # latency paired records ACROSS executions (the 2.6h fake-stage bug; console_validation/latency.md 2026-07-12).
    stage(make_run_id(prompt), "PROMPT", text=prompt, multi_assets=len(assets))
    multi = run_pipeline_multi(prompt, assets)
    groups = multi.get("groups") or []
    shared_1a = multi.get("layer1a") or {}
    lane0 = (groups[0]["lane"] if groups else {}) or {}

    # PROMPT-DERIVED DATE WINDOW [api-design H4 parity, 2026-07-12]: 'compare A and B last week' — when the FE sent no
    # explicit date_window, default it from the shared lane's 1a preset EXACTLY like build_response does (an explicit
    # FE pick always wins). Without this the compare filled every card with date_window=None while the single path
    # honored the asked range — the two response paths had silently drifted.
    if not date_window:
        from host.notes import window_from_preset
        # NARROW DEFAULT [no-range prompt] — parity with build_response: 1a found no prompt range → default 'today'
        # rather than a per-lane L2-invented wide window. Explicit prompt range / FE pick still win.
        _prompt_window = window_from_preset(lane0.get("window") or "today")
        if _prompt_window:
            date_window = _prompt_window

    from host.compare_overlay import merge_all, unique_comparand_tokens

    def _fill_one(lane, asset):
        """EXACTLY the historical per-asset loop body minus tag/extend (the order-sensitive parts stay serial below):
        rebind the class recipe at THIS asset's meter, fill from its own neuract table, attach the B1 disclosures."""
        recipe = lane.get("layer2") or {}                    # the class recipe (authored ONCE for this class)
        lane_i = {**lane, "layer2": rebind_consumer(recipe, asset)}       # point the recipe at THIS asset's meter
        cards_i = assemble_cards(lane_i, asset, date_window)              # fill from THIS asset's own neuract table
        _attach_l2_notes(cards_i, lane_i["layer2"])                       # B1 disclosures per card (same as single path)
        return cards_i

    def _mode_thunk():
        from host.compare_mode import compare_mode           # call-time import → the monkeypatch seam stays live
        return compare_mode(prompt)

    # PER-ASSET FILL FAN-OUT [Stage A, DB knob multi_asset.fill_concurrency; 0/1 = the sequential loop, byte-identical]:
    # fills are independent per asset (the recipe is rebind-deep-copied; reads ride the pooled neuract door), so they
    # may run concurrently — but ORDER IS LOAD-BEARING (merge_all groups by first-seen order), so the thunks only
    # COMPUTE; tagging + tokens_by_id + all_cards.extend happen in the serial reassembly loop below in the ORIGINAL
    # (group, asset) order. A thunk exception re-raises FIRST-IN-ORDER (parity with the serial loop's in-place raise).
    # The compare_mode LLM call rides the same fan-out ("__mode__", +1 worker so it never steals a fill slot) instead
    # of serializing after the fills.
    pairs = [(gi, group, ai, asset) for gi, group in enumerate(groups)
             for ai, asset in enumerate(group.get("assets") or [])]
    fill_cc = int(cfg("multi_asset.fill_concurrency", 0) or 0)
    results = None
    if fill_cc > 1 and len(pairs) > 1:
        from run.parallel import run_parallel
        thunks = {}
        if len(assets) >= 2:
            thunks["__mode__"] = _mode_thunk
        for gi, group, ai, asset in pairs:
            thunks[f"g{gi}a{ai}"] = (lambda L=(group.get("lane") or {}), A=asset: _fill_one(L, A))
        results = run_parallel(thunks, max_workers=fill_cc + (1 if "__mode__" in thunks else 0))

    all_cards = []
    named = []                                               # (tag id, token name) in lane order -> collision-free tokens [H1]
    for gi, group, ai, asset in pairs:                       # ORIGINAL group/asset order — load-bearing for merge_all
        cards_i = (results[f"g{gi}a{ai}"] if results is not None
                   else _fill_one(group.get("lane") or {}, asset))
        if isinstance(cards_i, Exception):
            raise cards_i                                    # first-in-order → the same 500 as the sequential loop
        # sectioned lanes share one mfm_id — the GROUPING id must still be distinct per lane [sections]
        _tid = (f"{asset.get('mfm_id')}{asset.get('section')}" if asset.get("section") else asset.get("mfm_id"))
        tag = {"id": _tid, "name": asset.get("name"), "class": asset.get("class")}
        # sectioned lanes: token from "<name> <section>" so two lanes of the SAME panel get distinct meaningful tokens
        named.append((_tid, f"{asset.get('name')} {asset.get('section')}" if asset.get("section")
                      else asset.get("name")))
        for c in cards_i:
            c["asset"] = tag                                              # FE groups + labels by this (additive)
        all_cards.extend(cards_i)
    # H1 FIX [T0-4]: comparand_token has no uniqueness guarantee ('PCC-Panel-1' and 'Pump-1' both -> 'P1') and
    # merge_overlay keys per-comparand payloads by token, so same-token comparands would silently OVERWRITE each
    # other in the merged overlay card. Build the tokens over the WHOLE comparand set instead -- collision-free,
    # deterministic in lane order -- BEFORE merge_all. [host/compare_overlay.unique_comparand_tokens]
    tokens_by_id = unique_comparand_tokens(named)            # tag id -> short comparand label (P1/Pu1 ...) for overlay merge

    # ★ COMPARE MODE [overlay vs groups] — the AI decides HOW to render a multi-comparand compare (host/compare_mode):
    #   overlay = merge the per-asset cards into ONE per-comparand set (each card shows every panel inline — the same
    #             section-overlay payload shape, N-generic); groups = keep the per-asset stacked dashboards (below).
    # Only >=2 comparands is a real compare. The merge is deterministic (host/compare_overlay); mode is fail-open overlay.
    if results is not None and "__mode__" in results:
        _m = results["__mode__"]
        if isinstance(_m, Exception):
            raise _m                                         # parity: an escaped compare_mode exception propagates
        mode = _m if len(assets) >= 2 else "groups"
    else:
        from host.compare_mode import compare_mode
        mode = compare_mode(prompt) if len(assets) >= 2 else "groups"
    if mode == "overlay" and len(assets) >= 2:
        all_cards = merge_all(all_cards, tokens_by_id)
    _grouped = (mode == "groups")

    val = lane0.get("validation") or {}
    # OUTAGE PROPAGATION [honest-terminal parity with build_response]: if any lane hit the data_unavailable terminal
    # (e.g. the neuract tunnel dropped mid-run), surface it so the FE shows the degrade notice — NOT a silent blank grid.
    unavail = next((g.get("lane") or {} for g in groups if (g.get("lane") or {}).get("data_unavailable")), None)
    stage(multi.get("run_id") or "-", "RESPONSE_MULTI", assets=len(assets), groups=len(groups),
          cards=len(all_cards), data_unavailable=bool(unavail), elapsed_ms=int((time.time() - t0) * 1000))
    return {
        "ok": bool(all_cards) or bool(shared_1a.get("cards")),
        "kind": "dashboard",                                  # FE PipelineResult discriminant — parity with the
        # single-asset build_response stamp (host/server.py); types.ts declares it REQUIRED. [R10/OBS-1]
        "prompt": prompt,
        "run_id": multi.get("run_id"),
        "elapsed_ms": int((time.time() - t0) * 1000),
        "sb_base": SB_BASE,
        "multi_asset": _grouped,                              # groups mode → FE per-asset grid; overlay → flat per-comparand cards
        "compare_mode": mode,                                 # 'overlay' | 'groups' (AI-decided) — telemetry + FE hint
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
        "date_window": date_window,
        "notes": lane0.get("notes") or {"loop1": [], "loop2": None},
        "errors": lane0.get("errors") or {},
    }
