-- db/seed_const_axis_bands.sql — CONSTANT / VARYING Y-SCALE DOMAIN-BAND knobs [audit+harden 2026-07-08].
--
-- Companion to seed_const_axis_zero_hi.sql (the ALL-ZERO 0..<top> knob). This file moves every remaining DOMAIN-BAND
-- literal out of the two post-fill scale passes into editable app_config rows WITH a code-default mirror, so ZERO
-- magic literal steers a chart axis. Behavior is byte-identical until a row is edited (defaults == the historical
-- constants). Each pass reads its own knob through a DB-backed accessor + code default:
--
--   ems_exec/executor/yscale.py   (the {yMax,yMin[,yTicks]} pair + ticks-only axes):
--     · chart.const_axis_band_halfwidth → const_band_halfwidth() → _nice_bounds(): the ±band around a NON-ZERO
--       CONSTANT series (line mid-axis, never a zero-range axis). Code default 1.0.
--     · chart.yscale_pad_pct           → pad_pct()             → _nice_bounds(): fractional headroom EACH side of a
--       VARYING series' data range. Code default 0.05 (5%).
--
--   ems_exec/executor/norm_series.py (the normalized-strip-chart contract: dataSeries + numeric-string yLabels):
--     · chart.norm_range_pad_pct → _range(): headroom EACH side of a varying range (CMD_V2 rangeFromSamples). Def 0.10.
--     · chart.norm_flat_pad_min  → _range(): the floor of a FLAT/constant series' pad (CMD_V2 ±max(1, 5%|hi|)). Def 1.0.
--     · chart.norm_flat_pad_pct  → _range(): the fractional part of that flat pad. Code default 0.05 (5%).
--
-- Together with chart.const_axis_zero_hi these guarantee: a CONSTANT series (any asset, any card of the shape) always
-- ships an explicit sane y-domain, so the FE never degenerates a constant into an epoch-magnitude axis; and a VARYING
-- series keeps its computed padded scale. All bands are small (<~1e3) → no served y-scale value ever lands in the
-- degenerate [1e9,1e11) epoch band.
--
-- Apply:  psql postgresql://postgres@127.0.0.1:5432/cmd_catalog -f db/seed_const_axis_bands.sql

INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('chart.const_axis_band_halfwidth', '1', 'number', 'chart',
   'yscale.py const_band_halfwidth(): half-width of the symmetric band around a NON-ZERO CONSTANT series in '
   '_nice_bounds (lo-hw .. hi+hw) so the flat line sits mid-axis, never a zero-range axis [DG-1 card-36 family]. '
   'Code default 1.0 (the historical 269..271 band on a 270 constant). Must be > 0 or the code default is used.'),
  ('chart.yscale_pad_pct', '0.05', 'number', 'chart',
   'yscale.py pad_pct(): fractional headroom padded on EACH side of a VARYING series data range in _nice_bounds '
   '(pad = span*this). Code default 0.05 (5%). A negative value falls back to the code default.'),
  ('chart.norm_range_pad_pct', '0.1', 'number', 'chart',
   'norm_series.py _range(): headroom padded EACH side of a normalized strip-chart VARYING range (CMD_V2 '
   'rangeFromSamples). Code default 0.10 (10%). A negative value falls back to the code default.'),
  ('chart.norm_flat_pad_min', '1', 'number', 'chart',
   'norm_series.py _range(): the FLOOR of a FLAT/constant normalized series pad (pad = max(this, pct*|hi|)); mirrors '
   'CMD_V2 rangeFromSamples ±max(1, 5%|hi|). Code default 1.0. Must be > 0 or the code default is used.'),
  ('chart.norm_flat_pad_pct', '0.05', 'number', 'chart',
   'norm_series.py _range(): the FRACTIONAL part of a FLAT/constant normalized series pad (pad = max(min, this*|hi|)). '
   'Code default 0.05 (5%). A negative value falls back to the code default.')
ON CONFLICT (key) DO UPDATE
  SET value = EXCLUDED.value, data_type = EXCLUDED.data_type,
      section = EXCLUDED.section, note = EXCLUDED.note, updated_at = now();
