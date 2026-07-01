"""layer2/catalog/catalog_row.py — assemble the full per-card cmd_catalog detail (catalog_row). [contract 4, signatures load_catalog_row]"""
from layer2.catalog import card_handling, card_data_recipe, contract, card_controls, card_grid_size, feasibility, card_payload


def load(card_id, page_key, title=None):
    h = card_handling.read(card_id)
    return {
        "card_id": int(card_id),
        "title": title,
        "handling_class": h.get("handling_class"),
        "resolver_scope": h.get("resolver_scope"),
        "payload_family": h.get("payload_family"),
        "backend_strategy": h.get("backend_strategy"),
        "recipe": card_data_recipe.read(card_id),
        "contract": contract.read(card_id, prefer_component=h.get("contract_component")),
        "controls": card_controls.read(card_id),
        "size": card_grid_size.read(card_id),
        "feasibility": feasibility.read(card_id),
        "default_payload": card_payload.default_for(card_id, page_key),  # ground-truth metadata defaults + data-leaf split
    }
