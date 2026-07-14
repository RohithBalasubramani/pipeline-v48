-- seed_column_dictionary.sql -- T1-9: the curated column-FACTS dictionary as an editable row (empty by default).
-- layer1b/basket/describe.py consults this FIRST in unit()/kind()/describe(): a hit's declared fields
-- ({"<lowercase column_name>": {"label": ..., "kind": ..., "unit": ...}}) are used VERBATIM; a miss (or an
-- undeclared field) falls through to the regex/suffix convention unchanged -- curated FACTS beat convention.
-- Default '{}' = behavior-identical until edited; an odd column (vendor rename, mislabeling suffix, site-local
-- naming) is then fixed with ONE row edit, no code change. Reader: describe._column_dictionary() (fail-open to {}).
-- Example edit:
--   UPDATE app_config SET value = '{"thd_current_r": {"kind": "derived", "unit": "A", "label": "THD Current (R)"}}'
--   WHERE key = 'vocab.column_dictionary';
INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('vocab.column_dictionary', '{}', 'json', 'vocab',
   'curated per-column {label,kind,unit} FACTS consulted FIRST by layer1b/basket/describe.py; keys are lowercase column names; declared fields are used verbatim, undeclared fields fall through to the regex/suffix convention; empty by default')
ON CONFLICT (key) DO NOTHING;
