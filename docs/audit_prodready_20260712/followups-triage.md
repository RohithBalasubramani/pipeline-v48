# Followups Triage — prod-readiness audit lens (2026-07-12, ~07:4x IST pass)

Lens: followups-triage. Every open item from EXECUTED_AND_FOLLOWUPS.md (follow-ups 1-12),
AUDIT_REPORT.md (R1-R10 + deferred), APPLY_LOG_unused_dupes_audit.md (leftovers), and the three
memory-pending items, triaged into: safe (main session implements NOW) / risky / owner-gated /
defer, or verified-DONE. Differential: items already recorded in the prior lens docs are only
re-listed here as triage rows with current in-tree status, not re-argued.

Environment facts established for this pass:
- Running host = pid 561102 under `v48-host.service`, started **07:35:27** (ss: holds :8770).
- `host/server.py` was edited at **07:38:39** (a concurrent session landed the `kind:"dashboard"` stamp
  mid-audit) → the live host is ONE edit behind its own file.
- Admin API pid 557560 on :8790 (started 07:33:48) — up.
- cmd_catalog probes were SELECT-only; no code edited.

---

## A. Memory-pending items — status

### (a) :8770 restart → pooled engine + AI Decision Inspector — VERIFIED LIVE ✅
- Pooled engine: `data/db_client.py:31` `_ENGINE = (os.environ.get("V48_DB_ENGINE") or "pool")` — default
  is pool; file mtime 06:44, host started 07:35 → running host imported the pooled engine. Direct evidence:
  `ss -tnp` shows pid 561102 holding **persistent** TCP conns to 127.0.0.1:5432 (×2) and :5433 (×2) — a
  psql-subprocess engine holds none.
- Inspector: `GET :8770/api/inspector/traces?n=2` returns real traces (newest `t_6fb1b0c9…`, 07:29:28).
  NOTE: bare `GET /api/inspector` → 404 `unknown inspector endpoint` — BY DESIGN (server.py:216-234; the
  endpoints are `/api/inspector/traces` and `/api/inspector/trace?id=`). Memory's "restart pending for
  adoption" is now satisfied.

### (b) kind:"dashboard" stamp — LANDED for single path at 07:38, but TWO gaps → OBS-1, OBS-2
- `host/server.py:97` now has `"kind": "dashboard"` in build_response (comment cites [R10]). Landed at
  07:38:39 — while this audit ran.
- Gap 1 (NEW drift): `host/multi_asset.py` `build_response_multi` envelope (return dict at ~line 117) does
  NOT stamp `kind` — multi-asset responses still lack the FE discriminant. This is exactly the H20
  "duplicated response assembly drifts" class, recreated the same day it was named.
- Gap 2: the running host (07:35:27) predates the 07:38:39 edit → live :8770 does not serve the stamp
  until the next restart.

### (c) H20 multi-asset date window — FIXED ✅ (by the unused-dupes session, APPLY_LOG Batch 5)
- `host/multi_asset.py:87-94`: when the FE sent no explicit date_window, it defaults from lane0's 1a
  preset via `host.notes.window_from_preset` — parity with build_response. Comment tagged
  "[api-design H4 parity, 2026-07-12]". Test gate: tests/test_window_extraction.py + tests/test_multi_asset.py.
- The remaining root-cause item (ONE `response_envelope()` shared by both paths) is still open — see OBS-1.

---

## B. NEW findings from this pass

### OBS-1 (HIGH, safe) — kind stamp missing from build_response_multi; envelope drift recurring
`host/multi_asset.py:117-135` (the return dict: ok/prompt/run_id/elapsed_ms/sb_base/multi_asset/…) has no
`"kind": "dashboard"` while `host/server.py:97` now does. FE `PipelineResult` discriminated union
(host/web/src/types.ts, R10 item 17) stays optional-discriminant for every multi-asset response.
**Fix (NOW):** add the one line to the multi envelope; **then** consider the H20/R10 `response_envelope()`
extraction (that part risky — hot serve path) so the third drift never happens.
**Test gate:** tests/test_multi_asset.py, `tsc --noEmit` in host/web; grep both envelopes for parity.

