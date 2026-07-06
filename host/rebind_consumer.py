"""host/rebind_consumer.py — point a REUSED Layer-2 recipe at a DIFFERENT (same-class) asset. [multi-asset author-once]

Layer 2 authors the card recipe ONCE per class; its data_instructions.fields bind by column NAME (portable across
sibling meters of the same class), so filling a sibling asset needs to change only the per-asset ENVELOPE — the WS
path key `consumer.mfm_id` + the `binding` (asset_id/table) — never the AI-authored fields / swap / exact_metadata.
The executor fills from the asset_table the host passes SEPARATELY (host/assemble), so this repoint keeps the SERVED
recipe honest (correct mfm_id for a per-card FE date re-fetch + telemetry). Returns a NEW l2 dict (deep-copied) so
compare lanes never alias each other's recipe. Cheap, no LLM, zero fabrication.
"""
import copy


def rebind_consumer(l2, asset):
    """New {card_id: Layer2CardOutput} with each card's data_instructions.consumer.mfm_id + binding (asset_id/table)
    repointed at `asset` (as_asset dict). fields / swap_decision / exact_metadata are the shared class recipe, copied
    verbatim. Non-dict entries pass through unchanged. Only keys that already exist are rewritten (never fabricated)."""
    mfm_id = (asset or {}).get("mfm_id")
    table = (asset or {}).get("table")
    out = {}
    for cid, o in (l2 or {}).items():
        if not isinstance(o, dict):
            out[cid] = o
            continue
        oc = copy.deepcopy(o)
        di = oc.get("data_instructions")
        if isinstance(di, dict):
            cons = di.get("consumer")
            if isinstance(cons, dict) and "mfm_id" in cons:
                cons["mfm_id"] = mfm_id
            bind = di.get("binding")
            if isinstance(bind, dict):
                if "asset_id" in bind:
                    bind["asset_id"] = mfm_id
                if "table" in bind:
                    bind["table"] = table
        out[cid] = oc
    return out
