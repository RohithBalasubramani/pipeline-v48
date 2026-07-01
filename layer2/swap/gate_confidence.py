"""layer2/swap/gate_confidence.py — a swap is honored only at confidence >= MIN_CONFIDENCE. [#13]"""
from config.swap import MIN_CONFIDENCE


def ok(decision):
    try:
        return float(decision.get("confidence") or 0) >= MIN_CONFIDENCE
    except (TypeError, ValueError):
        return False