### OBS-2 (MEDIUM, owner-gated) — running host is one edit behind host/server.py
pid 561102 started 07:35:27; host/server.py mtime 07:38:39 (kind stamp). Live :8770 serves NO
`kind:"dashboard"`. **Fix:** one `systemctl --user restart v48-host` AFTER OBS-1 lands (one restart covers
both); coordinate — concurrent sessions were live-testing against :8770 this morning.

### OBS-3 (MEDIUM, safe) — stray second host/server.py process (bind-failed, half-alive)
pid 562703 (`session-c118.scope`, started 07:35:55, STAT Ssl) is alive but NOT bound — :8770 is held by
561102 (v48-host.service). `outputs/host.log` tail ends in the matching traceback:
`OSError: [Errno 98] Address already in use` at server.py:407 `_Server(("0.0.0.0", PORT)…)`. The process
survives via its non-main threads (obs sinks/pools started at import). Risk: duplicate background writers
+ a restart race where the stray grabs :8770 with whatever tree state it imported at 07:35.
**Fix (NOW):** `kill 562703`. No code change.

### OBS-4 (HIGH, safe) — file-log retention still missing; outputs/ grew 485MB→1.3G today
`outputs/logs` = **1.2G across 1,441 files** (largest: `ai_r_*.jsonl`, `trace_*.jsonl`); outputs/ total
1.3G. The audit (R7/H-11) measured 485MB earlier TODAY. DB-side retention EXISTS
(`obs/sink_pg.py:78-82`, `obs.retention_days` default 30, daily purge) but nothing prunes/gzips the JSONL
sink or the legacy ai_r logs — and the audit flagged they contain full prompts (PII).
**Fix (NOW):** a prune+gzip pass keyed on the same `obs.retention_days` knob in the jsonl sink (or an ops
timer unit next to v48-host.service). Test gate: unit test on the prune predicate + `du` before/after.

### OBS-5 (MEDIUM, safe) — R9 migration ledger built but unadopted: schema_migrations has 0 rows
`SELECT count(*) FROM schema_migrations` → **0**, yet ≥8 SQL changes were applied to cmd_catalog today
outside `db/apply.py`: fix_orphan_knobs_20260712, fix_knob_home_consolidation, fix_retire_roster_column_knobs,
fix_deadend_knobs_20260712, seed_pf_of_record, retire_unused_tables_20260712, seed_llm_admission,
seed_conn_timeouts. The F2 "cannot reproducibly rebuild" risk is back the day the ledger shipped.
**Fix (NOW):** backfill today's applied files into the ledger (db/apply.py record mode), adopt `NNN_`
prefixes for new files. Test gate: `python db/apply.py --status` shows all applied files recorded.

### OBS-6 (LOW, safe) — ledgers/docs stale vs the tree (3 concrete spots)
1. `APPLY_LOG_unused_dupes_audit.md:152-153` says the DROP script is "written, NOT applied …
   `.owner_gated` (rename to arm)" — but `db/retire_unused_tables_20260712.sql` header says **APPLIED
   2026-07-12 ~07:50 IST (owner authorized)** and psql confirms all six tables are gone.
2. `EXECUTED_AND_FOLLOWUPS.md:113-118` still lists follow-ups 1-3 (validation→sweep rename, ttl_cache
   move, D1 pool dedup) as NOT executed — all three are DONE in-tree (see §D).
3. Project memory (MEMORY.md) still says "only table DROPs stay owner-gated" and ":8770 restart pending".
**Fix (NOW):** one doc-refresh pass + memory update.

---

## C. Triage of the remaining OPEN backlog (per source)

