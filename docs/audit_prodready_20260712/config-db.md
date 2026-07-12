# Production-readiness audit — lens: config-db — 2026-07-12

Scope: `config/` package (PEP-562 lazy knobs, policy readers), `db/` (seeds, apply.py ledger,
obs_schema), and live cmd_catalog state (:5432, SELECT-only). DIFFERENTIAL vs
docs/audit_2026-07-12/{database,hardcoded-rules}.md and the refactor ledger
(docs/findings/refactor_20260712/EXECUTED_AND_FOLLOWUPS.md). Only NEW findings, regressions
between today's concurrent sessions, half-applied refactors, or false "EXECUTED" claims.

Status: COMPLETE (8 findings OBS-1..OBS-8, verification list at bottom).

## Findings

### OBS-1 (medium, safe) — endpoint_policy retirement half-applied: render_guarantee_schema.sql still CREATEs the dropped table
`db/retire_unused_tables_20260712.sql` (APPLIED, owner-authorized per its header; live DB confirms all
6 tables gone) dropped `endpoint_policy` et al. The retirement scrub block-commented the dead DDL/seeds in
`db/round2_config_schema.sql:21-45` (`/* ... */`), `db/seed_round2_config.sql:20-41`, and
`db/seed_roster_recipes.sql:592-628` — but MISSED `db/render_guarantee_schema.sql:72-81`, which still has a
LIVE, uncommented `CREATE TABLE IF NOT EXISTS endpoint_policy`. A from-scratch rebuild via `db/apply.py`
(R9's whole point) resurrects `endpoint_policy` as an empty zombie table, contradicting the retire script
and the "reproducible declared state" goal. Fix: block-comment it with the same RETIRED banner. Also
stale: `scripts/seed_schema_and_endpoints.py:9` docstring still describes seeding endpoint_policy (the
function itself was correctly retired at :99-101).

### OBS-2 (low, safe) — APPLY_LOG doc contradicts the live DB: claims table DROPs are "NOT applied / owner-gated" but they WERE applied
`docs/findings/refactor_20260712/APPLY_LOG_unused_dupes_audit.md:53` ("NOT dropped (owner-gated, snapshots
ready)") and `:152` ("Owner-gated DROP script written, NOT applied: db/retire_unused_tables_20260712.sql.owner_gated")
are stale: the script was renamed to `.sql`, its header records "APPLIED 2026-07-12 ~07:50 IST (owner
authorized)", and live cmd_catalog confirms all six tables dropped (`to_regclass` NULL for endpoint_policy,
band_policy, limit_override, live_window_policy, card_rendering, card_render_map). Same stale claim in
`db/fix_deadend_knobs_20260712.sql:15-16` ("snapshotted but NOT dropped — table drops are owner-gated").
Doc-only fix; matters because these ledgers are the recovery/handoff record for a destructive op.

### OBS-3 (medium, safe) — PEP-562 lazy-knob conversion half-applied: ~8 consumers still freeze the value at import via module-level from-imports
Batch-2 ledger claims "Import-time cfg() freezes converted to lazy PEP-562 module attributes" and
`config/windows.py:3-5` promises "each access re-reads cfg() ... reaches every consumer". But a
module-level `from config.X import NAME` evaluates `__getattr__` ONCE at the consumer's import and pins
the value in the consumer's namespace for process life — exactly the freeze the refactor claims to have
removed. Module-level offenders: `layer2/swap/candidates.py:12` (SIZE_TOLERANCE, SWAP_POOL_MAX),
`layer2/swap/gate_confidence.py:2` (MIN_CONFIDENCE), `layer2/swap/gate_vague_reject.py:2` (VAGUE_CRITERIA),
`layer1a/route.py:15` (METRIC_VOCAB), `layer1a/parse/template_feasibility_gate.py:13`
(TEMPLATE_MAX_UNRENDERABLE_FRAC), `layer1a/parse/metric_intent_defaults.py:3` (INTENT_DEFAULT, INTENT_VOCAB),
`layer1a/db_reads/page_feasibility.py:8` (UNRENDERABLE_VERDICTS). Other consumers correctly moved the
from-import inside functions (`layer2/window_backfill.py:29`, `ems_exec/executor/window_policy.py:33`,
`layer1a/route_schema.py:55` ...). Consequence: a DB knob edit (e.g. swap.min_confidence) or a
boot-during-outage heal never reaches these 8 sites without a restart. Fix: attribute-access
(`config.swap.MIN_CONFIDENCE`) or in-function import, mechanical.

