"""layer2/build.py — Layer 2 GENERAL per-card entry (contract 5). One fan-out unit:
assemble input -> AI emit {swap, exact_metadata(morphs), data_instructions} -> deterministic gates -> Layer2CardOutput.
On an ACCEPTED swap, RE-EMIT for the swapped-in card (it has a different shape) — the payload always matches the FINAL
card. AI DECIDES (swap + morphs + recipe); deterministic code SUPPORTS (copy defaults, gate, assemble). [spec §2 L2]"""
from layer2.card_input import build_card_input, build_swap_target_input
from layer2.emit.emit import emit
from layer2.emit.metadata.producer import produce
from layer2.emit.data.consumer_binding import build as consumer_build
from layer2.resolve.column_override import apply as override_columns
from layer2.swap.decide import gate as swap_gate
from layer2.gates import gate_exact_metadata, gate_data_instructions, enforce_exact_metadata
from layer2.schema import validate_layer2_card_output
from data.db_client import q


def _page_card_ids(page_key):
    return [int(x[0]) for x in q("cmd_catalog",
            f"SELECT DISTINCT card_id FROM page_layout_cards WHERE page_key=$a${page_key}$a$ AND card_id IS NOT NULL") if x and x[0]]


def _finalize(ci, raw, swap, *, reemit_of=None):
    """Produce the Layer2CardOutput for the FINAL card (ci) from its AI emit (raw) + the resolved swap decision."""
    basket = ci["column_basket"]
    dp = ci["catalog_row"].get("default_payload")
    ai_meta = raw.get("exact_metadata") or {}
    morphed = ai_meta.pop("_morphed", []) if isinstance(ai_meta, dict) else []
    failures = []

    if dp:
        exact_metadata, applied, rejected = produce(dp["payload"], ai_meta, morphed)
        failures += [f"morph rejected: {r}" for r in rejected]
        ok_m, m_issues = gate_exact_metadata(exact_metadata, dp["payload"], morphed=applied)
        # LOAD-BEARING byte-identity enforcement [META-02]: if the gate flags any byte-identity/chrome/shape violation,
        # REVERT the offending leaves to their byte-identical default so the resting render is guaranteed conforming.
        # The producer already builds from defaults+applied, so this is belt-and-suspenders — but it makes the gate
        # non-advisory: a non-conforming payload NEVER ships, it self-heals to the default.
        if not ok_m:
            exact_metadata, reverted = enforce_exact_metadata(exact_metadata, dp["payload"], morphed=applied)
            failures += [f"reverted to default: {p}" for p in reverted]
            ok_m, m_issues = gate_exact_metadata(exact_metadata, dp["payload"], morphed=applied)
        failures += m_issues
    else:
        exact_metadata, applied = ai_meta, []
        ok_m = bool(ai_meta)
        if not ok_m:
            failures.append("no default payload + empty exact_metadata")

    di = raw.get("data_instructions") or {"fields": []}
    di, ov_issues = override_columns(di, basket)
    failures += ov_issues
    # DETERMINISTIC ENVELOPE COMPLETION [META-08]: backfill payload_shape/orientation/entity_dim from the catalog
    # card_data_recipe whenever the AI omitted them (a Qwen fail-open ships an incomplete envelope the FE mapper can't
    # key on). The recipe is the ground-truth per-card shape, so the envelope is ALWAYS complete even on emit failure.
    cr = ci["catalog_row"]
    _recipe = cr.get("recipe") or {}
    for _k in ("payload_shape", "orientation", "entity_dim"):
        if di.get(_k) in (None, "") and _recipe.get(_k) is not None:
            di[_k] = _recipe.get(_k)
    if "fields" not in di:
        di["fields"] = []
    # DETERMINISTIC: attach the consumer-driving params so the DATA-fill helper drives V48's ems_backend WS dispatcher
    di["consumer"] = consumer_build(cr, ci.get("asset"), ci["page_key"], window=di.get("window"), ai_spec=di.get("ems_backend"))
    if di.get("binding") is None and ci.get("asset"):
        a = ci["asset"]
        di["binding"] = {"asset_id": a.get("mfm_id"), "table": a.get("table"),
                         "panel_id": a.get("panel_id"), "ts_col": None, "nameplate_scope": "default"}
    ok_d, d_issues = gate_data_instructions(di, basket, is_group_card=ci["is_group_card"])
    failures += d_issues

    conforms = ok_m and ok_d and not ov_issues and bool(exact_metadata)
    # BEST-EFFORT / ANSWERABILITY: the AI reports whether it could answer the card's story with REAL columns —
    # "full" (exact), "partial" (rendered via a real substitute, + data_note), or "none" (a genuine GAP that the
    # orchestrator may re-route on). gap drives the reflect-loop; data_note (loop-1 note) is saved for the user.
    answerability = raw.get("answerability") or "full"
    if answerability not in ("full", "partial", "none"):
        answerability = "full"
    data_note = raw.get("data_note") or None
    gap = answerability == "none"
    # DETERMINISTIC infeasibility → gap. The AI's answerability is BLIND to topology (it sees columns, not feeders), so a
    # card that REQUIRES feeder topology resolved onto an asset with NO feeders silently claims "full". Force the gap so
    # the reflect-loop re-routes to a feasible page instead of dead-ending on an empty fan-out (the AI-self-healing wire).
    feas = ci["catalog_row"].get("feasibility") or {}
    if (feas.get("required_topology") or feas.get("required_mesh")) and not (ci.get("asset") or {}).get("has_feeders"):
        gap = True
        data_note = data_note or "card needs feeder topology; the resolved asset has no feeders"
    out = {
        "card_id": ci["card_id"],
        "$ctx": ci["group_id"] if ci["is_group_card"] else None,
        "render_slot": raw.get("render_slot") or "",
        "analytical_story": raw.get("analytical_story") or ci["story"]["analytical_story"],
        "swap_decision": swap,
        "exact_metadata": exact_metadata,
        "data_instructions": di,
        "controls": raw.get("controls"),
        "answerability": answerability,
        "data_note": data_note,
        "gap": gap,
        "conforms": conforms,
        "failure": None if conforms else {"stage": "emit", "reason": failures[0] if failures else "unknown",
                                          "detail": "; ".join(failures[:6])},
        "_applied_morphs": applied,
        "_reemit_of": reemit_of,
        "_default_payload": dp["payload"] if dp else None,    # data-leaf paths + offline replay source for the DATA-fill
    }
    out["_schema_issues"] = validate_layer2_card_output(out)
    # LOAD-BEARING SCHEMA GATE [META-08]: if the envelope still can't be completed after the deterministic backfill
    # (payload_shape/orientation/fields missing) the FE mapper has nothing to key on → honest-degrade rather than ship a
    # propless card marked answerable. A missing-shape issue flips answerability to 'partial' (no worse — the card still
    # renders its metadata frame, but the story is flagged as not fully data-bound).
    _shape_broken = any(("payload_shape" in i or "orientation" in i or "exact_metadata must be" in i)
                        for i in (out["_schema_issues"] or []))
    if _shape_broken and out["answerability"] == "full":
        out["answerability"] = "partial"
        out["data_note"] = out.get("data_note") or "data envelope incomplete (shape unresolved) — metadata-only render"
    return out


