"""layer2/swap/gate_no_dup.py — no-dup: never swap to a card already on the page / in 1a's template / already chosen. [#13]"""


def ok(decision, template_card_ids, already_chosen, page_card_ids):
    tid = decision.get("swap_to_id")
    forbidden = set(template_card_ids) | set(already_chosen) | set(page_card_ids)
    return tid is not None and tid not in forbidden
