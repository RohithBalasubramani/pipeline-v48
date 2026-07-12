-- db/seed_ts_index_fn.sql — flip the neuract ts EXPRESSION INDEX on [R3 / audit F1, 2026-07-12].
-- After db/create_neuract_ts_indexes.py --apply created neuract.ts_imm() + the per-table indexes, this makes every
-- read order/filter on neuract.ts_imm(timestamp_utc) so the index is HIT (seq scan → index scan; measured ~80x on the
-- hot path). SAFE to set before every table is indexed: a not-yet-indexed table's ts_imm() seq scan equals the old
-- ::timestamptz seq scan (no regression). Takes effect on the next host restart (cfg() is process-cached).
-- Code mirror: ems_exec/data/neuract._tsexpr() + config/neuract_dsn.ts_index_fn().
INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('neuract.ts_index_fn', 'ts_imm', 'text', 'neuract',
   'Schema-qualified IMMUTABLE wrapper fn for the ts expression index. ts_imm = index-backed reads; empty = raw '
   '::timestamptz cast (no index). Mirror: config/neuract_dsn.ts_index_fn().')
ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, note=EXCLUDED.note;