### From AUDIT_REPORT R1-R10
| Item | Status | Triage |
|---|---|---|
| R1 exec budget | DONE (host/exec_cards.py:20-21 per-call `_exec_budget_s`, ER-8 as_completed+cancel_futures; 2 ledgers confirm) | verified_ok |
| R2 pooled door | DONE + LIVE (see §A.a) | verified_ok |
| R3 ts index | Code-complete (`db/create_neuract_ts_indexes.py`, `_tsexpr` + `neuract.ts_index_fn` knob). DDL NOT applied — C3 seq-scans persist. | **OBS-7 owner-gated** (plant-schema DDL rights; logger owner). After apply, set knob `neuract.ts_index_fn=ts_imm`. HIGH value. |
| R4 admission | Knob landed default **0=off** (`llm/client.py:123`). No /api/run 429 cap; no call_qwen circuit breaker. Live trace `t_6fb1b0c9…` (07:29): honest data_unavailable terminal still held a thread **121.5s**. | **OBS-8**: knob flip = owner-gated ops; 429 cap + breaker = risky code (HIGH under load). |
| R5/R6 security | Django code fixes landed (audit items 16/18/22). REMAINING: rotate Keycloak secret (in git history) + set `DJANGO_SECRET_KEY`/`KC_ADMIN_CLIENT_SECRET` env before Daphne restart; pipeline-port auth `cfg('api.token')` shared-secret header NEVER implemented (grep host/+config/ = 0 hits); vLLM still 0.0.0.0. | **OBS-9 owner-gated, CRITICAL** (secret rotation) + the api.token header is implementable-now-but-breaking (risky). |
| R7 telemetry | contextvar run-id + trace layer DONE (concurrent session); DB retention DONE (obs/sink_pg.py:78-82). File retention MISSING. | **OBS-4 safe** (above) |
| R8 CI | pytest.ini offline lane DONE (0.69s collection). NO CI job exists: ops/ = db-tunnel/v48-admin/v48-host/v48-web units only, no timer/cron running offline tier + `npm run ssr-gate`. | **OBS-10 safe**, medium |
| R9 ledger | Built, unadopted | **OBS-5 safe** (above) |
| R10 structure | FE union DONE, `_finalize` split DONE, cycle break DONE (domain/), kind stamp single-path DONE. Left: multi-path stamp (OBS-1), `response_envelope()` extraction (risky), FE vite prod build param. | OBS-1 + defer-tail |

### From EXECUTED_AND_FOLLOWUPS follow-ups 1-12
| FU | Status | Triage |
|---|---|---|
| 1 validation→sweep | **DONE** — `validation/__init__.py` is a compat-alias package (`__path__ = sweep.__path__`), real home `sweep/` (17 modules) | verified_ok |
| 2 ttl_cache→lib | **DONE** — `data/ttl_cache.py` is a re-export facade of `lib/ttl_cache.py` | verified_ok |
| 3 D1 neuract pool dedup | **DONE** — `data/neuract_pool.py` exists (APPLY_LOG 2nd pass; 102 tests green there) | verified_ok |
| 4 registries/neuract→data/neuract_live | OPEN, optional 17-file churn | **OBS-11 safe**, low — do with facade when tree quiet |
| 5 monoliths F4-F10 | OPEN: meta_path import-hook still installed (`ems_exec/executor/indexed_families.py:582-602`); fill.py 672 lines / **21** `except Exception:` sites; members.py 443; user_message.py 417; measurable_resolve.py 405. quantity_class item SUPERSEDED (hoisted to `domain/quantity_class.py`). | **OBS-12 risky** (fill hot path); measurable_resolve two-vocab consolidation sub-item = owner-gated (DB rows) |
| 6 typing F2/F3/F5/F7-F11 | OPEN — no layer2/ems_exec/layer1b `types.py` | **OBS-13 safe**, low (annotation-only, specified in typing-contracts.md) |
| 7 error-handling F3/F4 | OPEN — no `ems_exec/executor/degrade.py`, no `obs/errfmt.py`; obs session (idle) did NOT land equivalents | **OBS-14 safe**, medium — clear to implement now |
| 8 llm/parse.py extract_json | OPEN — file absent | **OBS-15 risky** (needs replay-corpus parity proof; _insight is a certified port) |
| 9 frontend F4/F11/F12/F16 | F14 DONE (retired wire fields confirmed in server.py comment ~line 80). F4 vc-sanitize = risky (client-gate over saved DG responses); F11/F12 splits = safe w/ FE gates (registry.tsx now 296 lines — urgency reduced); F16 heatmap dedup = safe | **OBS-16 mixed**, low |
| 10 owner decisions (PF 0.9 / statutory band / epoch floors) | **DONE** — `db/seed_pf_of_record.sql` + `tests/test_statutory_band_per_class.py` exist; epoch DO-NOT-UNIFY notes cross-referenced | verified_ok |
| 11 F6 phase-2 legacy-home drop | PREPARED not applied — `db/drop_legacy_knob_homes_phase2.sql` exists; `data_quality_policy` still has **52 rows** | **OBS-17 owner-gated** — gate: ≥1 clean cert/sweep cycle after today's churn; fallback-read removal is a separate semantics step |
| 12 pyproject.toml | OPEN (absent); pytest.ini rootdir pin mitigates | **OBS-18 safe**, low |

