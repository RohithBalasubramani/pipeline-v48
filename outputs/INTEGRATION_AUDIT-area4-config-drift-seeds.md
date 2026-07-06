# INTEGRATION AUDIT — AREA 4: CONFIG DRIFT + SEEDS
Auditor: area4 subagent · Date: 2026-07-06 · Scope: every cfg()/vocab()/qp.txt()/qp.num() accessor in the changed files (244 changed .py) vs live cmd_catalog rows (app_config 158, data_quality_policy 87) + all 51 db/*.sql seeds.
Method: AST extraction of (key, code_default) incl. `_cfg`/`_vocab_*`/`_set` wrappers and f-string key patterns; live SELECT via data.db_client.q; membership-equal compare for json vocabularies; per-statement seed idempotency parse + seed-vs-live value match.
VOLATILE-TREE NOTE: layer2/gates.py, layer2/quantity_class.py, grounding/default_assemble.py, ems_exec/executor/yscale.py, db/render_guarantee_seed.sql all have mtimes within hours of this audit (batch12 layer2 agent mid-edit) — findings on those files may be mid-flight, re-verify at merge.

## FINDINGS (severity-ordered)

### F1. CERT-BLOCKING — seed re-run REGRESSES a hardening row: seed_seed_leak_policy.sql clobbers vocab.chrome_subtree_keys
- db/seed_seed_leak_policy.sql:18 seeds `vocab.chrome_subtree_keys` = `["bandthresholds","curvesag"]` with ON CONFLICT DO UPDATE.
- db/fix_ieee_limit_chrome_subtree.sql:16 (2026-07-03 hardening) supersedes it with the 7-key value that IS the live row (`bandthresholds,curvesag,limitpct,scalemaxpct,defaultlimits,ieee519limitpct,limits…`).
- "apply all db/seed_*.sql" (the pending round2/cert step) in glob order runs fix_* BEFORE seed_* → the stale 2-key value lands LAST and silently reverts the IEEE-limit byte-identical fix.
- FIX: update seed_seed_leak_policy.sql to the superseding 7-key value (or delete the key from it / mark the fix file canonical).

### F2. SHOULD-FIX — fix_narrative_slots_seed_scrub.sql is missing `aitext`; re-run drops a live policy token
- Live dqp `narrative_slots` = 21 tokens ending `…,lifenote,aitext`. The newest seed (db/fix_narrative_slots_seed_scrub.sql:21-24) carries only 20 (no `aitext`); NO seed file anywhere contains `aitext` (direct DB edit).
- Re-running the fix (ON CONFLICT full-value SET) silently un-scrubs `aitext` narrative leaves.
- FIX: fold `aitext` into fix_narrative_slots_seed_scrub.sql.

### F3. SHOULD-FIX — narrative_slots code-default drift (the display.unit_value_key_suffixes class)
- grounding/default_assemble.py:66-68 code default = 14 tokens; live row = 21. DB-only: `aisummary,aisummarytext,why,headroomcaption,agingcaption,lifenote,aitext`.
- On a cmd_catalog outage the scrub narrows and exactly the fabricated capacity/aging/life/AI-summary text the 2026-07-03 defect fix targeted leaks again.
- FIX: mirror the 21-token row into the code default.

### F4. SHOULD-FIX — metrics.vocab / metrics.aliases code defaults lag the DB rows (outage loses DG/OLTC metrics)
- config/metrics.py:7 default lacks DB-only vocab `fuel,pressure,level,runtime,soh,tap`; config/metrics.py:10 default lacks 15 DB-only aliases (`fuel level`,`run hours`,`tap position`,`state of health`,…).
- On outage, DG/transformer prompts mis-normalize to `power` (METRIC_DEFAULT). FIX: mirror rows into the code defaults.

### F5. SHOULD-FIX — quantity.unit_classes REVERSE drift: code default newer than row+seed (DB-up behavior loses it)
- layer2/quantity_class.py:152 `_UNIT_CLASSES_DEFAULT` adds count-unit keys `'#','count','counts','events','nos'` that are in NEITHER the live row NOR db/seed_quantity_class.sql (row==seed, both stale).
- Because the row EXISTS, cfg() serves the stale value and the new count-unit classification is dead in production paths. (Volatile file — batch12 edit in flight; if the code change is meant to land, the seed+row must be updated with it.)

### F6. SHOULD-FIX — two seeds present but never applied (row absent from live DB)
- `emit.dual_owned_keys` — db/seed_layer2_residual_knobs.sql:13 (seed value == code default at layer2/emit/user_message.py:102, so behavior is currently identical; still unapplied).
- `emit.morphmap_mode` — db/seed_morphmap_flag.sql:11 (seed 'off' == code default at layer2/emit/morphmap/mode.py:15; flag row reserved for the post-cert seam).
- FIX: run both seeds (or consciously defer; they are no-op-by-value today).

### F7. SHOULD-FIX — data_quality_policy carries 51 ORPHAN rows (no reader anywhere in the live tree, v47 tree, or v48 archive)
- band.* (34 rows: band.ieee519.* 13, band.overview.* 13, band.pq_fleet.* 8) + the whole `band_policy` table — db/seed_band_policy.sql:3 says "Read ONLY by config/bands.py" but config/bands.py DOES NOT EXIST and never existed at HEAD; the backend2-parity band port's reader never landed. The rtm.* app_config rows (read by ems_exec/renderers/_story/real_time_monitoring.py:24-28) carry overlapping thresholds.
- scope_map.* (7 rows) — endpoint-resolve feature retired (db/seed_endpoint_resolve_policy.sql.retired; grounding/endpoint_resolve.py deleted); rows left behind.
- l3.* (6 rows) — layer3/ archived 2026-07-02 (archive/layer3_archive_20260702.tar.gz); rows left behind.
- history.dip_load_pct, history.surge_load_pct (2) — no reader, no seed file.
- cumulative_counter_policy — superseded by cfg `fill.window_register_delta` (ems_exec/executor/fill.py:75) + roster.energy_register_pairs, yet STILL re-seeded by db/render_guarantee_seed.sql:18.
- event_marker_array_keys — superseded by vocab role_scrub.event_parents (grounding/event_skeleton_scrub.py:28).
- FIX: delete rows (and the dead seed lines/seed_band_policy.sql) or land the readers; at minimum stop re-seeding cumulative_counter_policy.

### F8. SHOULD-FIX — app_config carries 10 ORPHAN rows
- flags.ctx_source_form, flags.page_wise_shared_detection, flags.require_live_sentinel (config/flags.py + contracts/ deleted this batch)
- payload_shapes.canonical, payload_shapes.shape_map (config/payload_shapes.py deleted)
- panel_aggregate.member_columns, panel_aggregate.sum_columns, panel_aggregate.event_neutral_column (superseded by the READ roster.member_columns/roster.sum_columns keys — ems_exec/executor/roster.py:114-115)
- ems_backend.frame_budget_s (renamed → accessor now reads `ems_exec.card_budget_s`, host/exec_cards.py:18, which itself has NO row — the budget row is stranded under the old key while the new key is unseeded)
- display.rate_key_pattern (no reader anywhere)
- FIX: delete/rename rows; for the budget knob, re-key the row to ems_exec.card_budget_s.

### F9. SHOULD-FIX — windows.default_range outage fallback flips the default window
- layer2/build.py:196 falls back to DEFAULT_WINDOW (= cfg('windows.default_window','today') → 'today') while the live row says 'last-24h'. A cmd_catalog outage silently changes every unspecified card window from rolling-24h to calendar-today. FIX: align the code fallback with the row ('last-24h').

### F10. COSMETIC / NOTED
- window.site_tz (config/windows.py:19) uses the SINGULAR `window.` namespace — every sibling key is `windows.*`; unseeded today, and a future `windows.site_tz` seed would be silently unread. Naming trap.
- roster.member_columns / roster.sum_columns code default `[]` vs 20/5-column rows and registered_card_ids (grounding/swap_settle.py:30) default "" vs a 38-id row — deliberate row-as-home honest-degrade, but outage behavior differs; acknowledged, not mirrored by design.
- routes.page_tail_alias (layer1a/parse/granularity_reconcile.py:43) default {} vs 2-alias row — same row-as-home class.
- panel_aggregate.load_factor_fns row is camelCase, code default lowercase — consumer lowercases (ems_exec/renderers/panel_aggregate.py:230-232); functionally equal.
- llm.timeout.asset_resolve/basket/stories rows are data_type 'int' while llm.timeout/llm.timeout.l2_emit are 'number' — harmless (client floats them), inconsistent typing.
- vocab.py:5 claims "the DB is the SINGLE home, there are NO code literals", but 8 vocab names are UNSEEDED with code-literal fallbacks (vocab.yscale_max_keys/min_keys/ticks_key/series_keys, vocab.series_time_keys, vocab.time_label_patterns, vocab.verdict_scaffold_keys, vocab.sampling_refine_ladder) — doc-contract drift only; the fallbacks behave.
- placeholder.narrative dqp row exists with BOTH columns empty → accessor serves the code default "" anyway (inert but harmless).
- data-type/inert-row sweep: ALL 158 app_config rows cast cleanly under their declared data_type; no unknown data_type values (tests/test_config_cast_integrity.py polices this class).

## NOT-ORPHANS (naive key-grep false positives — read via namespace/wrapper/pattern)
- consts.hotspot_warn_c, consts.stress_border_pct — namespace scan `consts.` in layer2/quantity_class.py:346-350.
- emit.oversize_array_exemplars/basket_cap/sibling_exemplars — layer2/emit/user_message.py:205/233.
- quantity.axis_max/min/range_source_tokens — layer2/gates.py:351-368 `_axis_dir_tokens`.
- rating_slot.contracted_capacity_kw / rated_capacity_kw — config/nameplate_slot_map.py:39 prefix build.
- llm.timeout.* / llm.guided_json.* — llm/client.py:65/100 f-string per-stage keys (live stages: route, basket, asset_resolve, stories, l2_emit — every llm.timeout.* row maps to a real stage).

## SEED AUDIT (all 51 db/*.sql)
- Idempotency: ALL PASS. Every INSERT carries ON CONFLICT (…) DO UPDATE/DO NOTHING; schema files use CREATE TABLE IF NOT EXISTS / ADD COLUMN IF NOT EXISTS / CREATE OR REPLACE; two parser flags manually cleared (seed_feasibility_marks.sql ON CONFLICT at :52; seed_roster_recipes.sql all 5 INSERTs guarded at :49/:55/:100/:284/:510).
- Value-vs-live-row match: PASS for all applied seeds EXCEPT the four exceptions above (F1 clobber-hazard, F2 missing aitext, F6 two unapplied, F7 render_guarantee_seed.sql re-seeding the orphan cumulative_counter_policy). seed_band_policy.sql values match its 34 live rows exactly — the rows are just unread (F7).
- seed_endpoint_resolve_policy.sql retired correctly as a file; its scope_map.* rows were NOT retired from the DB (F7).

## MISSING-ROW INVENTORY (intentionally unseeded — code default is the live behavior; no seed file mentions the key)
cfg: emit.slot_catalog_cap(0), ems_exec.card_budget_s(env 45 — see F8 rename), feasibility.pool_verdicts(['render_real']), feasibility.template_max_unrenderable_frac(0.4), feasibility.unrenderable_verdicts(['drop','no_data']), fill.window_register_delta('on'), llm.gate_retry(1), llm.max_tokens(0 = uncapped by design), llm.parse_retry(1), llm.transport_retry(1), metrics.domain_stems, metrics.generic_slot_tokens, metrics.slot_shorthand, nameplate.nominal_pf(0.8), neuract.host/port/db/schema/user/password/ts_col/ts_cast(fall back to data.databases constants), renderers.telemetry_snapshot_keys(None), routes.granularity_shells, swap.forced_swap_confidence(2.0), validation.rollup_legacy_any_fail(False), validation.time_column(env), wall_replay.corpus_globs/md_fp_cap/rule_examples_cap, window.site_tz('Asia/Kolkata' — see F10), windows.reference_now('')
vocab: sampling_refine_ladder, series_time_keys, time_label_patterns, verdict_scaffold_keys, yscale_max_keys, yscale_min_keys, yscale_series_keys, yscale_ticks_key (all with working code fallbacks — see F10 doc drift)
qp: scrub.bare_day_pattern, scrub.provenance_tokens, scrub.temporal_pattern (code regex defaults active)

## FULL DRIFT TABLE (every changed-file accessor key)
| key | family | code_default | DB row (value ⇢ cast dt) | status | accessor |
|---|---|---|---|---|---|
| chart.yscale_ticks | cfg | EXPR:_DEFAULT_TICK_COUNT | 5 (int) | OK (const _DEFAULT_TICK_COUNT=5 == DB) | ems_exec/executor/yscale.py:75 |
| display.digit_key_suffixes | cfg | ['decimals', 'digits'] | ['decimals', 'digits'] (json) | OK | host/display_dash.py:107 |
| display.no_assert_fallbacks | cfg | EXPR:{"driverFallbackCode": DASH} | {'driverFallbackCode': '—'} (json) | OK (DASH == DB) | host/display_dash.py:118 |
| display.null_dash | cfg | unit_adjacent | unit_adjacent (text) | OK | host/display_dash.py:69 |
| display.trend_flat_pct | cfg | 0.02 | 0.02 (number) | OK | ems_exec/executor/trend_badge.py:34 |
| display.unit_sibling_suffixes | cfg | ['unit'] | ['unit'] (json) | OK | host/display_dash.py:79 |
| display.unit_value_key_suffixes | cfg | ['kw', 'kwh', 'kva', 'kvar', 'pct'] | ['kw', 'kwh', 'kva', 'kvar', 'pct'] (json) | OK | host/display_dash.py:96 |
| emit.dual_owned_keys | cfg | ['sectionContracts', 'pres.spokes', 'pres.select… | — | MISSING-ROW — seed exists but UNAPPLIED (seed_layer2_residual_knobs.sql) | layer2/emit/user_message.py:102 |
| emit.morphmap_mode | cfg | off | — | MISSING-ROW — seed exists but UNAPPLIED (seed_morphmap_flag.sql) | layer2/emit/morphmap/mode.py:15 |
| emit.prompt_char_budget | cfg | 36000 | 36000 (int) | OK | layer2/emit/user_message.py:174 |
| emit.repeated_exemplar_threshold | cfg | 6 | 6 (int) | OK | grounding/exemplar_reduce.py:38 |
| emit.slot_catalog_cap | cfg | 0 | — | MISSING-ROW (intentionally unseeded; code default active) | layer2/emit/slot_catalog.py:242 |
| ems_backend.connect_timeout_s | cfg | EXPR:float(os.environ.get("EMS_CONNECT_TIMEOUT",… | 8.0 (number) | OK (env-default 8 == DB) | config/ems_backend.py:13 |
| ems_backend.fetch_attempts | cfg | EXPR:int(os.environ.get("EMS_FETCH_ATTEMPTS", "3… | 3 (int) | OK (env-default 3 == DB) | config/ems_backend.py:20 |
| ems_backend.frame_timeout_s | cfg | EXPR:float(os.environ.get("EMS_FRAME_TIMEOUT", "… | 60.0 (number) | OK (env-default 60 == DB) | config/ems_backend.py:17 |
| ems_backend.retry_backoff_s | cfg | EXPR:float(os.environ.get("EMS_RETRY_BACKOFF", "… | 0.4 (number) | OK (env-default 0.4 == DB) | config/ems_backend.py:21 |
| ems_exec.card_budget_s | cfg | EXPR:float(os.environ.get("V48_EXEC_BUDGET_S", "… | — | MISSING-ROW (intentionally unseeded; code default active) | host/exec_cards.py:18 |
| feasibility.pool_verdicts | cfg | ['render_real'] | — | MISSING-ROW (intentionally unseeded; code default active) | layer2/swap/candidates.py:19 |
| feasibility.template_max_unrenderable_frac | cfg | 0.4 | — | MISSING-ROW (intentionally unseeded; code default active) | config/feasibility.py:18 |
| feasibility.unrenderable_verdicts | cfg | ['drop', 'no_data'] | — | MISSING-ROW (intentionally unseeded; code default active) | config/feasibility.py:13 |
| fill.window_register_delta | cfg | on | — | MISSING-ROW (intentionally unseeded; code default active) | ems_exec/executor/fill.py:75 |
| freshness.stale_after_s | cfg | 180.0 | 180.0 (number) | OK | ems_exec/executor/freshness.py:36 |
| gates.chrome_markers | cfg | ['=>', 'function(', 'function (', 'React.', 'onC… | ['=>', 'function(', 'function (', 'React.', … (json) | OK | layer2/gates.py:14 |
| gates.fields_optional_classes | cfg | ['nav_index', 'narrative_ai', 'topology_sld', 'a… | ['nav_index', 'narrative_ai', 'topology_sld'… (json) | OK (both call-site defaults equal) | tools/wall_corpus_replay.py:281 |
| gates.period_label_keys | cfg | EXPR:_LABEL_KEYS_DEFAULT | ['periodLabel', 'period', 'periodText', 'ran… (json) | OK (const == DB) | layer2/coherence.py:56 |
| gates.window_label_policy | cfg | morph | morph (text) | OK | layer2/coherence.py:107 |
| intents.vocab | cfg | ['trend', 'distribution', 'snapshot', 'table', '… | ['trend', 'distribution', 'snapshot', 'table… (json) | OK | layer1a/route.py:89 |
| layer1b.basket.derive_avg_from_phase | cfg | True | True (bool) | OK | layer1b/basket/column_basket.py:112 |
| layer1b.basket.include_logged_floor | cfg | True | True (bool) | OK | layer1b/basket/column_basket.py:78 |
| layer1b.basket.label_dedup | cfg | True | True (bool) | OK | layer1b/basket/describe.py:66 |
| layer1b.basket.max_columns | cfg | 400 | 400 (int) | OK | layer1b/basket/column_basket.py:91 |
| layer1b.basket.quality_guidance | cfg | EXPR:_QUALITY_GUIDANCE | The GENEROUS feasible basket MUST also inclu… (text) | OK (const == DB) | layer1b/basket/column_basket.py:59 |
| layer1b.class_concept_hints | cfg | EXPR:_CONCEPT_HINTS | {'UPS': {'tokens': ['ups'], 'concepts': ['ba… (json) | OK (const == DB) | layer1b/resolve/class_from_subject.py:58 |
| layer1b.has_data_window_rows | cfg | 20 | 20 (int) | OK | layer1b/basket/col_dict.py:38 |
| llm.gate_retry | cfg | 1 | — | MISSING-ROW (intentionally unseeded; code default active) | layer2/build.py:619 |
| llm.guided_json.asset_resolve | cfg | off | off (text) | OK | layer1b/resolve/answer_schema.py:35 |
| llm.max_tokens | cfg | 0 | — | MISSING-ROW (intentionally unseeded; code default active) | llm/client.py:135 |
| llm.no_retry_kinds | cfg | timeout,truncated | timeout,truncated (text) | OK | layer2/emit/emit.py:149 |
| llm.parse_retry | cfg | 1 | — | MISSING-ROW (intentionally unseeded; code default active) | llm/client.py:139 |
| llm.prompt_budget_tok | cfg | 45000 | 45000 (int) | OK | llm/client.py:143 |
| llm.seed | cfg | 42 | 42 (int) | OK | llm/client.py:130 |
| llm.temperature | cfg | 0 | 0.0 (number) | OK | llm/client.py:129 |
| llm.timeout | cfg | 120 | 120.0 (number) | OK | llm/client.py:64 |
| llm.transport_retry | cfg | 1 | — | MISSING-ROW (intentionally unseeded; code default active) | layer2/emit/emit.py:145 |
| metrics.aliases | cfg | {'power factor': 'pf', 'reactive power': 'pf', '… | {'power factor': 'pf', 'reactive power': 'pf… (json) | DRIFT (DB superset: +15 DG/OLTC aliases) | config/metrics.py:10 |
| metrics.default | cfg | power | power (text) | OK | config/metrics.py:4 |
| metrics.domain_stems | cfg | {'voltage': 'voltage', 'volt': 'voltage', 'curre… | — | MISSING-ROW (intentionally unseeded; code default active) | config/metrics.py:59 |
| metrics.generic_slot_tokens | cfg | ['value', 'val', 'amount', 'data', 'vm', 'kpis',… | — | MISSING-ROW (intentionally unseeded; code default active) | config/metrics.py:55 |
| metrics.slot_shorthand | cfg | {'v': 'voltage', 'i': 'current'} | — | MISSING-ROW (intentionally unseeded; code default active) | config/metrics.py:53 |
| metrics.vocab | cfg | ['current', 'voltage', 'power', 'energy', 'thd',… | ['current', 'voltage', 'power', 'energy', 't… (json) | DRIFT (DB superset: +fuel,pressure,level,runtime,soh,tap) | config/metrics.py:7 |
| nameplate.nominal_pf | cfg | 0.8 | — | MISSING-ROW (intentionally unseeded; code default active) | ems_exec/derivations/nameplate.py:26 |
| neuract.db | cfg | EXPR:_db.PG_DB | — | MISSING-ROW (intentionally unseeded; code default active) | config/neuract_dsn.py:27 |
| neuract.host | cfg | EXPR:_db.PG_HOST | — | MISSING-ROW (intentionally unseeded; code default active) | config/neuract_dsn.py:19 |
| neuract.password | cfg | EXPR:_db.PG_PASSWORD | — | MISSING-ROW (intentionally unseeded; code default active) | config/neuract_dsn.py:39 |
| neuract.port | cfg | EXPR:_db.PG_PORT | — | MISSING-ROW (intentionally unseeded; code default active) | config/neuract_dsn.py:23 |
| neuract.schema | cfg | EXPR:_db.PG_SCHEMA | — | MISSING-ROW (intentionally unseeded; code default active) | config/neuract_dsn.py:31 |
| neuract.ts_cast | cfg | EXPR:_db.DATA_TS_CAST | — | MISSING-ROW (intentionally unseeded; code default active) | config/neuract_dsn.py:49 |
| neuract.ts_col | cfg | EXPR:_db.DATA_TS_COL | — | MISSING-ROW (intentionally unseeded; code default active) | config/neuract_dsn.py:44 |
| neuract.user | cfg | EXPR:_db.PG_USER | — | MISSING-ROW (intentionally unseeded; code default active) | config/neuract_dsn.py:35 |
| panel_aggregate.energy_export_column | cfg | active_energy_export_kwh | active_energy_export_kwh (text) | OK | ems_exec/renderers/panel_aggregate.py:67 |
| panel_aggregate.energy_import_column | cfg | active_energy_import_kwh | active_energy_import_kwh (text) | OK | ems_exec/renderers/panel_aggregate.py:66 |
| panel_aggregate.load_factor_fns | cfg | ['loadfactorpct', 'loadfactorwindowpct'] | ['loadFactorPct', 'loadFactorWindowPct'] (json) | OK (case-differs; consumer lowercases) | ems_exec/renderers/panel_aggregate.py:230 |
| panel_aggregate.register_policy | cfg | pick_mover | pick_mover (text) | OK | ems_exec/renderers/panel_aggregate.py:68 |
| quantity.axis_slot_tokens | cfg | ['ymin', 'ymax', 'miny', 'maxy'] | ['ymin', 'ymax', 'miny', 'maxy'] (json) | OK | layer2/gates.py:342 |
| quantity.compatible_slot_source_pairs | cfg | EXPR:_COMPATIBLE_SLOT_SOURCE_PAIRS_DEFAULT | [['current', 'deviation-spread'], ['voltage'… (json) | OK (const == DB) | layer2/quantity_class.py:170 |
| quantity.dimensional_classes | cfg | EXPR:_DIMENSIONAL_CLASSES_DEFAULT | ['voltage', 'current', 'power', 'energy', 'f… (json) | OK (const == DB) | layer2/quantity_class.py:165 |
| quantity.expectation_slot_tokens | cfg | ['expected', 'forecast', 'predicted'] | ['expected', 'forecast', 'predicted'] (json) | OK | layer2/gates.py:405 |
| quantity.name_classes | cfg | EXPR:_NAME_CLASSES_DEFAULT | {'voltage': 'voltage', 'volt': 'voltage', 'c… (json) | OK (const == DB) | layer2/quantity_class.py:157 |
| quantity.semantic_families | cfg | EXPR:_SEMANTIC_FAMILIES_DEFAULT | {'efficiency': {'markers': ['efficiency'], '… (json) | OK (const == DB) | layer2/quantity_class.py:286 |
| quantity.structural_const_tokens | cfg | EXPR:_STRUCTURAL_CONST_TOKENS_DEFAULT | ['decimals', 'opacity', 'index', 'layout', '… (json) | OK (const == DB) | layer2/quantity_class.py:177 |
| quantity.unit_classes | cfg | EXPR:_UNIT_CLASSES_DEFAULT | {'v': 'voltage', 'kv': 'voltage', 'a': 'curr… (json) | DRIFT (CODE superset: +'#',count,counts,events,nos not in row/seed) | layer2/quantity_class.py:152 |
| quantity.weak_classes | cfg | EXPR:_WEAK_CLASSES_DEFAULT | ['percent'] (json) | OK (const == DB) | layer2/quantity_class.py:161 |
| reasons.max_roster_records | cfg | 80 | 80 (int) | OK | ems_exec/executor/roster_gaps.py:25 |
| reasons.max_unbound_records | cfg | 60 | 60 (int) | OK | ems_exec/executor/gaps.py:137 |
| reflect.min_gap_frac | cfg | 0.34 | 0.34 (number) | OK | run/harness.py:59 |
| reflect.reroute_on | cfg | hard_failure | hard_failure (text) | OK | run/harness.py:66 |
| renderers.telemetry_snapshot_keys | cfg | None | — | MISSING-ROW (intentionally unseeded; code default active) | ems_exec/renderers/__init__.py:72 |
| roster.energy_column | cfg | active_energy_import_kwh | active_energy_import_kwh (text) | OK | ems_exec/executor/roster.py:116 |
| roster.energy_export_column | cfg | active_energy_export_kwh | active_energy_export_kwh (text) | OK | ems_exec/executor/members.py:182 |
| roster.energy_register_pairs | cfg | EXPR:default | {'active_energy_import_kwh': 'active_energy_… (json) | OK (default dict == DB) | ems_exec/executor/members.py:201 |
| roster.interpreter_enabled | cfg | on | on (text) | OK | ems_exec/executor/roster.py:95 |
| roster.member_columns | cfg | [] | ['active_power_total_kw', 'reactive_power_to… (json) | DRIFT-ON-OUTAGE (DB 20 cols vs code []) | ems_exec/executor/roster.py:114 |
| roster.pf_columns | cfg | ['kpi_true_pf', 'power_factor_total'] | ['kpi_true_pf', 'power_factor_total'] (json) | OK | ems_exec/executor/bindings.py:41 |
| roster.power_column | cfg | active_power_total_kw | active_power_total_kw (text) | OK | ems_exec/executor/bindings.py:42 |
| roster.sections_key_default | cfg | sections | sections (text) | OK | ems_exec/executor/roster_modes_groups.py:82 |
| roster.status_synonyms | cfg | {'critical': ['critical', 'danger'], 'warning': … | {'critical': ['critical', 'danger'], 'warnin… (json) | OK | ems_exec/executor/bindings.py:43 |
| roster.sum_columns | cfg | [] | ['active_power_total_kw', 'reactive_power_to… (json) | DRIFT-ON-OUTAGE (DB 5 cols vs code []) | ems_exec/executor/roster.py:115 |
| route.card_titles_max | cfg | 400 | 400 (int) | OK | layer1a/route.py:35 |
| route.catalog_archetype | cfg | False | False (bool) | OK | layer1a/route.py:41 |
| route.story_max_chars | cfg | 320 | 320 (int) | OK | layer1a/catalog_compress.py:62 |
| route.story_min_new_ratio | cfg | 0.6 | 0.6 (number) | OK | layer1a/catalog_compress.py:61 |
| route.story_min_new_tokens | cfg | 4 | 4 (int) | OK | layer1a/catalog_compress.py:60 |
| routes.granularity_shells | cfg | EXPR:_GRANULARITY_SHELLS | — | MISSING-ROW (intentionally unseeded; code default active) | layer1a/parse/granularity_reconcile.py:33 |
| routes.page_tail_alias | cfg | {} | {'harmonics-pq': 'power-quality', 'overview-… (json) | DRIFT-ON-OUTAGE (DB 2 aliases vs code {}) | layer1a/parse/granularity_reconcile.py:43 |
| routes.panel_granularity_classes | cfg | ['Panel'] | ['Panel'] (json) | OK | config/asset_granularity.py:16 |
| rtm.busbar_temp_crit_c | cfg | 75.0 | 75.0 (number) | OK | ems_exec/renderers/_story/real_time_monitoring.py:28 |
| rtm.busbar_temp_warn_c | cfg | 65.0 | 65.0 (number) | OK | ems_exec/renderers/_story/real_time_monitoring.py:28 |
| rtm.current_unbal_warn_pct | cfg | 10.0 | 10.0 (number) | OK | ems_exec/renderers/_story/real_time_monitoring.py:27 |
| rtm.load_crit_pct | cfg | 100.0 | 100.0 (number) | OK | ems_exec/renderers/_story/real_time_monitoring.py:24 |
| rtm.load_warn_pct | cfg | 85.0 | 85.0 (number) | OK | ems_exec/renderers/_story/real_time_monitoring.py:24 |
| rtm.pf_floor | cfg | 0.9 | 0.9 (number) | OK | ems_exec/renderers/_story/real_time_monitoring.py:25 |
| rtm.pf_warn | cfg | 0.95 | 0.95 (number) | OK | ems_exec/renderers/_story/real_time_monitoring.py:25 |
| rtm.voltage_dev_crit_pct | cfg | 10.0 | 10.0 (number) | OK | ems_exec/renderers/_story/real_time_monitoring.py:26 |
| rtm.voltage_dev_warn_pct | cfg | 5.0 | 5.0 (number) | OK | ems_exec/renderers/_story/real_time_monitoring.py:26 |
| site.name | cfg | PEGEPL · SEETARAMPUR | PEGEPL · SEETARAMPUR (text) | OK | host/server.py:215 |
| swap.forced_swap_confidence | cfg | 2.0 | — | MISSING-ROW (intentionally unseeded; code default active) | layer2/swap/gate_force_renderable.py:28 |
| validation.event_name_pattern | cfg | (_event_active$\|_status$\|_compliance_ieee519$) | (_event_active$\|_status$\|_compliance_ieee5… (text) | OK | config/validation.py:42 |
| validation.failure_policy | cfg | EXPR:os.environ.get("V48_VALIDATE_POLICY", "anno… | annotate (text) | OK (env-default annotate == DB) | config/validation.py:49 |
| validation.max_null_rate | cfg | EXPR:float(os.environ.get("V48_MAX_NULL_RATE", "… | 0.5 (number) | OK (env-default 0.5 == DB) | config/validation.py:20 |
| validation.min_rows_series | cfg | EXPR:int(os.environ.get("V48_MIN_ROWS_SERIES", "… | 12 (int) | OK (env-default 12 == DB) | config/validation.py:22 |
| validation.payload_exempt_classes | cfg | ['narrative_ai', 'topology_sld', 'panel_aggregat… | ['narrative_ai', 'topology_sld', 'panel_aggr… (json) | OK | validate/payload_validate.py:12 |
| validation.phase_suffixes | cfg | ['_r', '_y', '_b', '_n', '_ry', '_yb', '_br', '_… | ['_r', '_y', '_b', '_n', '_ry', '_yb', '_br'… (json) | OK | config/validation.py:27 |
| validation.plumbing_columns | cfg | ['ts', 'panel_id', 'timestamp_utc', 'id', 'mfm_i… | ['ts', 'panel_id', 'timestamp_utc', 'id', 'm… (json) | OK | config/validation.py:35 |
| validation.probe_rows | cfg | EXPR:int(os.environ.get("V48_VALIDATE_ROWS", "50… | 500 (int) | OK (env-default 500 == DB) | config/validation.py:17 |
| validation.rollup_legacy_any_fail | cfg | False | — | MISSING-ROW (intentionally unseeded; code default active) | validate/report.py:17 |
| validation.small_array_max | cfg | EXPR:int(os.environ.get("V48_SMALL_ARRAY_MAX", "… | 8 (int) | OK (env-default 8 == DB) | config/validation.py:46 |
| validation.time_column | cfg | EXPR:os.environ.get("V48_TIME_COLUMN", DATA_TS_C… | — | MISSING-ROW (intentionally unseeded; code default active) | config/validation.py:16 |
| validation.warn_null_rate | cfg | EXPR:float(os.environ.get("V48_WARN_NULL_RATE", … | 0.1 (number) | OK (env-default 0.1 == DB) | config/validation.py:21 |
| view.auto_select | cfg | on | on (text) | OK | ems_exec/executor/view_select.py:21 |
| wall_replay.corpus_globs | cfg | EXPR:_DEFAULT_GLOBS | — | MISSING-ROW (intentionally unseeded; code default active) | tools/wall_corpus_replay.py:514 |
| wall_replay.md_fp_cap | cfg | 60 | — | MISSING-ROW (intentionally unseeded; code default active) | tools/wall_corpus_replay.py:459 |
| wall_replay.rule_examples_cap | cfg | 3 | — | MISSING-ROW (intentionally unseeded; code default active) | tools/wall_corpus_replay.py:340 |
| window.honor_declared_range | cfg | on | on (text) | OK | ems_exec/executor/window_policy.py:60 |
| window.site_tz | cfg | Asia/Kolkata | — | MISSING-ROW (intentionally unseeded; code default active) | config/windows.py:19 |
| windows.default_range | cfg | EXPR:DEFAULT_WINDOW | last-24h (text) | DRIFT-ON-OUTAGE (DB last-24h vs fallback DEFAULT_WINDOW=today) | layer2/build.py:196 |
| windows.default_window | cfg | today | today (text) | OK | config/windows.py:11 |
| windows.period_families | cfg | EXPR:_PERIOD_FAMILIES_DEFAULT | {'today': 'day', 'daily': 'day', 'yesterday'… (json) | OK (const == DB) | layer2/coherence.py:48 |
| windows.range_labels | cfg | EXPR:_RANGE_LABELS_DEFAULT | {'today': 'Today', 'yesterday': 'Yesterday',… (json) | OK (const == DB) | layer2/coherence.py:52 |
| windows.reference_now | cfg |  | — | MISSING-ROW (intentionally unseeded; code default active) | layer2/build.py:110 |
| windows.time_windows | cfg | {'today': {'lookback': '1 day', 'bucket': 'hour'… | {'today': {'lookback': '1 day', 'bucket': 'h… (json) | OK | config/windows.py:4 |
| xaxis.bucket_fallback | cfg | on | on (text) | OK | ems_exec/executor/xaxis.py:40 |
| xaxis.clock_patterns | cfg | EXPR:default | ['^\\d{1,2}:\\d{2}(:\\d{2})?$'] (json) | OK (default == DB) | ems_exec/executor/xaxis.py:50 |
| xaxis.derive_labels | cfg | on | on (text) | OK | ems_exec/executor/xaxis.py:30 |
| xaxis.label_format | cfg | %H:%M | %H:%M (text) | OK | ems_exec/executor/xaxis.py:65 |
| vocab.chrome_subtree_keys | vocab | EXPR:None | ['bandthresholds', 'curvesag', 'limitpct', '… (json) | OK (membership equal) | validate/leaf_classify.py:39 |
| vocab.delta_projection_keys | vocab | EXPR:None | ['delta', 'deltaText', 'deltaTone'] (json) | OK (membership equal) | ems_exec/executor/display.py:52 |
| vocab.element_chrome_keys | vocab | EXPR:None | ['decimals', 'width', 'dash', 'warn', 'trip'… (json) | OK (membership equal) | validate/leaf_classify.py:48 |
| vocab.element_value_keys | vocab | [] | ['value', 'values', 'totalKw', 'totalKwh', '… (json) | OK (membership equal) | validate/render_verdict.py:57 |
| vocab.label_keys | vocab | EXPR:None | ['label', 'title', 'name', 'prefix', 'qualif… (json) | OK (membership equal) | validate/leaf_classify.py:33 |
| vocab.measured_annotation_keys | vocab | EXPR:None | ['label', 'sub', 'sublabel', 'caption'] (json) | OK (membership equal) | grounding/measured_annotation_scrub.py:62 |
| vocab.numeric_axis_keys | vocab | {'xticks', 'axislabels', 'ticklabels', 'xlabels'… | ['yticks', 'ylabels', 'xticks', 'xlabels', '… (json) | OK (membership equal) | validate/leaf_classify.py:68 |
| vocab.occurrence_bool_parents | vocab | {'events', 'ticks', 'anomalies', 'occurrences', … | ['ticks', 'activity', 'events', 'anomalies',… (json) | OK (membership equal) | validate/leaf_classify.py:57 |
| vocab.role_scrub.active_state_parents | vocab | {'statusbadge', 'state', 'service', 'ieeebadge',… | ['status', 'statusbadge', 'badge', 'freshnes… (json) | OK (membership equal) | grounding/role_scrub.py:55 |
| vocab.role_scrub.active_value_keys | vocab | {'label', 'statuskey', 'insightkey', 'key', 'dri… | ['label', 'statuslabel', 'statuskey', 'tone'… (json) | OK (membership equal) | grounding/role_scrub.py:61 |
| vocab.role_scrub.derived_pick_parents | vocab | {'selectedpanel', 'worst'} | ['worst', 'selectedpanel'] (json) | OK (membership equal) | grounding/role_scrub.py:51 |
| vocab.role_scrub.dictionary_subtree_keys | vocab | {'notevocab', 'causevocab', 'drivervocab', 'voca… | ['statusvocab', 'insightvocab', 'causevocab'… (json) | OK (membership equal) | grounding/role_scrub.py:95 |
| vocab.role_scrub.event_parents | vocab | {'anomaly', 'events', 'anomalies', 'event'} | ['anomalies', 'events', 'event', 'anomaly'] (json) | OK (membership equal) | grounding/role_scrub.py:84 |
| vocab.role_scrub.event_value_keys | vocab | {'label', 'title', 'type', 'status', 'severity'} | ['title', 'label', 'type', 'severity', 'stat… (json) | OK (membership equal) | grounding/role_scrub.py:88 |
| vocab.role_scrub.global_active_keys | vocab | {'severityaction', 'availability', 'statuskey', … | ['ieeestate', 'filterstate', 'availability',… (json) | OK (membership equal) | grounding/role_scrub.py:106 |
| vocab.role_scrub.metric_value_keys | vocab | {'displayvalue', 'value'} | ['value', 'displayvalue'] (json) | OK (membership equal) | grounding/role_scrub.py:130 |
| vocab.role_scrub.metric_value_parents | vocab | {'kpi', 'metric', 'metrics', 'kpicells', 'stat',… | ['stats', 'stat', 'metrics', 'metric', 'kpis… (json) | OK (membership equal) | grounding/role_scrub.py:124 |
| vocab.role_scrub.mfm_pointer_pattern | vocab | EXPR:None | ^\s*MFM[_-]?\d+\s*$ (json) | OK (membership equal) | grounding/role_scrub.py:144 |
| vocab.role_scrub.reference_line_parents | vocab | {'referencelines', 'watchlines'} | ['referencelines', 'watchlines'] (json) | OK (membership equal) | grounding/role_scrub.py:117 |
| vocab.role_scrub.roster_blank_keys | vocab | {'table', 'cause', 'causekey', 'driverkey', 'dri… | ['status', 'cause', 'causekey', 'driver', 'd… (json) | OK (membership equal) | grounding/role_scrub.py:79 |
| vocab.role_scrub.roster_identity_keys | vocab | {'panel', 'id'} | ['id', 'panel'] (json) | OK (membership equal) | grounding/role_scrub.py:74 |
| vocab.role_scrub.roster_parents | vocab | {'periods', 'panels'} | ['panels', 'periods'] (json) | OK (membership equal) | grounding/role_scrub.py:69 |
| vocab.role_scrub.tone_key_suffix | vocab | EXPR:None | tone (json) | OK (membership equal) | grounding/role_scrub.py:112 |
| vocab.sampling_refine_ladder | vocab | EXPR:None | — | MISSING-ROW (code-default/honest-degrade fallback active; contradicts vocab.py 'DB is the SINGLE home' doc) | ems_exec/executor/indexed_families.py:105 |
| vocab.series_time_keys | vocab | EXPR:None | — | MISSING-ROW (code-default/honest-degrade fallback active; contradicts vocab.py 'DB is the SINGLE home' doc) | ems_exec/executor/series_fill.py:82 |
| vocab.time_axis_keys | vocab | EXPR:None | ['sampletimestamps', 'timelabeltimestamps', … (json) | OK (membership equal) | layer2/emit/slot_catalog.py:220 |
| vocab.time_label_patterns | vocab | EXPR:None | — | MISSING-ROW (code-default/honest-degrade fallback active; contradicts vocab.py 'DB is the SINGLE home' doc) | layer2/emit/slot_catalog.py:88 |
| vocab.unit_quantities | vocab | EXPR:db_link | {'v': 'voltage', 'volt': 'voltage', 'volts':… (json) | OK (membership equal) | config/vocab.py:44 |
| vocab.value_keys | vocab | EXPR:None | ['value', 'val', 'displayValue', 'delta', 'd… (json) | OK (membership equal) | validate/leaf_classify.py:29 |
| vocab.verdict_scaffold_keys | vocab | [] | — | MISSING-ROW (code-default/honest-degrade fallback active; contradicts vocab.py 'DB is the SINGLE home' doc) | validate/render_verdict.py:37 |
| vocab.yscale_max_keys | vocab | EXPR:_DEFAULT_MAX_TOKENS | — | MISSING-ROW (code-default/honest-degrade fallback active; contradicts vocab.py 'DB is the SINGLE home' doc) | ems_exec/executor/yscale.py:50 |
| vocab.yscale_min_keys | vocab | EXPR:_DEFAULT_MIN_TOKENS | — | MISSING-ROW (code-default/honest-degrade fallback active; contradicts vocab.py 'DB is the SINGLE home' doc) | ems_exec/executor/yscale.py:54 |
| vocab.yscale_series_keys | vocab | EXPR:_DEFAULT_SERIES_KEYS | — | MISSING-ROW (code-default/honest-degrade fallback active; contradicts vocab.py 'DB is the SINGLE home' doc) | ems_exec/executor/yscale.py:236 |
| vocab.yscale_ticks_key | vocab | EXPR:(_DEFAULT_TICKS_KEY,) | — | MISSING-ROW (code-default/honest-degrade fallback active; contradicts vocab.py 'DB is the SINGLE home' doc) | ems_exec/executor/yscale.py:58 |
| narrative_slots | qp.txt | insight,text,summary,note,caption,subtitle,likel… | insight,text,summary,note,caption,subtitle,l… (txt_value) | DRIFT (DB +aisummary,aisummarytext,why,headroomcaption,agingcaption,lifenote,aitext) | grounding/default_assemble.py:66 |
| negative_power_convention | qp.txt | abs_with_flag | abs_with_flag (txt_value) | OK | ems_exec/executor/verify.py:24 |
| placeholder.narrative | qp.txt |  | NULL (txt_value) | ROW-PRESENT-BUT-NULL (accessor serves code default) | grounding/default_assemble.py:74 |
| placeholder.scalar | qp.txt | 0 | 0 (txt_value) | OK | ems_exec/executor/graft.py:97 |
| rating.capacity_pf | qp.num | 0.9 | 0.9 (num_value) | OK | config/rating_knobs.py:52 |
| rating.contracted_factor | qp.num | 0.9 | 0.9 (num_value) | OK | config/rating_knobs.py:35 |
| rating.critical_load_factor | qp.num | 0.5 | 0.5 (num_value) | OK | config/rating_knobs.py:40 |
| rating.current_alarm_factor | qp.num | 1.2 | 1.2 (num_value) | OK | config/rating_knobs.py:29 |
| rating.energy_target_hours | qp.num | 12.0 | 12.0 (num_value) | OK | config/rating_knobs.py:46 |
| rating.feeder_pf | qp.num | 0.9 | 0.9 (num_value) | OK | config/rating_knobs.py:17 |
| rating.lv_line_v | qp.num | 415.0 | 415.0 (num_value) | OK | config/rating_knobs.py:23 |
| scrub.bare_day_pattern | qp.txt | ^\s*\d{1,2}\s*$ | — (txt_value) | MISSING-ROW (intentionally unseeded; code default active) | grounding/default_assemble.py:107 |
| scrub.clock_strings | qp.txt | on | on (txt_value) | OK | grounding/default_assemble.py:96 |
| scrub.embedded_number_pattern | qp.txt | EXPR:_EMBEDDED_DEFAULT | (?<![\w#])[+-]?\d+(?:[.,]\d+)?\s*(?:%\|°\s*[… (txt_value) | OK | grounding/measured_annotation_scrub.py:47 |
| scrub.embedded_numbers | qp.txt | on | on (txt_value) | OK | grounding/measured_annotation_scrub.py:55 |
| scrub.provenance_tokens | qp.txt | mock,fake,demo,seed,sample,stub,placeholder,dumm… | — (txt_value) | MISSING-ROW (intentionally unseeded; code default active) | grounding/default_assemble.py:134 |
| scrub.temporal_pattern | qp.txt | EXPR:_TEMPORAL_DEFAULT | — (txt_value) | MISSING-ROW (intentionally unseeded; code default active) | grounding/default_assemble.py:92 |
| topology.loss_plausible_max_pct | qp.num | 10.0 | 10.0 (num_value) | OK | config/topology_policy.py:30 |
| topology.loss_plausible_min_pct | qp.num | 0.0 | 0.0 (num_value) | OK | config/topology_policy.py:29 |
| topology.trend_deadband | qp.num | 0.05 | 0.05 (num_value) | OK | config/topology_policy.py:37 |
