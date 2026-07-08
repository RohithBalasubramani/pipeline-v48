# Stream B — ratings/limits accessors + breakerOverloadPct derivation

STATUS: in progress (2026-07-08). Incremental log per hard rule 6.

## Verified ground truth (live cmd_catalog :5432, 2026-07-08)
- equipment.breaker: 301 rows, 168 rated (1000–2500 A). By type: ACB 202 rows / 168 rated, MCCB 99 rows / 0 rated
  → the 133 NULL-rating rows are 99 MCCB + 34 ACB (the design brief's "all MCCB" is slightly off; code never
  depended on it — NULL is NULL regardless of type). UNIQUE(mfm_id); FK mfm_id → equipment.mfm(id).
- equipment.rtm_threshold: 18 rows = 6 metrics (amp,i_unbal,kvar,kw,pf,volt) × 3 panel types
  (distribution_panel, lt_panel, transformer); 0 equipment-scoped rows (equipment_id NULL on all 18) — per-equipment
  resolution is future-proofing only, exactly as the design states.
- equipment.equipment_config: only rated_kva(113) + voltage_statutory_deviation_pct(7) non-null; 7 deviation rows
  confirmed. rated_kva NOT exposed (public.asset_nameplate stays the single rating authority).
- 18 duplicated table_name groups in equipment.mfm confirmed (dup → honest None from the bridge).
- app_config: PK(key), data_type NOT NULL default 'number'; knob convention = data_type 'text', value 'on'/'off';
  consts.* convention = data_type 'number', section 'consts'. 0 pre-existing consts.rtm_% keys.
- Worked fixtures (unique table_name, verified): rated breaker gic_30_n1_33kv_main_transformer_1_feeder_pm8000
  (ACB 2500); NULL-rated gic_29_n2_dg_og_1_sch (MCCB); rtm lt_panel gic_20_n4_lam_8_1_p1; voltage deviation
  gic_30_n7_ht_panel_m1_se (10.0).
- derivation_binding: PK(metric), columns metric/fn/base_columns/fidelity/expression/scope(default 'row').
  PRECEDENT (seed_derivation_binding_full.sql): "a fn without a row → executor built an EMPTY input row → honest
  None even when every base column was live"; upsRatedKva keeps non-frame inputs OUT of base_columns.

## Critic notes addressed
- FATAL R2-2 (cert regression at default knobs): gated at the SOURCE — registry.catalog() OMITS breakerOverloadPct
  when equipment.derivations.enabled is off (absent from every rendering: no new library line, no hidden-count
  drift, no new trailer on certified cards). The fn body ALSO returns None at knob-off, so even a hallucinated
  reference can never produce a payload leaf. emit.py keeps the '<word>:' pseudo-prefix generalization + the
  tri-state known-empty hiding for the knob-ON path only. The trailer wording is byte-untouched. A knobs-off
  SYSTEM-prompt byte test is in tests/test_equipment_ratings.py.
- B API contradiction (tri-state): ratings.breaker_state(asset_table) -> True|False|None added as the pinned probe
  (True = rated>0; False = known-empty: no breaker row / NULL or non-positive rating / dup-table meter — all
  deterministic no-fill states; None = unknown: no table given / DB error → NEVER hides, mirroring _nameplate_rated).
- Honest under-offer (recorded per critic): overload_pct's only plain declared base is current_avg, so a meter
  carrying per-phase current columns but NO current_avg has the fn basket-hidden in the emit prompt even though the
  max-phase basis could bind. Accepted honest under-offering (never over-offers).
- consts.rtm_* DO-UPDATE vs DO-NOTHING: documented IN THE SEED — equipment.rtm_threshold is the ground truth;
  re-applying re-derives the consts (overwrites hand-edits BY DESIGN; tune the rtm_threshold row instead). The knob
  row stays ON CONFLICT DO NOTHING (operator flips never reverted).
- Single-door raw-text scan: no '(from|join) equipment.' phrase (case-insensitive) appears in any non-exempt file I
  touched — comments in breaker.py/emit.py/registry.py say "equipment-schema" / name the accessor module instead.

## Deviation (written justification per brief)
- ADDED one derivation_binding row for breakerOverloadPct to db/seed_equipment_ratings.sql (metric=fn=
  'breakerOverloadPct', base_columns='current_avg', fidelity='real_exact', scope='row'). The design's seed list
  (knob + 72 consts) omitted it, but without a binding row config.derivation_binding.binding() returns None →
  ems_exec/executor/derived._run_derived builds an EMPTY input row → the fn can NEVER fill at knob-ON (the exact
  defect seed_derivation_binding_full.sql was shipped to fix). base_columns deliberately excludes 'breaker:rating_a'
  (not a frame column; the fn resolves the rating itself via data/equipment/ratings — the upsRatedKva precedent),
  which also keeps bindable() satisfiable. Byte-safe at knobs-off: the row only matters for a card that names the
  fn, and the fn is never offered at knobs-off (and returns None anyway).
- catalog() entries gain an OPTIONAL 'note' key (only present when the descriptor carries one) and emit renders
  ' | note=...' for it — this is how the design's "the library line STATES the basis" requirement is met without
  touching any existing line (no existing descriptor has a note → byte-identical at knobs-off).

## Files
- data/equipment/ratings.py — breaker_rating / breaker_state / rtm_bands_for_asset / rtm_const_key /
  voltage_deviation_pct (fail-open, :5432 only, no accessor for the all-NULL config columns).
- ems_exec/derivations/breaker.py — enabled() knob + overload_pct(ctx) (max-phase basis, empty-denominator gate).
- ems_exec/derivations/registry.py — breakerOverloadPct in _NAMEPLATE (+note), _QUANTITY 'load-percent-of-rated'
  (existing HARD class), source-gated catalog().
- layer2/emit/emit.py — pseudo-prefix generalization, _breaker_rated tri-state hiding (knob-ON only, lazy probe).
- db/seed_equipment_ratings.sql — knob (DO NOTHING) + 72 consts.rtm_* (DO UPDATE, re-derivation authority) +
  derivation_binding row (DO UPDATE).
- tests/test_equipment_ratings.py — see test list in-file.

## Progress log
- [x] Census re-verified (counts above) — matches design except the "all MCCB" nuance (recorded).
- [ ] ratings.py written
- [ ] breaker.py written
- [ ] registry.py edited
- [ ] emit.py edited
- [ ] seed written + applied live
- [ ] tests written + green
- [ ] full -k equipment + touched-seam tests green
