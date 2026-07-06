-- db/fix_ups_recipe_derivations.sql — UPS card_data_recipe accuracy repair (db-data hardening, 2026-07-03).
-- Idempotent: content-guarded per-metric rewrites + reconciled NULLs; safe to re-run.
--
-- DEFECT (adversarial pages 17+18 + audit): the UPS asset dashboard cards (17,50,52,53,54,55,56,57,59) declare
-- COMPOSITE / PERMISSIVE / CAPACITY SCORES, TRANSFER-EVENT COUNTS, and BATTERY / AUTONOMY / RUNTIME telemetry as
-- kind='raw' metrics (ups_transfer_composite_score, ups_*_permissive_score, ups_capacity_*_score, ups_transfers_30d,
-- ups_transfer_events_today, ups_battery_soc_pct, ups_autonomy_index, ...). VERIFIED against live neuract
-- (gic_01_n3_ups_01_p1, 72 cols, 49k rows, 2026-07-03): NONE of these ups_* names is a real gic column, and NONE is a
-- derivation-registry LIBRARY key (only upsRatedKva exists). A single electrical UPS meter logs ZERO battery / SOC /
-- autonomy / runtime / transfer-event columns.
--   · kind='raw' on a NON-column metric FORCES the L2 AI to bind the closest column → the RAW-INTO-SCORE leak seen live:
--     card 54 readiness.metrics[]=100 / 0.993 (loadFactorPct on -186 kW); card 56 composite.floor.value=-178.3 /
--     kpiCells "Transfers today"=50 / "Average Input Voltage"=238.63 (active_power_total_kw + voltage_avg leaked into
--     score / transfer-count / voltage slots) — physically-impossible negative/>100 "scores" presented as fact.
--   · the SAME leak also produced the FALSE "not logged by this meter" per-leaf reasons on cards 57/58 for
--     active_power_total_kw / current_avg / voltage_avg / frequency_hz — those columns DO exist with 49k real rows;
--     the pipeline mis-bound (or failed to bind) and emitted a misleading reason.
--
-- FIX (honest-blank convention, layer2/prompts/data_instructions.md §derived/§73/§82 physical-walls):
--   PART A  reconciled_fields → NULL on 54/55/56/57/59 (recipe_reconcile.py is a dead stub; each mangled the
--           descriptive metric names into raw SLOT-name binds — 'score','readiness','inputVoltageV','scoreCells[i]'
--           — the exact vector for the raw-column leak). read() then COALESCEs the correct original `fields`.
--           (card 58 already NULLed by db/fix_card_data_recipe_repairs.sql PART A.)
--   PART B  the FOUR REAL electrical UPS metrics → their real gic column, kept kind='raw' (bind honestly):
--             ups_input_voltage_v  -> voltage_avg      ups_input_current_a -> current_avg
--             ups_bypass_frequency_hz -> frequency_hz  ups_demand          -> active_power_total_kw
--   PART C  every UNMEASURABLE ups_* metric (scores, permissives, capacity scores, transfer counts, battery / SOC /
--           reserve / thermal / autonomy / runtime / headroom, bypass-specific voltage on a single-meter UPS,
--           operating-mode) flips kind='raw' -> kind='derived'. It stays CATALOG-TRUTHFUL (these ARE derived
--           quantities, not raw columns) and the L2 AI honest-blanks it per the prompt: for a kind=derived slot with
--           no LIBRARY fn whose base_columns are all in the basket (there is none), emit NO field -> the leaf renders
--           blank with a 'derivation unbound' per-leaf reason instead of a fabricated raw-column value. The descriptive
--           metric name survives so the honest reason is accurate.
--
-- Run: psql -U postgres -h 127.0.0.1 -p 5432 -d cmd_catalog -f db/fix_ups_recipe_derivations.sql

-- ══ PART A — mangled reconciled_fields → NULL ═════════════════════════════════════════════════════════════════════
UPDATE card_data_recipe SET reconciled_fields = NULL
 WHERE card_id IN (54, 55, 56, 57, 59)
   AND reconciled_fields IS NOT NULL;

-- ══ PART B — real electrical ups_* metrics → real gic column (kind stays raw, binds honestly) ═════════════════════
-- Generic per-metric rewrite (no card ids in logic); ORDINALITY preserves field order; the @> guard makes re-runs no-ops.
UPDATE card_data_recipe SET fields = (
  SELECT jsonb_agg(CASE WHEN e->>'kind'='raw' AND e->>'metric'='ups_input_voltage_v'
                        THEN e || '{"metric":"voltage_avg"}'::jsonb ELSE e END ORDER BY ord)
  FROM jsonb_array_elements(fields) WITH ORDINALITY AS t(e, ord))
 WHERE fields @> '[{"kind":"raw","metric":"ups_input_voltage_v"}]';

UPDATE card_data_recipe SET fields = (
  SELECT jsonb_agg(CASE WHEN e->>'kind'='raw' AND e->>'metric'='ups_input_current_a'
                        THEN e || '{"metric":"current_avg"}'::jsonb ELSE e END ORDER BY ord)
  FROM jsonb_array_elements(fields) WITH ORDINALITY AS t(e, ord))
 WHERE fields @> '[{"kind":"raw","metric":"ups_input_current_a"}]';

UPDATE card_data_recipe SET fields = (
  SELECT jsonb_agg(CASE WHEN e->>'kind'='raw' AND e->>'metric'='ups_bypass_frequency_hz'
                        THEN e || '{"metric":"frequency_hz"}'::jsonb ELSE e END ORDER BY ord)
  FROM jsonb_array_elements(fields) WITH ORDINALITY AS t(e, ord))
 WHERE fields @> '[{"kind":"raw","metric":"ups_bypass_frequency_hz"}]';

UPDATE card_data_recipe SET fields = (
  SELECT jsonb_agg(CASE WHEN e->>'kind'='raw' AND e->>'metric'='ups_demand'
                        THEN e || '{"metric":"active_power_total_kw"}'::jsonb ELSE e END ORDER BY ord)
  FROM jsonb_array_elements(fields) WITH ORDINALITY AS t(e, ord))
 WHERE fields @> '[{"kind":"raw","metric":"ups_demand"}]';

-- ══ PART C — unmeasurable ups_* metrics → kind='derived' (AI honest-blanks; no fabricated raw bind) ═══════════════
-- The remaining ups_* raw metrics (after PART B renamed the four real ones) are ALL non-column derived quantities.
-- A single generic UPDATE flips every surviving kind='raw' + metric LIKE 'ups\_%' to kind='derived'.
UPDATE card_data_recipe SET fields = (
  SELECT jsonb_agg(CASE WHEN e->>'kind'='raw' AND (e->>'metric') LIKE 'ups\_%'
                        THEN e || '{"kind":"derived"}'::jsonb ELSE e END ORDER BY ord)
  FROM jsonb_array_elements(fields) WITH ORDINALITY AS t(e, ord))
 WHERE fields @> '[{"kind":"raw"}]'
   AND EXISTS (SELECT 1 FROM jsonb_array_elements(fields) x
              WHERE x->>'kind'='raw' AND (x->>'metric') LIKE 'ups\_%');
