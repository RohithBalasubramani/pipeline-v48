== data_instructions (the parseable DATA-fill RECIPE — the helper fills the DATA from it) ==
Emit a recipe the helper parses to FILL the DATA tier — NOT data, NOT SQL, NOT numbers. It is a RESOLVED recipe: one resolved field per data slot, plus the per-card fill envelope. Bind every field to a REAL column from the COLUMN BASKET by the field's `metric` — never bind every tile to the same column (the 'every tile = active_power' bug). Shape:
- payload_shape — which DATA tier to fill (the card's payload_shape).
- orientation — time | entity | snapshot (the row shape).
- entity_dim / selection_dim — what each row/series IS and what selection drives it.
- selection_role — the card's interdependency role (both|produces|consumes|emits|none) — provisional.
- binding — { asset_id, table, ts_col, panel_id, nameplate_scope } (from 1b's resolved asset). Null for a pure-$ctx group atom (DATA from the shared buffer) or a pure-const card. (There is NO top-level `source` on data_instructions — fill source is PER-FIELD `fields[].source`.)
- window — { lookback, sampling, time_mode } from the card controls (re-slice = re-bind only).
- ems_backend — ★ the fetch spec that DRIVES the live backend. The helper opens `ws/mfm/<asset mfm_id>/<endpoint>/`; the consumer returns the card's DATA (incl. the history time-series); the frontend feeds that frame to the CMD V2 card's OWN mapper. YOU set the prompt-driven knobs so it returns the APPROPRIATE data:
    { endpoint, window_seconds, interval_seconds, sample_count, range, start, end, sampling, metrics, selection }
  - endpoint — the consumer screen. Pick EXACTLY ONE from this card's `ems_backend ENDPOINT` hint above (the live set + retired blocklist are listed there, derived from ems_backend — that is the authority, not this prose). Match it to the card's nature:
      · REAL-TIME card (live rolling values / scrubber / now-snapshot) → the card's LIVE screen, driven by window_seconds/interval_seconds.
      · TREND / PROFILE / HISTORY card (values should CHANGE WHEN THE USER PICKS A DATE) → one of the card's DATE-CAPABLE history variants, driven by range/start/end/sampling — this is what makes the card date-navigable. If the hint lists NO history variant, the card's live screen already serves history via range/sampling (e.g. `power-quality-summary`).
      · NEVER invent an endpoint or use a legacy name that is not in the hint's live set — anything outside it DOES NOT EXIST (it lands on the catch-all and returns no data).
      · THE CLOSED SET — ONLY these endpoints EXIST (emit EXACTLY one): {{LIVE_ENDPOINTS}}.
      · ★ RETIRED — DO NOT EXIST, NEVER emit: {{RETIRED_ENDPOINTS}}. ALL Harmonics/PQ data is the SINGLE live socket `power-quality-summary` (no PQ history variant).
      · CHOOSE BY the card's ANALYTICAL INTENT (the recipe's orientation/intent in the user message), NOT keyword overlap: a now/snapshot card → the LIVE screen; a trend/profile/history card → a history variant. STRONG preference for the card's NATURAL endpoints line in the user message; a RELATED screen is fine if THIS card's story needs it (e.g. a PQ card plotting a current trend → current-history). Only an UNRELATED page's screen (e.g. real-time-monitoring on a power-quality card) is wrong.
  - LIVE knobs (real-time endpoints): window_seconds (rolling reach, e.g. 30), interval_seconds (cadence, e.g. 2), sample_count (depth, e.g. 12). Set range/start/end/sampling = null.
  - DATE-WINDOW knobs (history endpoints — THE DATE NAVIGATION SEAM): range = today | yesterday | last-7-days | this-month | custom-range (the DEFAULT window; the frontend OVERRIDES it when the user changes the date). start/end = ISO or bare YYYY-MM-DD, ONLY when range=custom-range. sampling = hourly | 2hour | shift | day | week (bucket width must suit the range: today→hourly/2hour/shift; week→day; month→week). Set window_seconds/interval_seconds/sample_count = null.
  - metrics — which measured quantities this card's history needs (kw, kvar, pf, voltage, current, iUnbalance, …). Ground in the card + the prompt metric.
  - selection — the initial selected entity/section/bucket (or null).
  Leave a knob at its control default unless the prompt narrows it; null the OTHER family's knobs. This block is HOW ems_backend fills the DATA — author it so the history time-series + numbers come back correct AND the card responds to date changes.
  - ★ WINDOW/LABEL COHERENCE (deterministically enforced): the range/window you declare here, the `window.lookback`
    you emit, and every PERIOD-DECLARING metadata leaf (`periodLabel`, `range`, a "Monthly"/"Weekly"/"Today" caption)
    MUST all name the SAME window — the one the consumer will actually fill from. A 'Monthly' label over a 24h fill
    mislabels every number under it (fabrication by caption). If you keep a default period label that does NOT match
    the window you declare, MORPH that label leaf to the window's truth (declare it in `_morphed`) or the gate morphs/
    blanks it for you and records the incoherence. Your declared range also DRIVES the backfilled fill window — so
    declare the range the card's story actually needs, once, and keep every label consistent with it.
- fields[] — one resolved field per data slot, each:
    { slot, kind(raw|bucketed|time|derived|const|text|event), role(series|kpi|column|line|cell|tile|row|spoke),
      metric, column, label, unit, agg(avg|last|sum|count|derived), source(live|test-db|const|$ctx),
      value?(const only), base_columns?/sql_fragment?/nameplate_refs?(derived only), edge?(event only),
      sampling?(bucketed only), filters_table, has_data }
  ★★ `slot` IS THE #1 CORRECTNESS RULE — it MUST be COPIED VERBATIM from the "FILLABLE DATA-LEAF SLOTS" block in the
     user message (the exact dotted/indexed leaf path, e.g. `health.data.phases[0].value`, `flow.vm.kpis.lossKw`,
     `history.data.series[0].values`). The executor fills ONLY the leaf a slot names; an invented token (tile_r,
     kpi_actual, series_r, sourceInputKw, instantaneous_power) resolves to NOTHING and the field — even with a perfect
     column — is DISCARDED and the leaf stays empty. NEVER emit a slot that is not on that list. One field per leaf you
     fill; a per-phase / per-series leaf gets ONE field per element path ([0].value, [1].value, …), each bound to the
     column for THAT phase (R→*_r, Y→*_y, B→*_b, N→*_neutral).
  Rules per kind (NOTE: `kind` is WHAT the field is; `source` is WHERE its data lives — set source by DATA-RESIDENCE below, NOT by kind):
  - raw → bind `column` to a real basket column for this field's metric, COPIED VERBATIM (exact spelling/case); agg avg/last/sum.
    ★ MANDATE: for a raw data leaf you MUST name a real column that measures its quantity. The "FILLABLE DATA-LEAF
    SLOTS" block gives each slot's VERBATIM payload context (its own label / unit / section title, copied from the card);
    the COLUMN BASKET above is the COMPLETE schema (every real column + metric + unit + has_data). MATCH them yourself:
    a slot with label="R-Phase" · unit="V" · section="Voltage Monitor" binds the R-phase VOLTAGE column (voltage_r_n);
    the same label under section="Current Monitor" · unit="A" binds current_r. Section title + unit name the quantity;
    the label picks the phase/member. ★ HONEST-BLANK = OMIT THE FIELD: when NO schema column measures the leaf's
    quantity OR it is one of the FIVE PHYSICAL WALLS / an off-domain quantity this meter class does not measure (a
    battery SOC / battery temperature / fuel level on an electrical meter), emit NO field for that leaf AT ALL —
    leave the slot out of fields[], the leaf renders an honest blank, and data_note says why (answerability=partial).
    NEVER emit a raw or bucketed field with column=null / a missing column — a columnless raw/bucketed field is a
    gate defect ('missing a resolved column'), not an honest blank; kind="time" is the ONLY field that carries no
    column. Do NOT omit a leaf when the schema HAS a matching column — that blanks a card that HAS data (the #1
    defect). Do NOT bind `$ctx` on a STANDALONE card (see below).
  - bucketed → a HISTORY / TREND numeric-ARRAY SERIES leaf (a `kind=array` slot in the "FILLABLE DATA-LEAF SLOTS" list —
    e.g. `history.data.series[0].values`, `trend.data.series[1].values`). The slot's payload leaf is a pure numeric list
    (`[…]`), so the executor fills it with an ORDERED time-bucketed value array (avg per bucket, ascending) from
    neuract, NOT a single latest number. Use `kind="bucketed"` for EVERY numeric-array series leaf (kind=array in the
    slot list). Emit:
    {kind:"bucketed", role:"series", column:"<ONE real basket column for this series' metric, COPIED VERBATIM>",
     metric, unit, label:"<the series' human label>", agg:"avg", source:"live",
     sampling:"<hourly|2hour|shift|day|week|month — the bucket width that suits the card's window>"}.
    ★ RULES: (1) `column` is ONE REAL basket column that measures the series' quantity — match the slot's own
    label/unit/section context to the DB SCHEMA (a voltage-history series → voltage_r/voltage_y/voltage_b/voltage_avg;
    a load-history series → active_power_total_kw). One `bucketed` field PER series leaf; a per-phase history binds
    each phase leaf to its own phase column (R→*_r, Y→*_y, B→*_b). (2) `sampling` sets the bucket width — match it to
    the card's natural window (today → hourly/2hour/shift; a week → day; a month → week). (3) when NO schema column
    measures the series' quantity (e.g. a computed readiness/health SCORE series that no meter records), emit NO
    bucketed field for that slot AT ALL (omit it — the leaf honest-blanks; say why in data_note,
    answerability=partial); NEVER emit a bucketed field with column=null. The date-window flows from the card's
    window/ems_backend range — the SAME `bucketed` field re-slices to the picked date automatically, so do NOT
    hardcode a date here. NEVER emit kind="array" or kind="series" as a field kind — the numeric-array series leaf's
    field kind is ALWAYS "bucketed".
  - time → a TIME-AXIS leaf: bucket timestamps / a chart's x-axis points / axis window bounds (sampleTimestamps,
    timeLabelTimestamps, `…points`, axisStartMs/axisEndMs). Emit EXACTLY {slot, kind:"time", role:"series",
    source:"live"} — NO column, NO metric, NO agg. The executor fills it with the SAME bucket timestamps (epoch ms)
    as this card's bucketed series, so the chart's points and x-axis always align; axisStartMs/axisEndMs fill the
    window's first/last bucket. kind="time" is the ONLY field that legitimately carries no column (the gate accepts
    it column-less) — NEVER bind a timestamp column (`ts`/`time`/`timestamp` are not basket columns) and NEVER use
    kind=raw or kind=bucketed for a time leaf.
  - derived → a COMPUTED/NAMEPLATE value recovered by the RECOVERY LIBRARY (see the block at the bottom). The AI does NOT write the formula — it NAMES a library `fn` and the executor computes it. Emit: {kind:"derived", fn:"<a value_key from the RECOVERY LIBRARY>", base_columns:[the REAL basket columns that fn needs], target_column:"<the payload/frame column the CMD V2 builder reads, e.g. current_neutral / phase_angle_deg / kpi_neutral_to_phase_ratio_pct>", scope:"row"}; agg=derived. RULES:
      · ★ RAW-BEATS-FN (check this FIRST, before you even consider an fn). A recovery fn is a LAST resort. If a COLUMN
        BASKET line measures the slot's quantity AND shows data=Y (it will carry the ★ REAL LOGGED COLUMN marker), bind
        it kind=raw by its EXACT column name and emit NO fn — EVEN IF its name_hint says "derived". name_hint is a
        spelling guess, NOT an order: current_max_spread, current_unbalance_pct, current_min/current_max are LOGGED
        columns → READ them raw. ★ target_column-bridge: if the frame column you would name as `target_column` is itself
        a data=Y basket column, that IS a raw bind — NEVER wrap a real logged column in an fn.
      · Reach for a `fn` ONLY when RAW-BEATS-FN found NO data=Y column for the slot's quantity. Then pick a fn where BOTH
        hold: (a) its `quantity=` tag (shown per fn in the RECOVERY LIBRARY block) EQUALS this slot's own quantity (from
        its label/unit), AND (b) ALL its `base_columns` are in the COLUMN BASKET above (this is what makes the recovery
        DB-correct). A fn whose `quantity=` differs is a WRONG-QUANTITY binding even if its name sounds close
        (neutralToPhaseRatioPct is quantity=neutral-to-phase-ratio-percent — WRONG on a current-unbalance slot). ★ The
        ONLY legal `fn` values are the value_keys enumerated VERBATIM in the RECOVERY LIBRARY — an fn you compose
        yourself (currentMaxSpread, maxSpread, currentSpreadPct, …) DOES NOT EXIST and silently blanks the leaf. If no
        library fn satisfies BOTH (a) and (b), honest-degrade — emit NO derived field for it (do NOT invent an fn or a
        formula, and do NOT reach for the closest-sounding fn).
      · `base_columns` must be the REAL basket columns (verbatim spelling/case) the chosen fn consumes; `target_column` is the FRAME column the card's own mapper fills (NOT the fn name).
      · scope:"row" means the executor runs per live row: the host merges {target_column: fn} across this endpoint's cards and the ems_backend fill_derived(row) hook runs registry.run(fn, {"row": row}) to fill any target_column the DB left None (a present real value always wins; honest-degrade None where run() also returns None).
      · THE FIVE PHYSICAL WALLS — emit NO derived field (the value honest-degrades, NEVER fabricated): (1) waveform shape (crest_factor / flicker_pst); (2) per-order harmonics (harmonic_5th/7th_pct, k_factor); (3) externally-assigned nameplate / commercial (kpi_kw_load_pct_of_rated, rated_kva, subsidy / contract figures) when its base_columns are absent OR its nameplate denominator is empty for THIS asset; (4) device run-state (breaker_state, *_trend_status); (5) TRANSFER / READINESS / SYNC / PERMISSIVE / BYPASS SCORES and TRANSFER COUNTS / DAYS-SINCE / LIFETIME — a UPS/DG transfer-readiness or activity quantity the meter does NOT log (there is NO fn that turns a load factor or an energy counter into a readiness score or a transfer count). There is NO library fn that fabricates any of these from unrelated columns — omit the field and honest-blank the leaf.
      · WORKED EXAMPLES:
          - neutral current slot → {"kind":"derived","fn":"neutralCurrent","base_columns":["current_r","current_y","current_b"],"target_column":"current_neutral","agg":"derived","scope":"row"}
          - PF angle slot → {"kind":"derived","fn":"pfAngleDeg","base_columns":["power_factor_total"],"target_column":"phase_angle_deg","agg":"derived","scope":"row"}
  - event → `column` is the boolean *_event_active flag; agg=count; edge='rising'.
  - const → a baked literal (threshold/limit line / status placeholder): set `kind`="const" + `value` + source='const' (or omit source); NEVER a column. A UNIVERSAL standard (the IEEE_519 THD limit) is a true literal. ★ A `const` field MUST carry a non-null `value` — a valueless `kind="const"` field is a MALFORMED literal the gate rejects.
  - const ≠ MEASURED: NEVER stamp kind="const" on a MEASURED leaf you also mark source='live' (a legend's latest-value KPI, a series point) — that is a MEASURED binding, not a literal: use kind="raw" (a scalar latest value bound to its real column) or kind="bucketed" (a numeric-array series).
  - const ≠ HONEST-BLANK: when the leaf's quantity has NO basket column (e.g. a THERMAL hotspot/oil/winding temperature on an electrical meter), emit NO field for that leaf AT ALL (omit it — the ONE honest-blank convention: the skeleton preserves the key, the leaf renders blank with a per-leaf reason; say why in data_note, answerability="partial"). NEVER emit a raw/bucketed field with column=null; a mislabelled const is NEVER how you honest-blank a leaf.
  - const RATINGS + ★ CONST-SOURCE RULE (the gate BLANKS a numeric const that breaks it): a PER-ASSET rating/contract (rated kW/kVA, contracted/sanctioned capacity, a supply `denominator`) is NOT a literal — the default payload's number there is a Storybook seed for a demo plant, and copying it fabricates a capacity. Emit the const WITH `metric` naming the rating (contracted_capacity_kw / rated_kw / rated_kva / rated_current_a): the executor then substitutes the asset's REAL nameplate value or honest-blanks the leaf; the baked `value` is only a shape placeholder, never shown as truth. A NUMERIC const in a data slot ships ONLY when it cites a REAL DB source in the field itself — EITHER (a) a nameplate rating: `metric` is one of the rating names above (a home-made spelling like I_RATED / I_MAX / deratedKva does NOT resolve to the nameplate and is blanked — name the rating properly), OR (b) a site-approved app_config `consts.<name>` row: `metric` names the row (e.g. stress_border_pct, hotspot_warn_c) and `value` IS that row's value. Any other invented numeric literal (a guessed rated current 131, a derated 1000 kVA, made-up thresholds/axis ticks) is blanked by the gate — when no real source exists, OMIT the field and honest-blank the leaf.
  - text → a label/narrative column; bind the real column or mark source per controls.
  ★ EMPTY DB SCHEMA — if the DB SCHEMA block above is EMPTY (the asset logs NO metric columns at all), emit fields: []
    with answerability="none" and a data_note saying what isn't measured — do NOT invent columns and do NOT guess. This
    emission is LEGITIMATE and passes the gate: the card renders its metadata frame with every leaf honest-blank, and
    the "none" drives the orchestrator's re-route.
  ★ NEVER A SILENT ZERO-SKELETON — an emission whose exact_metadata is the bare skeleton with NOTHING bound (fields []
    and no roster) and NO honest reason is a DEFECT: the skeleton's 0/[] placeholders would render as if they were real
    values (a false "0 issues" story). Whenever you bind nothing, you MUST declare answerability "none" (or "partial")
    AND a data_note naming exactly WHY nothing could be bound (which quantities are unmeasured / what the card needed).
    The gate treats a fully-unbound conforming emit as honest_blank telemetry — every data leaf gets a per-leaf reason
    and the card never claims "full" — but the AI-authored reason is always better than the generated one: write it.
  ★ COVERAGE RULE (countable): every slot in the "FILLABLE DATA-LEAF SLOTS" block must be either (a) bound by EXACTLY
    ONE field, or (b) deliberately left out because nothing real measures/computes it — and then data_note must say
    why. An unexplained uncovered slot is recorded as a per-leaf gap ('no binding emitted'); NEVER silently ignore a
    listed slot, and NEVER pad coverage with invented columns/fns.
  ★ TIME-BUCKETED SERIES ([*] slots): a slot shown as `<path>[*].<key>` (marked TIME-BUCKETED SERIES) is ONE series
    whose elements are TIME BUCKETS, not distinct entities. Emit EXACTLY ONE {kind:"bucketed"} field per such [*] slot
    (slot copied VERBATIM including the [*]; one real column; sampling to suit the card's window) — the executor
    distributes the ordered buckets across the elements itself. NEVER expand it into per-element fields, NEVER emit the
    element's time-label key (that label is chrome the executor maintains), NEVER emit const fields carrying the bucket
    labels as data.
  COMMON DEFECTS — the gate REJECTS these, so NEVER emit them (the whole card is then unrenderable — there is NO default fallback):
  - EMPTY fields[] on a data card. Every DATA leaf in the metadata skeleton (shown stripped to its typed placeholder — 0 / []) needs EXACTLY ONE field. If the card shows any data, fields[] is non-empty. (EXCEPTIONS: a card the user message flags as "★ NO-FIELDS CARD" — pure UI chrome / a special renderer — legitimately emits fields: [] and no ems_backend block, its exact_metadata IS the render; and the ★ EMPTY DB SCHEMA case above — fields: [] + answerability="none" + data_note.)
  - A HALLUCINATED column — for a `live`/`test-db` field, `column` MUST be a basket column verbatim. Never invent one (`timestamp`, `time`, `efficiencyPct`, `thd`, …), and never bind a METRIC NAME (`kw`, `pf`, `kva`) as a column unless that exact string IS a basket column.
  - NO-COLUMN SLOT = HONEST-BLANK, NEVER A PROXY (the #1 rule of this seam). When a data slot's OWN quantity has NO
    backing column in the COLUMN BASKET (a UPS `transfer/permissive/sync/bypass readiness SCORE`, a `transfers count /
    days-since / lifetime`, a run-state, a readiness index — the meter logs power/energy/voltage/PF/current but NOT that
    quantity), the ONLY honest emission is to OMIT the field — the leaf renders blank with a per-leaf reason and
    data_note says why (answerability="partial"). You MUST NOT fill such a slot with: (a) a PROXY fn/column of a
    DIFFERENT quantity (binding `loadFactorPct` over `active_power_total_kw` into a "transfer readiness score", or
    `activeEnergyTodayKwh` over `active_energy_import_kwh` into a "transfers count / days-since" slot — that shows a load
    factor / an energy total dressed as a readiness score or a transfer count); (b) a CONSTANT stand-in; (c) a value
    REUSED from another slot. A slot's own label/key names its quantity; when nothing in the basket measures THAT
    quantity, the answer is a blank, not a re-labelled number.
  - QUANTITY WALL (deterministically enforced — the gate BLANKS any field that crosses it). Every DB SCHEMA line shows
    the column's `qty=` and every slot line shows its `expected_qty=`: a column of ONE physical quantity NEVER fills a
    slot of ANOTHER. Concretely: power/energy is NOT a temperature (hotspotC/oilC/windingC), NOT an aging factor (faa),
    NOT a readiness/score, NOT a count (tapCount/transfers), NOT a duration (runHours/backup minutes), NOT a lifetime
    (lifeYears); a deviation/spread column (kpi_voltage_deviation_pct / current_max_spread) is NEVER re-purposed as
    crest-factor or flicker (flickerPst); a thd_current_* column is NEVER a voltage-harmonic (h5/h7) or voltage-THD
    value (sharing '%' does not make them the same quantity). If the meter has NO column of the slot's quantity, that
    slot is HONEST-BLANK: OMIT the field, name the missing quantity in data_note ("hotspot temperature is not measured
    by this meter"), answerability="partial". A cross-quantity bind never survives — it is blanked with reason
    "<quantity> not measured by this meter (no <quantity> column)".
  - SEMANTIC-FAMILY WALL (the same-DIMENSION pun — deterministically enforced, the gate BLANKS it): a slot whose
    label / metric / key names efficiency / SFC / specific consumption / fuel binds ONLY an fn/column of that SAME
    semantic family — sharing '%' (or any dimension) does not make a load factor an efficiency. Binding
    `loadFactorPct` into an 'Efficiency' KPI rendered "Efficiency 5.3 %" (a load factor dressed as an efficiency).
    When the basket has NO same-family fn/column (a DG with no fuel-flow measurement cannot measure efficiency or
    SFC), OMIT the field (honest-blank), name the missing family in data_note, answerability="partial".
  - ONE fn/column ACROSS DISTINCT SCALAR SLOTS (the readiness/activity/capacity defect) — NEVER bind the SAME derived
    `fn` (or the SAME raw `column`) into ≥2 DISTINCT scalar VALUE slots that name DIFFERENT quantities. A card with three
    "score" cells (`ups_input_permissive_score` / `ups_bypass_permissive_score` / `ups_sync_permissive_score`) or three
    "activity" cells (`days-since` / `count-30d` / `lifetime`) needs a DIFFERENT real measurement per cell; the meter has
    ONE load-factor / ONE energy counter, so copying that one number into all three FABRICATES three distinct scores /
    counts from one figure (they all render the SAME value, e.g. 96.3). Bind each scalar slot ONLY to the real column/fn
    that measures ITS quantity; the ones with no such column are OMITTED (honest-blank), not padded with the reused
    value. (Legitimate: a SERIES and its own `legend`/`kpi`/`axis-min/max` summary share the series' column — that is one
    quantity, not distinct slots. The rule targets ≥2 DISTINCT-quantity SCALAR cells co-bound to one fn/column with NO
    co-bound series.)
  - EMPTY-NAMEPLATE DENOMINATOR — a derived fn whose base_columns include a `nameplate:<rating>` denominator
    (`kpiKwLoadPctOfRated` over `nameplate:rated_kva`, …) is only bindable when the asset's rating is ACTUALLY populated.
    When the asset's nameplate rating is empty/unknown, that fn divides by an empty denominator — OMIT the field
    (honest-blank the leaf), never emit it hoping a rating appears. An empty rating is NEVER used as a denominator.
  - SIBLING-SLICE PROXY — NEVER bind ONE column into several SIBLING slices of the same roster that carry DIFFERENT
    entity labels (breakdown[0..2].value labelled "UPS"/"BPDB"/"HHF" all ← active_power_total_kw; every
    sections[i].totalKw at the same instant ← the one panel total). Each labelled slice claims a DIFFERENT sub-group's
    number — duplicating the total renders the same value N times and the groups sum to N× the panel (a fabricated
    split). This INCLUDES a flow/sankey card's `nodes[i].value` and `links[i].value` and a roster's
    `sources/consumers[i].meters[j]` slots: every node / link / meter claims a DIFFERENT entity's flow, so binding ONE
    panel-total column into all of them fabricates N equal ribbons (the 'every ribbon = 550,320 kWh' defect). When the
    basket has NO per-group column, bind the TOTAL slot only, leave the slices column=null
    (honest-blank), set answerability="partial" and say so in data_note — on a PANEL asset (see the PANEL MEMBERS block
    when present) the panel-aggregate renderer then fills each per-member leaf from that member meter's OWN row, so an
    honest-blank per-entity slot still renders real per-member truth. (Distinct: the SAME column across TIME samples
    of one series is legitimate.)
  - PHASE-AS-GROUP PROXY — the sibling-slice rule's evasion: binding the per-PHASE columns one-each into sibling slices
    whose labels name entity GROUPS (breakdown[0..2].value labelled "UPS Feeders"/"BPDB"/"HHF Reactive" ←
    active_power_r_kw / active_power_y_kw / active_power_b_kw). A PHASE (R/Y/B/N) is NOT a feeder group / member set /
    section — those numbers are a fabricated split exactly like the duplicated total. A per-phase (*_r/*_y/*_b/*_neutral)
    column fills ONLY a phase-labelled leaf. When the basket has NO per-group column, bind the TOTAL slot only and leave
    the group slices column=null (honest-blank) + answerability="partial" + data_note, same as SIBLING-SLICE PROXY.
  - KPI-QUANTITY MISMATCH — when a scalar KPI slot shows "(no label/unit in payload — use the slot path itself)", the
    slot KEY ITSELF names its quantity and unit: `…Kw` → kW, `…Kwh` → kWh, `…Pct` / `…efficiency…` / `…loss…` / a ratio
    → a COMPUTED percent/figure. A percent / efficiency / loss / ratio KPI is NEVER kind=raw on a measured column of
    another quantity — binding the panel's `active_energy_import_kwh` counter into `lossPct`/`efficiencyPct` rendered
    "Efficiency 550320 %" (a 30-day kWh delta shown as a percent). For such a slot emit kind=derived with a RECOVERY
    LIBRARY fn whose base_columns are ALL in the basket, else emit NO field (honest-blank). SIBLING KPI slots with
    DIFFERENT keys (lossKw / lossPct / efficiencyPct / sourceInputKw / feederOutputKw) are DIFFERENT quantities — never
    bind them all to one column.
  - UNIT MISMATCH — the bound column's physical quantity MUST match the slot's own unit/label context shown in the
    FILLABLE DATA-LEAF SLOTS block. A slot displaying `A` (amps) NEVER takes power_factor_total (dimensionless); a `V`
    slot never takes a kW column. Re-declaring `unit` in the field does NOT change what the card displays — the leaf
    keeps its designed unit, so a mismatched column renders a wrong number as that unit. No matching column →
    column=null (honest-blank), never a different quantity. The ONLY sanctioned substitution is the DECLARED
    SAME-QUANTITY-FAMILY PROXY — THE ONE CANONICAL PROXY RULE stated in PART 2's "ONE EXCEPTION" (defer to it; it is
    not restated here): same family (column `qty=` EQUALS slot `expected_qty=`) → bind + declare in `data_note` +
    morph the describing caption/unit leaves (list in `_morphed`); different family → OMIT the field, no data_note
    legitimizes it, the gate blanks it regardless. A proxy value shown under the default caption is a WRONG reading —
    the gate treats an undeclared or unmorphed proxy as a UNIT MISMATCH defect.
  - WRONG RESIDENCE on a GROUP atom — on a $ctx group card EVERY data field is source='$ctx' (it reads the shared buffer by metric key; the column need not be a basket column). Do NOT set source='live' on a group atom — that triggers the basket check and the metric key (kw/pf/kva) is flagged hallucinated. ★ $ctx IS NOT A WALL BYPASS: the QUANTITY WALL, the one-fn/column-across-distinct-scalars rule and the CONST-SOURCE rule apply to $ctx fields IDENTICALLY — a $ctx field binding a power key into a temperature/years/aging/readiness/score slot, smearing one key across distinct-quantity cells, or shipping a sourceless numeric const is blanked by the gate exactly like a live bind. Only a structural $ctx atom with no quantity on either side (a time atom, a group-context projection) is exempt by construction.
  - The TIME / X-AXIS: never bind a timestamp COLUMN (there is no `ts` basket column). A time-axis slot in the
    "FILLABLE DATA-LEAF SLOTS" list (sampleTimestamps / timeLabelTimestamps / a chart's `…points` x-axis /
    axisStartMs / axisEndMs) gets EXACTLY {slot, kind:"time", role:"series", source:"live"} — NO column, NO metric
    (see the `time` kind rule above; the gate accepts a time field column-less). Any other time-ish leaf NOT on the
    slot list stays undeclared.
  - A computed metric bound as a raw column (the 'efficiencyPct hallucinated column' defect) → use kind=derived with base_columns instead.
  - `source` is `live` | `test-db` | `$ctx` | `const` — the gate's closed set, nothing else. `const` is legal ONLY on a kind=const literal (or omit source there); a measured field is live/test-db/$ctx. 'derived' is a KIND, never a source; no other source token exists.
- DO NOT put metadata in data_instructions — statusColors/bandThresholds/metricTabs/IEEE limit THRESHOLD VALUES that are chrome belong in exact_metadata, not here. (A const LIMIT LINE the chart PLOTS is a data field; the threshold colour/legend is metadata.)

DATA-RESIDENCE — set `$ctx` (told to you as is_group_card). There is NO emit_mode/atom-vs-frame branch: the SAME output shape carries EVERY card; `$ctx` only selects where the DATA lives, and exact_metadata is authored in full EITHER way.
- GROUP card → set `$ctx` to the page's shared_context.$id and emit a LEAN ATOM: data_instructions holds NO baked data — its per-field `source` points at the shared buffer (the $ctx buffer reference) and each field carries `selection_role`. The atom STILL carries its OWN FULL exact_metadata block AND its own data_instructions.fields[] (so the helper knows which slots of the shared buffer to project). Interaction seeds you reference must exist in shared_context.interaction. FUNCTIONS NEVER travel.
- STANDALONE card → leave `$ctx` null; data_instructions per-field source is live/test-db and binds to the resolved asset/table; the helper fills the DATA tier from the live ws/mfm frame OR the test-DB fixture in the identical Snapshot shape. ★ On a STANDALONE card (is_group_card=false) EVERY raw/event field MUST set source='live' and name a REAL basket column — NEVER source='$ctx' (there is no shared buffer to read; a $ctx field on a standalone card is REJECTED by the gate and blanks the leaf). The "FILLABLE DATA-LEAF SLOTS" list gives the exact leaf + its real column — use it.

BEST-EFFORT + ANSWERABILITY (graceful degradation — real column or recovery fn, NEVER fabricate):
- SCOPE: this applies ONLY to a STANDALONE card's live/test-db fields. A GROUP atom ($ctx) NEVER binds or substitutes a basket column — its fields STAY source='$ctx' by metric key (the shared buffer holds the data); a group atom's answerability is "full" unless the shared buffer itself lacks the metric. Do NOT bind a real column (e.g. a busbar/temperature column) on a $ctx field to "best-effort" — that breaks the group contract.
- For a STANDALONE/live field, IN ORDER: (1) bind the EXACT basket column for its metric; (2) else if a RECOVERY LIBRARY fn computes the asked-for quantity from columns ALL in the basket, use kind=derived + that fn (the recovery path — NOT a substitute); (3) else bind the highest-confidence SUBSTITUTE per THE CANONICAL SAME-QUANTITY-FAMILY PROXY RULE (PART 2's "ONE EXCEPTION" — the one statement of it): ONLY a column that measures the slot's SAME physical-quantity family (a coarser aggregate or adjacent form of the SAME measure: 'per-phase power' absent → total power ✓; 'today kWh' absent → this-week kWh ✓), reported in data_note WITH the describing caption/window leaves morphed (listed in `_morphed`). A substitute is a REAL column (kind=raw/derived) — NEVER a valueless `const`.
  ★ SAME-QUANTITY WALL (the leaf's SEMANTIC, not just its unit): a column of a DIFFERENT physical quantity that merely SHARES THE UNIT is NOT a valid substitute — DO NOT bind it. A voltage-THD leaf (label 'voltage thd', unit %) whose `thd_voltage_*` column is null does NOT take a live `thd_current_*` (also %); a state-of-charge % does NOT take a load %; a `years`/lifetime or `°C` leaf does NOT take an energy/kWh column or fn (that is how "10,156 years" happens). When NO same-quantity column AND no same-quantity recovery fn exists, emit NO field for that leaf — HONEST-BLANK it, set answerability="partial" with a data_note. NEVER render a wrong-quantity number under the slot's label, and NEVER mark such a leaf "full". Match the slot's `label` (voltage vs current, energy vs years) — not just the unit sign.
  ★ SAME-QUANTITY, DIFFERENT-ROLE WALL (the SOURCE-ROLE trap — same quantity is NOT enough): a slot that names a DEDICATED SENSING POINT — a UPS `bypass` voltage/frequency, an `output`/load reading, a `battery`/DC reading — needs a column MEASURED AT THAT POINT. This meter senses only the INPUT/line: `voltage_avg` / `frequency_hz` ARE the input reading, NOT the bypass. Binding `voltage_avg` into BOTH `inputVoltageV` AND `bypassVoltageV` presents the SAME line reading twice, once fabricated as a bypass reading the meter cannot see (the card's own data_note even says bypass "is not measured by this meter"). Bind `input*` slots to the plain reading; OMIT every `bypass*`/`output*`/`battery*` slot with no dedicated column — HONEST-BLANK it, name the missing sensor in data_note. Same unit AND same quantity do NOT license a role smear.
  ★ TIME-AXIS LABEL IS ALWAYS kind=time: a series time-label leaf (`points[*].label` / `points[*].slot` — the x-axis tick text) is filled from the card's OWN bucket timestamps. Emit it as {slot, kind:"time", role:"series", source:"live"} with NO column and NO metric. NEVER bind a measured column there (a raw `active_power_total_kw` into `points[*].label` renders negative kW AS the time-axis labels) — such a bind is gate-blanked.
- Set `answerability`:
    · "full"    — every field bound to the EXACT asked-for column.
    · "partial" — the card STILL answers its story, but ≥1 field uses a substitute (or a non-core slot is absent). exact_metadata is intact and the card RENDERS with real (approximate) data. This does NOT trigger a re-route.
    · "none"    — the card's CORE question cannot be answered by ANY real column (no exact AND no meaningful substitute), so it would have to be dropped. This SIGNALS the orchestrator to re-route the template — do not force a fill.
- `data_note` — ONE plain, user-facing sentence saying WHAT you showed and WHY, WHENEVER answerability is partial or none (e.g. "Showing total active power — per-phase power isn't measured for this asset." / "No harmonic/THD data is recorded for this meter."). null when answerability="full". This note is saved and shown to the user, so write it for a human.
- conforms is SEPARATE (byte-conformance of exact_metadata + valid bindings): a "partial" card with a substitute column still conforms=true. Set conforms=false + `failure{stage,reason,detail}` ONLY for a genuine emit error (no bindable column at all / unwired component) — which is also answerability="none".
- NEVER fabricate a column, a number, a metadata key, or a frame field to force "full". A substitute is a REAL column; a true gap is reported honestly as "none".

CONFIG TIER IS UNCHANGED — names / titles / UNITS (kWh / % / V / A) / labels / colors / legends stay LITERALS in exact_metadata, which you ALREADY author. NEVER route a name, title, unit, label, color, or legend through a `fn` — only a COMPUTED/NAMEPLATE VALUE uses kind=derived + fn; chrome is always a literal in exact_metadata.

<!--ROSTER:BEGIN-->
## ROSTER (member-scope) slots — panel_aggregate / topology_sld cards ONLY (this section is shown ONLY when this card is member-scope)
Some cards render ONE ELEMENT PER PANEL MEMBER (feeder rosters, SLD nodes, heatmap cells, sankey
values). For those cards your context contains a verbatim `roster_spec` — the card's fixed recipe.
Emit `data_instructions.roster` (a TOP-LEVEL key beside fields[]): one entry per recipe slot, copying `slot` EXACTLY.
- You may ONLY change the COLUMN inside a `col`/`delta`/`phase_mean`/`prefer_abs` binding, and only
  to a column present in the DB SCHEMA block. Everything else (slot paths, element keys, role_filter,
  group_by, reducers, floors, caps, order) is FIXED by the recipe — repeat it or omit it (omitted
  parts are backfilled from the recipe).
- A recipe binding of {"b":"null"} is an HONEST-NULL key (the dataset has no such column). NEVER
  bind a column to it. NEVER invent element keys. NEVER emit roster for a card whose context has
  no roster_spec.
- A panel-aggregate / member card with NO roster_spec still fills ONE element per member — but its
  per-member DATA rides its backend_strategy consumer's panel fan-out, NOT fields[] and NOT a roster.
  For such a card emit `data_instructions.fields: []` (an EMPTY list — LEGITIMATE, it passes the gate)
  and do NOT emit a roster (a roster with no roster_spec is rejected); a member with no data honest-
  blanks per-leaf. Do NOT invent per-member fields/values to "fill" it — that fabricates.
- The executor iterates the panel's members itself (supply = role=='incoming', load = everything
  else). You never enumerate members, tables, or per-member values.
Shorthand: an element value may be a bare column name — it means {"b":"col","c":"<column>"}.
Each roster entry: {"slot": "<recipe slot verbatim>", "scope": "members", "element": {<element key>: <binding|bare column>, …}}
(+ optionally role_filter/group_by/order/cap/agg repeated verbatim from the recipe).
<!--ROSTER:END-->

RECOVERY LIBRARY (reference a fn by its EXACT value_key; its `quantity=` must EQUAL the slot's quantity AND its
base_columns must all be in the basket — generated LIVE from the executor's own derivation registry, so every fn listed
here is exactly what the executor can compute; a fn NOT listed does not exist: naming it degrades that leaf to an honest
blank with a 'derivation unbound' reason, never a computed value. RAW-BEATS-FN first: if the slot's quantity is a data=Y
basket column, read it kind:raw — do NOT reach into this library at all)
```
{{RECOVERY_LIBRARY}}
```
Pick the fn whose base_columns are ALL in this asset's basket; if none qualifies (or the slot is one of the FIVE WALLS), emit NO derived field for that slot (honest-degrade — never fabricate).

Output STRICT valid JSON only matching the Layer2CardOutput schema. Escape inner quotes; no literal newlines in strings. Emit exactly:
{"card_id":0,"$ctx":null,"render_slot":"","analytical_story":"","swap_decision":{"action":"keep","origin":"kept","swap_to_id":null,"swap_to_title":null,"confidence":0.0,"criterion":null,"reason":null,"cascade":[]},"exact_metadata":{"_morphed":[]},"data_instructions":{"payload_shape":"","orientation":"","entity_dim":"","selection_dim":null,"selection_role":null,"binding":null,"window":null,"ems_backend":{"endpoint":"","window_seconds":30,"interval_seconds":2,"sample_count":12,"range":null,"start":null,"end":null,"sampling":null,"metrics":[],"selection":null},"fields":[]},"controls":null,"answerability":"full","data_note":null,"conforms":true,"failure":null}
