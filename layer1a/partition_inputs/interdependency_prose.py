"""layer1a/partition_inputs/interdependency_prose.py — cards.interdependency 'Linked cards' prose -> edges. [spec section 6]"""
import re

from data.db_client import q


def read_prose_edges(page_key, page_cards, db="cmd_catalog"):
    title_to_id = {c["title"]: c["card_id"] for c in page_cards}
    ids = [c["card_id"] for c in page_cards]
    if not ids:
        return []
    rows = q(db, f"SELECT id, coalesce(interdependency,'') FROM cards WHERE id IN ({','.join(str(i) for i in ids)})")
    edges = []
    for r in rows:
        cid = int(r[0])
        m = re.search(r"Linked cards on this page:\s*(.+?)(?:\||$)", r[1])
        if not m:
            continue
        for t in (x.strip() for x in m.group(1).split(";")):
            if t in title_to_id and title_to_id[t] != cid:
                edges.append((cid, title_to_id[t], "prose"))
    return edges
