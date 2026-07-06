"""scripts/sync_neuract_registry.py — mirror the CANONICAL neuract asset/topology REGISTRY into cmd_catalog.

USER DIRECTIVE (2026-07-04, 'all these bring to OUR dbs'): the pipeline must read all asset→table→column→class→feeder
METADATA locally (cmd_catalog, :5432), never over the flaky :5433 tunnel at request time. This script is the ONE
re-runnable sync: SELECT each canonical registry table from the :5433 tunnel (target_version1.neuract, READ-ONLY —
NEVER writes neuract) and land it in cmd_catalog as `registry_<name>`, refreshed atomically per table
(CREATE-IF-ABSENT + full delete/insert inside one transaction = idempotent upsert + stale-row delete), then stamp
`registry_sync_meta` (table_name, synced_at, row_count). Re-run whenever the plant DBs change:

    PYTHONPATH=. python3.11 scripts/sync_neuract_registry.py

Time-series DATA reads stay on :5433 — ONLY registry metadata is mirrored.

Enrichment stamped during sync (the F11 registry-drift reconcile):
  · registry_lt_mfm.table_exists   — the row's table_name physically exists in the neuract schema (14 canonical rows
                                     point at ghost tables: gic_15 *_sch stubs + gic_30 *_se);
  · registry_lt_mfm.never_wired    — the table has ZERO device_mappings rows (the data-driven never-wired signal that
                                     replaces the `_sch` name-suffix hardcode in asset_candidates);
  · registry_sync_meta '_unreferenced_physical_tables' row — live physical gic_*/pqm_* data tables that NO canonical
                                     registry row references (recorded, not fabricated into the registry).
"""
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.databases import DATA_DB, DATA_SCHEMA, CMD_CATALOG          # noqa: E402
from data.db_client import pg_connect                                   # noqa: E402

# the canonical registry tables to mirror (asset_parameter/lt_mfm_incoming are currently thin/empty — mirrored anyway
# for completeness so a future canonical fill needs no code change here).
TABLES = ("device_mappings", "asset", "asset_type", "asset_parameter",
          "lt_mfm", "lt_mfm_type", "lt_mfm_incoming", "lt_mfm_outgoing")

MIRROR_PREFIX = "registry_"


def _cols(src_cur, table):
    src_cur.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position", (DATA_SCHEMA, table))
    return src_cur.fetchall()


def _ddl_type(data_type):
    """information_schema.data_type is valid DDL for every type these tables use (bigint, text, character varying,
    double precision, real, timestamp with time zone)."""
    return {"ARRAY": "text[]", "USER-DEFINED": "text"}.get(data_type, data_type)


def _physical_tables(src_cur):
    src_cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=%s", (DATA_SCHEMA,))
    return {r[0] for r in src_cur.fetchall()}


def sync():
    src = pg_connect(DATA_DB)          # :5433 tunnel — READ-ONLY source
    dst = pg_connect(CMD_CATALOG)      # local :5432 — the mirror home
    now = datetime.now(timezone.utc)
    counts = {}
    try:
        with src.cursor() as sc, dst.cursor() as dc:
            dc.execute("CREATE TABLE IF NOT EXISTS registry_sync_meta ("
                       "table_name text PRIMARY KEY, synced_at timestamptz NOT NULL, "
                       "row_count integer NOT NULL, note text)")

            physical = _physical_tables(sc)
            sc.execute(f"SELECT DISTINCT table_name FROM {DATA_SCHEMA}.device_mappings")
            wired = {r[0] for r in sc.fetchall()}

            for t in TABLES:
                cols = _cols(sc, t)
                if not cols:
                    print(f"  !! {t}: not found on source — skipped")
                    continue
                names = [c[0] for c in cols]
                quoted = ", ".join(f'"{n}"' for n in names)
                mirror = f"{MIRROR_PREFIX}{t}"
                ddl_cols = ", ".join(f'"{n}" {_ddl_type(dt)}' for n, dt in cols)
                extra = ", table_exists boolean, never_wired boolean" if t == "lt_mfm" else ""
                dc.execute(f'CREATE TABLE IF NOT EXISTS "{mirror}" ({ddl_cols}{extra})')
                # additive drift-safety: a NEW source column appears on re-run without dropping the mirror
                for n, dt in cols:
                    dc.execute(f'ALTER TABLE "{mirror}" ADD COLUMN IF NOT EXISTS "{n}" {_ddl_type(dt)}')

                sc.execute(f'SELECT {quoted} FROM {DATA_SCHEMA}."{t}"')
                rows = sc.fetchall()
                dc.execute(f'DELETE FROM "{mirror}"')                     # stale-row delete (atomic in this txn)
                if rows:
                    ph = ", ".join(["%s"] * len(names))
                    if t == "lt_mfm":
                        i_tbl, insert_cols = names.index("table_name"), quoted + ', table_exists, never_wired'
                        rows = [tuple(r) + (r[i_tbl] in physical, r[i_tbl] not in wired) for r in rows]
                        ph += ", %s, %s"
                        dc.executemany(f'INSERT INTO "{mirror}" ({insert_cols}) VALUES ({ph})', rows)
                    else:
                        dc.executemany(f'INSERT INTO "{mirror}" ({quoted}) VALUES ({ph})', rows)
                counts[t] = len(rows)
                dc.execute("INSERT INTO registry_sync_meta (table_name, synced_at, row_count) VALUES (%s,%s,%s) "
                           "ON CONFLICT (table_name) DO UPDATE SET synced_at=EXCLUDED.synced_at, "
                           "row_count=EXCLUDED.row_count", (mirror, now, len(rows)))
                print(f"  {mirror}: {len(rows)} rows")

            # F11 reconcile telemetry: physical data tables NO canonical registry row references (recorded, not invented)
            sc.execute(f"SELECT table_name FROM {DATA_SCHEMA}.lt_mfm UNION SELECT table_name FROM {DATA_SCHEMA}.asset")
            referenced = {r[0] for r in sc.fetchall()}
            unreferenced = sorted(t for t in (physical - referenced)
                                  if "timestamp_utc" in _col_names(sc, t))    # data tables only, not registry tables
            dc.execute("INSERT INTO registry_sync_meta (table_name, synced_at, row_count, note) VALUES (%s,%s,%s,%s) "
                       "ON CONFLICT (table_name) DO UPDATE SET synced_at=EXCLUDED.synced_at, "
                       "row_count=EXCLUDED.row_count, note=EXCLUDED.note",
                       ("_unreferenced_physical_tables", now, len(unreferenced), json.dumps(unreferenced)))
            print(f"  unreferenced physical data tables recorded: {len(unreferenced)}")
        dst.commit()
    except Exception:
        dst.rollback()
        raise
    finally:
        src.close()
        dst.close()
    return counts


def _col_names(src_cur, table):
    src_cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema=%s AND table_name=%s",
                    (DATA_SCHEMA, table))
    return {r[0] for r in src_cur.fetchall()}


if __name__ == "__main__":
    print(f"syncing canonical neuract registry → {CMD_CATALOG} (registry_*) ...")
    c = sync()
    print(f"done: {sum(c.values())} rows across {len(c)} tables")
