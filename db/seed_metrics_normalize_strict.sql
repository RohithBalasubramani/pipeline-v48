-- db/seed_metrics_normalize_strict.sql - T0-6: strict-mode flag for config/metrics normalize_metric, DEFAULT OFF.
--
-- metrics.normalize_strict - read (fail-open to off) by config/metrics.py:
--   * normalize_metric  (gates the two legacy substring loops)
--   * prompt_metric_hint (the 1b basket's prompt->metric hint; layer1b/basket/column_basket.py)
-- When OFF (this default) normalize_metric is BYTE-IDENTICAL to the pre-T0-6 legacy path: exact vocab word, exact
-- alias phrase, then the two SUBSTRING loops (vocab-word-in-phrase before alias-key-in-phrase - the order-dependence
-- that makes 'power factor trend' resolve to 'power' instead of 'pf'), then the default.
-- When ON the substring loops are SKIPPED: exact vocab + exact alias only; any fallthrough returns the default AND
-- records obs.failures metric_unresolved (stage 'metric_normalize') so a silent default-collapse is visible telemetry.
-- (The legacy terminal fall-through records metric_unresolved too - telemetry only, both modes.)
--
-- ON CONFLICT DO NOTHING (not UPDATE): re-running this seed must never flip an operator's 'on' back to 'off'.
-- Idempotent. Run: psql (cmd_catalog DSN per config/databases.py) -f db/seed_metrics_normalize_strict.sql

INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('metrics.normalize_strict', 'off', 'text', 'metrics',
  'T0-6: strict metric normalization; off = legacy substring loops byte-identical (vocab-substring beats alias, silent default); on = exact vocab + exact alias only, fallthrough returns metrics.default and records obs.failures metric_unresolved (config/metrics.normalize_metric + prompt_metric_hint)')
ON CONFLICT (key) DO NOTHING;
