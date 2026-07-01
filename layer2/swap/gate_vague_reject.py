"""layer2/swap/gate_vague_reject.py — reject a swap whose criterion is vague (must name a concrete story-angle word). [#13]"""
from config.swap import VAGUE_CRITERIA


def ok(decision):
    c = (decision.get("criterion") or "").strip().lower()
    return bool(c) and c not in VAGUE_CRITERIA
