-- db/derivation_expression_schema.sql — FORMULAS INTO THE DB (2026-07-03).
-- The RESOLVERS map collapses into derivation_binding: a row may now carry its FORMULA as a restricted arithmetic
-- `expression` executed by the ONE generic evaluator (ems_exec/derivations/evaluate.py). NULL expression = the metric
-- still runs its retained python fn (series/topology/stateful/config-wired formulas stay code).
--   expression : the restricted formula text. Vocabulary: numeric literals, + - * / ** unary-minus, parentheses,
--                sqrt/abs/min/max/round, bare column names (→ ctx.row), start.<col>/end.<col> (→ window endpoint rows),
--                nameplate.<key> (→ the asset nameplate). Any missing input / non-finite result → None (honest-degrade).
--   scope      : 'row' (latest-row arithmetic) | 'window' (deltas over the start/end endpoint rows). Metadata for
--                catalog/queryability; the expression's own names are what the evaluator resolves.
ALTER TABLE derivation_binding
    ADD COLUMN IF NOT EXISTS expression text,
    ADD COLUMN IF NOT EXISTS scope text DEFAULT 'row';
