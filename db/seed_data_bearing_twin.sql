-- db/seed_data_bearing_twin.sql — dead-twin → live-twin member/incomer redirect. DEFAULT OFF (byte-identical).
--
-- topology.data_bearing_twin — data/neuract_live/members._member_row (via data/neuract_live/twin.live_twin_table).
-- ON: when a panel member/incomer's topology edge points at a DEAD twin meter (an `_sch` schematic stub: 0 columns,
-- never_wired, table_exists=false), its DATA table is redirected to its live sibling — the meter of the SAME physical
-- asset (GIC-scoped key: strip only the -Nxx- meter position + [model] suffix; so 'GIC-15-N10-PCC-01 (Transformer-01)'
-- and 'GIC-15-N3-PCC-01 (Transformer-01) [Secure Elite300]' match, but a generic 'Spare' never cross-matches across GIC
-- groups) whose registry row is table_exists AND not never_wired. Redirects ONLY when exactly ONE live twin exists.
-- The display id/name stay the topology's; only the neuract table swaps. Fixes the panel SUPPLY side at root — the
-- Energy Input card, the Energy Flow sankey source/incomers, and the SLD upstream all read the live meter instead of an
-- empty stub. Live coverage: 7 GIC-15 HT meters (4 PCC transformers, Spare, 11 KV Incomer, TIE feeder); 17 topology
-- edges pointed at dead twins. OFF (this default) = the topology edge's own (often dead) table, byte-identical.
--
-- ON CONFLICT DO NOTHING (idempotent; never flips an operator 'on' back to 'off').

INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('topology.data_bearing_twin', 'off', 'text', 'topology',
  'Redirect a member/incomer whose registry meter is a DEAD twin (_sch stub, never_wired, 0 cols) to its live sibling table (same GIC-scoped physical asset, exactly-one live twin; data/neuract_live/twin.py). Fixes panel supply-side blanks (Energy Input/Flow sankey/SLD incomers) at root; 7 GIC-15 HT meters. off=byte-identical.')
ON CONFLICT (key) DO NOTHING;
