-- db/fix_derivation_binding_loadpct.sql — metric-vocabulary binding for the AI's per-point 'loadPct' series metric.
--
-- WHY [card-58 empty sparkline, sweep #3]: Layer 2 emits the UPS load sparkline as column-less bucketed fields with
-- metric='loadPct' (unit '%'). The executor's per-point series family resolves a COLUMN-LESS field through
-- cmd_catalog.derivation_binding keyed on the field's METRIC name — but no 'loadPct' row existed, so every point
-- honest-blanked while the same table had ~25 real hourly active-power buckets. loadPct IS the same measure the
-- scalar KPI already computes: kpiKwLoadPctOfRated = |active_power_total_kw| ÷ nameplate rated_kw × 100 (real power
-- reading + real asset_nameplate rating — never a fabricated denominator; no nameplate → every point honest-None).
--
-- GENERIC: a metric-name→fn row (the AI's metric vocabulary), NOT a card/slot/asset rule. scope='series' (a per-point
-- trend metric). Idempotent upsert.
-- Run: psql (cmd_catalog DSN per config/databases.py) -f db/fix_derivation_binding_loadpct.sql

INSERT INTO derivation_binding (metric, fn, base_columns, fidelity, scope) VALUES
 ('loadPct', 'kpiKwLoadPctOfRated', 'active_power_total_kw,nameplate:rated_kva', 'real_exact', 'series')
ON CONFLICT (metric) DO UPDATE SET fn = EXCLUDED.fn, base_columns = EXCLUDED.base_columns,
                                   fidelity = EXCLUDED.fidelity, scope = EXCLUDED.scope;
