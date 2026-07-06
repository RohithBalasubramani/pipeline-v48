-- db/seed_emit_coherence.sql — EMIT COHERENCE + OVERSIZED-PROMPT policy rows (code-default mirrors in
-- layer2/coherence.py and layer2/emit/user_message.py — behavior is identical until a row is edited).
--
-- (2) WINDOW/LABEL COHERENCE [c14 'Monthly'+range=this-month over a 24h fill; c16 declared last-7-days beside a
--     24h-backfilled window]: a period-declaring metadata leaf must agree with the fill window the shipped consumer
--     uses, or the gate morphs/blanks it (layer2/coherence.reconcile_window_labels, wired in layer2/build._finalize).
--     The declared range also drives the backfilled window bounds (layer2/build._backfill_default_window).
--   gates.window_label_policy — morph (rewrite the leaf to the window truth) | blank | off.
--   windows.period_families   — period token → family (day/week/month); BOTH sides must classify to flag.
--   windows.range_labels      — range token → the truthful human label a morph writes.
--   gates.period_label_keys   — metadata leaf KEYS that declare a period/range (key-exact, case-insensitive;
--                               *options* picker arrays are never touched).
--
-- (4) OVERSIZED-PROMPT CONTEXT CAP [c24 harmonics-timeline ~23.4K-tok emit prompt → llm_timeout payload_error]:
--     a user message over emit.prompt_char_budget chars is REBUILT compacted — skeleton arrays → first-K exemplars,
--     DB SCHEMA lines capped (rank order kept, '+N more' trailer), sibling per-element slot lines folded to K
--     exemplars + a summary line. Generic — NO card ids (layer2/emit/user_message.build_user).
--
-- Idempotent. Run: psql (cmd_catalog DSN per config/databases.py) -f db/seed_emit_coherence.sql

INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('gates.window_label_policy', 'morph', 'text', 'gates',
  'window/label coherence action on a period leaf that disagrees with the fill window: morph (rewrite to the window truth) | blank | off (layer2/coherence.py)'),
 ('windows.period_families',
  '{"today":"day","daily":"day","yesterday":"day","day":"day","last-24h":"day","last 24h":"day","last-24-hours":"day","24h":"day","weekly":"week","this-week":"week","last-7-days":"week","week":"week","7d":"week","monthly":"month","this-month":"month","last-month":"month","last-30-days":"month","month":"month","30d":"month"}',
  'json', 'windows',
  'period token/label → family (day/week/month) for the window/label coherence gate — both sides must classify to flag (unclassified = compatible, the quantity-wall principle)'),
 ('windows.range_labels',
  '{"today":"Today","yesterday":"Yesterday","last-24h":"Last 24h","last-7-days":"Weekly","this-week":"Weekly","this-month":"Monthly","last-month":"Monthly","last-30-days":"Monthly"}',
  'json', 'windows',
  'range token → the truthful display label a window/label coherence morph writes into a periodLabel-class leaf'),
 ('gates.period_label_keys',
  '["periodLabel","period","periodText","rangeLabel","windowLabel","range","selectedRange","timeRange"]',
  'json', 'gates',
  'metadata leaf KEYS that declare a period/range (key-exact, case-insensitive) — the window/label coherence gate polices only these; leaves inside *options* picker arrays are chrome and never touched'),
 ('emit.prompt_char_budget', '36000', 'int', 'emit',
  'l2_emit USER-message char budget — over it the message is rebuilt compacted (skeleton exemplars + basket cap + sibling-slot fold); 0 = off. Sized to the largest emit proven to complete within llm.timeout.l2_emit (the c24 ~43K-char message timed out; its ~34K siblings completed)'),
 ('emit.oversize_array_exemplars', '2', 'int', 'emit',
  'compacted-prompt skeleton: arrays longer than this show only their first K elements + a marker (omitted tail ships byte-identical defaults via enforce_exact_metadata — display-only, never a render change)'),
 ('emit.oversize_basket_cap', '40', 'int', 'emit',
  'compacted-prompt DB SCHEMA line cap (rank order kept; a +N-more trailer names the truncation so the model never assumes the schema ends there)'),
 ('emit.oversize_sibling_exemplars', '3', 'int', 'emit',
  'compacted-prompt slot catalog: sibling per-element slot lines (panels[0..9].kw) fold to K exemplars + ONE summary line per [*] group — the omitted indices stay named as real bindable slots (card-77 lesson: never hide slots silently)')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, data_type = EXCLUDED.data_type,
                                section = EXCLUDED.section, note = EXCLUDED.note;
