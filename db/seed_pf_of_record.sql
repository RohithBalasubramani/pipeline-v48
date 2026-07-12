-- seed_pf_of_record.sql — ONE kVA→kW PF-of-record (hardcoding audit 2026-07-12, F7 — owner decided 0.9).
--
-- Two knobs converted nameplate kVA → rated kW with DIFFERENT factors: `rating.feeder_pf` (seeded 0.9, used by
-- config/nameplates.derive_ratings) and `nameplate.nominal_pf` (no row, code default was 0.8, used by
-- ems_exec/derivations/nameplate.feeder_rated_kw) — the same asset could render rated kW 12.5% apart between two
-- cards on one page. Owner picked 0.9 (matches the seeded rating.feeder_pf row and the 600 kVA × 0.9 = 540 kW
-- fixtures certified in tests). This seeds the row; the code default mirror in derivations/nameplate.py is 0.9 too.
-- BEHAVIOR CHANGE (intended): cards filled via feeder_rated_kw now show rated kW 12.5% higher than the old 0.8.
INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('nameplate.nominal_pf', '0.9', 'number', 'derivations.power',
   'kVA->kW PF-of-record for feeder_rated_kw; owner-aligned with rating.feeder_pf=0.9 (2026-07-12, hardcoding F7)')
ON CONFLICT (key) DO NOTHING;
