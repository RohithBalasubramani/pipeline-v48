"""host/multi_asset.py — the /api/run MULTI-ASSET response: compare 1+ assets in ONE run. [author-once-per-class]

Resolve the picker's asset_ids → run_pipeline_multi (1a routes ONCE; Layer 2 authors the recipe ONCE PER CLASS) → for
each asset reuse ITS class recipe (rebind_consumer) + fill from ITS OWN neuract table (host/assemble.assemble_cards) +
TAG every card by asset → concat into ONE response the FE groups by `card.asset`. The single-asset build_response is
NEVER touched: N==1 stays on that path byte-for-byte; this file is only reached when the picker returns 2+ ids. [atomic]
"""
from obs.errfmt import record_exc as _record_exc   # failures-channel telemetry [EH F4]
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
    # STAGE TELEMETRY [silent-bail fix]: every decision this gate makes is now attributable in the run log — a compare
    # that silently degrades to single (rows<2 / ambiguous member / <2 confident) previously left NO trace, making a
    # live mis-route a forensic dig through polluted AI logs. stderr keeps the fail-open line for exceptions.
    def _tel(**kw):
        try:
            import sys
            sys.stderr.write("[natural_compare] " + " ".join(f"{k}={v}" for k, v in kw.items())[:300] + "\n")
        except Exception:
            pass
    try:
        from layer1b.resolve.asset_candidates import asset_candidates
        from layer1b.compare.detect import named_full_rows
        cands = asset_candidates()                        # ONE probe shared by detection + every sub-resolve
        rows = named_full_rows(prompt, cands)
        if len(rows) < 2:
            # BUS-SECTION COMPARE [sections]: 'compare pcc 1a and pcc 1b' — BOTH aliases are the SAME canonical panel
            # (A/B are its bus sections), so detection honestly collapses to ONE row. When the prompt names >=2
            # DIFFERENT sections of that one panel, the user is comparing SECTIONS: two lanes of the same panel, each
            # fan-out filtered to its section's members (equipment.mfm.section). Deterministic — no AI resolution
            # needed (the aliases already pin the panel).
            # BUS-SECTION MENTIONS OF ONE PANEL ['compare pcc 1a and pcc 1b'] stay on the SINGLE page [user 2026-07-12:
            # "2 sections should never be there"]: the panel page's cards are MEMBER-driven (both sections' bays are
            # its members), so the honest render is ONE page over the union — the in-chart per-section overlay
            # (per-section series, section-coloured members) is the roster-interpreter follow-up, not a page split.
            if len(rows) == 1:
                from layer1b.resolve.asset_resolve import _pcc_section_index
                from layer1b.compare.discriminators import _norm
                p = _norm(prompt)
                panel_name = str(rows[0][1])
                secs = sorted({sec for al, (pn, sec) in _pcc_section_index().items()
                               if pn == panel_name and al in p})
                if len(secs) >= 2:
                    _tel(decision="single_page_section_union", panel=panel_name[:24], sections=secs)
            if "compare" in str(prompt).lower():          # only narrate prompts that LOOK like compares (low noise)
                _tel(decision="single", rows=len(rows), detected=[str(r[1])[:30] for r in rows])
            return []
        from layer1b.compare.resolve_names import resolve_compare
        r = resolve_compare(prompt, cands)
        confident = r.get("confident") or []
        ambiguous = r.get("ambiguous") or []
        # EVERY named asset must pin (no ambiguous name) AND 2+ confident — otherwise the honest answer is the single
        # picker for the unresolved name, not a partial auto-compare that silently drops it.
        if ambiguous or len(confident) < 2:
            _tel(decision="single", rows=len(rows), confident=len(confident),
                 ambiguous=[str(a)[:30] for a in ambiguous],
                 hows=[f"{str(x.get('name'))[:24]}:{x.get('how')}" for x in (r.get("resolutions") or [])])
            return []
        _tel(decision="compare", rows=len(rows), confident=len(confident))
        return confident
    except Exception as e:
        import sys
        sys.stderr.write(f"[natural_compare] fail-open to single path ({type(e).__name__}: {str(e)[:120]})\n")
        _record_exc("host.multi_asset.natural_compare", e)
        return []


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

    from host.compare_overlay import comparand_token, merge_all
    all_cards = []
    tokens_by_id = {}                                        # tag id → short comparand label (P1/P2 …) for overlay merge
    for group in groups:
        lane = group.get("lane") or {}
        recipe = lane.get("layer2") or {}                    # the class recipe (authored ONCE for this class)
        for asset in (group.get("assets") or []):
            lane_i = {**lane, "layer2": rebind_consumer(recipe, asset)}   # point the recipe at THIS asset's meter
            cards_i = assemble_cards(lane_i, asset, date_window)          # fill from THIS asset's own neuract table
            _attach_l2_notes(cards_i, lane_i["layer2"])                   # B1 disclosures per card (same as single path)
            # sectioned lanes share one mfm_id — the GROUPING id must still be distinct per lane [sections]
            _tid = (f"{asset.get('mfm_id')}{asset.get('section')}" if asset.get("section") else asset.get("mfm_id"))
            tag = {"id": _tid, "name": asset.get("name"), "class": asset.get("class")}
            tokens_by_id[_tid] = comparand_token(asset.get("name"))
            for c in cards_i:
                c["asset"] = tag                                          # FE groups + labels by this (additive)
            all_cards.extend(cards_i)

    # ★ COMPARE MODE [overlay vs groups] — the AI decides HOW to render a multi-comparand compare (host/compare_mode):
    #   overlay = merge the per-asset cards into ONE per-comparand set (each card shows every panel inline — the same
    #             section-overlay payload shape, N-generic); groups = keep the per-asset stacked dashboards (below).
    # Only >=2 comparands is a real compare. The merge is deterministic (host/compare_overlay); mode is fail-open overlay.
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
