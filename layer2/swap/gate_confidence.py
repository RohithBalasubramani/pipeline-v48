"""layer2/swap/gate_confidence.py — a swap is honored only at confidence >= MIN_CONFIDENCE. [#13]"""
from config import swap as _swap   # lazy module attrs — read per call so DB row edits reach the gate live


def ok(decision):
    try:
        return float(decision.get("confidence") or 0) >= _swap.MIN_CONFIDENCE
    except (TypeError, ValueError):
        return False
