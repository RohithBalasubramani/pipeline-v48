"""config/seed_app_config.py — seed cmd_catalog.app_config from the ATOMIC per-concern def files (config/defs/*). The
def files are the single source of every DB-backed config key/default/type; this walks ALL_DEFS and upserts. Run after
adding/editing a def. No hand-written monolith seed. [atomic DB-config]

  python3 config/seed_app_config.py        # upsert every def into app_config
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # run standalone from anywhere

from data.db_client import pg_connect
from config.databases import CMD_CATALOG
from config.defs import ALL_DEFS


def _as_str(d):
    """The def's `default` (native literal) → the app_config string value, matching its data_type."""
    v, dt = d["default"], d["data_type"]
    if dt == "json":
        return v if isinstance(v, str) else json.dumps(v)
    if dt == "bool":
        return "true" if (v is True or str(v).lower() in ("1", "true", "yes", "t")) else "false"
    return str(v)


def seed():
    rows = [(d["key"], _as_str(d), d["data_type"], d.get("section", "")) for d in ALL_DEFS]
    conn = pg_connect(CMD_CATALOG)
    try:
        cur = conn.cursor()
        cur.executemany(
            "INSERT INTO app_config (key, value, data_type, section) VALUES (%s,%s,%s,%s) "
            "ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, data_type=EXCLUDED.data_type, "
            "section=EXCLUDED.section, updated_at=now()",
            rows,
        )
        conn.commit()
        return len(rows)
    finally:
        conn.close()


if __name__ == "__main__":
    n = seed()
    print(f"seeded {n} app_config keys from config/defs/")
