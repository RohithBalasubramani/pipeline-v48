"""validate/handling_lookup.py — validate-side FACADE over THE card_handling read (layer2/catalog/card_handling —
dedup D11, 2026-07-12; the SQL lives there now). Kept as a facade (not deleted) so validate keeps its documented
property of importing without layer2 imports at module time — the delegate import is lazy, inside the call."""


def handling_class_for(card_id):
    """The card_handling.handling_class for card_id, or None (absent row / DB error — honest fail-open)."""
    from layer2.catalog.card_handling import handling_class
    return handling_class(card_id)
