"""layer2/swap/gate_pool_valid.py — swap target must be one of THIS slot's offered candidates. [#13, contract 4]"""


def ok(decision, pool_ids):
    return decision.get("swap_to_id") in set(pool_ids)
