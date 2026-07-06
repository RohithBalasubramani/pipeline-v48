"""validate/payload_lookup.py — read default card payloads (the byte-match ground truth) for a 1a card. [validate]
Rows also carry payload_stripped — the STORED pre-stripped skeleton (built by scripts/build_stripped_payloads.py);
NULL until built, so every reader keeps an on-the-fly strip fallback. `payload` stays the RAW harvested truth."""
import psycopg2
from psycopg2.extras import RealDictCursor

from config.databases import CMD_CATALOG, PSQL_USER


def card_payloads_for(card_id, page_key, *, include_subcards=False):
    """All stories in card_payloads for this card_id on this page (cards first). Returns list of dicts."""
    sub = "" if include_subcards else "AND is_subcard = false"
    conn = psycopg2.connect(dbname=CMD_CATALOG, user=PSQL_USER)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"""
                SELECT story_id, story_name, variant, is_subcard, payload, payload_stripped, key_roles, import_path
                FROM card_payloads
                WHERE card_id = %s AND page_key = %s {sub}
                ORDER BY is_subcard, story_id
            """, (card_id, page_key))
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def card_payloads_home(card_id, *, include_subcards=False):
    """The card's payload rows on its HOME page (card_id alone — each card_id maps to exactly one page in
    card_payloads). Needed for a swapped-IN card: swap targets are OFF-PAGE by rule, so a (card_id, slot-page)
    lookup is empty by construction and the re-emit would lose its metadata skeleton + slot catalog."""
    sub = "" if include_subcards else "AND is_subcard = false"
    conn = psycopg2.connect(dbname=CMD_CATALOG, user=PSQL_USER)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"""
                SELECT page_key, story_id, story_name, variant, is_subcard, payload, payload_stripped, key_roles, import_path
                FROM card_payloads
                WHERE card_id = %s {sub}
                ORDER BY is_subcard, story_id
            """, (card_id,))
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
