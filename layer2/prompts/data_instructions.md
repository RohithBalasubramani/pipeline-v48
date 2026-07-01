== data_instructions (the parseable DATA-fill RECIPE — the helper fills the DATA from it) ==
Emit a recipe the helper parses to FILL the DATA tier — NOT data, NOT SQL, NOT numbers. It is a RESOLVED recipe: one resolved field per data slot, plus the per-card fill envelope. Bind every field to a REAL column from the COLUMN BASKET by the field's `metric` — never bind every tile to the same column (the 'every tile = active_power' bug). Shape:
- payload_shape — which DATA tier to fill (the card's payload_shape).
- orientation — time | entity | snapshot (the row shape).
- entity_dim / selection_dim — what each row/series IS and what selection drives it.
- selection_role — the card's interdependency role (both|produces|consumes|emits|none) — provisional.
- binding — { asset_id, table, ts_col, panel_id, nameplate_scope } (from 1b's resolved asset). Null for a pure-$ctx group atom (DATA from the shared buffer) or a pure-const card. (There is NO top-level `source` on data_instructions — fill source is PER-FIELD `fields[].source`; do NOT hardcode 'mock'.)
- window — { lookback, sampling, time_mode } from the card controls (re-slice = re-bind only).
- ems_backend — ★ the fetch spec that DRIVES the live backend. The helper opens `ws/mfm/<asset mfm_id>/<endpoint>/`; the consumer returns the card's DATA (incl. the history time-series); the frontend feeds that frame to the CMD V2 card's OWN mapper. YOU set the prompt-driven knobs so it returns the APPROPRIATE data:
    { endpoint, window_seconds, interval_seconds, sample_count, range, start, end, sampling, metrics, selection }
  - endpoint — the consumer screen. Pick EXACTLY ONE from this card's `ems_backend ENDPOINT` hint above (the live set + retired blocklist are listed there, derived from ems_backend — that is the authority, not this prose). Match it to the card's nature:
      · REAL-TIME card (live rolling values / scrubber / now-snapshot) → the card's LIVE screen, driven by window_seconds/interval_seconds.
      · TREND / PROFILE / HISTORY card (values should CHANGE WHEN THE USER PICKS A DATE) → one of the card's DATE-CAPABLE history variants, driven by range/start/end/sampling — this is what makes the card date-navigable. If the hint lists NO history variant, the card's live screen already serves history via range/sampling (e.g. `power-quality-summary`).
      · NEVER invent an endpoint or use a legacy name that is not in the hint's live set — anything outside it DOES NOT EXIST (it lands on the catch-all and returns no data).
  - LIVE knobs (real-time endpoints): window_seconds (rolling reach, e.g. 30), interval_seconds (cadence, e.g. 2), sample_count (depth, e.g. 12). Set range/start/end/sampling = null.
  - DATE-WINDOW knobs (history endpoints — THE DATE NAVIGATION SEAM): range = today | yesterday | last-7-days | this-month | custom-range (the DEFAULT window; the frontend OVERRIDES it when the user changes the date). start/end = ISO or bare YYYY-MM-DD, ONLY when range=custom-range. sampling = hourly | 2hour | shift | day | week (bucket width must suit the range: today→hourly/2hour/shift; week→day; month→week). Set window_seconds/interval_seconds/sample_count = null.
  - metrics — which measured quantities this card's history needs (kw, kvar, pf, voltage, current, iUnbalance, …). Ground in the card + the prompt metric.
  - selection — the initial selected entity/section/bucket (or null).
  Leave a knob at its control default unless the prompt narrows it; null the OTHER family's knobs. This block is HOW ems_backend fills the DATA — author it so the history time-series + numbers come back correct AND the card responds to date changes.
- fields[] — one resolved field per data slot, each:
    { slot, kind(raw|derived|const|text|event), role(series|kpi|column|line|cell|tile|row|spoke),
      metric, column, label, unit, agg(avg|last|sum|count|derived), source(live|test-db|const|$ctx),
      value?(const only), base_columns?/sql_fragment?/nameplate_refs?(derived only), edge?(event only),
      filters_table, has_data }
  Rules per kind (NOTE: `kind` is WHAT the field is; `source` is WHERE its data lives — set source by DATA-RESIDENCE below, NOT by kind):
  - raw → bind `column` to a real basket column for this field's metric, COPIED VERBATIM (exact spelling/case); agg avg/last/sum.
  - derived → a COMPUTED/NAMEPLATE value recovered by the RECOVERY LIBRARY (see the block at the bottom). The AI does NOT write the formula — it NAMES a library `fn` and the executor computes it. Emit: {kind:"derived", fn:"<a value_key from the RECOVERY LIBRARY>", base_columns:[the REAL basket columns that fn needs], target_column:"<the payload/frame column the CMD V2 builder reads, e.g. current_neutral / phase_angle_deg / kpi_neutral_to_phase_ratio_pct>", scope:"row"}; agg=derived. RULES:
      · PICK a `fn` whose `base_columns` are ALL present in THIS asset's COLUMN BASKET above — that is what makes the recovery DB-correct (compat vs lt_panels). If no library fn's base_columns are fully in the basket, this slot honest-degrades — emit NO derived field for it (do NOT invent an fn or a formula).
      · `base_columns` must be the REAL basket columns (verbatim spelling/case) the chosen fn consumes; `target_column` is the FRAME column the card's own mapper fills (NOT the fn name).
      · scope:"row" means the executor runs per live row: the host merges {target_column: fn} across this endpoint's cards and the ems_backend fill_derived(row) hook runs registry.run(fn, {"row": row}) to fill any target_column the DB left None (a present real value always wins; honest-degrade None where run() also returns None).
      · THE FOUR PHYSICAL WALLS — emit NO derived field (the value honest-degrades, NEVER fabricated): (1) waveform shape (crest_factor / flicker_pst); (2) per-order harmonics (harmonic_5th/7th_pct, k_factor); (3) externally-assigned nameplate / commercial (kpi_kw_load_pct_of_rated, rated_kva, subsidy / contract figures) when its base_columns are absent; (4) device run-state (breaker_state, *_trend_status). There is NO library fn that fabricates these from unrelated columns.
      · WORKED EXAMPLES:
          - neutral current slot → {"kind":"derived","fn":"neutralCurrent","base_columns":["current_r","current_y","current_b"],"target_column":"current_neutral","agg":"derived","scope":"row"}
          - PF angle slot → {"kind":"derived","fn":"pfAngleDeg","base_columns":["power_factor_total"],"target_column":"phase_angle_deg","agg":"derived","scope":"row"}
  - event → `column` is the boolean *_event_active flag; agg=count; edge='rising'.
  - const → a baked literal (threshold/limit line / status placeholder): set `kind`="const" + `value`; NEVER a column, NEVER a source ('const' is a kind, not a source). (IEEE_519 limit, rated/contracted lines, etc.)
  - text → a label/narrative column; bind the real column or mark source per controls.
  COMMON DEFECTS — the gate REJECTS these, so NEVER emit them (the whole card is then unrenderable — there is NO default fallback):
  - EMPTY fields[] on a data card. Every `$DATA` leaf in the metadata skeleton needs EXACTLY ONE field. If the card shows any data, fields[] is non-empty.
  - A HALLUCINATED column — for a `live`/`test-db` field, `column` MUST be a basket column verbatim. Never invent one (`timestamp`, `time`, `efficiencyPct`, `thd`, …), and never bind a METRIC NAME (`kw`, `pf`, `kva`) as a column unless that exact string IS a basket column.
  - WRONG RESIDENCE on a GROUP atom — on a $ctx group card EVERY data field is source='$ctx' (it reads the shared buffer by metric key; the column need not be a basket column). Do NOT set source='live' on a group atom — that triggers the basket check and the metric key (kw/pf/kva) is flagged hallucinated.
  - The TIME / X-AXIS is NOT a data field — it comes from `binding.ts_col`. Never emit a field whose column is the timestamp/time/x-axis.
  - A computed metric bound as a raw column (the 'efficiencyPct hallucinated column' defect) → use kind=derived with base_columns instead.
  - `source` is `live` | `test-db` | `$ctx` ONLY. 'const' / 'mock' / 'derived' are NOT sources.
- DO NOT put metadata in data_instructions — statusColors/bandThresholds/metricTabs/IEEE limit THRESHOLD VALUES that are chrome belong in exact_metadata, not here. (A const LIMIT LINE the chart PLOTS is a data field; the threshold colour/legend is metadata.)

DATA-RESIDENCE — set `$ctx` (told to you as is_group_card). There is NO emit_mode/atom-vs-frame branch: the SAME output shape carries EVERY card; `$ctx` only selects where the DATA lives, and exact_metadata is authored in full EITHER way.
- GROUP card → set `$ctx` to the page's shared_context.$id and emit a LEAN ATOM: data_instructions holds NO baked data — its per-field `source` points at the shared buffer (the $ctx buffer reference) and each field carries `selection_role`. The atom STILL carries its OWN FULL exact_metadata block AND its own data_instructions.fields[] (so the helper knows which slots of the shared buffer to project). Interaction seeds you reference must exist in shared_context.interaction. FUNCTIONS NEVER travel.
- STANDALONE card → leave `$ctx` null; data_instructions per-field source is live/test-db and binds to the resolved asset/table; the helper fills the DATA tier from the live ws/mfm frame OR the test-DB fixture in the identical Snapshot shape.

BEST-EFFORT + ANSWERABILITY (graceful degradation — real column or recovery fn, NEVER fabricate):
- SCOPE: this applies ONLY to a STANDALONE card's live/test-db fields. A GROUP atom ($ctx) NEVER binds or substitutes a basket column — its fields STAY source='$ctx' by metric key (the shared buffer holds the data); a group atom's answerability is "full" unless the shared buffer itself lacks the metric. Do NOT bind a real column (e.g. a busbar/temperature column) on a $ctx field to "best-effort" — that breaks the group contract.
- For a STANDALONE/live field, IN ORDER: (1) bind the EXACT basket column for its metric; (2) else if a RECOVERY LIBRARY fn computes the asked-for quantity from columns ALL in the basket, use kind=derived + that fn (the recovery path — NOT a substitute); (3) else bind the highest-confidence SUBSTITUTE basket column from RELEVANT COLUMNS (e.g. 'per-phase power' absent → total power) and report it in data_note. A substitute is a REAL column (kind=raw/derived) — NEVER a valueless `const` (a const ALWAYS carries a non-null `value`; it is a baked literal, not a degradation placeholder).
- Set `answerability`:
    · "full"    — every field bound to the EXACT asked-for column.
    · "partial" — the card STILL answers its story, but ≥1 field uses a substitute (or a non-core slot is absent). exact_metadata is intact and the card RENDERS with real (approximate) data. This does NOT trigger a re-route.
    · "none"    — the card's CORE question cannot be answered by ANY real column (no exact AND no meaningful substitute), so it would have to be dropped. This SIGNALS the orchestrator to re-route the template — do not force a fill.
- `data_note` — ONE plain, user-facing sentence saying WHAT you showed and WHY, WHENEVER answerability is partial or none (e.g. "Showing total active power — per-phase power isn't measured for this asset." / "No harmonic/THD data is recorded for this meter."). null when answerability="full". This note is saved and shown to the user, so write it for a human.
- conforms is SEPARATE (byte-conformance of exact_metadata + valid bindings): a "partial" card with a substitute column still conforms=true. Set conforms=false + `failure{stage,reason,detail}` ONLY for a genuine emit error (no bindable column at all / unwired component) — which is also answerability="none".
- NEVER fabricate a column, a number, a metadata key, or a frame field to force "full". A substitute is a REAL column; a true gap is reported honestly as "none".

CONFIG TIER IS UNCHANGED — names / titles / UNITS (kWh / % / V / A) / labels / colors / legends stay LITERALS in exact_metadata, which you ALREADY author. NEVER route a name, title, unit, label, color, or legend through a `fn` — only a COMPUTED/NAMEPLATE VALUE uses kind=derived + fn; chrome is always a literal in exact_metadata.

RECOVERY LIBRARY (reference a fn by name; base_columns must be in the basket)
```
nominalVoltageLN | base_columns=[voltage_avg,kpi_voltage_deviation_pct] | fidelity=real_exact
voltageStatutoryBand | base_columns=[voltage_avg,kpi_voltage_deviation_pct] | fidelity=real_exact
voltageHistoryDomain | base_columns=[voltage_avg,voltage_r_n,voltage_y_n,voltage_b_n] | fidelity=real_exact
windowEnergyKwh | base_columns=[active_energy_import_kwh] | fidelity=real_exact
todaysEnergyTotalKwh | base_columns=[active_energy_import_kwh,reactive_energy_import_kvarh] | fidelity=real_exact
progressActivePct | base_columns=[active_energy_import_kwh,reactive_energy_import_kvarh] | fidelity=real_exact
activeEnergyMvah | base_columns=[active_energy_import_kwh] | fidelity=real_exact
reactiveEnergyMvarh | base_columns=[reactive_energy_import_kvarh] | fidelity=real_exact
cumulativeApparentMvah | base_columns=[active_energy_import_kwh,reactive_energy_import_kvarh] | fidelity=real_exact
expectedLossKwh | base_columns=[active_energy_import_kwh] | fidelity=real_exact
loadFactorPct | base_columns=[active_power_total_kw] | fidelity=real_approx
worstPeakKw | base_columns=[active_power_total_kw] | fidelity=real_exact
worstPeakAt | base_columns=[active_power_total_kw,ts] | fidelity=real_exact
apparentPeakKva | base_columns=[apparent_power_total_kva] | fidelity=real_approx
activePowerDeltaPerMinute | base_columns=[active_power_total_kw,ts] | fidelity=real_exact
lossPct | base_columns=[active_power_total_kw] | fidelity=real_exact
aiSummary | base_columns=[active_power_total_kw] | fidelity=real_exact
sectionTrendSums | base_columns=[active_power_total_kw] | fidelity=real_exact
upsRatedKva | base_columns=[<asset name>] | fidelity=real_approx
neutralCurrent | base_columns=[current_r,current_y,current_b] | fidelity=real_approx
neutralToPhaseRatioPct | base_columns=[current_r,current_y,current_b,current_avg] | fidelity=real_approx
pfAngleDeg | base_columns=[power_factor_total] | fidelity=real_exact
thdTrendLabel | base_columns=[thd_current_r_pct,thd_current_y_pct,thd_current_b_pct,ts] | fidelity=real_approx
thdTrendRatePctPerHour | base_columns=[thd_current_r_pct,thd_current_y_pct,thd_current_b_pct,ts] | fidelity=real_approx
ratedKw | base_columns=[active_power_total_kw,kpi_kw_load_pct_of_rated] | fidelity=real_exact
ratedKva | base_columns=[derated_capacity_kva] | fidelity=real_exact
sectionContracts | base_columns=[active_power_total_kw,kpi_kw_load_pct_of_rated] | fidelity=real_exact
```
Pick the fn whose base_columns are ALL in this asset's basket; if none qualifies (or the slot is one of the FOUR WALLS), emit NO derived field for that slot (honest-degrade — never fabricate).

Output STRICT valid JSON only matching the Layer2CardOutput schema. Escape inner quotes; no literal newlines in strings. Emit exactly:
{"card_id":0,"$ctx":null,"render_slot":"","analytical_story":"","swap_decision":{"action":"keep","origin":"kept","swap_to_id":null,"swap_to_title":null,"confidence":0.0,"criterion":null,"reason":null,"cascade":[]},"exact_metadata":{},"data_instructions":{"payload_shape":"","orientation":"","entity_dim":"","selection_dim":null,"selection_role":null,"binding":null,"window":null,"ems_backend":{"endpoint":"","window_seconds":30,"interval_seconds":2,"sample_count":12,"range":null,"start":null,"end":null,"sampling":null,"metrics":[],"selection":null},"fields":[]},"controls":null,"answerability":"full","data_note":null,"conforms":true,"failure":null}
