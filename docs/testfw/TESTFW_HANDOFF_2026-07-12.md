# V48 Prompt Testing Framework — Status (updated 2026-07-12 ~03:40)

> **RENAMED 2026-07-12 (same day, after handoff):** the package `validation/` is now **`sweep/`** — the
> `validate/` vs `validation/` name collision was flagged by both the refactor-campaign ledger (follow-up #1)
> and the architecture audit. Every `python -m validation.cli …` line below still works via a compat alias
> package; prefer `python -m sweep.cli …` going forward. Output paths (`outputs/validation/`) are unchanged.

## TL;DR

The framework EXISTS and is feature-complete: **`pipeline_v48/validation/`** (built 2026-07-12 by two concurrent
sessions co-editing; corpus/runner/judge/analyzers by one, gap-fill modules by the other). It is DB-driven
(cmd_catalog `prompt_category` / `prompt_template` / `prompt_vocab`, seeded via `db/seed_prompt_corpus.sql`,
`db/prompt_corpus_schema.sql`), generates **30,747 deterministic cases** across 18 workflow categories
(budgets = DB rows, the size dial), runs them in parallel with vLLM-safe throttling, captures per-stage logs,
judges per-category expectations, and emits coverage / failure / regression / JSON / HTML reports.

## Entry points

    cd pipeline_v48
    python -m validation.cli generate                 # corpus from live universe x DB templates -> outputs/validation/corpus.jsonl
    python -m validation.cli stats                    # per-category counts vs DB budgets (shortfalls reported)
    python -m validation.cli run --limit 200 --concurrency 2 [--category X] [--session NAME]
    python -m validation.cli report|coverage [--session S]
    python -m validation.cli replay <case_id> | replay-failed [--session S]
    python -m validation.cli regress --baseline <sid> [--session <sid>]     # exit 1 on new_fail
    python -m validation.cli determinism --limit 10 --repeats 3
    python -m validation.cli datesync [--session S]   # /api/frame reslice checks (no-LLM lane)

Session artifacts: `outputs/validation/sessions/<sid>/{manifest,metrics,coverage,failures,report,regression}.json`,
`report.html` (self-contained), `cases/<case_id>.json` (replayable record), `raw/<case_id>.json` (full response),
`stagelogs/<case_id>/` (per-stage pipeline logs snapshotted at case time).

## Module map (atomic, one concern per file)

- `config.py` — knobs (env-overridable): run lane default 2 / max 3 (vLLM contention!), frame lane 8, 420s run
  timeout, 900s compare-lane timeout (`timeout_for`), auto-throttle window, `ARCHIVE_AI` policy, dirs.
- `response.py` — THE /api/run parser; 7-outcome vocabulary (cards/picker/knowledge/refused/empty/unavailable/
  compare); every field gotcha encoded (candidates under asset.*, verdict-is-optimistic → leaf_stats, page_key on
  top-level page object, ascii_safe surrogate guard).
- `corpus/` — `universe.py` (cmd_catalog ground truth: registry_lt_mfm classes, unique names, homonym tokens,
  pcc aliases, page_layout_cards), `store.py` (DB rows, fail-open to `templates.py` mirror), `fill.py` (slot
  grounding), `mutators/` (casing/spelling/abbrev/partial/plural/aliasing/conversational), `mutate.py`,
  `generate.py` (deterministic sub-seeded streams; budgets downsample).
- `runner.py` — parallel executor: per-lane semaphore throttle + rolling-error auto-halve, full artifact capture,
  per-case judgment; case `pin`/`pins` → `asset_id`/`asset_ids`; **stagelogs capture at case time** (run_id is
  deterministic per prompt — later same-prompt fires overwrite outputs/logs); **unexpected-picker resume leg**
  (diagnostic re-POST pinned to first has_data candidate; original judgment stands; manifest counts resume_legs/
  resume_completed).
- `checks/expectations.py` — the judge (honesty-aware: unavailable-on-cards-case = degraded pass; payload_error
  ALWAYS fails as layer2_emit). `checks/determinism.py` (structural fingerprint repeats), `checks/datesync.py`.
- `stagelogs.py` — per-case snapshot of `pipeline_/failures_/ai_<rid>.jsonl` + notes into the session dir, plus
  log-reason mining -> `{'<stage>:<reason>': count}` (fine-grained auto-categorization: llm:timeout,
  layer1b:stage_error, exec:card_fail, ...). ai_ log archived per `V48_VALIDATE_ARCHIVE_AI` = fail(default)/all/never.
- `failures.py` — failure inventory grouped by stage/category/class/page + degraded-by-why.
- `coverage.py` — achieved-vs-universe matrix (pages/cards/classes/assets/categories) + uncovered lists.
- `metrics.py` — latency percentiles overall + per category; totals incl. fabrication + leaf fill_pct.
- `regression.py` — case-id join of two sessions: new_fail/fixed/still_fail/newly_degraded/recovered_degraded/
  corpus-drift; latency + coverage delta; verdict flips ONLY on new_fail.
- `report_json.py` (diff-stable) / `report_html.py` (self-contained human dashboard) / `replay.py` (single +
  replay_failed) / `cli.py` (dispatch only).

Tests: `tests/test_prompt_corpus.py`, `tests/test_validation_regression.py`, `tests/test_validation_stagelogs.py`,
`tests/test_validation_runner_legs.py` (all offline, all passing as of tonight).

## Operational rules (hard-won, do not relearn)

- **Concurrency ≤2-3** on /api/run — vLLM contention manufactures fake llm timeouts. Compare lanes need the 900s
  client timeout. /api/frame is no-LLM (lane 8 fine).
- **Coordinate live fires across sessions**: tonight NINE concurrent pytest runs + live sweeps from parallel
  sessions contended on CPU/vLLM. Before a live sweep: check `ls -lt outputs/logs/pipeline_*.jsonl | head` for
  fresh writes and `ps -ef | grep pytest`. The corpus/report/regress sides are all offline-safe.
- Honest-blank / unavailable are PASS-degraded, not failures; picker on ambiguous categories is a PASS.
- Corpus shortfalls (knowledge 93/400, off_domain 54/300) are vocab-pool limits, reported by `stats`, not bugs.

## Remaining niceties (optional)

1. Live regression demo blocked twice by lane contention tonight — run when quiet:
   `bash outputs/validation/regress_demo.sh` (waits for quiet lane, runs regress_base/regress_new 8-case slices,
   then `regress`). Unit tests already cover the mechanics.
2. Corpus-side: derive `ambiguous` tokens from real homonym grouping (universe.homonym_tokens regex known
   degenerate — GIC-N prefixes; see map gotcha) — DB vocab rows can override without code.
3. Wire `regress` into a cron/CI loop against a pinned baseline session id.

## Reference

Subsystem map (6 parallel readers, file:line refs): `docs/testfw/v48_subsystem_map_2026-07-12.json`.
Sessions so far: `smoke_1` (36 cases, 33 pass), `compare_recheck` (12 compare cases, 6 pass — compare-lane
timeout fix followed). Corpus: `outputs/validation/corpus.jsonl` (30,747).
