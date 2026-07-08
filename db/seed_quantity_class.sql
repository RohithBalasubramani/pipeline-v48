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
--   quantity.source_roles — NAME-level SOURCE roles {role: {markers, dedicated}}: a same-QUANTITY, different-ROLE
--                           smear the dimensional + reuse walls both miss. A slot naming a DEDICATED-SENSING role
--                           (bypass) binds ONLY a same-role source; the meter's plain input/line reading of that
--                           quantity honest-blanks — the card-59 bypassVoltageV ← voltage_avg (no bypass column).
--                           A non-dedicated role (input) never flags (input* ← voltage_avg is the real reading).
--   quantity.source_role_markers — role → RAIL-QUALIFIER marker tokens {output/bypass/input/mains/utility/grid/
--                           incoming/line_side/source}: the SOURCE-ROLE CLASSIFIER (source_role_of / is_non_output_
--                           source) the ems_exec.executor.measurable_resolve source-role WALL consumes (via getattr)
--                           to resolve a qualified electrical label to its physical rail and REFUSE this output-
--                           metering MFM's own voltage_avg/current_avg reading for any NON-output rail — 'Output
--                           Voltage' KEEPS (the meter's own terminal), 'Average Bypass Voltage' / Input/Mains/Utility/
--                           Grid/Incoming/Line-side honest-blank (a separate un-metered rail; DEFECT 56, card 56).
--                           Token-exact markers, multi-word = adjacent run (never a substring). 'output' is the ONE
--                           measured/self role (is_non_output_source False); every other role is a distinct rail (True).
--   quantity.time_axis_label_tokens — series TIME-AXIS LABEL leaf tokens: a per-element points[*].label / .slot leaf
--                           fills from the card's OWN bucket timestamps (kind=time), never a measured column — a
--                           column/fn bound there ships the reading AS a time label (card-59 secondary:
--                           points[*].label ← active_power_total_kw = negative kW as x-axis labels); it honest-blanks.
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
  '{"v":"voltage","kv":"voltage","a":"current","ka":"current","kw":"power","mw":"power","w":"power","kva":"power","kvar":"power","kwh":"energy","mwh":"energy","kvah":"energy","kvarh":"energy","hz":"frequency","%":"percent","pct":"percent","score":"score-index","/100":"score-index","°c":"temperature","degc":"temperature","celsius":"temperature","°f":"temperature","years":"lifetime","year":"lifetime","yrs":"lifetime","min":"duration","mins":"duration","minutes":"duration","s":"duration","sec":"duration","h":"duration","hr":"duration","hrs":"duration","hours":"duration","ms":"duration","days":"duration","/hr":"rate","/hrs":"rate","/hour":"rate","/h":"rate","perhr":"rate","perhour":"rate","ops":"count","ops/hr":"rate","ops/hrs":"rate","ops/h":"rate","opsperhr":"rate","°":"angle","deg":"angle"}',
  'json', 'quantity',
  'unit token → physical-quantity class (dimensional lookup) — classifies a basket column''s describe unit, a slot''s sibling unit chrome, and (gate fallback) the emitted field''s own display unit; score//100 = score-index (the battery/readiness score cells); /hr//hrs//hour = rate (per-hour OCCURRENCE-RATE — the transformer tap-rtcc Peak/Average tap-count KPIs, card 14, distinct from the bare hr/hrs DURATION and from power, so a worstPeakKw power fn under a /hrs tap-rate leaf honest-blanks); ops = count / ops/hr = rate (the transformer tap-rtcc Tap-Activity KPIs/legend/points, card 81, declare unit=ops for a discrete OLTC operation TALLY and unit=ops/hr for the operations-per-hour Rate cells — an ops count/rate is NOT a power/load-factor, so a worstPeakKw/loadFactorPct derivation shipped under an ops tap-operation KPI honest-blanks; this is the primary card-81 anchor since every fabricated Tap-Activity leaf has a generic value slot leaf) (layer2/quantity_class.unit_class)'),
 ('quantity.name_classes',
  '{"voltage":"voltage","volt":"voltage","current":"current","amps":"current","ampere":"current","lol":"lifetime","lolpct":"lifetime","power":"power","kw":"power","kva":"power","kvar":"power","watt":"power","demand":"power","kwh":"energy","kvah":"energy","kvarh":"energy","mwh":"energy","energy":"energy","consumption":"energy","frequency":"frequency","hz":"frequency","temperature":"temperature","temp":"temperature","hotspot":"temperature","hotspotc":"temperature","oil":"temperature","oilc":"temperature","winding":"temperature","windingc":"temperature","ambient":"temperature","lifeyears":"lifetime","lifetime":"lifetime","life":"lifetime","years":"lifetime","aging":"aging-factor","ageing":"aging-factor","faa":"aging-factor","readiness":"readiness","tapcount":"count","count":"count","transfers":"count","tapchanges":"count","tapchange":"count","tapoperations":"count","tapoperation":"count","operations":"count","operation":"count","events":"count","starts":"count","breaches":"count","trips":"count","faults":"count","crestfactor":"crest-factor","crest":"crest-factor","flicker":"flicker","flickerpst":"flicker","pst":"flicker","plt":"flicker","h3":"voltage-harmonic","h5":"voltage-harmonic","h7":"voltage-harmonic","h9":"voltage-harmonic","h11":"voltage-harmonic","h13":"voltage-harmonic","thdcurrent":"current-thd","currentthd":"current-thd","ithd":"current-thd","thdi":"current-thd","thdvoltage":"voltage-thd","voltagethd":"voltage-thd","vthd":"voltage-thd","thdv":"voltage-thd","ithdpk":"current-thd","thdpk":"current-thd","peakthd":"current-thd","thdpeak":"current-thd","deviation":"deviation-spread","spread":"deviation-spread","unbalance":"unbalance","imbalance":"unbalance","powerfactor":"power-factor","pf":"power-factor","cosphi":"power-factor","loadfactor":"load-factor","loadpct":"load-factor","efficiency":"efficiency","headroom":"headroom","soc":"battery-charge","slot":"timestamp","angle":"angle","deg":"angle","minutes":"duration","hours":"duration","runtime":"duration","backuptime":"duration","tap":"tap-position","tapposition":"tap-position","oltc":"tap-position","tapchanger":"tap-position","totap":"tap-position","fromtap":"tap-position","enginespeed":"engine-speed","speedraw":"engine-speed","rpm":"engine-speed","oilp":"pressure","oilpressure":"pressure","pressure":"pressure","manifold":"pressure","fuel":"fuel","fuellevel":"fuel","fuelrate":"fuel","totalfuel":"fuel","fueltank":"fuel","autonomy":"autonomy","autonomyindex":"autonomy","batteryscore":"readiness","batteryhealthscore":"readiness","healthscore":"readiness","transferdays":"count","lasttransfer":"count","mtbf":"reliability","mttr":"reliability","reliability":"reliability","fraction":"availability","availability":"availability"}',
  'json', 'quantity',
  'name token / adjacent-token-pair → physical-quantity class — classifies slot-path segments, column names and fn names, leaf-most token first, pair beats single. G-family closure additions: loadpct(pair)→load-factor, efficiency, headroom, soc→battery-charge, slot→timestamp; c61/c64 count words events/starts/breaches/trips/faults; precision-rework: lol/lolpct→lifetime (the aging-ancestor-bleed FP — lolPct ← loss_of_life_pct is the RIGHT bind). card-72 reliability closure: mtbf/mttr/reliability→reliability + fraction/availability→availability — MTBF/MTTR reliability-hours and active/reactive fractions are NOT measured by an electrical MFM (no failure/repair-event column), so an active-energy counter re-labelled there honest-blanks (reliability/availability != energy → compatible False). card-14 tap-rtcc closure: tapchanges/tapchange/tapoperations/tapoperation(PAIR)→count — an OLTC tap OPERATION is a discrete tap-change tally (count / per-hour rate), NOT a power reading, so a worstPeakKw/loadFactorPct power fn under a tap-count KPI honest-blanks (count != power); PAIR tokens keep the bare tap PATH token as tap-position (OLTC step, cards 78-81). card-81 Tap-Activity closure: operations/operation→count — the LABEL count word (Total operations / Tap operations (hourly)) anchors the wall even when the slot leaf is a generic value and the unit is stripped, complementing the unit=ops primary anchor; the bare ops abbreviation is DELIBERATELY ABSENT from name_classes (it rides the container slot token liveOps on card 70 Availability, NOT a count — the unit_classes ops key covers card 81 with no slot collision). card-04 peak-THD closure (DEFECT B): ithdpk/thdpk/peakthd/thdpeak→current-thd — a peak individual-harmonic-THD-current leaf is a distortion %, NOT a raw amps magnitude, and NO peak-THD column exists on gic_*, so measurable_resolve refuses the raw current_avg bind (the 265-amps-as-peak-THD fab) and the leaf honest-blanks (the ithd pair already caught iThdPk; these token-exact keys classify the bare peak-THD spellings too) (layer2/quantity_class.name_class/slot_class)'),
 ('quantity.weak_classes',
  '["percent"]',
  'json', 'quantity',
  'dimension-only classes too generic to flag a cross-quantity mismatch on (an unclassified-by-name % column could be ANY percent semantic — cautious keep, never a blank on dimension alone)'),
 ('quantity.semantic_families',
  '{"efficiency":{"markers":["efficiency"],"classes":["efficiency"]},"specific-consumption":{"markers":["sfc","specific consumption","specific fuel consumption","specific energy consumption"],"classes":[]},"consumption":{"markers":["consumption","consumed"],"classes":["energy","power"]},"fuel":{"markers":["fuel"],"classes":[]},"unbalance":{"markers":["unbalance","imbalance"],"classes":["unbalance"]}}',
  'json', 'quantity',
  'NAME-level semantic families — a slot whose name (slot path / metric / sibling label) claims a family binds only a same-family source fn/column or a family-licensed quantity class; blocks the card-65 same-dimension pun (Efficiency ← loadFactorPct passes the WEAK-percent dimensional wall). Token-exact markers, multi-word = adjacent token run (layer2/quantity_class.semantic_family_mismatch)'),
 ('quantity.source_roles',
  '{"bypass":{"markers":["bypass"],"dedicated":true},"input":{"markers":["input","line","mains"],"dedicated":false}}',
  'json', 'quantity',
  'NAME-level SOURCE roles — a same-QUANTITY, different-ROLE smear the dimensional wall (voltage↔voltage compatible) and the reuse-smear wall (classified bind defers) both miss. A slot naming a DEDICATED-SENSING role (dedicated:true) binds ONLY a source whose name carries that SAME role; the meter''s plain input/line reading of the same quantity is a fabrication and honest-blanks (card-59 bypassVoltageV/bypassFrequencyHz ← voltage_avg/frequency_hz: the gic_* UPS meter has NO bypass column, verified against information_schema). A NON-dedicated role (input/line/mains — the plain reading) never flags: input* slots legitimately bind bare voltage_avg. Token-exact markers, leaf-most first. Seed ONLY the verified bypass role — output/battery/rectifier punned binds are already caught by the score-index/quantity walls (layer2/quantity_class.source_role_mismatch)'),
 ('quantity.source_role_markers',
  '{"output":["output","load side","load-side","loadside"],"bypass":["bypass"],"input":["input"],"mains":["mains"],"utility":["utility"],"grid":["grid"],"incoming":["incoming"],"line_side":["line side","line-side","lineside","line"],"source":["source"]}',
  'json', 'quantity',
  'role → RAIL-QUALIFIER marker tokens — the SOURCE-ROLE CLASSIFIER (layer2.quantity_class.source_role_of / is_non_output_source) the ems_exec.executor.measurable_resolve source-role WALL consumes (via getattr) to resolve a qualified electrical label to its physical sensing rail. This OUTPUT-metering gic_* MFM senses only its OWN output — voltage_avg/current_avg ARE that measured (output) reading, NOT a separate bypass static-switch / input-line / mains / utility / grid / incoming / line-side / source rail. So the wall REFUSES the meter''s own reading for any NON-output rail: Output Voltage → role output → KEEP (the meter''s own terminal); Average Bypass Voltage → role bypass → [] honest-blank (no bypass sensor on this meter, verified against information_schema); Input/Mains/Utility/Grid/Incoming/Line-side → non-output rail → [] (a separate un-metered rail). DEFECT 56, card 56 avg-bypass-v. Token-EXACT markers, a multi-word marker (line side / load side) matches an ADJACENT token run — never a substring (sourced/grinder/inputted never fire). output is the ONE measured/self role (is_non_output_source False, wins when a label pairs it with a rail word); every other classified role is a physically distinct un-metered rail (is_non_output_source True). A label carrying NO rail qualifier classifies None → the plain reading is legitimate, never blanked. This is the ONE source-role vocabulary (hoisted from the wall''s former inline set so it is DB-config-driven with a code-default mirror)'),
 ('quantity.time_axis_label_tokens',
  '["label","slot","time","ts","tick","axislabel","timestamp","bucket"]',
  'json', 'quantity',
  'series TIME-AXIS LABEL leaf tokens — a per-element points[*].label / .slot leaf is the time-axis tick label, filled from the card''s OWN bucket timestamps (kind=time), NEVER a measured column. A raw/bucketed/derived field binding a column/fn into such a leaf ships the reading AS an x-axis time label (card-59 secondary: composite.points[*].label ← active_power_total_kw = negative kW as time labels); it honest-blanks. Only a per-ELEMENT ([*]/indexed) series leaf matches — a bare scalar label (legend/badge) is not a time axis; a kind=time atom (no column) is exempt (layer2/quantity_class.is_time_axis_label_slot, layer2/gates._time_axis_label_bind)'),
 ('quantity.compatible_slot_source_pairs',
  '[["current","deviation-spread"],["voltage","deviation-spread"]]',
  'json', 'quantity',
  'ORDERED [slot_class, source_class] compatibility grants — a statistic-kind source may fill a slot of the base dimension it is a statistic OF (the card-46 Max Spread (A) cell ← current_max_spread; 91 corpus FPs where the sibling-unit A outranked the spread label). The REVERSE is NOT granted (maxDeviation ← voltageStatutoryBand stays a catch) and crest-factor/flicker ← spread stays blocked (layer2/quantity_class.compatible)'),
 ('quantity.structural_const_tokens',
  '["decimals","opacity","index","layout","windowdays"]',
  'json', 'quantity',
  'const metric/slot-leaf name tokens (token-exact / adjacent-pair) that state a pure DISPLAY/FRAME knob, not a measurement — decimals, areaOpacity/dimOpacity, selectedSampleIndex, layout, windowDays — exempt from the const-source guard (~450 corpus FPs of broken formatter/selection chrome); a quantity-named const (131 A / 0.0 kW / 1461 kWh) never matches and stays policed (layer2/quantity_class.structural_const_name)'),
 ('quantity.mixed_container_tokens',
  '["energyreliability"]',
  'json', 'quantity',
  'slot-path CONTAINER segments (concatenated tokens, token-EXACT) that name TWO distinct quantities — slot_class SKIPS them so a container never smears one class onto every child cell. energyReliability (card 72) groups energy AND reliability cells under a generic .cells[N].value leaf: letting it assert energy passed the MTBF/MTTR reliability cells fed the active-energy counter (the family fabrication), and asserting reliability would over-blank the real active/reactive ENERGY cells — so it is skipped and the per-cell unit (h→duration / MWh→energy) + sibling label (MTBF→reliability / Active→energy) discriminate. A SINGLE-quantity container (hotspotC / fuelTemp / lifetimeTransfers) is NOT listed and classifies leaf-most as before (layer2/quantity_class.slot_class)'),
 ('quantity.axis_chrome_const_slots',
  '["ymax","ymin","yticks","watchlines"]',
  'json', 'quantity',
  'slot path SEGMENTS whose const value is AXIS-GEOMETRY chrome (yMax/yMin/yTicks bounds + watchLines threshold lines) — exempt from the const-source guard (c49 LoadImpactChart false-positive: a design-default axis scale/threshold re-supplied as a const is not a fabricated reading; post-fill yscale recomputes filled views). ANY-SEGMENT match so watchLines[*].value is exempted while stats[*].value (a real KPI reading, no axis segment) stays policed (layer2/gates._axis_chrome_const_segs)'),
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
