"""data/registry/drift.py — registry↔information_schema drift check (ONE concern).

Answers: does every neuract.lt_mfm row's table_name physically exist, and does the cmd_catalog mirror's
sync-stamped table_exists flag AGREE with live truth? The dangerous class is `dangling_unmarked` — a table
missing live while the mirror still says table_exists='t' (a stale mirror lets the resolver pin a ghost and
the basket sampler hit the dark-table lane the hard way). [audit 2026-07-14, 01 F1; permanence check]

Never raises: an unreachable tunnel returns {"skipped": ...} — a drift check must not report drift it cannot
verify. Consumers: sweep/checks/registry_drift.py (CLI), host/server.py boot hook (fail-open telemetry),
tests/test_registry_drift_live.py (live CI lane)."""
from data.db_client import q
from config.databases import DATA_DB, CMD_CATALOG, CONSUMER_SCHEMA


def check():
    """{"dangling_marked": [...], "dangling_unmarked": [...], "unreferenced_physical": int, "mirror_synced_at": str}
    Each dangling entry is {"id", "name", "table"}. Outage → {"skipped": "outage: ..."}."""
    from data.outage import is_outage_error
    try:
        live = q(DATA_DB,
                 f"SELECT m.id, m.name, m.table_name FROM {CONSUMER_SCHEMA}.lt_mfm m "
                 "LEFT JOIN information_schema.tables t "
                 f"ON t.table_schema=$a${CONSUMER_SCHEMA}$a$ AND t.table_name=m.table_name "
                 "WHERE m.table_name IS NOT NULL AND t.table_name IS NULL ORDER BY m.id")
        phys = q(DATA_DB,
                 "SELECT count(*) FROM information_schema.tables t "
                 f"WHERE t.table_schema=$a${CONSUMER_SCHEMA}$a$ AND t.table_name LIKE $a$gic_%$a$ "
                 f"AND NOT EXISTS (SELECT 1 FROM {CONSUMER_SCHEMA}.lt_mfm m WHERE m.table_name=t.table_name)")
    except Exception as e:
        if is_outage_error(str(e)):
            return {"skipped": f"outage: {str(e)[:200]}"}
        raise
    dangling = {str(r[0]): {"id": r[0], "name": r[1], "table": r[2]} for r in (live or []) if r}
    try:
        mirror = q(CMD_CATALOG, "SELECT id, table_exists FROM registry_lt_mfm")
        synced = q(CMD_CATALOG, "SELECT synced_at FROM registry_sync_meta WHERE table_name=$a$registry_lt_mfm$a$")
    except Exception as e:
        # live truth known but the mirror is unreadable — report every dangler as unmarked (the safe direction)
        return {"dangling_marked": [], "dangling_unmarked": sorted(dangling.values(), key=lambda d: d["id"]),
                "unreferenced_physical": int(phys[0][0]) if phys and phys[0] else 0,
                "mirror_synced_at": None, "mirror_error": str(e)[:200]}
    stamp = {str(r[0]): r[1] for r in (mirror or []) if r}
    marked, unmarked = [], []
    for k, d in sorted(dangling.items(), key=lambda kv: kv[1]["id"]):
        # psql-engine rows read as text 'f'/'t'; pooled rows as bool — normalize
        flag = stamp.get(k)
        exists_stamp = flag in (True, "t", "true", "True")
        (unmarked if exists_stamp else marked).append(d)
    return {"dangling_marked": marked, "dangling_unmarked": unmarked,
            "unreferenced_physical": int(phys[0][0]) if phys and phys[0] else 0,
            "mirror_synced_at": str(synced[0][0]) if synced and synced[0] else None}
