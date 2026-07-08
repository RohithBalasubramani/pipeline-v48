-- db/seed_cache_ttl.sql — the resolution-cache TTL knob [poison-permanent-fix 2026-07-09].
-- Bounds the lifetime of any per-process resolution-cache entry (panel members, registry rows/edges, has_data) so a
-- transient :5433 tunnel flap can never poison the long-running host server past this many seconds. Code default 120s
-- (data/ttl_cache.py). Idempotent. Run: psql -h localhost -p 5432 -d cmd_catalog -f db/seed_cache_ttl.sql
INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('cache.resolution_ttl_s', '120', 'int', 'cache',
   'Seconds a resolution-cache entry (panel_members/lt_mfm/has_data TTLCache) stays valid before re-read. A tunnel '
   'flap self-heals within this window with no server restart. Mirror: data/ttl_cache.py _TTL_DEFAULT.')
ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, note=EXCLUDED.note;
