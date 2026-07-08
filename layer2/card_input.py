"""layer2/card_input.py — DETERMINISTIC assembly of one fan-out unit (Layer2CardInput, contract 4).
Joins 1a story + 1b asset/basket + the card's cmd_catalog catalog_row + (group cards) the shared_ctx ref + swap pool."""
from layer2.catalog.catalog_row import load as load_catalog_row
from layer2.swap.candidates import pool as swap_pool


def _group_of(l1a, card_id):
    for g in l1a.get("interdependency_groups", []):
        if card_id in (g.get("card_ids") or []):
            return g
    return None


def build_card_input(run_id, card_id, l1a, l1b, *, shared_ctx_ref=None):
    page_key = l1a["page_key"]
    cards = {c["card_id"]: c for c in l1a.get("cards", [])}
    card1a = cards.get(card_id, {})
    template_ids = [c["card_id"] for c in l1a.get("cards", [])]
    group = _group_of(l1a, card_id)

    catalog = load_catalog_row(card_id, page_key, title=card1a.get("title"))
    return {
        "run_id": run_id,
        "card_id": int(card_id),
        "page_key": page_key,
        # A card is a shared-context GROUP card (emits a lean $ctx atom that reads the page's shared buffer) ONLY when
        # a shared buffer actually EXISTS for this run (shared_ctx_ref). Approach-B shared_context is DEFERRED — the
        # fan-out calls run_card with shared_ctx_ref=None — so a mere page COUPLING (esp. a `time-bucket` date-sync
        # coupling, which is handled by the cross-card date sync, NOT by data sharing) must NOT make a card emit $ctx:
        # with no buffer to read, its $ctx data leaves false-blank measurable columns (card-73 DG power trend). Until
        # Approach-B builds the buffer, every card is STANDALONE and fills its OWN data (src=live) — the plan's path.
        "is_group_card": group is not None and shared_ctx_ref is not None,
        "group_id": (group["group_id"] if group else None) if shared_ctx_ref is not None else None,
        "shared_ctx_ref": shared_ctx_ref,
        "story": {
            "page_story": l1a.get("story", ""),
            "analytical_story": card1a.get("analytical_story", ""),
            "role_in_story": card1a.get("role_in_story"),
            "metric": l1a.get("metric"),
            "intent": l1a.get("intent"),
            "template_card_ids": template_ids,
        },
        "asset": l1b.get("asset"),
        "column_basket": l1b.get("column_basket", {"tables": [], "columns": []}),
        "catalog_row": catalog,
        "swap_candidates": swap_pool(card_id, page_key, template_ids,
                                     width=catalog["size"].get("width_px"),
                                     height=catalog["size"].get("height_px"),
                                     metric=l1a.get("metric")),
    }


def build_swap_target_input(run_id, target_id, original_ci, l1b):
    """Layer2CardInput for a swapped-IN (off-page) card: it fills the ORIGINAL slot, so it INHERITS the slot's story
    angle + group membership + template set + asset/basket, but brings its OWN catalog_row (shape/recipe/defaults).
    No further swap is offered (the slot is settled). [swap-target re-emit]"""
    page_key = original_ci["page_key"]
    return {
        "run_id": run_id,
        "card_id": int(target_id),
        "page_key": page_key,
        "is_group_card": original_ci["is_group_card"],
        "group_id": original_ci["group_id"],
        "shared_ctx_ref": original_ci.get("shared_ctx_ref"),
        "story": dict(original_ci["story"]),            # inherit the slot's analytical angle + template_card_ids
        "asset": original_ci.get("asset"),
        "column_basket": original_ci["column_basket"],
        "catalog_row": load_catalog_row(target_id, page_key, title=None),  # the TARGET's own shape/recipe/defaults
        "swap_candidates": [],                          # slot settled — never re-swap
    }
