"""layer2/swap/gate_template_dedup.py — explicit guard that the target is NOT one of 1a's sacred template cards. [#13]"""


def ok(decision, template_card_ids):
    return decision.get("swap_to_id") not in set(template_card_ids)
