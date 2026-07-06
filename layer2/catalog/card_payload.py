"""layer2/catalog/card_payload.py — the harvested default payload = the byte-identical METADATA source + the
per-leaf DATA/METADATA split (reuses validate/). This is the GROUND TRUTH the morph authors against. [v48-card-payloads-db]"""
from validate.payload_lookup import card_payloads_for, card_payloads_home
from validate.leaf_classify import classify


def default_for(card_id, page_key):
    """The card's (non-subcard) default payload + its data-leaf paths. None if not harvested.
    HOME-PAGE FALLBACK [swap-target re-emit]: a swapped-IN card is OFF-PAGE by rule, so the (card_id, slot-page)
    row does not exist — fall back to the card's own home-page row (card_id → exactly one page in card_payloads)
    so the re-emit still gets the target's metadata skeleton + slot catalog instead of a groundless generic emit."""
    rows = card_payloads_for(card_id, page_key, include_subcards=False)
    if not rows:
        rows = card_payloads_home(card_id, include_subcards=False)
    if not rows:
        return None
    row = rows[0]
    payload = row["payload"]
    split = classify(payload)
    data_paths = [d["path"] for d in split["data_leaves"]]
    return {"story_id": row["story_id"], "variant": row["variant"], "payload": payload,
            "payload_stripped": row.get("payload_stripped"),  # STORED seedless skeleton (build_stripped_payloads); read directly, None fails loudly downstream
            "key_roles": row["key_roles"], "data_paths": data_paths,
            "metadata_leaf_count": split["metadata_leaves"], "demand": split["demand"]}
