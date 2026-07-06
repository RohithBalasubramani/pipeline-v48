-- db/seed_item21_catalog_compress.sql — DB rows for the ITEM-21 catalog-compression / label-dedup knobs.
-- [AI_QUALITY_BACKLOG item 21 / D5: "1a catalog compression + 1b label dedup"]
--
-- layer1a/catalog_compress.py merges each page's purpose/theme/answers (3 prose restatements, ~10.4K of the
-- 14.7K-char router user message) into ONE deduplicated story line (measured 14,733 -> 7,954 chars, x27 calls/sweep);
-- layer1b/basket/describe.py stops repeating title-case(column_name) as the label in every basket line
-- (~1.26K chars/call on the 71-col anchor meter). These rows are BYTE-EQUAL to the code defaults, so seeding is
-- behavior-neutral; edit a row to retune (or set label_dedup/catalog_archetype to flip behavior) with no code change.
--
-- Idempotent (ON CONFLICT upsert). Apply: psql -U postgres -h 127.0.0.1 -p 5432 -d cmd_catalog -f db/seed_item21_catalog_compress.sql

INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('route.story_min_new_tokens', '4', 'int', 'route',
   '1a catalog story merge: a purpose/theme/answers clause is kept only when it adds >= this many unseen content tokens. [item 21]'),
  ('route.story_min_new_ratio', '0.6', 'number', 'route',
   '1a catalog story merge: ... AND that many is >= this fraction of the clause''s content tokens (catches paraphrase restatements). [item 21]'),
  ('route.story_max_chars', '320', 'int', 'route',
   '1a catalog story merge: per-page story cap, cut at a clause boundary; 0 = uncapped. Titles keep the class-concern keywords verbatim regardless. [item 21]'),
  ('route.catalog_archetype', 'false', 'bool', 'route',
   '1a catalog: show the [archetype] layout tag on each page line (routing rules never key on it; off saves ~720 chars). [item 21]'),
  ('layer1b.basket.label_dedup', 'true', 'bool', 'layer1b',
   '1b column dictionary: emit the label only when it differs from title-case(column_name) — today never, so the basket lines drop the repeat. [item 21]')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, data_type = EXCLUDED.data_type,
  section = EXCLUDED.section, note = EXCLUDED.note;
