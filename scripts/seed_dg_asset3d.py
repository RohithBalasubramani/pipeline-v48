"""scripts/seed_dg_asset3d.py — seed the REAL Diesel-Generator 3D models into the neuract lt_asset_3d catalog.

CLOSES sweep DEFECT K (fullsweep_20260706_004334, page 11 dg/engine-cooling, card 60 Engine 3D Callout Viewer):
the 4-tier resolver (layer2/emit/metadata/asset_3d.py) read an EMPTY neuract.lt_asset_3d + all-NULL
lt_mfm.asset_3d_override_id, so a DG page honest-blanked its 3D card even though a REAL DG model exists —
cmd_catalog.asset_3d_registry 'dg-final-v2' → /home/rohith/CMD_V2/public/models/dg_final_v2.glb (985 KB, verified
GLB nodes: Engine / Alternator / DAY tank / exhaust manifold / oil pump — a genuine generator model, NOT a re-labelled
panel). That blank was AVOIDABLE, so per the fix-order mandate (prompts → DB rows → code) this is a pure DB seed.

WHAT IT DOES (idempotent, re-runnable):
  1. reads the model rows from cmd_catalog.asset_3d_registry (the CMD_V2 ground-truth catalog — slug, label,
     category, description, file_abs). NO model metadata is invented here.
  2. copies each registry GLB into the v48 web media home (host/web/public/media/3d/glb/ — served by the web origin) so the
     emitted absolute url (config.asset3d_media: viewer.glb_media_base + file) actually serves. sha256-compared —
     copied only when absent/different.
  3. upserts neuract.lt_asset_3d (key, name, category, file, description) — the table the 4-tier resolver reads.
  4. binds the ENGINE-CALLOUT model (ENGINE_SLUG) as the per-MFM override (lt_mfm.asset_3d_override_id, resolver
     tier 1) for the ACTUAL generator meters only. Type-default (tier 3) is deliberately NOT used: every DG meter
     shares mfm_type 2 'LT Panel' with 257 panel/feeder meters — a type default would smear the DG model onto
     non-DG assets (fabrication). Generator meters are matched by name (\\mDG[- ]?0?[1-6]\\M), which selects
     'DG-1 MFM'…'DG-6 MFM' + 'GIC-28-N?-DG-0? [Jackson]' and EXCLUDES the non-generator DG-side meters
     ('GIC-29 DG OG-*' outgoing feeders, 'GIC-30 11KV HT DG Incomer') — a generator model on a feeder/incomer
     meter would be the wrong asset. Existing non-NULL overrides are never clobbered.

The fuel-tank model ('dg-v1', card 63 Fuel Tank Anatomy) is cataloged + media-copied too, but NOT bound as an
override: only one model binds per meter (no rating/page_type variant columns until the 0014 migration lands), and
card 63's GLB is a frontend asset anyway (ems_exec/renderers/fuel_anatomy.py never touches it).

Run:  PYTHONPATH=. python3.11 scripts/seed_dg_asset3d.py            (add --dry-run to preview)
After a run, re-run scripts/sync_neuract_registry.py so the cmd_catalog registry_lt_mfm mirror picks up the
new asset_3d_override_id values.
"""
import hashlib
import os
import shutil
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.databases import CMD_CATALOG, DATA_DB, DATA_SCHEMA          # noqa: E402
from data.db_client import pg_connect                                    # noqa: E402

# the registry slugs to catalog (cmd_catalog.asset_3d_registry is the metadata source of truth) + which one binds.
SLUGS = ("dg-final-v2", "dg-v1")
ENGINE_SLUG = "dg-final-v2"                                # tier-1 override target (card 60 Engine 3D Callout Viewer)

# generator-meter matcher: \mDG[- ]?0?[1-6]\M — 'DG-1 MFM', 'GIC-28-N3-DG-03 [Jackson]'; NOT 'DG OG-1', NOT
# 'HT DG Incomer'. Belt-and-braces NOT-ILIKE exclusions guard future rename drift.
GENERATOR_NAME_SQL = (r"name ~* '\mDG[- ]?0?[1-6]\M' AND name NOT ILIKE '%%incomer%%' AND name NOT ILIKE '%% OG%%'")
MAX_GENERATOR_MATCHES = 20                                 # sanity fuse — a broader match means the pattern drifted

# GLB media home = host/web/public/media (the v48 web origin serves it directly; legacy-EMS :8890 RETIRED 2026-07-12).
_V48 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA_ROOT = os.environ.get(
    "EMS_MEDIA_ROOT",
    os.path.normpath(os.path.join(_V48, "host", "web", "public", "media")))
