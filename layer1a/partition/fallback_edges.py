"""partition/fallback_edges.py — orphan rescue: attach a standalone card to a group it shares page_layout_cards (region,tab) with. [REVIEW G4, OPEN]"""
from data.db_client import q


def _region_tab(page_key, db):
    rows = q(db, "SELECT card_id, coalesce(region,''), coalesce(tab,'') FROM page_layout_cards "
                 f"WHERE page_key=$k${page_key}$k$ AND card_id IS NOT NULL")
    return {int(r[0]): (r[1], r[2]) for r in rows}


def attach_orphans(page_key, page_cards, groups, standalone, db="cmd_catalog"):
    rt = _region_tab(page_key, db)
    still = []
    for s in standalone:
        key = rt.get(s)
        attached = False
        if key and key != ("", ""):
            for g in groups:
                if any(rt.get(m) == key for m in g):
                    g.append(s)
                    attached = True
                    break
        if not attached:
            still.append(s)
    return groups, still
