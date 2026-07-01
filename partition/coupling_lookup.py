"""partition/coupling_lookup.py — gather all coupling edges for a page (card_link/combo/page_control/prose). [spec section 6, contract 6]"""
from layer1a.partition_inputs.card_link import read_card_link_edges
from layer1a.partition_inputs.card_combo import read_combo_member_groups
from layer1a.partition_inputs.page_control import read_page_control_groups
from layer1a.partition_inputs.interdependency_prose import read_prose_edges


def _chain(group):
    return [(group[i], group[i + 1], "group") for i in range(len(group) - 1)]


def gather_edges(page_key, page_cards, db="cmd_catalog"):
    edges, dims = [], set()
    for a, b, d in read_card_link_edges(page_key, db):
        edges.append((a, b, d))
        if d:
            dims.add(d)
    for g in read_combo_member_groups(page_key, db):
        edges += _chain(g)
    for g in read_page_control_groups(page_key, db):
        edges += _chain(g)
    edges += read_prose_edges(page_key, page_cards, db)
    return edges, dims
