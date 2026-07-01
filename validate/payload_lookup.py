"""validate/payload_lookup.py — read default card payloads (the byte-match ground truth) for a 1a card. [validate]"""
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
                SELECT story_id, story_name, variant, is_subcard, payload, key_roles, import_path
                FROM card_payloads
                WHERE card_id = %s AND page_key = %s {sub}
                ORDER BY is_subcard, story_id
            """, (card_id, page_key))
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
