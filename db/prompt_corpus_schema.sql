-- db/prompt_corpus_schema.sql — the PROMPT-CORPUS home: templates + vocabulary the validation corpus generator
-- (validation/corpus/) permutes into tens of thousands of test prompts. Templates are DB ROWS, not code literals —
-- add a workflow phrasing / metric surface form / conversational wrapper by inserting a row, no code edit
-- [config → DB]. Code-default mirror: validation/corpus/store.py _DEFAULT_* (DB-down fallback only).
--
-- Run:  psql -h localhost -p 5432 -d cmd_catalog -f db/prompt_corpus_schema.sql   (idempotent — safe to re-run)

CREATE TABLE IF NOT EXISTS prompt_category (
  category text PRIMARY KEY,                 -- corpus category key ('single_asset', 'compare_2', 'ambiguous'...)
  expect   text NOT NULL,                    -- expected outcome, checks/expectations.py grammar:
                                             --   cards|picker|knowledge|refused|empty|unavailable|compare:N, '|' unions
  budget   integer NOT NULL DEFAULT 100,     -- post-expansion case budget (generator downsamples deterministically);
                                             --   the sum across enabled categories IS the corpus size dial
  enabled  boolean NOT NULL DEFAULT true,    -- false = category generated no cases (kill a lane without deleting rows)
  note     text DEFAULT ''                   -- what workflow this category certifies
);

CREATE TABLE IF NOT EXISTS prompt_template (
  tkey     text PRIMARY KEY,                 -- stable key '<category>.<slug>' (case ids survive row re-ordering)
  category text NOT NULL,                    -- prompt_category.category this template feeds
  template text NOT NULL,                    -- surface form with slots the fill engine grounds from the universe:
                                             --   <metric> <asset> <asset1>..<asset5> <panel> <window> <class>
                                             --   <token> <scope> <concept> <offdomain> <invalid>
  expect   text,                             -- per-template override of the category expect (NULL = inherit)
  weight   integer NOT NULL DEFAULT 1,       -- relative share within the category when the budget forces downsampling
  enabled  boolean NOT NULL DEFAULT true,    -- false = skip this phrasing
  note     text DEFAULT ''                   -- why this phrasing exists / what it probes
);

CREATE TABLE IF NOT EXISTS prompt_vocab (
  kind    text NOT NULL,                     -- vocabulary lane: metric | window | conv_prefix | conv_suffix |
                                             --   concept | off_domain | invalid_asset | scope_incomer |
                                             --   metric_abbrev | class_abbrev | plural
  value   text NOT NULL,                     -- the surface string ('power quality and harmonics', 'yesterday', 'pf')
  meta    text DEFAULT '',                   -- kind-specific: metric → csv of asset classes it applies to ('' = all
                                             --   electrical-metered classes); *_abbrev → the canonical word/phrase the
                                             --   abbreviation replaces; plural → the singular stem
  enabled boolean NOT NULL DEFAULT true,     -- false = drop from generation without deleting the row
  note    text DEFAULT '',                   -- provenance / when to prune
  PRIMARY KEY (kind, value)
);
