"""scripts/seed_quantity_vocab.py — materialize the quantity-vocab CODE DEFAULTS into cmd_catalog.app_config.

WHY: cfg() REPLACES (a DB `quantity.*` row overrides the code default entirely, it does not merge). The DB rows had
DRIFTED behind the code default (the unit-count keys #/count/events/nos were added to the code default but never
re-seeded), and the asset-domain classes (tap-position/engine-speed/pressure/fuel/autonomy/…) are new. This applier
makes the CODE DEFAULT the single source of truth and regenerates the DB rows from it — one home, no drift. Idempotent
(UPSERT the full dict). READ the code default, WRITE the DB. Run: python3 scripts/seed_quantity_vocab.py [--dry]

Re-run it any time a quantity_class default dict changes, so the live DB row never lags the code again.
"""
import sys, json
from config.databases import CMD_CATALOG
from data.db_client import pg_connect
from layer2 import quantity_class as qc

# key → (code-default value, note). Only the vocabularies with a code-default mirror in quantity_class.py.
SYNC = {
    "quantity.name_classes": (qc._NAME_CLASSES_DEFAULT,
        "name token / adjacent-pair → quantity class (leaf-most first, PAIR before single). Source of truth: "
        "layer2/quantity_class.py _NAME_CLASSES_DEFAULT. Regenerate via scripts/seed_quantity_vocab.py."),
    "quantity.unit_classes": (qc._UNIT_CLASSES_DEFAULT,
        "unit token → quantity class. Source of truth: layer2/quantity_class.py _UNIT_CLASSES_DEFAULT. "
        "Regenerate via scripts/seed_quantity_vocab.py."),
    "quantity.semantic_families": (qc._SEMANTIC_FAMILIES_DEFAULT,
        "name-level semantic family {family: {markers, classes}} — a slot naming a family binds only a same-family "
        "source (guards same-dimension '%' puns). Source of truth: quantity_class.py _SEMANTIC_FAMILIES_DEFAULT. "
        "Regenerate via scripts/seed_quantity_vocab.py."),
}

dry = "--dry" in sys.argv
conn = pg_connect(CMD_CATALOG)
conn.autocommit = False
cur = conn.cursor()
for key, (val, note) in SYNC.items():
    cur.execute("SELECT value FROM app_config WHERE key=%s", (key,))
    row = cur.fetchone()
    old = json.loads(row[0]) if row and row[0] else {}
    new = dict(val)
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted(k for k in set(old) & set(new) if old[k] != new[k])
    print(f"\n{key}: {len(old)} → {len(new)} keys")
    if added:   print(f"  + added   ({len(added)}): {added}")
    if removed: print(f"  - removed ({len(removed)}): {removed}")
    if changed: print(f"  ~ changed ({len(changed)}): {[(k, old[k], new[k]) for k in changed]}")
    if not (added or removed or changed):
        print("  (already in sync)")
    if not dry:
        cur.execute(
            "INSERT INTO app_config (key, value, data_type, section, note, updated_at) "
            "VALUES (%s, %s, 'json', 'quantity', %s, now()) "
            "ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, data_type='json', note=EXCLUDED.note, updated_at=now()",
            (key, json.dumps(new, ensure_ascii=False), note))
if dry:
    print("\n[--dry] no writes"); conn.rollback()
else:
    conn.commit(); print("\ncommitted.")
cur.close(); conn.close()
