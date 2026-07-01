"""Write the aliases table: curated + embedded (deterministic) and optional LLM aliases.

Curated/embedded aliases come from the copilot's `aliases` sibling module (METRIC_ALIAS /
ASSET_ALIAS / embedded_aliases); the --llm path additionally asks the 4B model for
colloquial synonyms for asset/metric entities.
"""
import aliases as al


def build_aliases(conn, ents_by_id):
    cur = conn.cursor()
    rows = []
    for eid, e in ents_by_id.items():
        hay = (e["canonical"] + " " + e["display"] + " " + e["class_scope"]).lower()
        if e["type"] == "metric":
            for alias, needle in al.METRIC_ALIAS.items():
                if needle in (e["canonical"] + " " + e["display"]).lower():
                    rows.append((eid, alias, "curated"))
        if e["type"] == "asset":
            for alias, needle in al.ASSET_ALIAS.items():
                if needle in hay:
                    rows.append((eid, alias, "curated"))
            for emb in al.embedded_aliases(e["_src_name"]):
                rows.append((eid, emb.lower(), "embedded"))
    cur.executemany("INSERT OR IGNORE INTO aliases(entity_id, alias, source) VALUES (?,?,?)", rows)
    conn.commit()
    return len(rows)


def add_llm_aliases(conn, ents_by_id):
    import llm
    if not llm.is_up():
        print("  [llm] endpoint not reachable — skipping LLM aliases")
        return 0
    items = [(eid, e["type"], e["display"]) for eid, e in ents_by_id.items()
             if e["type"] in ("asset", "metric")]
    print(f"  [llm] generating colloquial aliases for {len(items)} entities ...")
    gen = al.gen_llm_aliases(items)
    rows = [(eid, s, "llm") for eid, syns in gen.items() for s in syns if 2 <= len(s) <= 40]
    conn.cursor().executemany("INSERT OR IGNORE INTO aliases(entity_id, alias, source) VALUES (?,?,?)", rows)
    conn.commit()
    return len(rows)
