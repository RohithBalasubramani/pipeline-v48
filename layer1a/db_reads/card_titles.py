"""layer1a/db_reads/card_titles.py — page_key -> comma-joined real card titles. [spec section 10 1a]"""
from data.db_client import q


def read_card_titles(db="cmd_catalog"):
    rows = q(
        db,
        "SELECT pl.page_key, string_agg(c.title, ', ' ORDER BY pl.slot_order) "
        "FROM page_layout_cards pl JOIN cards c ON c.id=pl.card_id "
        "WHERE pl.card_id IS NOT NULL AND c.status='live' GROUP BY pl.page_key",
    )
    return {r[0]: r[1] for r in rows}
