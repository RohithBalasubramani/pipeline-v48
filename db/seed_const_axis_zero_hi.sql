-- db/seed_const_axis_zero_hi.sql — CONSTANT/ALL-ZERO Y-SCALE GUARANTEE knob [DG-1 card 36, 2026-07-07].
--
-- DEFECT: an honest all-zero filled series (an off DG's kW strip chart) is all-EQUAL and inside [0,1], so the
-- post-fill scale passes shipped NO explicit y-scale leaves (yLabels stayed the stripped []) and the FE degenerated
-- its y-domain — epoch-ms digits rendered as the y-axis (3.35e9–3.45e9). The scale passes now ALWAYS anchor a
-- constant series to an explicit sane domain; for the ALL-ZERO constant that domain is 0..<this row> (honest 0
-- floor, line on the floor where it belongs).
--
-- Consumers (code default 1.0 — the row makes the top visible/editable, no code change to tune):
--   · ems_exec/executor/yscale.py    const_zero_hi() → _nice_bounds() (yMax/yMin pairs + yTicks axes)
--   · ems_exec/executor/norm_series.py _const_domain() (the normalized strip-chart contract's yLabels axis, card 36)
--
-- Apply:  psql postgresql://postgres@127.0.0.1:5432/cmd_catalog -f db/seed_const_axis_zero_hi.sql

INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('chart.const_axis_zero_hi', '1', 'number', 'chart',
   'axis TOP for an ALL-ZERO constant series: the post-fill scale passes (ems_exec/executor/yscale.py '
   'const_zero_hi + norm_series.py _const_domain) ship an explicit 0..<this> y-domain when every filled point is 0 '
   '(an off DG), so the FE never degenerates a constant series into an epoch-digit axis [DG-1 card 36]. Non-zero '
   'constants keep their band conventions (yscale ±1; norm_series rangeFromSamples ±max(1, 5%)). Code default 1.0.')
ON CONFLICT (key) DO UPDATE
  SET value = EXCLUDED.value, data_type = EXCLUDED.data_type,
      section = EXCLUDED.section, note = EXCLUDED.note, updated_at = now();
