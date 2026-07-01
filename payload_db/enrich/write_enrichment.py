"""payload_db/enrich/write_enrichment.py — write the enrich-payload-db workflow output back into card_payloads.

Adds: card_id, card_match_confidence, card_match_reason, parent_story_id, key_roles (jsonb,
per-key DATA/METADATA/mixed split), match_verified, match_notes (per-leaf data/metadata detail).
Run: PYTHONPATH=. python3 payload_db/enrich/write_enrichment.py [/tmp/payload_mappings.json]
"""
import json
import sys

import psycopg2
from psycopg2.extras import Json

from config.databases import CMD_CATALOG, PSQL_USER

ALTER = """
ALTER TABLE card_payloads
  ADD COLUMN IF NOT EXISTS card_match_confidence text,
  ADD COLUMN IF NOT EXISTS card_match_reason     text,
  ADD COLUMN IF NOT EXISTS parent_story_id       text,
  ADD COLUMN IF NOT EXISTS key_roles             jsonb,
  ADD COLUMN IF NOT EXISTS match_verified        boolean,
  ADD COLUMN IF NOT EXISTS match_notes           text;
CREATE INDEX IF NOT EXISTS card_payloads_card_id_idx ON card_payloads(card_id);
"""


def write(path="/tmp/payload_mappings.json"):
    rows = json.load(open(path))
    conn = psycopg2.connect(dbname=CMD_CATALOG, user=PSQL_USER)
    conn.autocommit = False
    n = 0
    try:
        with conn.cursor() as cur:
            cur.execute(ALTER)
            for m in rows:
                cur.execute("""
                    UPDATE card_payloads SET
                        card_id=%s, card_match_confidence=%s, card_match_reason=%s,
                        parent_story_id=%s, key_roles=%s, match_verified=%s, match_notes=%s
                    WHERE story_id=%s
                """, (m.get("card_id"), m.get("card_match_confidence"), m.get("card_match_reason"),
                      m.get("parent_story_id"), Json(m.get("key_roles") or {}),
                      bool(m.get("verified")), m.get("notes"), m["story_id"]))
                n += cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return n


if __name__ == "__main__":
    n = write(sys.argv[1] if len(sys.argv) > 1 else "/tmp/payload_mappings.json")
    print(f"enriched {n} card_payloads rows")
