"""validate/handling_lookup.py — read ONE card's card_handling.handling_class (cmd_catalog) for the payload validator.

Single concern: the payload validator needs the handling CLASS to know whether a card renders WITHOUT a harvested
card_payloads default (the payload-exempt classes — mirrors layer2/catalog/feasibility_recompute.PAYLOAD_EXEMPT).
Fail-open: any DB error / absent row → None (the validator then falls back to its normal warn path). [validate]"""
from data.db_client import q


def handling_class_for(card_id):
    """The card_handling.handling_class for card_id, or None (absent row / DB error — honest fail-open)."""
    try:
        r = q("cmd_catalog", f"SELECT handling_class FROM card_handling WHERE card_id={int(card_id)} LIMIT 1")
        return r[0][0] if r and r[0] and r[0][0] else None
    except Exception:
        return None
