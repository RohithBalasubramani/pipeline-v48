"""scripts/seed_feeder_class.py — derive + UPSERT the FEEDER-CLASS fact for every registry meter (T2.1-3).

WHY: member_registry_facts restores type_code/load_group, but lt_mfm_type carries only 4 codes (apfc, lt_panel,
transformer, ups) — so bpdb/hhf/incomer/spare/dg/ahu feeders have NO type-code and can only be matched by the fragile
name_contains. feeder_class is the fact that fixes that: a token-derived class per meter table, stored in
registry_feeder_class, that the roster matchers key on (a feeder_classes any-of branch).

The derivation is a PURE, IMPORTABLE function (derive_feeder_class) so it is unit-tested offline. This applier reads
registry_lt_mfm (id, name, table_name) from the cmd_catalog mirror, derives the class from the meter NAME tokens
(split on [-_ ], token-exact, priority-ordered), and UPSERTs one row per table (reviewed=false — a human confirms /
edits the row, then flips reviewed). Idempotent: re-run any time the registry or the token rules change. Prints a
human-review report (count per class + the UNCLASSIFIED names so a human can add rows).

Run: python3 scripts/seed_feeder_class.py [--dry]
"""
import os
import re
import sys

# tokens split on dash / underscore / whitespace — ASCII-safe, token-EXACT membership (no substring puns).
_SPLIT = re.compile(r"[-_\s]+")

# priority-ordered (class, candidate tokens) — the FIRST rule with a token present wins. The solar+incomer PAIR is
# checked before plain 'incomer' (a 'solar incomer' is its own class, not a bare incomer). token-exact throughout.
_RULES = (
    ("incomer", ("incomer",)),
    ("ups", ("ups",)),
    ("bpdb", ("bpdb", "bpdp")),        # 'bpdp' is a common misspelling of the same board class → 'bpdb'
    ("hhf", ("hhf",)),
    ("apfcr", ("apfc", "apfcr")),      # APFC / APFCR panels → the one 'apfcr' class
    ("dg", ("dg",)),
    ("ahu", ("ahu",)),
    ("spare", ("spare",)),
)


def _tokens(name):
    """The lower-cased tokens of a meter name, split on [-_ ] (empties dropped)."""
    return [t for t in _SPLIT.split(str(name or "").strip().lower()) if t]


def _derive(name):
    """(feeder_class, derived_from_token) — priority-ordered token-EXACT classification; (None, None) when nothing
    matches (unclassified — a human adds the row)."""
    tset = set(_tokens(name))
    if "solar" in tset and "incomer" in tset:
        return "solar-incomer", "solar+incomer"
    for cls, cands in _RULES:
        for tok in cands:
            if tok in tset:
                return cls, tok
    return None, None


def derive_feeder_class(name):
    """PURE, importable: a meter NAME → its feeder class ('ups'/'bpdb'/'hhf'/'solar-incomer'/'incomer'/'apfcr'/'dg'/
    'ahu'/'spare') or None (unclassified). Token-exact + priority-ordered; 'solar incomer' → 'solar-incomer' (never the
    bare 'incomer'). This is the derivation the seed writes and the tests pin."""
    return _derive(name)[0]


def _meter_rows():
    """[(id, name, table_name)] from registry_lt_mfm (cmd_catalog mirror). DB-touching — called only from main()."""
    from config.databases import CMD_CATALOG
    from data.db_client import q
    rows = q(CMD_CATALOG,
             "SELECT id, regexp_replace(name,'[[:cntrl:]]',' ','g'), table_name "
             "FROM registry_lt_mfm WHERE table_name IS NOT NULL AND table_name <> '' ORDER BY id")
    return [(r[0], r[1], r[2]) for r in rows]


def main(argv):
    from config.databases import CMD_CATALOG
    from data.db_client import pg_connect

    dry = "--dry" in argv
    rows = _meter_rows()

    per_class = {}                                          # class -> count
    unclassified = []                                       # names with no class (human adds a row)
    upserts = []                                            # (table_name, feeder_class, derived_from)
    for _mid, name, table in rows:
        cls, tok = _derive(name)
        if cls is None:
            unclassified.append(name)
            continue
        per_class[cls] = per_class.get(cls, 0) + 1
        upserts.append((table, cls, tok))

    conn = pg_connect(CMD_CATALOG)
    conn.autocommit = False
    cur = conn.cursor()
    for table, cls, tok in upserts:
        cur.execute(
            "INSERT INTO registry_feeder_class (table_name, feeder_class, derived_from, reviewed) "
            "VALUES (%s, %s, %s, false) "
            "ON CONFLICT (table_name) DO UPDATE SET feeder_class=EXCLUDED.feeder_class, "
            "derived_from=EXCLUDED.derived_from",           # reviewed/note preserved on re-run (a human's edits stand)
            (table, cls, tok))

    # ── human-review report ─────────────────────────────────────────────────────────────────────────────────────────
    print(f"\nregistry meters read: {len(rows)}")
    print(f"classified: {len(upserts)}   unclassified: {len(unclassified)}")
    print("\nper class:")
    for cls in sorted(per_class):
        print(f"  {cls:<14} {per_class[cls]}")
    print(f"\nUNCLASSIFIED names ({len(unclassified)}) — a human may add registry_feeder_class rows for these:")
    for nm in unclassified:
        print(f"  - {nm}")

    if dry:
        conn.rollback()
        print("\n[--dry] no writes")
    else:
        conn.commit()
        print(f"\ncommitted: {len(upserts)} rows upserted into registry_feeder_class")
    cur.close()
    conn.close()


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    main(sys.argv)
