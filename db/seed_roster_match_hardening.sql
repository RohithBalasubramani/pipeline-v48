-- db/seed_roster_match_hardening.sql — Tier-2 item T2.1-2: BOUNDED roster/member matching flag, DEFAULT OFF.
--
-- roster.match_hardening — the ONE knob read by ems_exec/executor/match_bounds.py :: enabled() (via flag_on), which
-- the three roster/member matchers consult:
--   · roster_modes_sankey.py  _match_slug  (unique_bounded_match instead of the bidirectional 'k in s or s in k' loop)
--   · roster_modes_sankey.py  _node_role   (contains_bounded trunk containment instead of raw 's in p or p in s')
--   · roster_modes_series.py  _member_match / members.py _spec_match  (contains_bounded name_contains, not raw substring)
--   · roster_modes_groups.py  _match_def   (name_prefixes gains a right-boundary check)
-- When ON, a substring hit counts only when the chars adjacent to the match are non-word (a '-' / '_' / ' ' separator OR
-- a string edge), so the gic-2 / gic-20 (and pcc-panel-1 / pcc-panel-10) collisions no longer fold a foreign meter.
-- When OFF (this default) every matcher takes its byte-identical legacy substring path — output is unchanged.
--
-- ON CONFLICT DO NOTHING (not UPDATE): re-running this seed must never flip an operator's 'on' back to 'off'.
-- Idempotent. Run: psql (cmd_catalog DSN per config/databases.py) -f db/seed_roster_match_hardening.sql

INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('roster.match_hardening', 'off', 'text', 'roster',
  'T2.1-2: bounded roster/member matching (word-boundary substring) for _match_slug/_node_role/_member_match/_spec_match/_match_def; off = byte-identical legacy raw-substring path; on = gic-2 no longer collides gic-20 (ems_exec/executor/match_bounds.py enabled)')
ON CONFLICT (key) DO NOTHING;