### OBS-4 (medium, defer) — AUDIT_REPORT's "R7 implemented by concurrent session" is overstated: run-id is still a cross-labeling global; trace.current_run_id() has zero consumers
`run_traced` IS wired (host/server.py:157-169 — that half of the claim holds) and `obs/trace.py:86
current_run_id()` exists as a contextvar-backed accessor. But NOTHING consumes it (only its own test,
tests/test_obs_trace.py:67). `obs/ai_log.py:11` still holds the module-global `_RUN_ID`, `:67` still
monkeypatches `urllib.request.urlopen` process-wide, host/server.py:340 still sets the global per request,
and `config/reason_templates.py:41 _tell_failures` keys the whole failures channel by
`getattr(ai_log, "_RUN_ID", "default")`. Under the threaded server two concurrent runs still cross-label
ai_*.jsonl / failures_*.jsonl exactly as H14 describes. The consensus table correctly says H14
"Recommended (§R7)"; the closing note ("R7 ... was implemented by a concurrent session ... not duplicated
here") is wrong about the run-id leg. Deferred: the obs session owns ai_log.

### OBS-5 (medium, safe) — layout_fe.* app_config rows (8) are dead-end knobs; the dead-code lens claim "FE reads section layout_fe" is false
`host/web/src/layout/vocab.ts:7-10` documents the intended read path — "the server threads the resolved
app_config values onto the response as page.layout.fe_vocab ... Until the server populates it ... the
code-default mirror governs" — and grep shows NO `fe_vocab` producer anywhere in host/*.py, no other
reader of the `layout_fe` section (py/ts/tsx, incl. CMD_V2). So editing any of the 8 seeded rows
(layout_fe.band_regions/rail_regions/flex_primitive/default_primitive/fallback_*/rebase_min_row,
db/seed_layout_vocab.sql) silently does nothing — the exact dead-end-knob hazard class
fix_deadend_knobs_20260712.sql was written for. `docs/findings/refactor_20260712/dead-code.md:27` claims
these are "ALL read via dynamic prefixes ... FE reads section layout_fe" — not true. Fix: wire the
documented server-side fe_vocab pass-through (additive; FE overlay already handles it) or retire the rows.

### OBS-6 (medium, safe) — config/README.md promises TTL / no-restart knob edits; app_config is process-cached on success with no TTL and no reload caller
`config/README.md:14-18`: "TTL-cached; a missing row = the code default ... changes need no restart (TTL)".
Reality: `config/app_config.py:21,30-31,40` — `_CACHE` is populated once on the first SUCCESSFUL load and
served for the whole process life; the 2026-07-12 fix made FAILURE non-cached (correct) but added no TTL,
and nothing in host/ or admin/ ever calls `reload()`/`_load.cache_clear()`. An operator following the
README edits a row, sees no effect on the running :8770 host, and may then "fix" the legacy
data_quality_policy row instead — the precise wrong-home hazard drop_legacy phase-2 warns about. Fix:
either correct the README (restart/reload required) or give `_load` the TTLCache treatment (the database
lens F6 fix explicitly suggested the optional TTL; it was not taken).

### OBS-7 (low, safe/owner-gated) — residual orphan + half-knob app_config rows the orphan/dead-end sweeps missed
True orphans (no reader in v48, v47, or _archive; notes empty): `payload_shapes.canonical`,
`payload_shapes.shape_map` (verified: zero grep hits tree-wide outside the rows themselves). Known-orphan
quartet `ems_backend.{connect_timeout_s,fetch_attempts,frame_timeout_s,retry_backoff_s}` is documented as
deliberately left (config/ems_backend.py:6-8) but that module is itself now RETIRED (header :10-13),
so the rows have no prospective reader either. Declared-ahead-of-reader half-knobs (notes say "reader
lands in next-round" but code still hardcodes the value): `panel_aggregate.member_columns`,
`panel_aggregate.sum_columns` (`panel_aggregate.py:82 _SUM_COLS` hardcoded), `panel_aggregate.event_neutral_column`
(`panel_aggregate.py:73 _EVT_NEUTRAL` hardcoded), `display.rate_key_pattern` (display.py `_RATE_KEY_RE`).
These are the same class as the F10 half-knob the campaign retired by owner call — either land the
readers or retire the rows with a dated fix_*.sql. Rows-only cleanup; reader-verify first per the
verify-before-dead rule.

### OBS-8 (medium, owner-gated) — db/apply.py "apply all pending" is unsafe against the LIVE cmd_catalog: 62 DO-UPDATE seeds + a timing-gated drop + a DELETE-reseed would all fire in one command
The new R9 runner (`db/apply.py:95,117-123`) treats every unrecorded .sql as pending and applies them in
filename order; its docstring asserts "every seed is itself idempotent — ON CONFLICT / IF NOT EXISTS — so
re-apply is safe" (apply.py:20-22). That contradicts the same audit's F3/H26 finding: 62 of the .sql files
still use `ON CONFLICT ... DO UPDATE` (grep count today; the F3 "DO NOTHING convention" was never
executed), so a plain `python db/apply.py` against the live DB is a bulk operator-tuning rollback. It
would also apply `drop_legacy_knob_homes_phase2.sql` immediately — its guards check parity (pass today),
not the intended "after ≥ one clean cert/sweep cycle" gate (EXECUTED_AND_FOLLOWUPS.md item 11) — and
`render_guarantee_seed.sql:45` (`DELETE FROM metric_class;` then reseed). Fine for a from-scratch rebuild
(its stated purpose); dangerous as a routine sync. Fix: seed the ledger with the already-applied file set
before adoption (a `--baseline` mode recording all current files without running them), and/or an explicit
exclusion/hold list for timing-gated files. Owner decides adoption semantics.

## Verified OK (live probes, 2026-07-12)

- **Knob-home consolidation (batch 7 / F6 phase 1) is REAL and clean.** Readers are app_config-first with
  legacy fallback exactly as claimed: `config/policy_read.py:36-60` (num/txt via `_appcfg`),
  `config/quality_policy.py:10-33` (app_config-first, legacy read keeps RAISING semantics),
  `config/viewer_policy.py:84-102` (`_txt` app_config-first, `__knob__:` sentinel fallback). Live parity:
  app_config has 51 rows section='data_quality_policy' + 3 section='viewer'; phase-2 guard query returns
  0 divergences (the drop script would run clean). Legacy transition rows still present as expected:
  data_quality_policy = 52 rows (51 migrated + 1 deliberately-skipped both-columns-blank
  `placeholder.narrative`, documented in fix_knob_home_consolidation.sql:15), viewer_policy `__knob__:` = 3.
- **schema_migrations state:** table EXISTS (created by an `apply.py --status` probe — `_ensure_ledger`
  runs on --status) with **0 rows** — ledger not yet adopted, which matches the AUDIT_REPORT's "the
  operator adopts it". Recorded as state, not a defect (but see OBS-8 before adopting).
- **obs_schema.sql applied and the obs layer is LIVE:** obs_traces=20, obs_stage_events=2,594,
  obs_llm_calls=660, obs_db_queries=104,301 rows (matches the 4 tables obs_schema.sql declares).
- **fix_orphan_knobs_20260712.sql claims TRUE:** `llm.prompt_v2` and `flags.%` rows = 0;
  `ems_backend.frame_budget_s` gone; renamed `ems_exec.card_budget_s` row present (45, number).
- **cfg() never-cache-empty (audit fix #1) is real in code:** config/app_config.py:21-47 — failure not
  cached, 5s backoff, stderr log, `_load.cache_clear` back-compat hook preserved. (But no TTL — OBS-6.)
- **PEP-562 lazy modules behave correctly at the module level:** probed config/{windows,metrics,swap,
  intents,feasibility} — all lazy attrs resolve with correct types from the live DB; a typo'd attribute
  raises AttributeError (no silent-default hole in `__getattr__`). All 34 config/*.py modules import clean.
- **Seeds-vs-readers type drift: none found in a 15-key sample** (cache.resolution_ttl_s,
  ems_exec.card_budget_s, layer2.emit_concurrency, emit.morphmap_mode, windows.min_span_days,
  llm.timeout.l2_emit, gates.chrome_markers, windows.time_windows, fab_guards.epoch_ms_floor,
  validation.phase_suffixes, validate.event_semantic_tokens, freshness.stale_after_s,
  power.loading_plausible_max_pct, emit.prompt_char_budget, equipment.facts.enabled) — every cfg() cast
  matches the row's data_type. `app_config.data_type` values are all in-vocab (number/json/text/int/bool).
- **reason_template coverage holds:** every literal cause emitted through the reason channel
  (column_absent, data_unavailable, literal_scrubbed, no_asset_3d, no_data, no_default_payload,
  structurally_null, unbound_by_emit + gaps.py `_gap_of` returns derivation_unbound/no_nameplate/
  no_reading/quantity_mismatch/...) has a row among the 38 reason_template causes; reason() also
  falls back to the cause key itself so the channel never empties.
- **retire_unused_tables_20260712.sql applied cleanly:** all six tables gone from live cmd_catalog;
  the only surviving code reference (scripts/seed_schema_and_endpoints.py) had its seeding function
  correctly retired; round2_config_schema.sql / seed_round2_config.sql / seed_roster_recipes.sql dead
  sections properly block-commented (only render_guarantee_schema.sql missed — OBS-1).
- **config/README.md plane map is otherwise accurate** (module→table map spot-checked against source);
  seed_conn_timeouts.sql + seed_llm_admission.sql exist with the DO-NOTHING declaration convention as the
  audit describes — note they are NOT yet applied to the live DB (no neuract.connect_timeout_s /
  llm.global_concurrency rows), consistent with "additive, operator adopts", knobs serve code defaults.
- The `some_new_cause` literal is a test fixture (tests/test_failures_fanout.py:97), not a missing row.
- `fab_guards.*`, `llm.timeout.*`, `vocab.*` app_config families confirmed read via dynamic-prefix cfg()
  (knobs.py:24, llm/client, config/vocab.py) — not orphans.

## Status: COMPLETE
