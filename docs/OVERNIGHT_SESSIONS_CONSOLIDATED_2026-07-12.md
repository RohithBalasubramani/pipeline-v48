# V48 overnight session consolidation — 2026-07-11 20:34 UTC → 2026-07-12 07:46 IST

**What this is.** Between roughly **2:04am and 7:45am IST on 2026-07-12**, **19 separate Claude Code chat windows** ran concurrently against `pipeline_v48` (all rooted at the `pipeline_v47` working directory, but every task explicitly targeted v48). This document reconstructs what each one actually did, verified against the live filesystem/DB/git state as of this writing — not just what each session *claimed* in its own transcript. It was built by condensing all 19 raw session transcripts (stripping images/tool-result blobs), then fanning out one verification agent per session (plus manual verification for the one that failed structured output), each independently re-checking files, running tests, and querying the live DB.

Three sessions were excluded as stale (last real activity from 2026-07-06 through 2026-07-09, unrelated to this batch, only picked up by a filesystem mtime false-positive): a CMD-V2 session about emailing a folder, a "git full folder" session, and an old debugging session about voltage cards.

---

## TL;DR

- **19 chat windows, one shared working tree.** Everyone knew about everyone else — sessions repeatedly detected concurrent edits, deferred to each other, or explicitly coordinated (division of labor on the admin console, "don't touch this file, X is mid-edit," audits cross-referencing each other's findings docs).
- **Only 15 commits landed all night** — `5bd6891`..`d97f5cc`, all on one thread (the live validation campaign / compare-lane defect hunt, session `091476f9`). **Everything else — the entire refactor campaign, the 15-lens audit's fixes, the plugin architecture, observability, the admin console, replay engine, payload diff tool, AI decision inspector, latency profiler, property tests, and the dependency-graph fixes — is sitting uncommitted in the working tree.** `git status --short` currently shows **506 modified/untracked paths**.
- **Nothing was lost**, as far as this audit can tell — every claimed deliverable was independently re-verified present and functional on disk (imports resolve, tests pass, live services respond) — but it is all one `git add -A` / accidental `git checkout .` away from disaster, and it is genuinely hard to attribute which uncommitted change belongs to which session anymore.
- **One real regression was found**: `test_multi_asset.py::test_natural_compare_ids_fail_open_on_outage` now fails because a later session moved `asset_candidates` to a different import path than an earlier session's test expected. Small, easy fix, not yet done.
- **One doc is already stale**: `docs/audit_2026-07-12/architecture.md` (part of the 15-lens audit) flags two dependency cycles and the psql-subprocess DB client as open problems — both were already fixed by a different concurrent session (527db1ef) before that doc was finalized.
- **The validation campaign's headline defect (the "pump" 3-way compare case) was still unresolved when this audit started, and got closed literally while this audit was running** — commit `d97f5cc` at 07:46 IST.

---

## Session index

| # | Session | Task | Status | Active window (IST) |
|---|---------|------|--------|----------------------|
| A1 | `e0b5c9cb` | Refactor campaign — DB-driven cleanup ("do all this for pipeline v48") | Completed | 2:04–6:02am |
| A2 | `6ad09ae7` | Full 15-lens architectural audit + backlog-finish | Completed | 2:12–7:34am |
| A3 | `75037b14` | Dead code / duplication audit, fully implemented incl. DB table drops | Completed | 2:12–7:27am |
| A4 | `28ec694e` | Hardcoded business-logic audit → mapping/config moves | Mostly complete (tail unfinished) | 2:13–7:38am |
| A5 | `8f16dbce` | Plugin-friendly architecture refactor | Completed | 2:12–7:26am |
| A6 | `527db1ef` | Dependency graphs, cycles, coupling, god modules — audit **and implementation** | Completed | 2:12–7:45am |
| B1 | `9e3a3584` | Observability: trace_id + structured per-stage logs | Completed | 2:10–6:17am |
| B2 | `de623596` + `81d4d397` | Admin dashboard / Pipeline Explorer (same feature, two sessions, merged) | Completed | 2:11–6:45am |
| B3 | `e04d2ade` | Payload Diff Tool | Completed | 2:11–3:48am |
| B4 | `01b1bbe3` | Replay engine (trace_id → full re-execution) | Completed | 2:11–6:10am |
| B5 | `28467701` | AI Decision Inspector | Completed | 2:11–6:31am |
| B6 | `523200ed` | Latency profiler (mined + live) | Completed | 2:12–3:02am |
| C1 | `1e579c4d` | Property-based test suite | Completed | 2:14–6:00am |
| C2 | `32c73ee6` + `94fffcfb` | Prompt testing framework + DB-driven prompt corpus (same framework, two sessions) | Completed | 2:11–5:53am |
| C3 | `091476f9` | Live validation run → root-caused & fixed 8 real pipeline defects | Completed | 1:56–7:46am |
| D1 | `f7543cf6` | ARCHITECTURE.md (onboarding-grade docs) | Completed | 2:13–3:11am |
| E1 | `96aa8bc1` | "Production readiness audit" — dispatched a 15-way workflow, got cut off ~9 min in | Aborted, partial | 7:28–7:41am |

Grouped by theme below (A = refactor/architecture, B = observability/debug tooling, C = testing/validation, D = docs, E = incomplete).

---

## A. Refactor & architecture campaign (6 sessions)

These six sessions were effectively **one distributed campaign** sharing `docs/findings/refactor_20260712/` and `docs/audit_2026-07-12/` as coordination surfaces. Treat this whole section as a single effort with six contributors, not six independent projects.

### A1 — `e0b5c9cb`: Refactor campaign
**Ask:** a 20-point "make this a highly structured, DB-driven, reusable, maintainable codebase" refactoring brief, behavior-preserving.

Ran a 9-dimension audit (via a Workflow that got killed once by a session-limit wall, findings persisted to disk and resumed), then executed 8 gated batches inline, each verified by a targeted-then-full pytest run:
- Cruft/docs cleanup (10 dead placeholder tests deleted, stale root docs moved into `docs/`, `contracts/` archived, log/tmp files cleaned).
- Config hygiene: `config/policy_read.py` (new — the one DB-policy reader, dedups ~13 copy-pasted `_esc` clones), lazy PEP-562 config modules, DB knob-drift fixes.
- Dedup: `ems_exec/executor/blank.py` (the one blank-leaf predicate), `llm/transient_retry.py` (the one retry policy — and **deleted** `layer1b/guardrail/retry_one.py`, which was blindly re-sending deterministic failures and doubling hangs).
- Monolith splits: `layer2/build.py` 818→502 lines (window/reconcile/cross-domain extracted), `layer2/gates.py` 841 lines → `layer2/gates/` package, `fab_guards.py` 972 lines → `fab_guards/` package.
- Structure moves: `partition/` → `layer1a/partition/`, `layer2/emit/data/` → `layer2/emit/instructions/`, `services/` → `lib/`.
- Frontend: fixed a **pre-existing build break** (card-47 missing a new required field), added shared `icons.tsx`/`ErrorBoundary.tsx`/`HonestBlankTile.tsx`/`useSiteStatus.ts`, deleted all 17 `(result as any)`/`(card as any)` casts.

**Final suite: 1039 passed / 7 skipped / 1 failed** (the 1 was pre-existing, confirmed non-regression; later fixed by a different concurrent session). FE `tsc`+`vite build` green.

**Caveat found in verification:** git evidence shows a *different* session's commit (`a1b8c16`) captured this session's `git mv` of `partition/` mid-rewrite (old import content briefly committed under the new path) — a concrete example of the shared-working-tree hazard, though the file's current content is correct.

### A2 — `6ad09ae7`: Full 15-lens architectural audit + backlog-finish
**Ask:** treat V48 as pre-production-at-enterprise-scale; audit everything (code quality, architecture, hardcoding, DB, API, React, Django, AI pipeline, performance, concurrency, security, testing, observability); implement safe fixes.

This is the deepest single artifact of the night: **`docs/audit_2026-07-12/AUDIT_REPORT.md`** (374 lines) plus 15 lens sub-reports, produced via a 15-lens workflow with adversarial re-verification of Critical/High findings, live-measured against the real Postgres instances. The verdict: *"a disciplined, unusually well-reasoned codebase... the production-readiness gaps are operational, not correctness-of-logic, and cluster around ~6 root causes found independently by 3–5 lenses each."*

**Top findings** (full detail in the report):
1. **Critical** — the `:5433` tunnel can wedge the whole host (no connect/statement timeouts + a dead executor budget + one shared DB connection).
2. **Critical** — `::timestamptz` cast defeats every time index on the ~13M-row neuract tables (measured 80× slower).
3. **Critical** — Django `ems_backend` is a dev toybox: hardcoded `SECRET_KEY`, `DEBUG=True`, `AllowAny` everywhere, a **committed Keycloak admin secret** enabling unauthenticated privilege escalation.
4. High — no admission control anywhere (vLLM, DB, HTTP); no auth/CORS on any of the 4 ports; 485MB of unrotated logs; the new obs-trace layer was 0% wired at audit time (fixed by a concurrent session same night).

Over 5 implementation passes it landed **essentially the entire R1–R10 backlog**: never-cache-empty fixes everywhere, neuract connect-timeout+keepalives (the flagship tunnel-flap fix), a real executor wall-clock budget, a global vLLM admission semaphore (default-off), `pytest.ini` + CI test tiers (offline collection cut from a >2min hang to 0.69s), a migration ledger, a `::timestamptz` index generator (241/302 tables indexable, dry-run), and full Django hardening (removed the committed secret, env-driven `SECRET_KEY`/`DEBUG`/`CORS`/permissions, dropped `db_link` from two serializers, pinned `requirements.txt`). It also correctly detected and avoided duplicating three other sessions' in-flight work (the pooled-DB engine, the obs trace layer, the dependency-cycle fix).

**Verification:** re-ran a clean pytest subset (65/65 passed) and confirmed every named fix is present with correct logic, not stubs.

**Open, owner-gated items:** the Keycloak secret rotation, the `::timestamptz` index DDL apply (needs plant-schema rights), flipping `DJANGO_REQUIRE_AUTH`/`DJANGO_REDIS_URL` once V48 sends auth tokens.

### A3 — `75037b14`: Dead code / duplication audit — fully implemented
**Ask:** find unused files/functions/APIs, duplicate utilities/components/SQL/prompts/business logic, unreachable code, unused DB tables/config; report + recommend (don't auto-delete).

Built ad-hoc analyzers (AST import/call graph over 528 modules, a Vite import graph over 145 FE files, DB-consumer classification against live `cmd_catalog`, content-hashing for duplication) and cross-validated against the A1/A2 sessions' overlapping docs rather than re-deriving them. Report: **`docs/CODEBASE_AUDIT_UNUSED_DUPES_2026-07-12.md`**.

On "implement," it actually executed the plan: removed 33 dead functions across 27 files, **dropped 6 reader-less DB tables live from `cmd_catalog`** (`endpoint_policy`, `band_policy`, `limit_override`, `live_window_policy`, `card_rendering`, `card_render_map` — snapshotted first, independently confirmed gone), created 6 new dedup "home" modules, fixed a real bug (multi-asset compare wasn't defaulting the prompt-derived date window), and pruned dead FE wire-fields end-to-end.

**Verification:** re-ran the full offline suite myself — **986 passed, 1 failed**. The 1 failure (`test_natural_compare_ids_fail_open_on_outage`) is a genuine small regression: a *later* session (`091476f9`) moved `asset_candidates` to a new import path (`layer1b.resolve.asset_candidates`) after this session ended, stale-ing a test's monkeypatch target. **This is the one real cross-session regression found in this whole audit** — small, not caused by either session's own logic being wrong, just import-path drift. Not yet fixed.

### A4 — `28ec694e`: Hardcoded business-logic audit
**Ask:** find hardcoded page/asset/story/card mappings, thresholds, constants, prompts, config; move to DB where sensible.

Found that A1/A2 had already closed most threshold/config drift, so this session's real contribution was the **mapping layer**: moved the narrative card→page fallback map and the asset table→equipment-class vocabulary into `app_config` JSON knobs, wrote `docs/findings/refactor_20260712/mappings-addendum.md` with explicit keep/move verdicts, and closed 4 numbered follow-up items from A1's ledger (F6 knob-home consolidation — 54 scalar knobs migrated with 100%-parity verification; F10 half-knob retirement; F7 — built `config/endpoints.py` as the one `:8770/:8772/:8200` home). It also surfaced two genuine judgment calls to the user via `AskUserQuestion` (power-factor-of-record 0.9 vs 0.8; DG voltage statutory band 5% vs flat 10%) and implemented both decisions with DB seeds + new tests.

**Status: mostly complete.** A final "do the rest of the deferred backlog" push only got two small items done (pytest pythonpath, a `ttl_cache` facade move) before the transcript trails off mid-investigation of a larger item — treat that tail as not done.

### A5 — `8f16dbce`: Plugin-friendly architecture
**Ask:** registries/factories so new asset classes, page families, renderers, card types, AI providers, and executors need minimal-to-no code changes.

Delivered five concrete plugin seams, all independently verified live:
1. **Renderers** self-register via `HANDLING_CLASSES`; `ems_exec/renderers/__init__.py` discovers them via `pkgutil`.
2. **Roster slot modes** self-register via a `MODES` dict, replacing a 10-branch `if/elif`.
3. **Asset-class vocab** moved to `app_config` DB rows with code-default fail-open mirrors.
4. **New `llm/providers/` package** — `llm/client.py` is now provider-neutral, selected via env or DB knob.
5. **FE component barrels** — the monolithic `components.ts` split into per-family files merged via `import.meta.glob`.

Wrote **`docs/EXTENDING.md`** — the "how to add a plugin" recipe page, including an explicit list of what was deliberately *not* made pluggable (the reducer chain, `fill.py`'s certified pass order, FE envelope shapes, copilot/knowledge LLM bindings) — a scoping decision worth preserving.

Also found and fixed, as a side effect of chasing test failures, a genuine unrelated bug: `run/harness.py` had `validation_blocked` outranking the no-data lane, making a resolved-but-dark asset's honest-blank skeleton path unreachable dead code.

**Verification:** live-imported all three registries; a drop-in smoke test (throwaway renderer/mode/provider file, then removed) proved zero-code-change dispatch. Full suite 1034 passed / 5 failed initially, 4 attributed to a concurrent session's in-flight fix (later confirmed green), 1 the harness bug this session itself fixed.

### A6 — `527db1ef`: Dependency graphs, cycles, coupling — audited *and implemented*
**Ask:** dependency graphs for FE/backend/DB/AI/services/repos/hooks/utils; circular deps, high coupling, god modules, poor boundaries, unused modules; suggest improvements.

This is the session whose output doesn't live under `docs/` — it published a Claude Artifact and wrote memory notes instead, then (on "implement all") went well beyond analysis: **killed all 4 confirmed import cycles** via a new `domain/` kernel package, **replaced the psql-subprocess DB client with a pooled psycopg2 engine** (4.8× faster, byte-parity tested), made the CMD_V2 frontend path relocatable (was a hardcoded absolute path), wrote systemd units for all three V48 services, **archived ~459MB of dead pipeline trees** (`pipeline_v44`, `pipeline_v44_backup`, `pipeline_v46`, `p_v45_failed`), renamed `validation/`→`sweep/` (see C2/C3), and extracted `ems_backend` out of the dead `pipeline_v45` tree into `backend/ems_backend`.

**On explicit user request it also enabled and started the systemd units** — confirmed independently: `v48-host.service`, `v48-admin.service`, `v48-web.service` are all `loaded/active/running` right now on `:8770`/`:8790`/`:5188`.

**⚠️ This is where the audit found a real coordination gap.** A6's dependency-cycle fix and DB-pooling fix were **never cross-referenced into `docs/audit_2026-07-12/architecture.md`** (A2's output). That doc — finalized *after* A6's fixes had already landed — still lists both as open problems needing work. No harm was done (A6's facade pattern kept old import paths working, and the sessions cooperated at the code level), but **`docs/audit_2026-07-12/architecture.md` is stale on those two specific points** and should be corrected or annotated.

---

## B. Observability & debug tooling (6 sessions)

### B1 — `9e3a3584`: Observability — trace_id + structured per-stage logs
Built the foundational `obs/` package (`trace.py` contextvar propagation, `span.py` the one stage-boundary primitive, event/bus/sink fan-out to console/JSONL/Postgres, LLM/DB capture taps, HTTP middleware) plus `cmd_catalog.obs_*` schema (4 tables, 5 dashboard views, DB-tunable retention). Wired all 11 requested stages across 13 entry-point files. This became the substrate every other B-session built on top of.

**Verified live right now:** the 4 `obs_*` tables are populated with **20 traces, 2,594 stage events, 660 LLM calls, 104,309 DB queries**, timestamped hours after this session ended — confirming the instrumentation is genuinely capturing live traffic, not a one-off demo.

### B2 — `de623596` + `81d4d397`: Admin dashboard / Pipeline Explorer (merged)
Two sessions were independently asked for essentially the same thing (a comprehensive internal admin console vs. a "Pipeline Explorer" debug page) and **discovered each other mid-build and split the work rather than duplicating it**: `de623596` owned the `admin/` backend (15 modules, `:8790`) and most of the design docs; `81d4d397` contributed the FE foundation (`api.ts`, the canonical 9-stage taxonomy, `stageMap.ts`, shared display primitives) plus three backend spine enrichments (per-card exec latency, L2 confidence, knowledge-gate run_id). `81d4d397` drafted its own trace/run view components, found `de623596` had already built better-integrated equivalents, and deleted its own drafts rather than shipping a duplicate.

**Result is one coherent console, not two.** Verified live: `curl localhost:8790/admin/api/health` → 332 indexed runs; the SQL report endpoint shows 513,646 tracked SQL executions; AI usage shows 14,576 calls / 156M tokens tracked. Both sessions also jointly root-caused and fixed a stale-fixture test (`test_layer1_reconcile_no_data.py`, paired with A5's harness.py fix).

### B3 — `e04d2ade`: Payload Diff Tool
`tools/payload_diff/` (11 modules) — compares two pipeline executions across page/cards/metadata/bindings/SQL/validation/renderer-payload, dark/light self-contained HTML reports, exits code 2 on REAL→EMPTY regressions (usable as a cert gate). Added `obs/sql_trace.py` as a new SQL-observability leg since per-run SQL wasn't persisted before this. Survived two session-limit interruptions by falling back to inline work.

**Verified:** 18/18 unit tests pass; CLI runs live against 325 real logged runs; 3 real HTML diff reports + 2 snapshots exist on disk.

### B4 — `01b1bbe3`: Replay engine
`replay/` (14 modules) — captures full-fidelity per-request state (LLM calls, all 4 SQL doors with typed rows, pandas probes, executor fills, config/env snapshots) at 8 choke points, keyed on the B1 trace_id. `replay.cli replay <trace_id> [--mode pinned|live]` re-executes through the real `host.server` entry points and auto-generates a side-by-side IDENTICAL/DRIFT/DIVERGED/MISSING comparison report.

**Verified live and working:** `outputs/traces/` has 110 real trace bundles (timestamped past this session's own end, meaning the host is still capturing). Ran a real pinned replay myself — most sections IDENTICAL, some correctly flagged DRIFT because the DB tunnel happened to be down during verification (an honest degrade, not a bug). Live-mode replay separately surfaced a genuine external finding: vLLM returns different completions for byte-identical prompts under load (batching nondeterminism) — worth flagging to whoever owns the LLM serving layer.

### B5 — `28467701`: AI Decision Inspector
Built directly on B1's obs foundation: `obs/llm_tap.set_decision()` stamps every LLM call across all 7 AI stages with params + a size-bounded decision (candidates/selected/rejected/reasoning), a read-side `obs/decision_view.py` extractor, `/api/inspector/*` endpoints, and a three-pane `InspectorView.tsx` UI wired into the app header.

**Verified live:** `cmd_catalog.obs_llm_calls` has 71 rows already carrying real captured decision data; the inspector endpoints on the (since-restarted) live host return real trace data.

### B6 — `523200ed`: Latency profiler
`profiler/` (11 modules), two modes: "mine" (parses 1,287 historical runs from existing logs, zero live services needed) and "live" (in-process instrumented sweep of 13 real prompts). Computed avg/median/p95/p99/worst-case for every requested stage, published charts and an **interactive HTML dashboard Artifact** (screenshotted and visually verified via Playwright across two fix passes).

**Headline numbers (mined, n=1287):** median e2e **37.8s**, p95 **172s**, p99 **219s**, max **303s**. Real findings beyond raw numbers: the live sweep revealed **1b Asset Resolution is DB-bound, not LLM-bound** (expensive `has_data` UNION probes, ~7.4s avg / 29s worst), and Layer 2 emit floor is ~19.8s/card at concurrency=4 — the two biggest levers if latency work continues.

---

## C. Testing & validation (3 threads, 4 sessions)

### C1 — `1e579c4d`: Property-based test suite
`tests/property/` — 6 requested invariants (capitalization/whitespace/alias-invariant resolution, historical-routing, knowledge-never-dashboards, off-domain-rejection) plus extra fabrication-closure fuzzing. Two tiers: offline (44 tests, ~4,000 randomized cases via LLM-faked holders) and live (9 tests against real pinned-seed Qwen). Ran genuine mutation testing — injected 4 known regressions, 3 turned tests red, restored byte-identical source after.

**Verified:** re-ran the offline tier myself — **44 passed, 9 deselected**, matching the session's own numbers almost exactly.

### C2 — `32c73ee6` + `94fffcfb`: Prompt testing framework + DB-driven prompt corpus (merged)
Two sessions built one framework. `94fffcfb` built the DB-driven corpus generator (3 new `cmd_catalog` tables — 18 categories/42 templates/95 vocab rows — plus 7 mutator files for casing/spelling/abbrev/partial/plural/aliasing/conversational wrapping); `32c73ee6` discovered a *third* concurrent session had already built the surrounding scaffold (runner/checks/reports/CLI, committed as `5041cd3`) and filled 4 gaps instead of duplicating: `stagelogs.py` (per-case log snapshotting), `regression.py` (baseline-vs-session diff, exit-1 on new failures), pinned-asset case support, and a `replay-failed` CLI subcommand.

**Verified live:** `python -m sweep.cli generate` reproduces **30,747 deterministic cases** in ~1 second, byte-identical across reruns; `python -m sweep.cli stats` matches every claimed per-category number.

**Housekeeping note:** the package was later renamed `validation/` → `sweep/` by session A6 as part of its cycle-breaking work; a compat alias makes both names work.

### C3 — `091476f9`: Live validation run → 8 real defects found and fixed
A long-running, persistent Claude Code session (open since 2026-06-23, this is just its overnight tail) that first built its own copy of the validation framework, then **actually fired it at the live pipeline** and used the failures to root-cause and fix real bugs in the compare/asset-resolution path. This is the thread that produced **all 15 commits that actually landed in git overnight** (`5bd6891` .. `d97f5cc`).

**8 defects found and fixed, all commit-backed:**
1. Punctuation-heavy compare names silently degraded to a single asset (`_SEP` regex gap).
2. "Phantom-alias" infix false-positives (a 5-chiller compare found 9 rows because one asset's name contained another's alias as a substring).
3. Kept-name mutilation (stripping one asset's pattern could corrupt *another* asset's name mid-string).
4. Resolver lexical-neighbor substitution — the model silently swapped an explicitly-named asset for a similarly-named different one.
5. Concurrent tunnel sweeps flap-erroring the same compare (now share one candidate probe).
6. No-data/pending resolutions were mislabeled `cards` instead of `picker`.
7. Page-coverage parser bug (page identity lives on the top-level `page` object, not per-card).
8. A named-but-dark member in a compare wasn't counted as a confident resolution.

**Campaign record: `docs/validation_campaign_1.md`** (committed). At the time this audit began, one defect (a 3-way "pump" compare case) had gone through 8 replay rounds without closing, blocked by a real DB-tunnel outage during testing — **it closed while this audit was in progress**, commit `d97f5cc` at 07:46 IST: *"pump six-layer excavation final disposition (round-8: compare 3 groups, 0 errors)."*

**Known follow-up:** `docs/validation_campaign_1.md` itself is now slightly stale — it still says defect #4 is "re-replay pending" even though 5 more commits (including the closing one) landed after that doc was written.

---

## D. Documentation

### D1 — `f7543cf6`: ARCHITECTURE.md
An 829-line onboarding-grade doc at the pipeline_v48 root — 18 sections, 6 Mermaid diagrams, DB schema/endpoints verified against live `psql` at write time. Verified accurate on structural claims (endpoint list matches `host/server.py` routing exactly); a few point-in-time counts (table counts, `app_config` row counts, test-file counts) have already drifted because so many other sessions kept editing the DB/tests overnight — expected, not an error.

---

## E. Incomplete / aborted

### E1 — `96aa8bc1`: "Production readiness audit" — cut off ~9 minutes in
Started very late (7:28am IST, well after the other 18 sessions had mostly wrapped), dispatched a 15-way parallel workflow doing a *differential* audit (one lens per sub-agent, told to persist findings incrementally). All 15 sub-agents were killed mid-tool-call in the same ~15-second window about 9 minutes after launch — the whole session ran out of wall-clock time, not the individual agents finishing. A live 6-case smoke test it also kicked off *did* complete cleanly (6/6 HTTP 200), but that artifact only exists in a session scratchpad, not the repo.

**Result:** `docs/audit_prodready_20260712/` has 15 files; **4 have real, evidenced findings** (`security.md`, `data-layer.md`, `docs-dx.md`, `layer2-grounding.md` — e.g. security.md flags the admin console on `:8790` as completely unauthenticated), the other 11 are empty stubs. **The requested deliverable (one prioritized report + a production-readiness verdict) was never produced.** No code was touched; nothing committed. Worth mining the 4 substantive files in a follow-up rather than re-auditing from scratch.

---

## Cross-cutting risks & recommended next actions

1. **Commit the work, deliberately, in reviewed batches.** 506 files are uncommitted right now, representing ~18 sessions' worth of real, verified, working code plus DB migrations. This is the single biggest risk from tonight — one careless `git add -A && git commit` would flatten 19 sessions' provenance into one indistinguishable blob; one careless `git checkout .` would lose all of it. I did not commit anything (per your standing instruction to only commit when asked) — this needs a deliberate pass, probably grouped by the A/B/C sections above.
2. **Fix the one real regression:** `tests/test_multi_asset.py::test_natural_compare_ids_fail_open_on_outage` fails because `asset_candidates` moved import paths after the test was written (found during A3's verification).
3. **Correct or annotate `docs/audit_2026-07-12/architecture.md`** — it lists two problems (import cycles, psql-subprocess client) as open that session A6 already fixed the same night.
4. **`docs/validation_campaign_1.md`** needs a small update — defect #4 now reads "pending" but closed in commit `d97f5cc`.
5. **DB-only artifacts are uncommitted**: `db/prompt_corpus_schema.sql`, `db/seed_prompt_corpus.sql`, and several other `db/*.sql` migration files are live-applied to `cmd_catalog` but not in git — a fresh clone or DB rebuild would silently lose them.
6. **Owner-gated action items from the A2 audit, still open:** rotate the Keycloak secret (currently in git history), apply the `::timestamptz` index DDL (needs plant-schema rights), flip `DJANGO_REQUIRE_AUTH`/`DJANGO_REDIS_URL` once V48 sends auth tokens, apply the F6 phase-2 legacy-knob-drop script after one clean cert cycle.
7. **The three new systemd services are live right now** (`v48-host`, `v48-admin`, `v48-web`, all on their expected ports since session A6 enabled them) — worth knowing before starting your own dev-server copies on the same ports.

---

## Source material

Raw session transcripts were condensed to `~/.tmp/claude-1000/.../scratchpad/condensed/*.txt` (one file per session UUID) and are not part of the repo. This document is the durable artifact; the per-session verification detail (file-by-file checks, exact commands run, exact test counts) lives in the workflow journal at `~/.claude/projects/-home-rohith-desktop-BFI-backend-layer2-pipeline-v47/.../subagents/workflows/wf_f32fffcc-17c/journal.jsonl` if deeper drill-down is ever needed.
