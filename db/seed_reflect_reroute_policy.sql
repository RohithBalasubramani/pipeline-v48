-- db/seed_reflect_reroute_policy.sql — reflect-loop REROUTE-TRIGGER policy (run/harness.py _reflect_loop +
-- _preflight_reroute). Idempotent (upsert).
--
-- WHY [sweep #3, r_d7be9457fc]: 'ups source transfer for GIC-01-N3-UPS-01' routed CORRECTLY to
-- ups-asset-dashboard/source-transfer; cards 54/55 emitted CONFORMING answerability='none' with clean per-leaf
-- reasons (transfer telemetry genuinely unmeasured) — the PROPER honest output — and the old any-gap reflect loop
-- then DISCARDED the right page and re-routed to output-load-capacity (wrong page, inherited its own defects).
-- Per the per-leaf degradation mandate, honest-blank WITH reasons is a PASS, never a failure to route around.
--
--   'hard_failure' (default; code default identical) — re-route ONLY when a card has NO valid emit at all
--                  (emit exception / LLM timeout / non-conforming envelope, i.e. conforms=false). A conforming
--                  honest-blank page is a VALID TERMINAL: page + cards kept, user-facing reflect NOTE recorded.
--   'any_gap'      — legacy behavior: honest answerability='none' gaps (and validation expected-gaps pre-L2)
--                  also trigger the re-route. Rollback knob — edit the row, no code change.
INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('reflect.reroute_on', 'hard_failure', 'text', 'reflect',
   'reflect-loop re-route trigger: ''hard_failure'' (default) = re-route ONLY on cards with no valid emit '
   '(exception/timeout/non-conforming); a conforming honest-blank page (answerability=none + per-leaf reasons) is a '
   'VALID TERMINAL — kept + noted, never discarded. ''any_gap'' = legacy honest-gap re-route (also re-enables the '
   'pre-L2 expected-gap re-route). [sweep-#3 r_d7be9457fc ups source-transfer fix]')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, data_type = EXCLUDED.data_type,
                                section = EXCLUDED.section, note = EXCLUDED.note, updated_at = now();
