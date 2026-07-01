"""layer2/swap/combo_cascade.py — coupled cards swap all-or-nothing; every cascade partner must resolve to a listed target. [#13]"""


def ok(decision, pool_ids):
    cascade = decision.get("cascade") or []
    if not cascade:
        return True
    pool = set(pool_ids)
    return all(c.get("swap_to_id") in pool for c in cascade)
