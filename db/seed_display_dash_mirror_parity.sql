-- A6b (2026-07-06): display.unit_value_key_suffixes — the unit-suffixed VALUE-key vocabulary for the serve-boundary
-- honest-dash (host/display_dash.py SECOND RULE). This row was created/extended LIVE (never seeded): first
-- ["kw","kwh"] → ["kw","kwh","kva","kvar"] → ["kw","kwh","kva","kvar","pct"], so a fresh cmd_catalog provision
-- silently fell back to whatever the code default was at build time. Seed the canonical value so a fresh DB and the
-- code-default mirror (display_dash._value_key_suffixes) agree byte-for-byte — the A6b DB-outage fmt(null)
-- re-crash-parity contract: DB up, DB freshly seeded, and DB down must all dash the same leaves.
BEGIN;

INSERT INTO app_config (key, value, data_type, section, note)
VALUES ('display.unit_value_key_suffixes', '["kw","kwh","kva","kvar","pct"]', 'json', 'display',
        'honest-dash unit-suffixed VALUE-key vocabulary (suffix match, lowercase): a scalar null whose KEY ends in a listed measurement suffix (kw/kwh/kva/kvar/pct, totalKvar, utilizationPct) is dashed when the harvested default proves the leaf numeric at that path. Code default in host/display_dash.py MUST mirror this row byte-for-byte (A6b outage parity).')
ON CONFLICT (key) DO UPDATE
SET value = EXCLUDED.value, data_type = EXCLUDED.data_type, section = EXCLUDED.section, note = EXCLUDED.note,
    updated_at = now();

COMMIT;
