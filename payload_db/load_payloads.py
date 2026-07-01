"""payload_db/load_payloads.py — create card_payloads + upsert harvested Storybook payloads. [atomic loader]

Run: PYTHONPATH=. python3 payload_db/load_payloads.py [/tmp/ems_payloads.json]
Idempotent (ON CONFLICT upsert on story_id). Uses psycopg2 for safe jsonb.
"""
import json
import os
import sys

import psycopg2
from psycopg2.extras import Json, execute_values

from config.databases import CMD_CATALOG, PSQL_USER
from payload_db.page_map import to_page_key

_HERE = os.path.dirname(os.path.abspath(__file__))


def _connect():
    return psycopg2.connect(dbname=CMD_CATALOG, user=PSQL_USER)


def _coords(rec):
    parts = [p.strip() for p in (rec.get("title") or "").split("/")]
    shell = parts[1] if len(parts) > 1 else None
    page = parts[2] if len(parts) > 2 else None
    card_group = parts[3] if len(parts) > 3 else None
    is_sub = bool(card_group and "sub" in card_group.lower())
    payload = rec.get("payload")
    variant = payload.get("variant") if isinstance(payload, dict) else None
    keys = list(payload.keys()) if isinstance(payload, dict) else []
    return shell, page, card_group, is_sub, variant, keys


def load(path="/tmp/ems_payloads.json"):
    data = json.load(open(path))
    rows = []
    for rec in data:
        if not rec.get("argsOk") or rec.get("payload") is None:
            continue
        shell, page, card_group, is_sub, variant, keys = _coords(rec)
        rows.append((
            rec["id"], rec.get("title"), rec.get("name"), rec.get("group"),
            shell, page, card_group, is_sub,
            to_page_key(shell, page) if rec.get("group") == "EMS" else None,
            variant, Json(rec["payload"]), keys,
            rec.get("importPath"), rec.get("componentPath"),
        ))

    conn = _connect()
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute(open(os.path.join(_HERE, "schema.sql")).read())
            execute_values(cur, """
                INSERT INTO card_payloads
                  (story_id,title,story_name,story_group,shell,page,card_group,is_subcard,
                   page_key,variant,payload,payload_keys,import_path,component_path)
                VALUES %s
                ON CONFLICT (story_id) DO UPDATE SET
                  title=EXCLUDED.title, story_name=EXCLUDED.story_name, story_group=EXCLUDED.story_group,
                  shell=EXCLUDED.shell, page=EXCLUDED.page, card_group=EXCLUDED.card_group,
                  is_subcard=EXCLUDED.is_subcard, page_key=EXCLUDED.page_key, variant=EXCLUDED.variant,
                  payload=EXCLUDED.payload, payload_keys=EXCLUDED.payload_keys,
                  import_path=EXCLUDED.import_path, component_path=EXCLUDED.component_path,
                  harvested_at=now()
            """, rows)
        conn.commit()
    finally:
        conn.close()
    return len(rows)


if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ems_payloads.json"
    n = load(p)
    print(f"loaded/upserted {n} payload rows into {CMD_CATALOG}.card_payloads")
