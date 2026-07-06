-- db/seed_seed_leak_policy.sql — policy/vocab rows for the SEED-LEAK polish (pcc-1a real-time-monitoring audit).
-- One concern: the knobs behind (a) the clock-string scrub (fabricated Storybook time axes '13:14:10' shown as live),
-- (b) the const→nameplate rating substitution by METRIC name (the fabricated supply.denominator 2700), and
-- (c) the DESIGN-CHROME subtree exception in leaf_classify (bandThresholds are shade boundaries, not measured data).
-- All three have identical code defaults (config/*.py) — these rows make them editable with no code change.
-- Idempotent. Run: psql (cmd_catalog DSN per config/databases.py) -f db/seed_seed_leak_policy.sql

INSERT INTO data_quality_policy (key, num_value, txt_value, note) VALUES
 ('scrub.clock_strings', NULL, 'on',
  'strip_to_placeholders: scrub metadata STRINGS carrying a clock time (seed scrubber/footer/history labels) — a harvested Storybook timestamp shown unstripped renders a FABRICATED live time axis. ''off'' disables.'),
 ('rating_slot.contracted_capacity_kw', NULL, 'contracted_kw',
  'const field metric → derive_ratings key: a Layer-2 const with metric=contracted_capacity_kw resolves the asset''s REAL contracted kW (or honest-blanks) instead of the Storybook literal copied off the default payload.'),
 ('rating_slot.rated_capacity_kw', NULL, 'rated_kw',
  'const field metric → derive_ratings key (rated-capacity spelling of the same no-seed-const rule).')
ON CONFLICT (key) DO UPDATE SET num_value = EXCLUDED.num_value, txt_value = EXCLUDED.txt_value, note = EXCLUDED.note;

-- vocab.chrome_subtree_keys is OWNED by db/fix_ieee_limit_chrome_subtree.sql (the hardened 7-key value:
-- bandthresholds, curvesag, limitpct, scalemaxpct, defaultlimit, axes, limit). This file MUST NOT seed it —
-- an earlier 2-key INSERT here CLOBBERED the hardening on every re-run (integration audit, 2026-07-06 CERT-BLOCKING).
-- The row is intentionally omitted so this seed is idempotent WITHOUT regressing the IEEE-limit chrome protection.
