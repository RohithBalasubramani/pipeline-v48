"""CLI entrypoint: rebuild copilot_index.sqlite from the DBs (+ optional LLM aliases).

    python3 build.py            # rebuild from DBs + curated/embedded aliases
    python3 build.py --llm      # also generate colloquial aliases via the 4B model
"""
import argparse
import sqlite3

from config import INDEX_PATH

from .alias_build import add_llm_aliases, build_aliases
from .entities import fetch_entities
from .schema import SCHEMA


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true", help="also generate colloquial aliases via the 4B model")
    args = ap.parse_args()

    conn = sqlite3.connect(INDEX_PATH)
    conn.executescript(SCHEMA)

    ents = fetch_entities()
    cur = conn.cursor()
    ents_by_id = {}
    for i, e in enumerate(ents, start=1):
        e["id"] = i
        ents_by_id[i] = e
        cur.execute("""INSERT INTO entities(id,type,canonical,display,unit,class_scope,area,
                         table_name,panel_id,kind,has_data,popularity,keywords,payload)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (e["id"], e["type"], e["canonical"], e["display"], e["unit"],
                     e["class_scope"], e["area"], e["table_name"], e["panel_id"],
                     e["kind"], e["has_data"], e["popularity"], e["keywords"], e["payload"]))
    conn.commit()

    n_alias = build_aliases(conn, ents_by_id)
    if args.llm:
        n_alias += add_llm_aliases(conn, ents_by_id)

    by_type = {}
    for e in ents:
        by_type[e["type"]] = by_type.get(e["type"], 0) + 1
    print(f"index written: {INDEX_PATH}")
    print("  entities:", sum(by_type.values()), by_type)
    print("  aliases :", n_alias)
    conn.close()
