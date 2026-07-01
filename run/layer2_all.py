"""run/layer2_all.py — run Layer 2 for EVERY 1a card (the per-card fan-out). [glue: 1a+1b -> 2]

Returns {card_id: Layer2CardOutput}. Each card is an INDEPENDENT AI emit, so they run CONCURRENTLY against vLLM
(which batches) — N cards take ~one emit, not N. Per-card exceptions are captured (one bad card never sinks the page).

SWAP-COLLISION POST-PASS [META-04]: the parallel emits each run with an EMPTY already_chosen, so two slots can each
independently swap to the SAME off-page target → a duplicate card. After all emits, grounding.swap_settle.settle runs a
DETERMINISTIC second pass (highest-confidence-first) that reverts the lower-priority colliding swap to KEEP — both slots
still render distinct + byte-identical defaults. This settles swaps BEFORE Layer 3 so each L3 call is a pure function of
its own (settled) card. [contract: swaps resolved deterministically BEFORE L3]"""
from run.parallel import run_parallel
from layer2.build import run_card, _page_card_ids
from grounding.swap_settle import settle as settle_swaps
from obs.stage import stage


def _err(cid, e):
    return {"card_id": cid, "exception": f"{type(e).__name__}: {e}", "conforms": False,
            "exact_metadata": None, "payload": None, "swap_decision": {"action": "keep"}}


def _fill(o):
    """NO server-side DATA fill, NO default-replay seed (user: no default mode / no fallbacks anywhere). The payload IS
    the AI's `exact_metadata` (the METADATA tier, data leaves elided). The DATA is filled LIVE on the FRONTEND from the
    ems_backend frame (Option A) via each CMD V2 card's OWN mapper. No live frame ⇒ the card shows 'connecting' (honest),
    never a replayed default."""
    if o.get("exception"):
        return o
    o["payload"] = o.get("exact_metadata")
    o["fill_source"] = "live-frontend"
    return o


def run_2_all(run_id, l1a, l1b):
    cards = (l1a or {}).get("cards") or []
    if not cards:
        return {}
    page_key = (l1a or {}).get("page_key")
    template_ids = [c.get("card_id") for c in cards if c.get("card_id") is not None]
    tasks = {c["card_id"]: (lambda cid=c["card_id"]: run_card(run_id, cid, l1a, l1b)) for c in cards}
    res = run_parallel(tasks)
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
        stage(run_id, "L2.swap_revert", ERROR=f"{type(e).__name__}: {e}")

    for cid, o in out.items():
        sw = o.get("swap_decision") or {}
        stage(run_id, "L2.card", id=cid, swap=sw.get("action"), to=(sw.get("swap_to_id") or cid),
              conforms=o.get("conforms"), fill=o.get("fill_source"),
              answerability=o.get("answerability"), gap=o.get("gap"), note=o.get("data_note"),
              keys=list((o.get("exact_metadata") or {}).keys())[:4],
              endpoint=((o.get("data_instructions") or {}).get("consumer") or {}).get("endpoint"),
              fail=(o.get("exception") or (o.get("failure") or {}).get("reason")))
    return out
