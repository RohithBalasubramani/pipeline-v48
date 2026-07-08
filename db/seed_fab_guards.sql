-- db/seed_fab_guards.sql — the DB knobs + reason templates for the DETERMINISTIC POST-FILL FABRICATION GUARDS
-- (ems_exec/executor/fab_guards.py). Every threshold / per-class valve / structural-chrome vocabulary the guard reads is
-- an app_config ROW under section 'fab_guards' WITH a code-default mirror in fab_guards.py — editing a row changes the
-- guard's behavior with no code change; a missing row / DB outage falls back to the identical code default.
--
-- The guard blanks four slot-name-INDEPENDENT fabrication CLASSES post-fill:
--   epoch_ms      CLASS 1  epoch-millis time-leak   (a non-time-axis leaf holding an epoch-ms magnitude)
--   null_column   CLASS 2  null-column-as-reading   (a written leaf whose bound column is 100% NULL on the table)
--   no_source     CLASS 3  no-source value          (a written numeric leaf with no resolved column/fn/nameplate)
--   seed_leak     CLASS 4  unstripped seed-leak     (an UNWRITTEN leaf byte-identical to the harvested default)
--
-- Idempotent (ON CONFLICT). Run:
--   psql -h localhost -p 5432 -d cmd_catalog -f db/seed_fab_guards.sql
-- [BUCKET 3 — deterministic-guard completeness]

