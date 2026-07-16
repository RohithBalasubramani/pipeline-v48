-- db/seed_fab_guards_rework.sql — the fab_guards audit/rework knobs. ALL seeded at their BYTE-IDENTICAL default.
--
-- fab_guards.mode — 'enforce' (default; blanks live exactly as before) | 'report' (SHADOW: every class computes its
--   would-blank verdict against a deep COPY, records the gaps marked shadow=true, but NEVER mutates the served payload).
--   Report mode is the fleet-audit + cert instrument (tools/fab_guards_shadow_replay.py, tools/guard_corpus_replay.py):
--   set it live to gather the before/after verdict table with ZERO risk to served data. ems_exec/executor/fab_guards/apply.py.
--
-- fab_guards.live_literal — 'on' (default): the STRING-only guard that blanks a const/text leaf claiming source='live'
--   with no column/rating (card-78 'AUTO'/'Nominal' — a literal dressed as a live reading). Split off its OWN valve from
--   fab_guards.no_source [S1a] because that numeric CLASS-3 branch is being RETIRED while this string charter stays.
--   class23_source._live_literal_on.
--
-- fab_guards.null_column_writer_aware — 'off' (default byte-identical): ON makes CLASS 2 stand down on a PANEL-AGGREGATE
--   fill (values came from the member roll-up ctx['_agg_row'], not asset_table — so column_logged(control_table, member_col)
--   is a structural false-positive that blanked real member-rolled values; the card-15 family generalized beyond recipe
--   slots). class23_source._writer_aware_on. Adopt after the shadow-fleet baseline confirms it drops the panel FPs with no
--   new gaps.
--
-- fab_guards.no_source stays 'on' here (the numeric CLASS-3 valve). Its RETIREMENT is a separate operator UPDATE to 'off'
--   AFTER the shadow baseline shows zero true-positive numeric CLASS-3 fires across the fleet — NOT seeded here.
--
-- ON CONFLICT DO NOTHING (idempotent; never flips an operator value). Run: psql (cmd_catalog DSN) -f db/seed_fab_guards_rework.sql

INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('fab_guards.mode', 'enforce', 'text', 'fab_guards',
  'enforce (blank live, byte-identical) | report (shadow: compute would-blank verdicts on a copy, record gaps shadow=true, do NOT mutate served payload). The fleet-audit + cert instrument. ems_exec/executor/fab_guards/apply.py'),
 ('fab_guards.live_literal', 'on', 'text', 'fab_guards',
  'S1a: STRING-only guard blanking a const/text leaf claiming source=live with no column/rating (card-78 AUTO/Nominal). Own valve, split from the retiring numeric no_source branch; on=today. class23_source._live_literal_on'),
 ('fab_guards.null_column_writer_aware', 'off', 'text', 'fab_guards',
  'S2: ON makes CLASS 2 stand down on a panel-aggregate fill (values came from the member roll-up agg_row, not asset_table; column_logged(control_table, member_col) is a structural FP). off=byte-identical. class23_source._writer_aware_on')
ON CONFLICT (key) DO NOTHING;
