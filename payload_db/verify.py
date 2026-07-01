"""payload_db/verify.py — prove the load is complete + faithful (jsonb round-trips byte-equal to the harvest). [atomic verify]"""
import json
import sys

import psycopg2

from config.databases import CMD_CATALOG, PSQL_USER


def _norm(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"))


def verify(path="/tmp/ems_payloads.json"):
    src = {r["id"]: r for r in json.load(open(path)) if r.get("argsOk") and r.get("payload") is not None}
    conn = psycopg2.connect(dbname=CMD_CATALOG, user=PSQL_USER)
    fails = []
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM card_payloads")
        total = cur.fetchone()[0]
        cur.execute("SELECT story_group, count(*) FROM card_payloads GROUP BY 1 ORDER BY 1")
        groups = cur.fetchall()
        cur.execute("SELECT count(*) FROM card_payloads WHERE story_group='EMS'")
        ems = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM card_payloads WHERE story_group='EMS' AND page_key IS NULL")
        ems_unmapped = cur.fetchone()[0]
        cur.execute("SELECT page_key, count(*) FROM card_payloads WHERE page_key IS NOT NULL GROUP BY 1 ORDER BY 1")
        pages = cur.fetchall()
        cur.execute("SELECT is_subcard, count(*) FROM card_payloads WHERE story_group='EMS' GROUP BY 1")
        sub = dict(cur.fetchall())
        # faithfulness: every source payload must round-trip byte-equal from jsonb
        cur.execute("SELECT story_id, payload FROM card_payloads")
        for sid, pl in cur.fetchall():
            if sid in src and _norm(pl) != _norm(src[sid]["payload"]):
                fails.append(sid)
    conn.close()

    print(f"rows in DB: {total}  (source harvested: {len(src)})")
    print("by group:", dict(groups))
    print(f"EMS: {ems}  (unmapped page_key: {ems_unmapped})  cards={sub.get(False)} subcards={sub.get(True)}")
    print("\nEMS page_key coverage:")
    for pk, n in pages:
        print(f"  {n:3}  {pk}")
    print(f"\njsonb round-trip faithful: {len(src)-len(fails)}/{len(src)}", "OK" if not fails else f"MISMATCH {fails}")
    ok = (total == len(src)) and (ems_unmapped == 0) and (not fails)
    print("\nVERDICT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(verify(sys.argv[1] if len(sys.argv) > 1 else "/tmp/ems_payloads.json"))
