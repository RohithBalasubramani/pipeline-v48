-- db/seed_reflect_gap_weight.sql — T1-6: DEFAULT 'count' (byte-identical). reflect.gap_weight ∈ {count, area}.
-- count = len(trigger)/len(l2) (today); area = weight each card by its card_grid_size grid AREA so ONE huge failed
-- card crosses reflect.min_gap_frac a 1-of-N count never would. Read by run/harness._gap_frac.
INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('reflect.gap_weight', 'count', 'text', 'reflect',
  'T1-6: count (default, len/len byte-identical) | area (weight by card grid area so a huge failed card crosses the reflect floor) — run/harness._gap_frac')
ON CONFLICT (key) DO NOTHING;
