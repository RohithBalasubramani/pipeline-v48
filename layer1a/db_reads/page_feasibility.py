"""layer1a/db_reads/page_feasibility.py — per-page render-feasibility counts for the Layer 1a template gate.

For each candidate page_key: (total live cards on the page, cards whose card_feasibility.verdict is UNRENDERABLE).
A card WITHOUT a card_feasibility row counts as live-but-renderable (it is NOT unrenderable) — the gate only drops on a
verdict that explicitly says drop/no_data, never on a missing signal. [renderability gate — Layer 1a; user 2026-07-02]
"""
from data.db_client import q
from config.feasibility import UNRENDERABLE_VERDICTS


def read_page_feasibility(page_keys, db="cmd_catalog"):
    """{page_key: {"total": int, "unrenderable": int}} for the given page_keys (one query, live cards only)."""
    keys = [k for k in (page_keys or []) if k]
    if not keys:
        return {}
    inlist = ",".join(f"$a${k}$a$" for k in keys)
    verds = ",".join(f"$a${v}$a$" for v in UNRENDERABLE_VERDICTS) or "$a$__none__$a$"
    rows = q(
        db,
        f"""
        SELECT pl.page_key,
               count(*) AS total,
               sum(CASE WHEN f.verdict IN ({verds}) THEN 1 ELSE 0 END) AS unrenderable
        FROM page_layout_cards pl
        JOIN cards c ON c.id = pl.card_id
        LEFT JOIN card_feasibility f ON f.card_id = pl.card_id
        WHERE pl.card_id IS NOT NULL AND c.status = 'live' AND pl.page_key IN ({inlist})
        GROUP BY pl.page_key
        """,
    )
    return {r[0]: {"total": int(r[1] or 0), "unrenderable": int(r[2] or 0)} for r in rows if r and r[0]}
