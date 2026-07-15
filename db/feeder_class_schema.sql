-- db/feeder_class_schema.sql — THE FEEDER-CLASS FACT INTO THE DB (T2.1-3, 2026-07-14).
-- member_registry_facts restores type_code/load_group, but lt_mfm_type carries only 4 codes (apfc, lt_panel,
-- transformer, ups) — so bpdb/hhf/incomer/spare/dg/ahu feeders have NO type-code and can only be matched by the
-- fragile name_contains. feeder_class is the fact that fixes that: a token-derived class per meter TABLE, keyed on
-- registry_lt_mfm.table_name, that the roster matchers key on (a feeder_classes any-of branch). Seeded (idempotent
-- UPSERT) from the meter NAME tokens by scripts/seed_feeder_class.py; read by data/registry/feeder_class.py.
--   table_name   : the neuract data-table name (== registry_lt_mfm.table_name). PRIMARY KEY (one class per meter).
--   feeder_class : the derived class ('ups'|'bpdb'|'hhf'|'solar-incomer'|'incomer'|'apfcr'|'dg'|'ahu'|'spare'|…).
--   derived_from : the meter-name TOKEN the class was derived from (audit trail; 'solar+incomer' for the pair).
--   reviewed     : false until a human confirms/edits the row (the derivation is a best-effort default, not truth).
--   note         : free-text human annotation.
CREATE TABLE IF NOT EXISTS registry_feeder_class (
    table_name   text PRIMARY KEY,
    feeder_class text NOT NULL,
    derived_from text,
    reviewed     boolean DEFAULT false,
    note         text
);
