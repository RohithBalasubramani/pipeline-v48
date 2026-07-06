-- db/seed_basket_logged_floor.sql — SEAM 4: Layer-1b basket logged-column floor + avg-from-phase. Idempotent (upsert).
-- WHY: the 1b basket was ONLY the AI's `feasible` array, which on some prompts dropped a meter's REAL LOGGED columns
-- (mfm171 gic_15_n3_pcc_01_transformer_01_se: 57 logged -> 28 basket, voltage_r_n/voltage_avg dropped), and Layer 2 then
-- false-blanked cards for columns that ARE in the DB. These knobs make the basket ALWAYS carry the logged columns
-- (code defaults identical — rows make the policy visible/editable, no code change to tune).
INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('layer1b.basket.include_logged_floor', 'true', 'bool', 'layer1b',
   'the 1b basket ALWAYS includes the resolved meter''s real LOGGED metric columns (has_data=Y, kind!=event), unioned '
   'with the AI feasible set — so a logged column (voltage_r_n, current_r, active_power_total_kw) is never dropped from '
   'the basket and false-blanked by Layer 2. Set false to revert to AI-feasible-only. [SEAM 4: logged floor]'),
  ('layer1b.basket.max_columns', '400', 'int', 'layer1b',
   'upper bound on basket columns (logged floor kept ahead of empty AI-only columns, so a cap never drops a real logged '
   'column before an empty one). ~400 is effectively uncapped for neuract meters (~63 metric cols); guards ~190-col '
   'lt_panels tables. [SEAM 4: bounded basket]'),
  ('layer1b.basket.derive_avg_from_phase', 'true', 'bool', 'layer1b',
   'when a present-but-empty avg column (voltage_ll_avg, current_avg) has its per-phase siblings LOGGED, flag it '
   'derivable=avg_from_phase with the logged phase source columns so Layer 2/executor computes the mean instead of '
   'blanking. has_data stays false (no fabrication) — this is a recovery pointer. [SEAM 4: avg-from-phase]')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, data_type = EXCLUDED.data_type,
                                section = EXCLUDED.section, note = EXCLUDED.note, updated_at = now();
