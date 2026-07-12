"""layer2/swap/gate_vague_reject.py — reject a swap whose criterion is vague (must name a concrete story-angle word). [#13]"""
from config import swap as _swap   # lazy module attrs — read per call so DB row edits reach the gate live


def ok(decision):
    c = (decision.get("criterion") or "").strip().lower()
    return bool(c) and c not in _swap.VAGUE_CRITERIA
