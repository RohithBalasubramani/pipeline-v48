"""partition/group_detect.py — transitive-closure grouping -> interdependency groups + standalone. [spec section 6]"""
from partition.coupling_lookup import gather_edges
from partition.fallback_edges import attach_orphans


def _union_find(card_ids, edges):
    parent = {c: c for c in card_ids}

    def find(x):
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    for e in edges:
        a, b = e[0], e[1]
        if a in parent and b in parent:
            parent[find(a)] = find(b)
    comp = {}
    for c in card_ids:
        comp.setdefault(find(c), set()).add(c)
    return list(comp.values())


def detect_groups(page_key, page_cards, db="cmd_catalog"):
    card_ids = [c["card_id"] for c in page_cards]
    edges, dims = gather_edges(page_key, page_cards, db)
    comps = _union_find(card_ids, edges)
    groups = [sorted(s) for s in comps if len(s) >= 2]
    standalone = sorted(next(iter(s)) for s in comps if len(s) == 1)
    groups, standalone = attach_orphans(page_key, page_cards, groups, standalone, db)
    return [sorted(g) for g in groups], standalone, sorted(dims)
