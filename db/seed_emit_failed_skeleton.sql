-- db/seed_emit_failed_skeleton.sql — the INFRA-failure conforming-skeleton knob + its per-leaf reason template
-- [audit 2026-07-14, 04 F1/F6]. A per-card exception or llm-stage timeout/transport failure used to blank ALL the
-- card's leaves (conforms=False -> hard_fail) AND trigger a wasted page reroute (re-running N emits under the same
-- contention/bug). With the knob on, the card ships a CONFORMING skeleton: real component, per-leaf 'emit_failed'
-- reasons, no hard_fail, no reroute. EMIT-stage gate failures keep the retry+reroute contract (a second chance
-- genuinely helps there). Mirror: layer2/emit_failed.py.
-- Rollback: UPDATE app_config SET value='off' WHERE key='layer2.emit_failed_skeleton';  + v48-host restart (cfg cache)
-- Apply: psql -h localhost -p 5432 -U postgres -d cmd_catalog -f db/seed_emit_failed_skeleton.sql

INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('layer2.emit_failed_skeleton', 'on', 'text', 'layer2',
   'Per-card INFRA failures (exception / llm timeout / transport) degrade to a conforming skeleton with per-leaf emit_failed reasons - no hard_fail, no page reroute. off = pre-2026-07-15 behavior (whole-card blank + reroute). Restart required (cfg cache).')
ON CONFLICT (key) DO NOTHING;

INSERT INTO reason_template (cause, template) VALUES
  ('emit_failed', '{metric} — the AI emit for this card did not complete (system failure, not missing data); value left blank.')
ON CONFLICT (cause) DO UPDATE SET template = EXCLUDED.template;
