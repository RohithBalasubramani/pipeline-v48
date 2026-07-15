-- db/seed_emit_diet.sql — the emit OUTPUT-diet flags [decode-wall root fix, 2026-07-15]. Both default OFF =
-- today's exact prompt bytes (layer2/emit/emit._variant marker blocks; goldens pin the byte-identity).
-- Forensics (1,555 emits): ~55% of completion tokens were roster/fields retype the gates fold back to recipe truth,
-- and the 5-21K-token runaways were zero-filled data grids / 110-entry roster retypes — see
-- tests/fixtures/emit_forensics/ + docs/latency_audit_20260714/. ON CONFLICT DO NOTHING.
-- Adopt: UPDATE app_config SET value='on' WHERE key='emit.diet.roster';  (then morph_shape) + service reload.
-- Rollback: set the row back to 'off' + reload. Run: psql -h localhost -p 5432 -U postgres -d cmd_catalog -f db/seed_emit_diet.sql

INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('emit.diet.roster', 'off', 'text', 'emit',
   'Stage 1 roster-DIFF output contract: the model emits ONLY changed roster bindings (omitted slots backfill '
   'verbatim via gate_roster — layer2/gates/roster.py) + the code-owned envelope scaffold note. off = legacy '
   'full-retype wording, byte-identical. Evidence: obs row 1372 (110-entry retype, ALL rejected, recipe shipped).'),
  ('emit.diet.morph_shape', 'off', 'text', 'emit',
   'Stage 2 Mechanism-A root fix: collapse the shown skeleton''s DATA-tier subtrees to <<DATA: N element(s)>> '
   'markers (morph-map cards only) + the concrete NEVER-MORPH violation example. off = full skeleton shown, '
   'byte-identical. Evidence: obs row 4485 (14,614-token zero-filled harmonic-grid morphs, all producer-rejected).')
ON CONFLICT (key) DO NOTHING;
