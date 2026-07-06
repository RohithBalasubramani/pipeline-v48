-- db/fix_ieee_limit_chrome_subtree.sql — keep the IEEE-519 reference LIMIT leaves byte-identical (db-data hardening 2026-07-03)
-- Idempotent (full-value SET on conflict). Run: psql -U postgres -h 127.0.0.1 -p 5432 -d cmd_catalog -f db/fix_ieee_limit_chrome_subtree.sql
--   then REBUILD: scripts/build_stripped_payloads.py + scripts/scrub_stripped_event_seeds.py (payload_stripped is derived).
--
-- DEFECT (adversarial page 09, card 47 Power Quality): the harmonic snapshot's limitPct / scaleMaxPct / defaultLimit
-- leaves are the UNIVERSAL IEEE-519 reference thresholds (verified across ALL 155 card_payloads: limitPct=8 [current
-- THD limit], scaleMaxPct=16 [2x, chart scale], defaultLimit=8 — a single constant each, NEVER a measured per-asset
-- value). leaf_classify treats them as numeric DATA leaves, so strip_to_placeholders zeros them to 0.0. The component
-- then derives ieeeState="fail" (any measured value > a 0.0 limit => over-limit) → a FABRICATED "IEEE 519 Fail" alarm
-- badge on the honest-blank card. These are DESIGN-CHROME reference constants exactly like bandThresholds/curveSag —
-- add their keys to vocab.chrome_subtree_keys so leaf_classify keeps them byte-identical (8/16) and the IEEE verdict is
-- computed against the REAL standard, not a fabricated 0.0. (The measured harmonic VALUE leaves — valuePct, value —
-- stay data and honest-blank as before.)
-- value re-derived FROM LIVE 2026-07-06: the list gained "axes" and "limit" (axis/limit reference subtrees kept as chrome).
INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('vocab.chrome_subtree_keys',
  '["bandthresholds", "curvesag", "limitpct", "scalemaxpct", "defaultlimit", "axes", "limit"]', 'json', 'vocab',
  'leaf_classify: keys whose value is DESIGN CHROME / a UNIVERSAL reference constant even though numeric (heatmap '
  'band/shade thresholds + divisors; sankey ribbon curvature curveSag; IEEE-519 harmonic limitPct/scaleMaxPct/'
  'defaultLimit reference thresholds) — kept byte-identical, never stripped/filled. Extend by editing this row.')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, data_type = EXCLUDED.data_type,
                                section = EXCLUDED.section, note = EXCLUDED.note;
