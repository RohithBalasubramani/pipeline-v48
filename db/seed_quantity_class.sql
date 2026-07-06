-- db/seed_quantity_class.sql — the PHYSICAL-QUANTITY class vocabulary (layer2/quantity_class.py) + the sanctioned
-- `consts.*` namespace for site-approved literal data-slot constants.
--
--   quantity.unit_classes — unit token → quantity class ('°C'→temperature, 'A'→current, 'min'→duration, …): classifies
--                           a basket column's describe unit and a payload slot's sibling unit chrome.
--   quantity.name_classes — name token / adjacent-token-pair → class (hotspot→temperature, h5→voltage-harmonic,
--                           thd+current→current-thd, faa→aging-factor, readiness, tapcount, crest, flicker, …):
--                           classifies slot-path segments, column names and derivation fn names. Token-EXACT matching
--                           (never substring). Deliberately absent (false-positive-prone container words): load,
--                           score, transfer, days, max, min.
--   quantity.weak_classes — dimension-only classes ('percent') too generic to flag a mismatch on.
--   quantity.semantic_families — NAME-level families {family: {markers, classes}} (efficiency / sfc / consumption /
--                           fuel): a slot whose name (slot path / metric / sibling label) claims a family binds ONLY
--                           a same-family source fn/column (or a family-licensed quantity class) — the card-65
--                           same-dimension pun wall ('Efficiency' 5.3 ← loadFactorPct: percent is WEAK so the
--                           dimensional wall passes it; the FAMILY wall blanks it). Markers are token-exact;
--                           a multi-word marker matches an adjacent token run.
-- These drive BOTH the emit context (qty= per DB SCHEMA line, expected_qty= per slot line) AND the deterministic
-- QUANTITY-WALL honest-blank in layer2/gates.enforce_honest_blank ('X not measured by this meter (no X column)').
-- Code-default mirrors live in layer2/quantity_class.py — behavior is identical until a row is edited.
--
--   consts.<name>         — a site-approved literal a kind=const DATA field may ship: the emit cites the row by
--                           `metric` (normalized-name match on <name>) and the emitted value must EQUAL the row's.
--                           A numeric const that resolves to NEITHER a nameplate rating (config/nameplate_slot_map)
--                           NOR a consts.* row is BLANKED by the gate (the fabricated 131 A / 1000 kVA class).
-- Idempotent. Run: psql (cmd_catalog DSN per config/databases.py) -f db/seed_quantity_class.sql