-- ── per-CLASS valves + thresholds + structural-chrome vocab ────────────────────────────────────────────────────────
INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('fab_guards.epoch_ms', 'on', 'text', 'fab_guards',
   'CLASS 1 valve (on/off). Blanks a NON-time-axis leaf whose numeric value (scalar or every array element) is an '
   'epoch-millis magnitude that leaked into a value/scale slot. off = disable the class without a code change.'),
  ('fab_guards.null_column', 'on', 'text', 'fab_guards',
   'CLASS 2 valve (on/off). Blanks a WRITTEN leaf whose bound column is 100% NULL over the whole table (neuract '
   'column_logged==False) when the table is demonstrably reachable — a 0.0/placeholder posing as a reading.'),
  ('fab_guards.no_source', 'on', 'text', 'fab_guards',
   'CLASS 3 valve (on/off). Blanks a WRITTEN numeric leaf whose field resolved NO source — no present column, no '
   'derivation fn/metric binding, no nameplate rating — a no-source stray value.'),
  ('fab_guards.seed_leak', 'on', 'text', 'fab_guards',
   'CLASS 4 valve (on/off). Blanks an UNWRITTEN leaf whose FINAL value is byte-identical to the card DEFAULT payload '
   'at the same path (an unstripped Storybook seed, e.g. card-73 legendValue 52/71/85/43). off = disable the class.'),
  ('fab_guards.epoch_ms_floor', '1000000000000', 'number', 'fab_guards',
   'CLASS 1 threshold: the magnitude at/above which a bare number is treated as an epoch-MILLIS timestamp. 1e12 ms '
   '~= year 2001; every real EMS reading (kW/kWh/V/A/%/count/pf) sits many orders below it. Code default 1e12.'),
  ('fab_guards.time_axis_suffixes',
   '["ticks","labels","indexes","timestamps","timestamp","axisstart","axisend","axisstartms","axisendms","startms","endms"]',
   'json', 'fab_guards',
   'CLASS 1 exemption vocab: leaf-key SUFFIXES that mark a designated TIME axis (…ticks/…labels/…indexes/…timestamps/'
   '…startMs). A leaf whose key ENDS WITH one of these is allowed to hold an epoch-ms magnitude (a real time axis), so '
   'the epoch-leak guard never blanks it; a value/scale mislabel (maxLine/expectedMax/valuePct) matches none and is '
   'still policed. Matched case-insensitively by suffix. Code-default mirror in fab_guards._time_axis_suffixes.'),
  ('fab_guards.time_axis_exact',
   '["ts","time","label"]',
   'json', 'fab_guards',
   'CLASS 1 exemption vocab: EXACT (whole-key) time-axis tokens — a leaf whose key IS one of these (ts/time/label, e.g. '
   'a per-point {time,value} time key) is a time axis exempt from the epoch-leak blank. Unioned with '
   'fab_guards.time_axis_suffixes and the shared vocab.time_axis_keys row. Code-default mirror in '
   'fab_guards._time_axis_exact.'),
  ('fab_guards.scale_selector_keys',
   '["scalemaxpct","limitpct","scalemax","defaultlimit"]',
   'json', 'fab_guards',
   'CHROME-RESTORE sub-vocab (a SUBSET of chrome_selector_keys): the gauge SCALE/limit keys whose BLANK is a degenerate '
   '0/0.0 (a zero-max gauge cannot draw a bar), not a null/'''' string selector. For these keys restore_chrome treats a '
   'numeric 0 as blank and restores the default scale; for a string selector/enum a 0 is NOT a blank. Kept a separate '
   'row so a new scale key is added with no code change. Code-default mirror in fab_guards._scale_selector_keys.'),
  ('fab_guards.magnitude_units',
   '["kVArh","MVArh","kVAh","MVAh","kWh","MWh","kVAr","MVAr","kVA","MVA","kW","MW","kV","kA","VAr","VA","Wh","Hz","A","V","W","%"]',
   'json', 'fab_guards',
   'CLASS 4 magnitude-label vocab: the KNOWN PHYSICAL UNITS a data magnitude baked into a chrome label ends with '
   '(''Rated: 131A'', ''600 kVA'', ''13.5%''). A number at a word boundary followed by one of these units inside an '
   'otherwise-chrome string is a fabricated reading dressed as chrome (card 69): when the label equals a stale default '
   'seed the number is stripped to ''—'' and the label chrome kept. Ordered longest-first at match time so kWh beats kW. '
   'Code-default mirror in fab_guards._MAG_UNITS_DEFAULT.'),
  ('fab_guards.trivial_int_magnitude', '10', 'int', 'fab_guards',
   'CLASS 4 over-reach floor: |v| strictly below this integer magnitude makes an INTEGER-valued scalar too trivial to '
   'police as a seed (0..9 — a value a real fill / honest blank legitimately produces, so equal-to-default there is '
   'coincidental, never a surviving seed). A multi-digit / decimal scalar IS policed. Code default 10.'),
  ('fab_guards.trivial_string_maxlen', '1', 'int', 'fab_guards',
   'CLASS 4 over-reach floor: a stripped STRING of this length or shorter is too trivial to police as a seed (a 1-char '
   'string); a string LONGER than this is a seed shape worth policing. The SAME boundary drives _trivial_scalar (<=) and '
   '_seed_worth_policing (>). Code default 1.'),
  ('fab_guards.data_value_keys',
   '["value","val"]',
   'json', 'fab_guards',
   'CLASS 4 metadata-branch NARROWING vocab: the RENDERED-VALUE words (matched by a key''s LAST camel/snake word — '
   'legendValue->value, summaryVal->val) that a numeric leaf must carry for the strip-MISS carve-out to fire. The '
   'authoritative raw-vs-stripped wall classifies a leaf the strip kept byte-identical (raw==stripped) as METADATA and '
   'exempts it — but the strip MISSES the per-series legendValue scalar (it keeps 52/71/85/43 verbatim), silently '
   're-exempting the card-73 fabrication whenever shape_ref is threaded. So a numeric metadata leaf whose key is a '
   'data-VALUE word IS still policed (a strip-missed legend reading), while presentation CONFIG the strip legitimately '
   'keeps under a NON-value key (curveSag/rowHeight/headerHeight/dimOpacity.line/bandThresholds.divisors.kw/minWidth) is '
   'NEVER blanked (its last word is sag/height/line/kw/width, not value). Class-level field-kind vocab (deliberately '
   'omitted from every chrome vocab), not a per-card/per-slot hardcode. Code-default mirror fab_guards._data_value_keys.'),
  ('fab_guards.structural_chrome_keys',
   '["key","color","colour","dashed","dash","stroke","fill","order","separator","from","to","radius","opacity","z","zindex","width","span","index","decimals","align","variant","icon","id","label","name","axis","orientation","domain"]',
   'json', 'fab_guards',
   'CLASS 4 over-reach carve-out: leaf KEYS whose value is DESIGN-SYSTEM STRUCTURAL/DISPLAY chrome (a series/point '
   'identity, position, style, scale-binding, or DISPLAY-NAME leaf) — byte-identical to the default BY DESIGN, never a '
   'rendered reading. A leaf under one of these keys is EXEMPT from the seed-leak comparison so the guard never blanks a '
   'legend colour / series key / dashed flag / series name / axis-binding just because it equals the default (the '
   'card-73 over-reach). axis/orientation/domain = the scale-binding identity of a config-object series/axis (cards '
   '61/62). DELIBERATELY OMITS value/narrative keys (legendValue/warn/trip/value/val/why/title/severity/caption/note/'
   'source/delta/deltaTone) — those DO surface on-screen in a REAL data series, so a stale-seed one IS the fabrication '
   'CLASS 4 must catch; a CONFIG-OBJECT series (no value/time element key — its warn/trip are threshold LINES not '
   'readings) is exempted WHOLESALE by fab_guards._is_config_object_series, not by these keys.'),
  ('fab_guards.chrome_string_keys',
   '["title","label","labels","name","unit","units","prefix","suffix","legend","legends","axislabel","xaxislabel","yaxislabel","tab","id","key","kind","color","colour","ticks"]',
   'json', 'fab_guards',
   'CLASS 4 CHROME WALL [metadata-stripping root cause, run r_627ae7b326]: leaf KEYS whose STRING value (or whose '
   'axis/scale scalar-ARRAY value) is CARD CHROME — a title/unit/display-label/prefix/legend-text/axis-label/renderer-'
   'directive the metadata-only emit copies VERBATIM from card_payloads, so equal-to-default is CORRECT, never a '
   'surviving data seed. Blanking these shipped nameless, unitless cards and an emptied yLabels (degenerate LinePath '
   'y-domain — the 3.4e9 axis). Matched by the key''s LAST camel/snake WORD (metricId->id, axisKey->key, '
   'xAxisLabel->label, railLabels->labels, unitSuffix->suffix, yTicks->ticks) and by the immediate CONTAINER key for '
   'strings (railLabels.dkwDt). NEVER applies inside a LIST ELEMENT (a per-record narrative title/why/severity stays '
   'policed) and never to a numeric scalar (card-73 legendValue 52/71/85/43 still blanks — its last word is value). '
   'DELIBERATELY OMITS every value/narrative word (value/val/why/severity/caption/note/source/delta/deltaTone). '
   'Edit this row to extend the vocab; code-default mirror in fab_guards._chrome_string_keys.'),
  ('fab_guards.chrome_selector_keys',
   '["view","dir","glyph","glyphcolor","preset","resample","scalemaxpct","limitpct","scalemax","defaultlimit","tone","dstone","ieeestate"]',
   'json', 'fab_guards',
   'CHROME-RESTORE + CLASS-4 carve-out vocab: leaf KEYS whose value is PRESENTATION-CONFIG the CMD_V2 component '
   'INDEXES / SWITCHES / SCALES on UNGUARDED — an active-VIEW selector (loadImpact.view -> views[view]), an enum '
   'DIRECTION/glyph (trend.dir/glyph/glyphColor -> RT_DIR_PRESETS[dir].color), an event/strip filter SELECTOR '
   '(filterSelection.preset/resample -> rangeForPreset switch), a gauge SCALE/limit (snapshot.h5.scaleMaxPct/limitPct/'
   'scaleMax/defaultLimit -> a zero-max gauge cannot draw a bar), a tone/badge/ieee enum (tone/dsTone/ieeeState). A '
   'null/0 here does not just look wrong — it CRASHES SSR (RT_DIR_PRESETS[null].color; rangeForPreset(preset=null)-> '
   'undefined.start) or EMPTIES the card (views[null] = nothing). So a leaf under one of these keys (1) is EXEMPT from '
   'the CLASS-4 seed-leak comparison (like structural chrome — byte-identical-to-default here is config BY DESIGN, never '
   'a data seed) AND (2) is RESTORED from the default by fab_guards.restore_chrome when the emit / honest-blank / '
   'seed-leak pass stripped it to null/0/''''. NOT a measurement key: restoring one can never fabricate a reading (a '
   'genuine DATA leaf that honest-blanks still blanks — its key is not in this set). Edit this row to extend the vocab.')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, data_type = EXCLUDED.data_type,
  section = EXCLUDED.section, note = EXCLUDED.note;

-- ── per-leaf REASON templates (the gaps channel sentence for each machine cause) ───────────────────────────────────
-- Each blank the guard makes writes a per-leaf reason on the gaps channel keyed by these causes; without a row the
-- reason channel falls back to the bare cause key (config/reason_templates.py), so these rows are the human sentence.
INSERT INTO reason_template (cause, template) VALUES
  ('epoch_ms_leak',
   '{metric}: a timestamp value leaked into a data/scale slot (epoch-millis magnitude) — not a measurement; blanked'),
  ('null_column_reading',
   '{metric}: bound column {column} is 100% empty on this asset''s table — not measured, no reading to show; blanked'),
  ('no_source_value',
   '{metric}: no measuring column/derivation/nameplate resolved for this slot — a value here has no source; blanked'),
  ('unstripped_seed',
   '{metric}: value equalled the card''s template default and was never filled from neuract — an unstripped seed; blanked')
ON CONFLICT (cause) DO UPDATE SET template = EXCLUDED.template;