def run_card(run_id, card_id, l1a, l1b, *, already_chosen=None, shared_ctx_ref=None):
    already_chosen = already_chosen or set()
    ci = build_card_input(run_id, card_id, l1a, l1b, shared_ctx_ref=shared_ctx_ref)
    raw = emit(ci)

    swap = swap_gate(raw.get("swap_decision") or {"action": "keep"},
                     pool_ids=[c["card_id"] for c in ci["swap_candidates"]],
                     template_card_ids=ci["story"]["template_card_ids"], already_chosen=already_chosen,
                     page_card_ids=_page_card_ids(ci["page_key"]), current_card_id=card_id)

    # SWAP-TARGET RE-EMIT: the first emit authored the payload for `card_id`'s shape; the FINAL card is the swap
    # target, which has a DIFFERENT shape. Re-run the emit for the target (it inherits the slot's story) so the
    # payload matches the final card. The swap decision from pass 1 stands.
    tgt = swap.get("swap_to_id")
    if swap.get("origin") == "swapped" and tgt and tgt != card_id:
        target_ci = build_swap_target_input(run_id, tgt, ci, l1b)
        target_raw = emit(target_ci)
        return _finalize(target_ci, target_raw, swap, reemit_of=card_id)

    return _finalize(ci, raw, swap)