INSERT INTO app_config (key, value, data_type, section, note) VALUES
 ('quantity.unit_classes',
  '{"v":"voltage","kv":"voltage","a":"current","ka":"current","kw":"power","mw":"power","w":"power","kva":"power","kvar":"power","kwh":"energy","mwh":"energy","kvah":"energy","kvarh":"energy","hz":"frequency","%":"percent","pct":"percent","score":"score-index","/100":"score-index","°c":"temperature","degc":"temperature","celsius":"temperature","°f":"temperature","years":"lifetime","year":"lifetime","yrs":"lifetime","min":"duration","mins":"duration","minutes":"duration","s":"duration","sec":"duration","h":"duration","hr":"duration","hrs":"duration","hours":"duration","ms":"duration","days":"duration","°":"angle","deg":"angle"}',
  'json', 'quantity',
  'unit token → physical-quantity class (dimensional lookup) — classifies a basket column''s describe unit, a slot''s sibling unit chrome, and (gate fallback) the emitted field''s own display unit; score//100 = score-index (the battery/readiness score cells) (layer2/quantity_class.unit_class)'),
 ('quantity.name_classes',
  '{"voltage":"voltage","volt":"voltage","current":"current","amps":"current","ampere":"current","lol":"lifetime","lolpct":"lifetime","power":"power","kw":"power","kva":"power","kvar":"power","watt":"power","demand":"power","kwh":"energy","kvah":"energy","kvarh":"energy","mwh":"energy","energy":"energy","consumption":"energy","frequency":"frequency","hz":"frequency","temperature":"temperature","temp":"temperature","hotspot":"temperature","hotspotc":"temperature","oil":"temperature","oilc":"temperature","winding":"temperature","windingc":"temperature","ambient":"temperature","lifeyears":"lifetime","lifetime":"lifetime","life":"lifetime","years":"lifetime","aging":"aging-factor","ageing":"aging-factor","faa":"aging-factor","readiness":"readiness","tapcount":"count","count":"count","transfers":"count","events":"count","starts":"count","breaches":"count","trips":"count","faults":"count","crestfactor":"crest-factor","crest":"crest-factor","flicker":"flicker","flickerpst":"flicker","pst":"flicker","plt":"flicker","h3":"voltage-harmonic","h5":"voltage-harmonic","h7":"voltage-harmonic","h9":"voltage-harmonic","h11":"voltage-harmonic","h13":"voltage-harmonic","thdcurrent":"current-thd","currentthd":"current-thd","ithd":"current-thd","thdi":"current-thd","thdvoltage":"voltage-thd","voltagethd":"voltage-thd","vthd":"voltage-thd","thdv":"voltage-thd","deviation":"deviation-spread","spread":"deviation-spread","unbalance":"unbalance","imbalance":"unbalance","powerfactor":"power-factor","pf":"power-factor","cosphi":"power-factor","loadfactor":"load-factor","loadpct":"load-factor","efficiency":"efficiency","headroom":"headroom","soc":"battery-charge","slot":"timestamp","angle":"angle","deg":"angle","minutes":"duration","hours":"duration","runtime":"duration","backuptime":"duration"}',
  'json', 'quantity',
  'name token / adjacent-token-pair → physical-quantity class — classifies slot-path segments, column names and fn names, leaf-most token first, pair beats single. G-family closure additions: loadpct(pair)→load-factor, efficiency, headroom, soc→battery-charge, slot→timestamp; c61/c64 count words events/starts/breaches/trips/faults; precision-rework: lol/lolpct→lifetime (the aging-ancestor-bleed FP — lolPct ← loss_of_life_pct is the RIGHT bind) (layer2/quantity_class.name_class/slot_class)'),
 ('quantity.weak_classes',
  '["percent"]',
  'json', 'quantity',
  'dimension-only classes too generic to flag a cross-quantity mismatch on (an unclassified-by-name % column could be ANY percent semantic — cautious keep, never a blank on dimension alone)'),
 ('quantity.semantic_families',
  '{"efficiency":{"markers":["efficiency"],"classes":["efficiency"]},"specific-consumption":{"markers":["sfc","specific consumption","specific fuel consumption","specific energy consumption"],"classes":[]},"consumption":{"markers":["consumption","consumed"],"classes":["energy","power"]},"fuel":{"markers":["fuel"],"classes":[]}}',
  'json', 'quantity',
  'NAME-level semantic families — a slot whose name (slot path / metric / sibling label) claims a family binds only a same-family source fn/column or a family-licensed quantity class; blocks the card-65 same-dimension pun (Efficiency ← loadFactorPct passes the WEAK-percent dimensional wall). Token-exact markers, multi-word = adjacent token run (layer2/quantity_class.semantic_family_mismatch)'),
 ('quantity.compatible_slot_source_pairs',
  '[["current","deviation-spread"],["voltage","deviation-spread"]]',
  'json', 'quantity',
  'ORDERED [slot_class, source_class] compatibility grants — a statistic-kind source may fill a slot of the base dimension it is a statistic OF (the card-46 Max Spread (A) cell ← current_max_spread; 91 corpus FPs where the sibling-unit A outranked the spread label). The REVERSE is NOT granted (maxDeviation ← voltageStatutoryBand stays a catch) and crest-factor/flicker ← spread stays blocked (layer2/quantity_class.compatible)'),
 ('quantity.structural_const_tokens',
  '["decimals","opacity","index","layout","windowdays"]',
  'json', 'quantity',
  'const metric/slot-leaf name tokens (token-exact / adjacent-pair) that state a pure DISPLAY/FRAME knob, not a measurement — decimals, areaOpacity/dimOpacity, selectedSampleIndex, layout, windowDays — exempt from the const-source guard (~450 corpus FPs of broken formatter/selection chrome); a quantity-named const (131 A / 0.0 kW / 1461 kWh) never matches and stays policed (layer2/quantity_class.structural_const_name)'),
 ('quantity.axis_max_source_tokens',
  '["max","peak","worst","highest"]',
  'json', 'quantity',
  'source-name tokens that answer a MAX-bound axis slot (maxY/yMax/demandYMax ← current_max / worstPeakKw = a REAL measured windowed extremum, not a live-sample axis fabrication — 176 corpus FPs) (layer2/gates._axis_direction_ok)'),
 ('quantity.axis_min_source_tokens',
  '["min","lowest","floor"]',
  'json', 'quantity',
  'source-name tokens that answer a MIN-bound axis slot (minY ← current_min); a PEAK source into a min bound still blanks (degenerate floor) (layer2/gates._axis_direction_ok)'),
 ('quantity.axis_range_source_tokens',
  '["domain","band","range","bounds"]',
  'json', 'quantity',
  'source-name tokens for TWO-SIDED range fns that legitimately feed BOTH axis bounds (voltageHistoryDomain, voltageStatutoryBand) (layer2/gates._axis_direction_ok)'),
 ('consts.stress_border_pct', '100', 'number', 'consts',
  'thermal-life stress border (% of rated load where the stress zone begins) — the site-approved literal a kind=const data field may cite by metric=stress_border_pct (100% = load at nameplate rating)'),
 ('consts.hotspot_warn_c', '120', 'number', 'consts',
  'transformer hotspot WARN threshold (°C) — IEC 60076-7 continuous hotspot design limit; citable by a kind=const data field as metric=hotspot_warn_c / hotspotWarnC')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, data_type = EXCLUDED.data_type,
                                section = EXCLUDED.section, note = EXCLUDED.note;