### From APPLY_LOG leftovers
- Owner-gated table DROPs → **APPLIED** ~07:50 owner-authorized; psql: endpoint_policy/band_policy/
  limit_override/live_window_policy/card_rendering/card_render_map all absent. verified_ok (+ OBS-6 doc staleness).
- `seed_schema_and_endpoints.py` split → **RESOLVED in-code**: `scripts/seed_schema_and_endpoints.py:99-101`
  retires the endpoint_policy half ("seed_endpoint_policy RETIRED 2026-07-12 … table DROPPED") — re-running
  it cannot resurrect the dropped table. (Docstring header line ~9 still describes endpoint_policy — fold
  into OBS-6 doc pass.)
- v47-only tables (payload_shapes/nameplate_config/derived_metrics) → **OBS-19 defer/owner-gated** — retire
  with v47; still read by pipeline_v47.

---

## D. Positively verified OK (this pass)
1. Pooled psycopg2 engine live on :8770 (db_client.py:31 default + persistent :5432/:5433 conns held by pid 561102).
2. AI Decision Inspector served live (/api/inspector/traces returns real traces; bare-path 404 is by design).
3. H20 multi-asset date-window fix in code (multi_asset.py:87-94) with test gates.
4. kind:"dashboard" stamped in single-path build_response (server.py:97, landed 07:38 by concurrent session).
5. FU-1 validation→sweep rename DONE (compat alias package).
6. FU-2 ttl_cache home move DONE (facade).
7. FU-3 / D1 neuract pool dedup DONE (data/neuract_pool.py).
8. FU-10 owner decisions landed (seed_pf_of_record.sql + test_statutory_band_per_class.py; epoch DO-NOT-UNIFY).
9. Six dead tables DROPPED owner-authorized; snapshots archived; seed script cannot resurrect them.
10. R1 executor budget real (per-call budget, ER-8).
11. R7 DB-side obs retention exists (sink_pg.py:78-82, default 30d).
12. R8 offline pytest lane (pytest.ini) in place.
13. R9 db/apply.py + schema_migrations table exist (adoption gap = OBS-5).
14. domain/ kernel exists (quantity_class.py hoisted — import-cycle fix stands).
15. Admin API :8790 up (pid 557560).
16. Honest-terminal outage behavior worked live at 07:29 (:5433 refused → data_unavailable terminal, no fabrication, trace captured end-to-end by the new obs layer).

## E. Suggested execution order for the main session
1. OBS-1 (multi kind stamp, 1 line) → OBS-3 (kill stray pid 562703) → OBS-2 (single host restart, coordinated).
2. OBS-4 (log retention) + OBS-5 (ledger backfill) + OBS-6 (doc refresh) — all safe, independent.
3. OBS-10 (CI timer) then OBS-14 (errfmt/degrade) — safe, medium.
4. Owner queue: OBS-7 (R3 DDL + knob), OBS-8 knob flip, OBS-9 (secret rotation + api.token decision), OBS-17 (phase-2 drop after a clean cert), OBS-19 (v47 retirement).
5. Quiet-tree refactors: OBS-11/12/13/15/16/18.
