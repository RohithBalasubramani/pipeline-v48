-- seed_dataless_swap.sql — [#1 'card swap should work here'] DB knobs for the DATALESS force-swap.
-- The static card_feasibility.verdict answers "can this KIND of card ever render real data"; it cannot know THIS asset
-- has no column to feed a catalog-renderable card (Fuel Tank on a fuel-less DG; Load Anomalies with no anomaly telemetry).
-- The AI already emits that per-asset truth as answerability='none'. These knobs let the render-gate treat 'none' like an
-- unrenderable verdict and force-swap the card to a fillable same-page candidate (candidates.py filters to render_real);
-- with NO unclaimed candidate (a whole-page data dead-end) it honestly KEEPS the card. Code defaults mirror these rows
-- (config/feasibility.py), so behaviour is identical until edited — flip force_swap_on_dataless off to disable.
INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('feasibility.dataless_answerability', '["none"]', 'json', 'feasibility',
   'answerability values that mark a card WHOLLY unfillable for this asset -> render-gate force-swaps it'),
  ('feasibility.force_swap_on_dataless', 'true', 'bool', 'feasibility',
   'force-swap a catalog-renderable but data-empty (answerability=none) card to a fillable candidate; off = keep honest-blank')
ON CONFLICT (key) DO UPDATE
  SET value = EXCLUDED.value, data_type = EXCLUDED.data_type, section = EXCLUDED.section, note = EXCLUDED.note;
