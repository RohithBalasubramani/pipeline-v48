-- db/seed_residual_seed_scrub.sql — config rows for the LAST seed-leak classes (fullsweep_20260706_004334 closeout).
-- One concern: the vocab/policy knobs behind the four residual strip classes that still leaked Storybook seeds into
-- card_payloads.payload_stripped:
--   (a) OCCURRENCE BOOLEAN ARRAYS  — c55 activity.ticks [..true..true..] rendered 2 FAKE transfer events
--       (leaf_classify: vocab.occurrence_bool_parents → the bool array IS data, strips to empty).
--   (b) STRING-EMBEDDED MEASUREMENTS — c56/59 'Readiness: 70%', c17 'at 17', c71 'peak 77%', c51 'peak temp 35°C',
--       c37/38 'Max - 420V', c48 'Max: 480V' (grounding.measured_annotation_scrub: pattern + data-role).
--   (c) SEEDED NUMERIC-STRING AXES — c36 yLabels ['380'..'80'], c37/38 yTicks ['430'..'390'] presented as live scale
--       (leaf_classify: vocab.numeric_axis_keys → the axis-string array IS data, strips to []). REAL design bands
--       (bandThresholds / IEEE limitPct) stay under vocab.chrome_subtree_keys, untouched.
--   (d) SEED EVENT SKELETONS — c67/c42/DG-chart events/anomalies ghost rows (grounding.event_skeleton_scrub reuses
--       vocab.role_scrub.event_parents — no new row needed).
-- All knobs have identical code defaults (honest degrade on a missing row / DB outage). NO card_id anywhere.
-- Idempotent. Run: psql (cmd_catalog DSN per config/databases.py) -f db/seed_residual_seed_scrub.sql
--   then REBUILD: scripts/build_stripped_payloads.py (payload_stripped is DERIVED from these rows),
--   then VERIFY:  scripts/rescan_stripped_payloads.py (all classes at ZERO + fixed-point + dictionaries preserved).

INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('vocab.occurrence_bool_parents',
  '["ticks","activity","events","anomalies","event","anomaly","transfers","occurrences"]',
  'json', 'vocab',
  'leaf_classify: a BOOLEAN ARRAY whose own key or immediate parent key is one of these event/activity/tick ROLE keys is OCCURRENCE DATA (each true asserts "an event happened here" — c55 activity.ticks replayed 2 fake transfer events); it strips to empty (all-false rest). A boolean array outside these roles (structural toggles) stays chrome. Extend by editing this row.'),
 ('vocab.numeric_axis_keys',
  '["yticks","ylabels","xticks","xlabels","ticklabels","axislabels"]',
  'json', 'vocab',
  'leaf_classify: an array of NUMERIC STRINGS under one of these axis ROLE keys (yTicks ["430".."390"], yLabels ["380".."80"]) is a SEEDED AXIS — tick values scaled to the Storybook demo data, presented as a live scale (c36/37/38 drew a 430–390V axis over 228–240V live data); it is DATA and strips to []. Numeric-typed axis arrays are already data by the type rule. REAL design bands stay under vocab.chrome_subtree_keys / bandThresholds.'),
 ('vocab.measured_annotation_keys',
  '["label","sub","sublabel","caption"]',
  'json', 'vocab',
  'measured_annotation_scrub: the VALUE-adjacent annotation keys eligible for the embedded-measurement scrub — a string at one of these keys, embedding a number+unit/percent (scrub.embedded_number_pattern) AND sitting beside a numeric data sibling, is the seed measurement in text form (floor.label "Readiness: 70%", stats[].sub "at 17", thresholds[].label "Max - 420V") → blanked. A caption with no measured sibling (rangeOptions[] "Last 7 days") stays chrome. narrative_slots keys are already scrubbed wholesale upstream.')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, data_type = EXCLUDED.data_type,
                                section = EXCLUDED.section, note = EXCLUDED.note;

INSERT INTO data_quality_policy (key, num_value, txt_value, note) VALUES
 ('scrub.embedded_numbers', NULL, 'on',
  'measured_annotation_scrub: scrub annotation STRINGS that embed a measurement (number+unit/percent/"at <n>") in a data-role slot — the string-embedded form of a seed number ("Readiness: 70%", "peak 77%", "at 17", "Max - 420V"). ''off'' disables.'),
 ('scrub.embedded_number_pattern', NULL,
  '(?<![\w#])[+-]?\d+(?:[.,]\d+)?\s*(?:%|°\s*[CcFf]|(?:k[Ww]h?|k[Vv][Aa][Rr]?h?|k[Vv]|M[WV]A?h?|[Ww]h|[Vv][Aa]|[Vv]|[Aa]|[Hh][Zz]|[Hh]rs?|[Hh]|ms|min(?:s)?|sec|days?|yrs?|years?)\b)|(?i:\bat\s+[+-]?\d+(?:[.,]\d+)?\b)',
  'measured_annotation_scrub: the embedded-MEASUREMENT detector — number + %/°C/electrical-or-time unit (word-bounded so "5th Harmonic"/"IEEE 519"/"3 Phase" never match), or a unitless "at <n>" peak-position annotation; (?<![\w#]) guards hex colors ("#5fa64a") and identifier substrings. Overrides the code default when set.')
ON CONFLICT (key) DO UPDATE SET num_value = EXCLUDED.num_value, txt_value = EXCLUDED.txt_value, note = EXCLUDED.note;
