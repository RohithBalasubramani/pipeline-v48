"""layer1a/partition_inputs/page_control.py — page_control host + affects_cards int[] coupling. [spec section 6]"""
from data.db_client import q


def read_page_control_groups(page_key, db="cmd_catalog"):
    rows = q(db, "SELECT coalesce(host_card::text,''), coalesce(affects_cards::text,'') "
                 f"FROM page_control WHERE page_key=$k${page_key}$k$")
    groups = []
    for r in rows:
        host = int(r[0]) if r[0] else None
        arr = [int(x) for x in r[1].strip("{}").split(",") if x.strip().isdigit()] if r[1] else []
        g = set(arr)
        if host:
            g.add(host)
        if len(g) >= 2:
            groups.append(sorted(g))
    return groups