MEDIA_SUBDIR = "3d/glb"                                    # lt_asset_3d.file = '3d/glb/<basename>' hangs off /media/


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _registry_rows(slugs):
    """{key: (name, category, description, glb_path)} from cmd_catalog.asset_3d_registry. Fails loudly on a missing
    key or a missing/empty GLB file — this script never invents a model."""
    cat = pg_connect(CMD_CATALOG)
    try:
        with cat.cursor() as c:
            c.execute("SELECT key, name, category, description, glb_path FROM asset_3d_registry "
                      "WHERE key = ANY(%s)", (list(slugs),))
            rows = {r[0]: (r[1], r[2], r[3], r[4]) for r in c.fetchall()}
    finally:
        cat.close()
    for s in slugs:
        if s not in rows:
            raise SystemExit(f"asset_3d_registry has no row for key {s!r} — nothing to seed")
        fa = rows[s][3]
        if not fa or not os.path.isfile(fa) or os.path.getsize(fa) == 0:
            raise SystemExit(f"registry key {s!r} names no real GLB on disk ({fa!r}) — refusing to seed a ghost")
    return rows


def seed(dry_run=False):
    rows = _registry_rows(SLUGS)

    # ── 2. media copy (sha-compared, idempotent) ────────────────────────────────────────────────────────────────────
    dest_dir = os.path.join(MEDIA_ROOT, *MEDIA_SUBDIR.split("/"))
    os.makedirs(dest_dir, exist_ok=True)
    file_rel = {}
    for slug, (_l, _c, _d, file_abs) in rows.items():
        base = os.path.basename(file_abs)
        dest = os.path.join(dest_dir, base)
        file_rel[slug] = f"{MEDIA_SUBDIR}/{base}"
        if os.path.isfile(dest) and _sha(dest) == _sha(file_abs):
            print(f"  media ok      {file_rel[slug]} (unchanged)")
        elif dry_run:
            print(f"  media WOULD copy {file_abs} -> {dest}")
        else:
            shutil.copy2(file_abs, dest)
            print(f"  media copied  {file_abs} -> {dest} ({os.path.getsize(dest)} B)")

    # ── 3. lt_asset_3d upsert + 4. generator override bind ─────────────────────────────────────────────────────────
    now = datetime.now(timezone.utc)
    src = pg_connect(DATA_DB)
    try:
        with src.cursor() as c:
            ids = {}
            for slug, (label, category, description, _fa) in rows.items():
                if dry_run:
                    print(f"  WOULD upsert lt_asset_3d key={slug!r} file={file_rel[slug]!r}")
                    continue
                c.execute(
                    f"INSERT INTO {DATA_SCHEMA}.lt_asset_3d (key, name, category, file, description, created_at, updated_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (key) DO UPDATE SET name=EXCLUDED.name, category=EXCLUDED.category, "
                    "file=EXCLUDED.file, description=EXCLUDED.description, updated_at=EXCLUDED.updated_at "
                    "RETURNING id",
                    (slug, label, category or "source", file_rel[slug], description or "", now, now))
                ids[slug] = c.fetchone()[0]
                print(f"  lt_asset_3d   {slug!r} -> id {ids[slug]} (file {file_rel[slug]})")

            c.execute(f"SELECT id, name FROM {DATA_SCHEMA}.lt_mfm WHERE {GENERATOR_NAME_SQL} ORDER BY id")
            gens = c.fetchall()
            print(f"  generator meters matched ({len(gens)}): {[f'{i} {n}' for i, n in gens]}")
            if not gens or len(gens) > MAX_GENERATOR_MATCHES:
                raise SystemExit(f"generator matcher returned {len(gens)} rows — pattern drift, refusing to bind")
            if dry_run:
                print(f"  WOULD bind asset_3d_override_id={ENGINE_SLUG!r} on {len(gens)} meters (NULL overrides only)")
            else:
                c.execute(
                    f"UPDATE {DATA_SCHEMA}.lt_mfm SET asset_3d_override_id = %s "
                    f"WHERE {GENERATOR_NAME_SQL} AND (asset_3d_override_id IS NULL OR asset_3d_override_id = %s)",
                    (ids[ENGINE_SLUG], ids[ENGINE_SLUG]))
                print(f"  lt_mfm        asset_3d_override_id={ids[ENGINE_SLUG]} ({ENGINE_SLUG}) on {c.rowcount} meters")
        if dry_run:
            src.rollback()
        else:
            src.commit()
    except Exception:
        src.rollback()
        raise
    finally:
        src.close()


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    print(f"seeding DG 3D models → {DATA_DB}.{DATA_SCHEMA} (media root {MEDIA_ROOT}){' [DRY RUN]' if dry else ''}")
    seed(dry_run=dry)
    print("done." + ("" if dry else "  now re-run scripts/sync_neuract_registry.py to refresh the registry mirror."))
