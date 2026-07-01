"""layer2/catalog/card_payload.py — the harvested default payload = the byte-identical METADATA source + the
per-leaf DATA/METADATA split (reuses validate/). This is the GROUND TRUTH the morph authors against. [v48-card-payloads-db]"""
from validate.payload_lookup import card_payloads_for
from validate.leaf_classify import classify


def default_for(card_id, page_key):
    """The card's (non-subcard) default payload + its data-leaf paths. None if not harvested."""
    rows = card_payloads_for(card_id, page_key, include_subcards=False)
    if not rows:
        return None
    row = rows[0]
    payload = row["payload"]
    split = classify(payload)
    data_paths = [d["path"] for d in split["data_leaves"]]
    return {"story_id": row["story_id"], "variant": row["variant"], "payload": payload,
            "key_roles": row["key_roles"], "data_paths": data_paths,
            "metadata_leaf_count": split["metadata_leaves"], "demand": split["demand"]}
