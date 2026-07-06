-- db/fix_card_data_recipe_repairs.sql — card_data_recipe accuracy repairs (db-data hardening, 2026-07-03).
-- Idempotent: keyed UPDATEs guarded by content predicates; safe to re-run.
--
-- ══ PART A — WRONG-CARD reconciled_fields → NULL (fall back to the correct original `fields`) ══════════════════════
-- layer2/catalog/card_data_recipe.read() COALESCES reconciled_fields over fields. The reconcile process that wrote
-- these rows is GONE (layer2/resolve/recipe_reconcile.py is a TODO stub — nothing can regenerate them) and each row
-- below verifiably carries ANOTHER card's content (title/quantity/unit-family mismatch vs the card's own component,
-- checked against cards.title + card_handling + card_payloads.payload_stripped on 2026-07-03):
--   30  'kW Load % of Rated Capacity'      reconciled titled 'Energy Consumption' + lost every real column hint
--   38  'Current Monitor (Real-Time)'      reconciled = VOLTAGE monitor (voltage_r_n/_y_n/_b_n, V) — sibling card 37
--   45  'Current Live Health'              reconciled = 'Voltage Live Health' content (V tiles) — sibling card 43
--   46  'Current History'                  reconciled = VOLTAGE history series (voltage_r_n, V) — sibling card 44
--   58  'UPS Load'                         reconciled = readiness score-cells (kva/kw/current /100) — different card
--   61  'Thermal Timeline' (DG cooling)    reconciled = TRANSFORMER thermal (hotspot/oil/winding) — wrong asset class
--   64  'All Runs (Fuel Log)'              reconciled = PQ events table (sag/swell/vDeviation/cause) — wrong card
--   70  'Live Operations & Runtime'        reconciled = readiness score-cells — different card
--   72  'Energy & Reliability'             reconciled = readiness score-cells — different card
--   89  'DG Energy & Runtime'              reconciled = Frequency/PF pair — wrong quantities for the card
--   99  'Central 3D Asset Viewer (kit)'    reconciled = chiller metrics (evaporator_pressure/cop) — wrong card
--   106 'Element Health'                   reconciled = pressure content (peakPressure Bar) on a temp/vibration card
--   109 'Oil & Water Status'               reconciled = 'Motor Health' content (card 107's) — wrong card
--   111 'AHU — 3D Asset Viewer'            reconciled = chiller metrics (evaporator_pressure/cop) — wrong card
-- The original `fields` for every one of these describe the REAL card (audit: "the original fields were correct in
-- every case"), so NULL is a strict accuracy improvement, per-leaf honest, and reversible from git/pg history.
UPDATE card_data_recipe SET reconciled_fields = NULL
 WHERE card_id IN (30, 38, 45, 46, 58, 61, 64, 70, 72, 89, 99, 106, 109, 111)
   AND reconciled_fields IS NOT NULL;

-- ══ PART B — synthetic DERIVED frame keys mislabeled kind='raw' in `fields` ════════════════════════════════════════
-- These metric names are NOT neuract gic_* columns (live schema check 2026-07-03: 0 gic tables carry any of them);
-- they are the RECOVERY_FN target keys the executor fills via the derivation LIBRARY. Declared kind='raw' they steer
-- the L2 AI into hallucinated-column gate failures; as kind='derived' + the LIBRARY value_key in `metric` (the only
-- key _recipe_fields renders to the prompt) the AI can name the real recovery fn. Generic per-metric rewrite — no
-- card ids hardcoded; ORDINALITY preserves field order; the LIKE guard makes re-runs no-ops.
UPDATE card_data_recipe SET fields = (
  SELECT jsonb_agg(CASE WHEN e->>'kind'='raw' AND e->>'metric'='kpi_kw_load_pct_of_rated'
                        THEN e || '{"kind":"derived","metric":"kpiKwLoadPctOfRated"}'::jsonb ELSE e END ORDER BY ord)
  FROM jsonb_array_elements(fields) WITH ORDINALITY AS t(e, ord))
 WHERE fields @> '[{"kind":"raw","metric":"kpi_kw_load_pct_of_rated"}]';

UPDATE card_data_recipe SET fields = (
  SELECT jsonb_agg(CASE WHEN e->>'kind'='raw' AND e->>'metric'='kpi_load_factor'
                        THEN e || '{"kind":"derived","metric":"kpiLoadFactor"}'::jsonb ELSE e END ORDER BY ord)
  FROM jsonb_array_elements(fields) WITH ORDINALITY AS t(e, ord))
 WHERE fields @> '[{"kind":"raw","metric":"kpi_load_factor"}]';

UPDATE card_data_recipe SET fields = (
  SELECT jsonb_agg(CASE WHEN e->>'kind'='raw' AND e->>'metric'='active_energy_today_kwh'
                        THEN e || '{"kind":"derived","metric":"activeEnergyTodayKwh"}'::jsonb ELSE e END ORDER BY ord)
  FROM jsonb_array_elements(fields) WITH ORDINALITY AS t(e, ord))
 WHERE fields @> '[{"kind":"raw","metric":"active_energy_today_kwh"}]';

UPDATE card_data_recipe SET fields = (
  SELECT jsonb_agg(CASE WHEN e->>'kind'='raw' AND e->>'metric'='reactive_energy_today_kvarh'
                        THEN e || '{"kind":"derived","metric":"reactiveEnergyTodayKvarh"}'::jsonb ELSE e END ORDER BY ord)
  FROM jsonb_array_elements(fields) WITH ORDINALITY AS t(e, ord))
 WHERE fields @> '[{"kind":"raw","metric":"reactive_energy_today_kvarh"}]';

UPDATE card_data_recipe SET fields = (
  SELECT jsonb_agg(CASE WHEN e->>'kind'='raw' AND e->>'metric'='active_power_loss_pct'
                        THEN e || '{"kind":"derived","metric":"activePowerLossPct"}'::jsonb ELSE e END ORDER BY ord)
  FROM jsonb_array_elements(fields) WITH ORDINALITY AS t(e, ord))
 WHERE fields @> '[{"kind":"raw","metric":"active_power_loss_pct"}]';

UPDATE card_data_recipe SET fields = (
  SELECT jsonb_agg(CASE WHEN e->>'kind'='raw' AND e->>'metric'='rate_of_change_power_kw_per_min'
                        THEN e || '{"kind":"derived","metric":"rateOfChangePowerKwPerMin"}'::jsonb ELSE e END ORDER BY ord)
  FROM jsonb_array_elements(fields) WITH ORDINALITY AS t(e, ord))
 WHERE fields @> '[{"kind":"raw","metric":"rate_of_change_power_kw_per_min"}]';
