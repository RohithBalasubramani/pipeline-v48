"""scripts/seed_pcc1a_asset3d.py — seed the pcc1a-v1 GLB catalog row so the tier-4 global-default resolves.

CLOSES the audit's one asset_3d config defect [2026-07-14, 14 F3]: viewer.default_asset_3d_key='pcc1a-v1'
points at a key with NO neuract.lt_asset_3d row, so the honest tier-4 fallback (individual/overview page
types) silently died — ~189 PCC-1A no_asset_3d records hang on this one row. The GLB itself EXISTS and is
served (host/web/public/media/3d/glb/PCC1A_v1.glb, media-copied 2026-07-12); only the catalog row is missing.

WHAT IT DOES (idempotent, re-runnable; mirrors scripts/seed_dg_asset3d.py):
  1. reads the 'pcc1a-v1' row from cmd_catalog.asset_3d_registry (the ground-truth catalog — never invents
     model metadata);
  2. verifies the GLB physically exists in the SERVED media home (host/web/public/media/3d/glb/) — a dead
     file pointer is worse than an honest blank, so a missing file ABORTS (never repoints to a DG model:
     the wrong-model contract);
  3. upserts neuract.lt_asset_3d (key, name, category, file, description) — the table the 4-tier resolver
     (domain/asset_3d.py) reads.
No per-MFM override binding (tier 1) — the global default key only needs the catalog row.

Run:  PYTHONPATH=. python3 scripts/seed_pcc1a_asset3d.py            (add --dry-run to preview)
Verify: validate/config_defaults_check.check() → no viewer.default_asset_3d_key issue."""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.db_client import q, pg_connect                          # noqa: E402
from config.databases import DATA_DB, DATA_SCHEMA                 # noqa: E402

KEY = "pcc1a-v1"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA_ROOT = os.path.join(ROOT, "host", "web", "public", "media")
MEDIA_SUBDIR = "3d/glb"


def seed(dry_run=False):
    rows = q("cmd_catalog",
             f"SELECT key, name, category, file, description FROM asset_3d_registry WHERE key='{KEY}'")
    if not rows:
        raise SystemExit(f"asset_3d_registry has no {KEY!r} row — nothing ground-truth to seed")
    _, name, category, file_field, description = rows[0]
    base = os.path.basename(str(file_field or "PCC1A_v1.glb"))
    served = os.path.join(MEDIA_ROOT, *MEDIA_SUBDIR.split("/"), base)
    if not os.path.isfile(served) or os.path.getsize(served) < 1024:
        raise SystemExit(f"served GLB missing/empty at {served} — refusing to seed a dead pointer "
                         f"(upload the model first; NEVER repoint the default at a DG model)")
    file_rel = f"{MEDIA_SUBDIR}/{base}"
    print(f"  served GLB ok  {served} ({os.path.getsize(served)} B)")
    if dry_run:
        print(f"  WOULD upsert {DATA_SCHEMA}.lt_asset_3d key={KEY!r} file={file_rel!r}")
        return
    now = datetime.now(timezone.utc)
    src = pg_connect(DATA_DB)
    try:
        with src.cursor() as c:
            c.execute(
                f"INSERT INTO {DATA_SCHEMA}.lt_asset_3d (key, name, category, file, description, created_at, updated_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (key) DO UPDATE SET name=EXCLUDED.name, category=EXCLUDED.category, "
                "file=EXCLUDED.file, description=EXCLUDED.description, updated_at=EXCLUDED.updated_at "
                "RETURNING id",
                (KEY, name or "PCC1A v1", category or "lt_panel", file_rel,
                 (description or "") + " [tier-4 global default; seeded 2026-07-15, audit 14 F3]", now, now))
            rid = c.fetchone()[0]
            src.commit()
            print(f"  lt_asset_3d    {KEY!r} -> id {rid} (file {file_rel})")
    finally:
        src.close()


if __name__ == "__main__":
    seed(dry_run="--dry-run" in sys.argv)
