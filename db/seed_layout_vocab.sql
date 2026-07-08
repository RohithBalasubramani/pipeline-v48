-- db/seed_layout_vocab.sql — the ONE store for the FE grid-placement VOCABULARY + fallback knobs [layout_fe, 2026-07-08].
--
-- The frontend grid placer (host/web/src/layout/*) is 100% DB-driven off the page template (page_specs.layout_primitive
-- + page_layout_cards.cell/region/slot). The only *policy* string-sets / numbers it still needs — which region names lift
-- into the top band, which map to the rail column, which layout_primitive is the flex/RTM path, and the CSS fallbacks —
-- live HERE as app_config rows under section 'layout_fe', mirrored 1:1 by the code default in host/web/src/layout/vocab.ts
-- (LAYOUT_VOCAB). Editing a row retunes placement with NO code edit; the mirror is only the DB-down fallback.
--
-- READ PATH: the host server threads these rows onto the /api/run response as page.layout.fe_vocab (a JSON object of the
-- same keys), and vocab.ts resolveVocab() overlays them on the mirror. Until that wiring lands the mirror governs — and
-- the mirror already carries the 'banner' band fix + the full-span/lone rules, so behaviour is correct either way.
-- Idempotent (ON CONFLICT). Run:
--   psql -h localhost -p 5432 -d cmd_catalog -f db/seed_layout_vocab.sql

INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('layout_fe.band_regions', '["strip","header","top","banner"]', 'json', 'layout_fe',
   'page_layout_cards.region values LIFTED into the full-width TOP BAND above the grid (page header / control strip / '
   'intent banner). ''banner'' (transformers ''intent banner above grid'') MUST lift — a missing token seats it INSIDE '
   'the grid and displaces a body card. Mirror: vocab.ts LAYOUT_VOCAB.band_regions. Read by regions.isBand.'),
  ('layout_fe.rail_regions', '["right","rail"]', 'json', 'layout_fe',
   'region values that map to the RAIL (second) column of a REGION-driven (flex) layout; everything else → the main '
   '(first) column. Mirror: vocab.ts rail_regions. Read by regions.regionColumn/columnize.'),
  ('layout_fe.flex_primitive', 'flex', 'text', 'layout_fe',
   'the layout_primitive that routes a page to the RTM composite (region columns, not cell placement). Only '
   'panel-overview-shell/real-time-monitoring uses it today. Mirror: vocab.ts flex_primitive. Read by CardGrid.'),
  ('layout_fe.default_primitive', 'grid', 'text', 'layout_fe',
   'layout_primitive assumed when a page declares none. Mirror: vocab.ts default_primitive. Read by pageGrid.'),
  ('layout_fe.fallback_cols', 'minmax(0,1fr) 300px', 'text', 'layout_fe',
   'grid_template_columns used when the page declares no REAL CSS track list (prose/none/empty rejected by '
   'tracks.isCssTrackList). Mirror: vocab.ts fallback_cols. Read by pageGrid.'),
  ('layout_fe.fallback_gap', '0.75rem', 'text', 'layout_fe',
   'layout_gap default when page_specs declares none. Mirror: vocab.ts fallback_gap. Read by pageGrid.'),
  ('layout_fe.fallback_padding', '1rem', 'text', 'layout_fe',
   'layout_padding default when page_specs declares none. Mirror: vocab.ts fallback_padding. Read by pageGrid.'),
  ('layout_fe.rebase_min_row', '2', 'int', 'layout_fe',
   'a lifted top band occupies exactly one prose row, so a page whose BODY cells all start at row >= this value counted '
   'the band as row 1 → the placer rebases every body row down by 1 (harmonics r2/r3 → grid rows 1/2). '
   'Mirror: vocab.ts rebase_min_row. Read by gridPlan.planGrid.')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, data_type = EXCLUDED.data_type,
                                section = EXCLUDED.section, note = EXCLUDED.note, updated_at = now();
