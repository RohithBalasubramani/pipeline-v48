"""layer1a/db_reads/page_specs.py — read live page_specs for the router. [spec section 10 1a]"""
from data.db_client import q


def read_page_specs(db="cmd_catalog"):
    rows = q(
        db,
        "SELECT page_key, coalesce(title,''), coalesce(purpose,''), coalesce(reusable_answers,''), "
        "coalesce(analytical_theme,''), coalesce(archetype,''), coalesce(shell,'') "
        "FROM page_specs WHERE status='live' ORDER BY shell, page_key",
    )
    return [
        {"page_key": r[0], "title": r[1], "purpose": r[2], "answers": r[3],
         "theme": r[4], "archetype": r[5], "shell": r[6]}
        for r in rows
    ]
