-- db/fix_card42_load_anomalies_recipe.sql — card 42 (Load Anomalies) recipe accuracy repair (db-data hardening 2026-07-03)
-- Idempotent: content-guarded. Run: psql -U postgres -h 127.0.0.1 -p 5432 -d cmd_catalog -f db/fix_card42_load_anomalies_recipe.sql
--
-- DEFECT (adversarial page 08): card 42 emitted RAW-NUMBER arrays with negated / mis-scaled values (actualLoad
-- ~ -188..-196, presentValuePct -212.7). Root: the recipe_reconcile stub (now dead) rewrote card 42's CORRECT original
-- `fields` — where the load-percent + anomaly leaves are already kind='derived' (kpiKwLoadPctOfRated, kpiLoadFactor,
-- loadAnomalyEvents) — into kind='raw'/'event' bound to SLOT NAMES (actualLoad, expectedLoad, presentValuePct,
-- loadFactorPct, anomalies). kind='raw' on a slot-name forces the L2 AI to bind the closest column
-- (active_power_total_kw, which is NEGATIVE on this UPS) → the -212.7 leak. The original `fields` are strictly more
-- correct (audit: reconcile introduced the raw slot-name binds), so:
--   PART A  reconciled_fields → NULL (read() COALESCEs the correct original `fields`). Same pattern + rationale as
--           db/fix_card_data_recipe_repairs.sql PART A.
--   PART B  in the original `fields`, the ONE remaining raw non-column metric `demand_vs_rated_capacity_pct` (NOT a
--           gic column, NOT a LIBRARY key — verified live 2026-07-03) IS the load-percent-of-rated quantity → flip to
--           kind='derived' + metric='kpiKwLoadPctOfRated' (the LIBRARY value_key whose base_columns
--           active_power_total_kw + nameplate:rated_kva compute exactly this, giving a signed-correct 0-100 percent
--           instead of a raw negative kW). The expected_load_pct / expectedRange_min / expectedRange_max leaves are
--           already kind='text' (an unmeasurable expected-band → honest-blank), left as-is.

-- ══ PART A — mangled reconciled_fields → NULL ═════════════════════════════════════════════════════════════════════
UPDATE card_data_recipe SET reconciled_fields = NULL
 WHERE card_id = 42 AND reconciled_fields IS NOT NULL;

-- ══ PART B — demand_vs_rated_capacity_pct (raw, non-column) → kpiKwLoadPctOfRated (derived LIBRARY key) ════════════
-- Generic per-metric rewrite; ORDINALITY preserves order; @> guard makes re-runs no-ops.
UPDATE card_data_recipe SET fields = (
  SELECT jsonb_agg(CASE WHEN e->>'kind'='raw' AND e->>'metric'='demand_vs_rated_capacity_pct'
                        THEN e || '{"kind":"derived","metric":"kpiKwLoadPctOfRated"}'::jsonb ELSE e END ORDER BY ord)
  FROM jsonb_array_elements(fields) WITH ORDINALITY AS t(e, ord))
 WHERE fields @> '[{"kind":"raw","metric":"demand_vs_rated_capacity_pct"}]';
