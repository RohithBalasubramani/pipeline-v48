-- db/seed_vocab.sql — the structural payload VOCABULARIES (cmd_catalog.app_config, data_type='json').
-- THE single home of these vocabularies: config/vocab.py reads ONLY these rows (no code literals). Onboard a new data
-- DB / payload shape by editing rows: global key 'vocab.<name>', or per-DB override 'vocab.<db_link>.<name>'.
-- NO column-choice heuristics here — the AI binds columns itself from the full schema + verbatim leaf context.
-- Idempotent. Run: psql (cmd_catalog DSN per config/databases.py) -f db/seed_vocab.sql

INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('vocab.unit_quantities',
  '{"v":"voltage","volt":"voltage","volts":"voltage","a":"current","amp":"current","amps":"current","ampere":"current","kwh":"energy","kvah":"energy","kvarh":"energy","mvah":"energy","kw":"power","kva":"power","kvar":"power","hz":"frequency","%":"percent","pct":"percent"}',
  'json', 'vocab',
  'fixed dimensional lookup (declared unit → quantity); feeds ONLY the negative-power abs() convention in the executor'),
 ('vocab.element_value_keys',
  '["value","values","totalKw","totalKwh","utilizationPct","count","y","kw","kwh"]',
  'json', 'vocab',
  'object keys that carry the fillable NUMBER inside a series-of-objects (the PREFERRED enumeration for the executor, not column choice). When NONE of these match, the expander falls back to EVERY numeric element key that is not in vocab.element_chrome_keys.'),
 ('vocab.element_chrome_keys',
  '["decimals","width","dash","warn","trip","index","span","order","separator","from","to","legendvalue","stroke","opacity","radius","zindex","z","rowheight","headerheight","maxrowheight","fitmin","fitmax","minwidth","singlemodeminwidth","raildecimals","valuedecimals","tickdecimals","tickfractions","limdecimals","scalemax","ideal"]',
  'json', 'vocab',
  'per-element object keys that hold DESIGN CHROME even though they are numeric (line width/dash, decimals, warn/trip thresholds, positional index, zone from/to bounds, plus PRESENTATION-DIMENSIONAL layout literals: table rowHeight/headerHeight/maxRowHeight, column fit bounds fitMin/fitMax, table minWidth/singleModeMinWidth, rail railDecimals) — the series-of-objects expander DENYLIST: a numeric element key here is NEVER a fillable data leaf, so the whole series stays chrome. These recur across many table/series/rail cards and are pixel/format geometry, never a measured value; without them the type-only classifier data-classified them and strip_to_placeholders zeroed rowHeight:20→0.0 etc, wrecking table row height / column fit in the stored skeleton (unfillable → unbound_by_emit null at exec). Lower-cased match. 2026-07-15 [audit 10 F2]: + valueDecimals/tickDecimals/tickFractions/limDecimals/scaleMax/ideal — number-FORMAT and scale-config geometry the classifier data-classified (~7.7% of all unbound_by_emit telemetry); valuePct deliberately EXCLUDED (a measured percent on some cards). After editing this row run scripts/rescan_stripped_payloads.py — stored skeletons must re-derive.'),
 ('vocab.derived_sibling_keys',
  '{"displayValue": "value"}',
  'json', 'vocab',
  'derived-SIBLING leaf keys the slot catalog must not enumerate as bindable slots when their SOURCE sibling is also enumerated: the executor DERIVES them post-fill (display.py recomputes displayValue = fmt(value) whenever the bound value fills), so emitting/stamping them as unbound was pure telemetry noise (~2.9% of unbound_by_emit) and a wasted binding ask. A displayValue with NO value sibling stays enumerable (nothing derives it). [audit 2026-07-14, 10 F2]'),
 ('vocab.time_axis_keys',
  '["sampletimestamps","timelabeltimestamps","axisstartms","axisendms"]',
  'json', 'vocab',
  'TIME-AXIS leaf keys — the kind=''time'' contract: executor fills them from the card''s own bucket timestamps'),
 -- value_keys/label_keys re-derived FROM LIVE 2026-07-06: value_keys gained "pf"; both notes follow the live rows.
 ('vocab.value_keys',  '["value", "val", "displayValue", "delta", "deltaLabel", "deviation", "target", "sideValue", "pf"]',           'json', 'vocab',
  'numeric-STRING KPI detection (leaf_classify): a value/val string next to a label = measured data, not chrome'),
 ('vocab.label_keys',  '["label", "title", "name", "prefix", "qualifier", "sideLabel"]',  'json', 'vocab',
  'the sibling keys that mark a value/val numeric string as a labelled KPI (leaf_classify data-vs-chrome)')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, data_type = EXCLUDED.data_type,
                                section = EXCLUDED.section, note = EXCLUDED.note;
