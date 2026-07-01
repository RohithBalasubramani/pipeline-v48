"""layer1a/partition_inputs/card_link.py — read card_link coupling edges for a page. [spec section 6]"""
from data.db_client import q


def read_card_link_edges(page_key, db="cmd_catalog"):
    rows = q(db, f"SELECT src_card, dst_card, coalesce(dimension,'') FROM card_link "
                 f"WHERE page_key=$k${page_key}$k$")
    return [(int(r[0]), int(r[1]), r[2]) for r in rows if r and r[0] and r[1]]
