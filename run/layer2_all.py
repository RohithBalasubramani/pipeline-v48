"""run/layer2_all.py — run Layer 2 for EVERY 1a card (the per-card fan-out). [glue: 1a+1b -> 2]

Returns {card_id: Layer2CardOutput}. Each card is an INDEPENDENT AI emit, so they run CONCURRENTLY against vLLM
(which batches) — N cards take ~one emit, not N. Per-card exceptions are captured (one bad card never sinks the page).

SWAP-COLLISION POST-PASS [META-04]: the parallel emits each run with an EMPTY already_chosen, so two slots can each
independently swap to the SAME off-page target → a duplicate card. After all emits, grounding.swap_settle.settle runs a
DETERMINISTIC second pass (highest-confidence-first) that reverts the lower-priority colliding swap to KEEP — both slots
still render distinct + byte-identical defaults. Swaps are settled here, before the executor fill, so every downstream
pass is a pure function of its own (settled) card. [contract: swaps resolved deterministically before data-fill]"""
from obs.errfmt import fmt_exc as _fmt_exc   # the ONE exception string [EH F4]
from run.parallel import run_parallel
from layer2.build import run_card, _page_card_ids
from grounding.swap_settle import settle as settle_swaps
from obs.stage import stage


def _err(cid, e):
    return {"card_id": cid, "exception": _fmt_exc(e), "conforms": False,
            "exact_metadata": None, "payload": None, "swap_decision": {"action": "keep"}}


def _fill(o):
    """NO server-side DATA fill, NO default-replay seed (user: no default mode / no fallbacks anywhere). The payload IS
    the AI's `exact_metadata` (the METADATA tier, data leaves elided). The DATA is filled LIVE on the FRONTEND from the
    legacy-EMS frame (Option A, retired) via each CMD V2 card's OWN mapper. No live frame ⇒ the card shows 'connecting' (honest),
    never a replayed default."""
    if o.get("exception"):
        return o
    o["payload"] = o.get("exact_metadata")
    o["fill_source"] = "live-frontend"
    return o


def run_2_all(run_id, l1a, l1b):
    """OBS wrapper — the whole per-page fan-out is ONE `layer2_card_ai` parent span; each card's
    `layer2_card_ai.card` span (layer2/build.run_card) nests under it via the run_parallel context hop."""
    from obs.span import stage_span
    with stage_span("layer2_card_ai", inputs={"page_key": (l1a or {}).get("page_key"),
                                              "n_cards": len((l1a or {}).get("cards") or [])}) as sp:
        out = _run_2_all_inner(run_id, l1a, l1b)
        gaps = sum(1 for o in out.values() if (o or {}).get("gap"))
        hard_fails = sum(1 for o in out.values() if not (o or {}).get("conforms"))
        sp.set_outputs(cards=len(out),
                       conform=sum(1 for o in out.values() if (o or {}).get("conforms")),
                       partial=sum(1 for o in out.values() if (o or {}).get("answerability") == "partial"),
                       gaps=gaps, hard_fails=hard_fails,
                       swaps=sum(1 for o in out.values()
                                 if ((o or {}).get("swap_decision") or {}).get("origin") == "swapped"))
        if gaps or hard_fails:
            sp.set_degradation(gaps=gaps or None, hard_fails=hard_fails or None)
        return out


def _run_2_all_inner(run_id, l1a, l1b):
    cards = (l1a or {}).get("cards") or []
    if not cards:
        return {}
    page_key = (l1a or {}).get("page_key")
    template_ids = [c.get("card_id") for c in cards if c.get("card_id") is not None]
    tasks = {c["card_id"]: (lambda cid=c["card_id"]: run_card(run_id, cid, l1a, l1b)) for c in cards}
    # BOUND THE FAN-OUT [contention fail-fast margin]: each card is a large-prompt (~22K-tok) l2_emit; an UNBOUNDED
    # per-card pool put N concurrent emits on the vLLM at once, splitting decode throughput N ways so the biggest emit
    # (harmonics heatmap) sat at the 150s l2_emit fail-fast edge even on a solo page — and starved to a false timeout
    # under a multi-page sweep. Cap concurrency (DB knob layer2.emit_concurrency, code-default 4): excess cards queue,
    # each in-flight emit keeps enough throughput to finish with margin. Generic, no card ids; the code default holds on
    # a config outage. (run_parallel still fans the 2-thunk L1a∥L1b split fully — 2 < cap.)
    from config.app_config import cfg
    _cap = int(cfg("layer2.emit_concurrency", 4) or 4)
    res = run_parallel(tasks, max_workers=_cap)
    out = {}
    for cid, r in res.items():
        o = _err(cid, r) if isinstance(r, Exception) else _fill(r)
        out[cid] = o

    # DETERMINISTIC SWAP-COLLISION POST-PASS — revert lower-priority duplicate swaps to KEEP (parallel emits ran with an
    # empty already_chosen, so two slots can independently swap to the same off-page target). Settles swaps BEFORE L3.
    try:
        page_ids = _page_card_ids(page_key) if page_key else []
        st = settle_swaps(out, page_card_ids=page_ids, template_card_ids=template_ids)
        for rv in st.get("reverts") or []:
            stage(run_id, "L2.swap_revert", id=rv.get("card_id"), target=rv.get("target"),
                  reason=rv.get("reason"))
    except Exception as e:
        stage(run_id, "L2.swap_revert", ERROR=_fmt_exc(e))

    for cid, o in out.items():
        sw = o.get("swap_decision") or {}
        stage(run_id, "L2.card", id=cid, swap=sw.get("action"), to=(sw.get("swap_to_id") or cid),
              confidence=sw.get("confidence"),                  # the AI's swap confidence (admin dashboard; None on keep)
              conforms=o.get("conforms"), fill=o.get("fill_source"),
              answerability=o.get("answerability"), gap=o.get("gap"), note=o.get("data_note"),
              keys=list((o.get("exact_metadata") or {}).keys())[:4],
              endpoint=((o.get("data_instructions") or {}).get("consumer") or {}).get("endpoint"),
              fail=(o.get("exception") or (o.get("failure") or {}).get("reason")))
    return out
