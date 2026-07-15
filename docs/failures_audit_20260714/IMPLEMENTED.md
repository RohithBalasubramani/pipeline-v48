# Failures-Audit Fix Campaign — Implementation Ledger (2026-07-15)

Plan: `~/.claude/plans/make-a-detailed-plan-shiny-lightning.md` (approved 2026-07-15). 16 commits
(`468c825..f868f3b` range, interleaved with the emit-diet session's commits). Suite: 1,377 passed / 0 failed.
All seeds applied to cmd_catalog; `rescan_stripped_payloads` clean; v48-host + v48-admin restarted 17:06
(host pid 171882).

## Landed (by phase)

| Phase | What | Key files | Commit |
|---|---|---|---|
| 0 | baseline + registry sync + env-dependent test pin | tests/test_multi_parallel.py | 468c825 |
| 1.1 | libpq desync wordings = outage fingerprints | data/outage.py | c4860b5 |
| 1.2 | dangling-registry table samples DARK (never raises); ghost short-circuit | layer1b/basket/col_dict.py, column_basket.py | 9cbf210 |
| 1.3 | pipeline_error honest terminal (no silent ok=true page) | run/error_terminal.py, run/harness.py | 7077e09 |
| 1.4 | registry↔information_schema drift check (CLI + boot + live gate) | data/registry/drift.py, sweep/checks/, host/server.py | d9883c7 |
| 2.1 | V48_OBS_DIR structural pytest isolation + rid coercion | obs/paths.py + 6 writers + conftest + replay/isolate | 0e6b71a |
| 2.2 | head+tail truncation; llm records carry card_id | obs/failures.py, llm/client.py | 513da04 |
| 2.3 | ONE writer per fact (twins deleted; fill_gap ×4→×1 with the AI note; llm-mirror suppressed) | obs/stage.py, run/harness.py, obs/notes.py | ab5e8a5 |
| 2.4 | classify() + honest_gaps/quarantined/dedup buckets + FE panel | admin/failures_report.py, explorer.py, FailuresPage.tsx | f917d76 |
| 3 E1 | {column} template KeyError fix | fab_guards/knobs.py | a4ffdaa |
| 3 E2 | chrome keys + derived-sibling prune (displayValue) | db/seed_vocab.sql, layer2/emit/slot_catalog.py | a4ffdaa |
| 3 E3 | write-after-prune: pure sentence() + obs/gap_sink at 2 serve points; reconcile capped; '(' labels | config/reason_templates.py, obs/gap_sink.py, fill.py, enrich.py, roster_gaps/xaxis/gaps | d519b4a |
| 3 E4 | kind=time atoms only on time-axis leaves (front door for epoch_ms_leak) | layer2/gates/data_instructions.py | 651c8fd |
| 3 E5 | energy-polarity fn substitution (explicit sibling map, knob on) | registry._POLARITY_SIBLINGS, verify.py, fill.py | c9f8445 |
| 3 E6 | derivation-key normalize + derivation_alias table (unit-magnitude safe) | config/derivation_binding.py, db/seed_derivation_alias.sql | 08a6662 |
| 4 | INFRA failures → conforming skeleton (no hard_fail, no reroute; knob on) | layer2/emit_failed.py, build.py, run/layer2_all.py | 6ee1a93 |
| 5 | bounded outage connect-retry (db.connect_retry_s=8) + admission row pin | data/connect_retry.py, db_client.py, neuract_pool.py | 2f5c787 |
| 6 | pcc1a-v1 lt_asset_3d row (id 3, applied) + config-defaults net | scripts/seed_pcc1a_asset3d.py, validate/config_defaults_check.py | f868f3b |

## Live verification (2026-07-15, post-restart)

- **Gate 1** — `POST /api/run {"prompt":"gic 15 pcc transformer 1","asset_id":164}` → `asset_no_data:true`,
  4 per-leaf-null cards, `errors:{}` (was: uncaught raise → silent ok=true 0-card page).
- **Gate 2** — console `total` **1,345 → 386** real; `honest_gaps 98` · `quarantined 311` ·
  `dedup {layer_exception_twins:277, fill_gap_mirrors:273}` — exactly the predicted split; blanks untouched.
- **Gate 3** — DG gap run (`r_dd90453138`): **1** new fill_gap row (was 4/event) carrying the AI's real note;
  parity invariant holds: Σ per-card distinct served render.gaps (20) == sink stage=="reason" rows (20).
- Registry drift: 14 dangling_marked (the known rows), 0 dangling_unmarked, `sweep.cli registry-drift` exit 0.
- pcc1a-v1: `test_config_defaults_check -m live` green.
- Gate 4 (emit-failed skeleton): 13 offline pins green; not force-faulted on prod (knob-gated,
  `layer2.emit_failed_skeleton` rollback documented).

## Deliberately NOT done here (owned elsewhere / follow-ups)

- **roster-DIFF + max_tokens guillotine + prompt diet** — the concurrent emit-diet session owns these
  (`emit.diet.roster` / `emit.diet.morph_shape` flags, per-stage `llm.max_tokens.<stage>`, forensics-backed;
  commit c795870+). My planned 5.3/5.4 items were dropped to avoid duplication.
- **llm.global_concurrency** — operator already enabled at 4 (wait 300) before my enable SQL landed;
  `db/fix_enable_llm_admission_20260715.sql` kept as a guarded no-op documenting the audit's 8.
- **Ops**: vLLM `--enable-prefix-caching`, `--max-model-len` drift normalization, `llm.prompt_budget_tok`
  recalibration — operator items (audit 05 F3), blocked on the emit-diet bake.
- **P4 data/content backlog**: nameplate OCR seeding; per-class GLBs (pcc-1b/2a/2b/3a/3b files exist,
  rows unseeded); HHF feeder panel links; PCC incomer 164/166 → live-twin repoint.
- **Full 18-page SSR re-cert**: deferred — the other session is actively sweeping vLLM; firing an 18-page
  sweep now would manufacture the exact contention the audit documents. Run after their campaign settles.
- Historical blank-telemetry rows are untouched (report-side classification only, replay-safe) — steady-state
  blank RATE drops from the write-after-prune change (~50× roster floods gone, ~10% false positives gone).
