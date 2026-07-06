-- db/seed_morphmap_flag.sql — ITEM 18 PREP: the morph-map emit contract's DEFAULT-OFF switch.
--
-- emit.morphmap_mode — 'off' (DEFAULT, matches the code default in layer2/emit/morphmap/mode.py, so seeding this row
-- changes NOTHING on the default path). The morph-map parallel path ({"morphs": {path: value}} instead of the full
-- exact_metadata retype; layer2/emit/morphmap/) is BUILT + offline-A/B'd (tools/morphmap_ab.py,
-- outputs/morphmap_ab_offline.md) but NOT wired into layer2/emit/emit.py / layer2/build.py — the live seam lands
-- post-certification and will read this row. Values reserved for that seam: off | shadow | on.
--
-- Idempotent. Run: psql (cmd_catalog DSN per config/databases.py) -f db/seed_morphmap_flag.sql

INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('emit.morphmap_mode', 'off', 'text', 'emit',
  'morph-map emit contract switch (ITEM 18): off (default — full exact_metadata retype contract, current behavior) | shadow | on. Read by layer2/emit/morphmap/mode.py; the live seam is unwired until post-cert, so today only the flag exists.')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, data_type = EXCLUDED.data_type,
                                section = EXCLUDED.section, note = EXCLUDED.note;
