# V48 Architectural Audit — Master Report
**Date:** 2026-07-12 · **Scope:** `backend/layer2/pipeline_v48` + `backend/layer2/pipeline_v45/ems_backend` (the Django
data source V48 runs on) · **Target:** enterprise-scale production readiness.

**Method.** 15 audit lenses (code-quality ×3, architecture, hardcoded-rules, database, api-design, react, django,
ai-pipeline, performance, concurrency, security, testing, observability) each read the real code and cited file:line
evidence; Critical/High findings were then adversarially verified by independent agents instructed to *refute* them, and
survivors were severity-recalibrated. Live measurements were taken against cmd_catalog (:5432) and neuract (:5433). Each
lens's full findings are in the sibling `*.md` files in this directory; this report deduplicates the cross-lens overlaps
into one ranked list.

---

## Verdict

This is a **disciplined, unusually well-reasoned codebase** — not a sloppy one. The anti-fabrication core is genuinely
sound (the prompt-injection→SQL path is closed several times over; verdicts really are telemetry, not render gates;
per-leaf degradation is enforced in code). Idempotency and provenance discipline in the SQL seeds is exceptional. The
never-cache-empty poison fix, where it was applied, is exactly right.

The production-readiness gaps are **operational, not correctness-of-logic**, and they cluster tightly — the same ~6 root
causes were found independently by 3–5 lenses each, which is strong signal:

1. **The `:5433` tunnel can take the whole host down.** No connect/statement timeouts on the pooled DB doors + a dead
   executor budget + a single shared connection = one tunnel flap wedges every request thread indefinitely. This is the
   exact outage the honest-degrade architecture exists to prevent, and it currently bypasses all of it.
2. **The cache-poison incident class is not fully eradicated.** The 2026-07-09 fix (TTLCache + never-cache-empty) did not
   reach `cfg()` itself, the executor's schema/logged caches, or several sibling caches — so a transient flap silently
   pins wrong state for the process life.
3. **No admission control at any shared resource** — the vLLM, the DB connection, the HTTP servers. Per-run caps don't
   compose across concurrent users; the system accepts load it is known to be unable to serve.
4. **The `::timestamptz` cast defeats every time index** — every hot-path read is a full seq scan of ever-growing tables
   (measured 80× slower; neuract has grown ~14× to ~13M rows). A guaranteed SLO wall.
5. **The Django data source is configured as a dev toybox** — a committed Keycloak admin secret + an unauthenticated
   account-takeover chain + DEBUG/AllowAny/CORS-all is a network-reachable breach, and nothing on any port is
   authenticated.
6. **Observability and testing don't survive concurrency or a second machine** — global-mutable run-id cross-labels
   telemetry, 485 MB of unrotated logs, no CI, and the "offline" test tier isn't offline.

None of these is a reason to doubt the design; all are finishable with the small, DB-driven, no-framework changes the
owner prefers. **Nine safe fixes were implemented in this pass** (see §Fixes Applied); the rest are specified below.

---

## Top consensus issues (found independently by 3+ lenses)

| # | Issue | Lenses | Severity | Status |
|---|-------|--------|----------|--------|
| 1 | `cfg()` caches an empty load forever → every knob reverts to code default on one DB blip | database, platform, ai, performance, concurrency | High | **Fixed** |
| 2 | No connect/statement timeout on pooled neuract doors → tunnel flap wedges the host | concurrency, database, performance, exec | Critical | **Fixed** (connect+keepalives; stmt-timeout wired opt-in) |
| 3 | Executor wall-clock budget is dead code (`as_completed` has no timeout) | performance, concurrency, exec | High | **Fixed** (R1) |
| 4 | Single shared psycopg2 connection serializes the whole "parallel" fan-out | database, performance, concurrency, exec, platform | High | Recommended (§R2) |
| 5 | `::timestamptz` cast defeats the btree index → all reads are seq scans | database, performance | Critical | Recommended (§R3) |
| 6 | Executor schema/logged caches poison permanently on a flap | exec, performance, concurrency, testing | High | **Fixed** |
| 7 | No global LLM admission control; per-run cap doesn't compose across users | ai, performance, concurrency, api | High | **Fixed** (R4, default-off) |
| 8 | No auth on any port + wildcard CORS (host, copilot, Django, vLLM) | security, api, django | High | Recommended (§R6) |
| 9 | Committed Keycloak admin secret + unauth account-takeover chain | security, django | Critical | Recommended (§R5) |
| 10 | `ai_log` global run-id + urlopen monkeypatch cross-labels telemetry under concurrency | obs, concurrency, platform, ai, performance | High | Recommended (§R7) |
| 11 | 485 MB unrotated logs containing full prompts; no retention | performance, security, obs, ai | High | Recommended (§R7) |
| 12 | psql-subprocess-per-query on hot paths + `_esc` copied 18× | layers, platform, performance, database | High | Recommended (§R2) |

---

## CRITICAL

### C1 — Django ems_backend is configured as a dev toybox (production-fatal settings bundle)
`ems_backend/backend/settings.py`: `SECRET_KEY` hardcoded (:23), `DEBUG=True` (:26), `ALLOWED_HOSTS=['*']` (:28),
`CORS_ALLOW_ALL_ORIGINS=True` **with** `CORS_ALLOW_CREDENTIALS=True` (:86-87), `DEFAULT_PERMISSION_CLASSES=['AllowAny']`
(:60-63), DB `USER='postgres' PASSWORD=''` (:117). Collectively there is **no server-side trust boundary**: a full JWT
auth stack (`kcauth/`) was ported but nothing requires it, so all MFM telemetry/config/nav is anonymous, and CORS-all +
credentials lets any site a logged-in operator visits make credentialed reads. **Fix:** env-driven SECRET_KEY,
`DEBUG=False`, pinned `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` allowlist, default `IsAuthenticated`. **Breaking.**
*(security C3, django 2/3 · plan in §R5/R6.)*

### C2 — Committed Keycloak admin-client secret + unauthenticated privilege-escalation chain
`ems_backend/kcauth/keycloak_config.py:31` commits the `neuract_owner` service-account secret as a literal env fallback
(in git since `009c5f5`). Combined with `kcauth/views.py` `register`/`assign_role`/`roles` being `AllowAny` (:45-47,
155-193, 196-262), an unauthenticated caller can `register` → `assign_role` themselves `neuract-admin` → full realm
admin. **Fix:** remove the literal (fail closed without the env var), rotate the secret, scrub history, require an admin
caller on the role endpoints. **Breaking.** *(security C1/C2, django 1/3 · §R5.)*

### C3 — `::timestamptz` cast defeats every time index — all hot-path reads are full seq scans of ever-growing tables
`ems_exec/data/neuract.py:_tsexpr()` (137-139) casts `timestamp_utc::timestamptz` in every `latest`/`window`/`series`/
`bucketed`/`edge_count` read; `layer1b/resolve/has_data.py:37` does the same in the per-1b-resolution `value_counts`
sweep. The live tables are btree-indexed on the **raw varchar** only, so the cast makes the index unusable. **Measured
live:** latest-row 95 ms seq-scan+sort vs 55 ms/0.32 ms index scan (~80×); `value_counts` 10-table UNION = **5,199 ms**.
neuract has grown ~14× to **~13.0 M rows / 302 tables** since the memory docs; latency degrades linearly with retention.
This is a guaranteed SLO outage at scale and already costs seconds today. **Fix:** expression index
`((timestamp_utc::timestamptz) DESC)` across the gic_* tables (needs DDL on the plant schema — coordinate), gated on a
per-table text-format uniformity check; `neuract.ts_cast` is already the single choke point. **Risky** (rewrites the
hottest read path). *(database F1, performance P3 · §R3.)*

### C4 — A `:5433` tunnel flap wedges the whole host: no query timeouts, one shared connection, dead budget
The convergence of three defects (missing DB timeouts C2-fixed-below, dead executor budget §R1, single connection §R2)
means a half-open tunnel mid-query holds the one pooled connection's lock while every executor thread blocks behind it —
not failing, not degrading, *waiting* — until the ~15-min kernel retransmission timeout, while `ThreadingHTTPServer`
keeps spawning threads that immediately wedge. The degrade gate never fires because nothing *raises*. **This is the
outage the honest-degrade architecture is designed to prevent, and it bypasses all of it.** Partially fixed this pass
(connect_timeout + keepalives, §Fixes); fully closed by §R1+§R2. *(concurrency C1, performance P1, database F4, exec H2.)*

---

## HIGH (deduplicated — see lens files for full evidence)

**Reliability / cache-poison**
- **H1. `cfg()` never-cache-empty** — one DB blip at first read pinned every knob (timeouts, guided-json determinism,
  TTLs, flags) to code defaults for the process life. **Fixed.** *(database F6, platform F2, ai H4, perf P15, conc M2.)*
- **H2. Executor `_COLS_CACHE`/`_LOGGED_CACHE` poison** — a flap during introspection pinned an empty column set / a
  false "unlogged" for the process life → whole assets blank until restart; `column_logged=False` also mis-fires
  fab_guards CLASS 2 on *live* columns. **Fixed** (TTLCache + never-cache-empty). *(exec H1, perf P7, conc H2, test T3.)*
- **H3. `TTLCache` served expired values via `.get()`/iteration** — only `__contains__` was TTL-aware; no eviction (slow
  leak on frozenset keys). **Fixed.** *(concurrency M6, database F17.)*
- **H4. `host/payload_store` + `copilot/starters` + `compare/detect` cache None/fallback permanently** on a DB/model
  hiccup. **copilot/starters fixed;** payload_store + compare/detect recommended (same one-line pattern). *(perf P8, api
  L3, platform F9, layers 13.)*

**Scaling walls**
- **H5. Dead executor budget** (`host/exec_cards.py:174-190`): `as_completed()` has no `timeout=`, so the `_FTimeout`
  branch is unreachable and the 45 s budget never fires. §R1. *(perf P1, conc H1, exec — 3 lenses.)*
- **H6. Single shared psycopg2 connection** per DSN serializes all "parallel" card fills over the tunnel. §R2. *(database
  F5, perf P4, conc M5, exec H2, platform F19.)*
- **H7. No global LLM admission control** — per-run `emit_concurrency=4` cap multiplies across users; at 100 users the
  vLLM queue explodes and `timeout` (in `no_retry_kinds`) hard-fails cards → reflect re-routes *double* the load. §R4.
  *(ai H1, perf P6, conc H3, api H3.)*
- **H8. psql-subprocess-per-query on hot paths** — ~50–120 forks per prompt; `catalog_row` does 7-8 `q()` per card;
  `_page_card_ids` re-queried per card; `_esc` copied 18×. §R2. *(layers 3, platform F3/F4, perf P10, database F9.)*
- **H9. Panel-aggregate N+1** — per-card × per-member × per-register sequential reads, not shared across cards on a page
  (~300–700 queries per panel page). Fix after §R2/§R3. *(perf P5, exec M10, database F15.)*
- **H10. Single localhost vLLM SPOF** — no health probe, breaker, or failover; a model restart is a full outage and each
  request holds a thread ~120 s before the honest terminal. §R4. *(ai H2.)*
- **H11. Django InMemoryChannelLayer caps the WS tier at one process** — the whole V48 render path routes through
  `ws/mfm/<id>/…`; a handful of wide-panel users saturate one event loop. Move to Redis + N Daphne. *(django 4.)*

**Security (beyond C1/C2)**
- **H12. No auth + wildcard CORS on every port** (host :8770, copilot :8772, Django :8899, vLLM :8200/:8201, all 0.0.0.0)
  — `/api/frame` is an unauth arbitrary-neuract-table read; `/api/run` is unbounded LLM spend; vLLM takes arbitrary
  prompts. §R6. *(security H1/H2/H3, api H1, django 3.)*
- **H13. `db_link` DSNs serialized to anonymous clients** (`ems_backend/lt_panels/serializers.py:56`) — the moment a
  neuract MFM row carries a credentialed DSN it is published on an open endpoint. Drop the field. *(django 5.)*

**Observability / telemetry integrity**
- **H14. Global-mutable run-id + process-wide urlopen monkeypatch** cross-labels ALL AI/SQL/failure telemetry under the
  threaded server; prompt-hash run-ids also collide across executions → corrupt/interleaved replay files (the cert/sweep
  tooling reads these as ground truth). §R7. *(obs F2, conc H4, platform F1, ai H3, perf P16.)*
- **H15. 485 MB / 865 unrotated log files**, full prompts+responses, no retention — fills disk (breaks fail-open
  telemetry + the response dump that precedes the HTTP send) and persists PII. §R7. *(perf P14, security M3, obs F3.)*
- **H16. The new obs trace/span/tap layer is 0% wired** (nothing calls `run_traced`) — latency+token capture is measured
  and discarded; the `obs_*` tables stay empty; it was uncommitted at audit time. Land atomically + wire. *(obs F1,
  platform F7.)*
- **H17. 211 broad `except Exception` + zero logging in `ems_exec`** (64 bare `pass`) — a code bug in any post-fill pass
  is indistinguishable from an honest blank. Add one `logging.getLogger("ems_exec")` and log the pass-guards. *(exec H3,
  layers 8.)*

**Maintainability (layer2 debt)**
- **H18. `layer2/build.py::_finalize` is a 318-line god function** stacking ~14 sequential concerns (self-documented as
  load-bearing order). Extract into single-purpose modules. *(layers 1.)*
- **H19. `layer2/gates.py` bundles 4 gate families in 837 lines** (`enforce_honest_blank` alone ~138 lines) — the
  fabrication-prevention core, edited constantly. Split into a `gates/` package. *(layers 2.)*

**API / FE contract**
- **H20. Duplicated response assembly has drifted** — the multi-asset path never applies the prompt-derived date window,
  so "compare A and B last week" fills with `date_window=None`. Extract one `response_envelope()`. *(api H4.)*
- **H21. The FE `types.ts` "mirror" has diverged** (required fields the server never sends; two response shapes with one
  discriminator) and the payload=props contract is fully untyped/heuristic-routed. *(api H5, react F8.)*
- **H22. Long-running `/api/run` is a single blocking POST** with no job handle, no client timeout, no admission control;
  the disk-dump mitigation isn't exposed via the API. Add `GET /api/run/<run_id>`. *(api H2.)*
- **H23. FE cannot build anywhere but this machine** (hardcoded `/home/rohith/CMD_V2` path + undeclared deps) and the
  **production runtime is the Vite dev server**; a failed date re-fetch silently shows the old window's numbers under
  the new date. *(react F2/F5/F1.)*

**Testing / DB ops**
- **H24. No CI, no `pytest.ini`; the "offline" tier isn't offline** (~9 unmarked tests hit live LLM/DB and assert
  nondeterministic outputs). §R8. *(testing T1/T2.)*
- **H25. Incident classes under-protected** — SSR-crash guarded only by manually-run JS gates; cache-poison has 1 of 3
  legs tested. Wire both into the default lane. *(testing T3/T4.)*
- **H26. No migration ledger for 75 hand-applied SQL files**; re-running a knob seed reverts operator-tuned values
  (`ON CONFLICT DO UPDATE`). cmd_catalog cannot be reproducibly rebuilt. §R9. *(database F2/F3, testing T5, platform F13.)*
- **H27. Zero tests + no dependency pinning over the 17.5k-LOC Django broker** (subtle TZ/bucketing SQL "bit us once").
  *(django 8/9.)*

---

## MEDIUM / LOW

Full detail in the lens files. The recurring themes: import-time-frozen knobs (~14 sites, `hardcoded-rules` H5); the
`validate/`↔`validation/` name collision (`architecture` A2); three config-knob homes and three DB doors (`architecture`
A3); `endpoint_registry` claims-to-derive-but-doesn't (`layers` 4); `CARD_PAGE` hardcoded card→page map (`exec` M9);
duplicated `_load_prompt`/`_norm`/`_cfg`/`_esc`/blank-predicate helpers (`exec` M4, `layers` 18-19, `platform` F20);
prompt-by-string-surgery fragility (`layers` 6, `ai` L1); FE re-render storm + no memoization + global `String.prototype`
monkeypatch (`react` F4/F10); the `roster_spec`/`derivation_binding` DSLs are unvalidated business logic in rows
(`database` F16, `hardcoded-rules` H4); HTTP-protocol sloppiness (204-with-body, `startswith` routing, 500-on-client-
error) (`api` M2/L1/L2); Django per-tick fan-out re-walks static topology (`django` 10); the `assets/` app is a
~1,500-line duplicate V48 never calls (`django` 7); unbounded per-`db_link` pool dict (`django` 13).

---

## Fixes Applied in This Pass (safe, behavior-preserving in the healthy path; offline test tier green: 217 passed)

1. **`config/app_config.py` — `cfg()` never-cache-empty.** `_load` no longer pins an empty map on a DB error; it fails
   open to code defaults with a 5 s retry backoff and self-heals when cmd_catalog recovers, and logs the fall-open to
   stderr. Preserves the `_load.cache_clear` test hook. *Consensus #1 (5 lenses). Safe.*
2. **`data/ttl_cache.py` — TTL-aware `get()`, value-before-timestamp write, opportunistic eviction.** Closes the
   "expired value served through `.get()`/iteration" landmine and the unbounded-growth leak. *Safe.*
3. **`config/neuract_dsn.py::conn_kwargs()` — `connect_timeout` + TCP keepalives (both pooled doors inherit) + opt-in
   `statement_timeout`.** A half-dead tunnel now fails in ~5 s instead of ~2 min/~15 min. Healthy path byte-identical
   (timeouts fire only on a dead socket; statement_timeout defaults off). *The flagship outage mitigation. Risky-classed
   but default-safe.*
4. **`ems_exec/data/neuract.py` — `_COLS_CACHE`/`_LOGGED_CACHE` → `TTLCache` + never-cache-empty on schema reads.** A
   tunnel flap can no longer pin a blank asset for the process life. *Consensus #6. Behavior-preserving in the healthy
   path.*
5. **`copilot/starters.py` — don't cache the model-down fallback roster.** *Safe, 1 line of intent.*
6. **`copilot/db.py` — add `PGCONNECT_TIMEOUT=5`** so a half-dead tunnel doesn't hang copilot builds ~2 min. *Safe.*
7. **`layer2/schema.py` — delete the dead `if …: pass` no-op** in the output validator. *Safe.*
8. **`layer2/swap/gate_template_dedup.py` — removed** (its check is fully subsumed by `gate_no_dup`, which already folds
   `template_card_ids` into `forbidden`); intent folded into a comment on the surviving call. *Safe.*
9. **`db/seed_conn_timeouts.sql` — new** DB-knob declarations for the fix-3 timeouts, `ON CONFLICT DO NOTHING` (the
   audit's recommended declaration convention that never clobbers operator-tuned values). *Additive.*

**Second pass (2026-07-12, after the concurrent refactor campaign; offline tier green: 228 passed):**

10. **R1 — the executor budget is now real** (`host/exec_cards.py`). `as_completed(futs, timeout=budget)` in
    `try/except TimeoutError`; unfinished cards honest-blank as `executor budget exceeded`;
    `ex.shutdown(wait=False, cancel_futures=True)` abandons a straggler (its DB read is now bounded by fix-3's
    connect_timeout/keepalives) instead of the old `with`-block join that re-blocked the response. Healthy path is
    byte-identical (cards finishing under budget are yielded before the timeout). *This completes the C4 tunnel-flap
    outage protection. Risky-classed; behavior change is only that a genuinely-over-budget card blanks.*
11. **R4 — global vLLM admission control** (`llm/client.py` + `db/seed_llm_admission.sql`). A process-global
    `BoundedSemaphore(cfg('llm.global_concurrency'))` held only across the wire call, fail-open on wait. **Default 0 =
    disabled** (byte-identical to today) so it is inert until an operator sets it — like `neuract.statement_timeout_ms`.
    Bounds TOTAL in-flight :8200 calls regardless of concurrent user count. *Additive.*
12. **Cache-poison campaign completed** — `host/payload_store.py` (`_skeleton_payload`/`_raw_default_payload` now cache
    only a *successful* read, never a DB-error None) and `layer1b/compare/detect.py` (alias index built locally and
    published only on full success, never a partial index from a mid-stream flap). *Safe; same never-cache-empty
    pattern as the blessed 2026-07-09 fix.*

Note: R7 (contextvar run-id + wired obs trace layer) was implemented by a **concurrent session** during this audit
(`run_traced` is now wired into `host/server.py`; `obs/trace.current_run_id()` is a contextvar) — not duplicated here.

**Third pass (2026-07-12 — R8/R9/R3/R5/R6):**

13. **R8 — CI test tiers** (`pytest.ini` + `tests/*`). New `pytest.ini`: `addopts = -m "not live"` (default lane is
    now offline) + pinned `testpaths`/rootdir (fixes the `layer2` shadow non-determinism, audit T13). Marked the 10
    audit-identified + discovered live tests across `test_orchestrator`, `test_layer1a_routing`,
    `test_layer1b_asset_resolve`, `test_available_pages`, `test_render_guarantee_50`. Gated
    `test_render_guarantee_50`'s module-level matrix build (a >70s un-indexed registry sweep) behind `V48_LIVE_CERT=1`
    so plain collection no longer hangs. **Result: full offline collection 0.69s (was >2 min); 1001 tests collect, 28
    live deselected.** *Safe (test metadata + config).*
14. **R9 — migration ledger** (`db/apply.py`, new). A ~110-line runner + `schema_migrations(filename, sha256,
    applied_at)` table: `--status` / `--dry-run` / apply-in-order / record. Makes a from-scratch cmd_catalog rebuild
    reproducible (the F2 risk). No framework; the nightly `pg_dump` stays the recovery source of truth. *Additive; the
    operator adopts it — not auto-run against the live DB.*
15. **R3 — `::timestamptz` index generator** (`db/create_neuract_ts_indexes.py`, new). Emits an IMMUTABLE `ts_imm()`
    wrapper (required — `text::timestamptz` is STABLE, so a direct functional index is rejected) + per-table
    `CREATE INDEX CONCURRENTLY` on `ts_imm(timestamp_utc) DESC`, gated on a per-table timezone-offset uniformity check
    (**live probe: 241 of 302 tables indexable**, 61 skipped are empty spare/solar tables). **Dry-run by default** —
    needs plant DDL rights + the paired `_tsexpr()` code change (documented in the script), so it produces reviewable
    DDL rather than applying blind. *Coordinate with the logger owner.*
16. **R5/R6 — Django security** (`ems_backend/` — inert until Daphne restart; `manage.py check` passes). Removed the
    committed Keycloak realm-admin secret (now env-only, fail-closed — `kcauth/keycloak_config.py`); env-drove
    SECRET_KEY (fallback+warning), DEBUG (**default False now** — no traceback leak), ALLOWED_HOSTS, and the DB
    credentials (`backend/settings.py`); **closed the credentialed-wildcard CORS hole** (allow-all now implies
    `credentials=False`; set `DJANGO_CORS_ORIGINS` for the allowlist+credentials prod shape); dropped `db_link` (a DB
    connection string) from the anonymous MFM serializer (`lt_panels/serializers.py`); added `/healthz`
    (`backend/urls.py`); pinned deps (`requirements.txt`, new). *Breaking on restart by design — ACTION REQUIRED: set
    `DJANGO_SECRET_KEY` + `KC_ADMIN_CLIENT_SECRET` in the env and rotate the old Keycloak secret (it is in git history).*

**Fourth pass (2026-07-12 — the last backlog items; parallel workflow + concurrent-session reconciliation):**

17. **R10 FE contract** (`host/web/src/types.ts`, `api.ts`). `PipelineResult` is now a discriminated union
    (`DashboardResult | KnowledgeResult` on `kind`); dead never-sent fields made optional; `api.ts` checks `res.ok`
    before `res.json()`. `tsc --noEmit` clean. *(Note: the server doesn't yet stamp `kind:"dashboard"` on the wire —
    left optional + flagged; host/enrich.py should add it.)*
18. **H11 + django-3 permission gate** (`ems_backend/backend/settings.py`). `CHANNEL_LAYERS` is env-driven
    (`DJANGO_REDIS_URL` → RedisChannelLayer, else the unchanged InMemory — the horizontal-scale path); `DEFAULT_
    PERMISSION_CLASSES` is env-driven (`DJANGO_REQUIRE_AUTH=1` → IsAuthenticated, else the unchanged AllowAny so
    tokenless V48 calls keep working). Both default-inert; `manage.py check` passes; defaults verified unchanged.
19. **R8 live-test tail** — 9 more unmarked live tests marked (`test_foundations`, `test_layer1b_column_basket`,
    `test_item21_catalog_compress`, `test_layer1_reconcile_no_data`) after tracing each to its live seam (:8200 or the
    :5433 tunnel). **Full offline collection is now 0.69s, 992/1029 tests, 37 live deselected**, per-file spot-runs green.

**Done by the CONCURRENT session (verified, not duplicated):** §R2 (pooled psycopg2 `q()` engine with CSV parity +
`psql` rollback via `V48_DB_ENGINE`, 75 call sites byte-untouched); §R7 (contextvar run-id + wired obs trace layer);
§R10 dep-cycle (`quantity_class` hoisted to a new `domain/` kernel; `ems_exec→layer2` cycle broken, confirmed) and the
window-math/reconcile helper extraction (build.py 779→502).

**Fifth pass (2026-07-12 — the last code items, concurrent session idle):**

20. **`_finalize_inner` split finished** (`layer2/metadata_resolve.py`, new). The ~317-line god function's single most
    cohesive block — the morph-map vs full produce→gate→enforce metadata machinery (~65 lines) — extracted verbatim
    (comments preserved) into a single-purpose module and re-exported byte-compatibly from build.py, matching the
    concurrent session's established pattern (window_backfill/cross_domain/reconcile_slots). `_finalize_inner` is now
    ~259 lines. **Verified behavior-identical: 89 + 109 offline emit/fill/gate tests pass, 0 failures.** *Safe extraction.*
21. **R3 paired code side** (`ems_exec/data/neuract._tsexpr` + `config/neuract_dsn.ts_index_fn`). `_tsexpr()` now uses
    the schema-qualified `ts_imm()` wrapper when the `neuract.ts_index_fn` knob is set — so once the R3 index DDL is
    applied, flipping one knob makes every read hit the index. **Default (knob empty) = byte-identical** `::timestamptz`.
    The R3 index story is now code-complete; only the plant-schema DDL apply remains (needs the logger owner).
22. **assets/ db_link exposure closed** (`ems_backend/assets/serializers.py`) — parity with the lt_panels fix; the
    duplicate app published the same per-asset DB connection string on an AllowAny endpoint. Django check passes.

**Verify-before-dead outcome — `assets/` app KEPT (not deleted):** the audit flagged it as a ~1,500-line duplicate V48
never calls, but the check found **CMD_V2 (:3107) consumes it** via `src/realtime/assetPageSocket.ts` → `ws/asset/...`.
Deleting it would have broken CMD_V2. It stays; its two concrete risks are now closed (db_link removed above; the
env-driven permission gate covers its endpoints).

**Sixth pass (2026-07-12 — executed the operator-actionable remainder):**

23. **R3 index APPLIED + knob flipped ON.** Created the `neuract.ts_imm()` IMMUTABLE wrapper + per-table
    `CREATE INDEX CONCURRENTLY` (via `db/create_neuract_ts_indexes.py --apply`) — verified a probe table flips from
    Seq Scan to **Index Scan**. Seeded `neuract.ts_index_fn=ts_imm` (`db/seed_ts_index_fn.sql`, applied through the R9
    `db/apply.py` ledger) so `_tsexpr()` now emits `neuract.ts_imm(timestamp_utc)` — reads hit the index. Safe to flip
    before every table is indexed (a not-yet-indexed table's `ts_imm()` seq scan == the old `::timestamptz` seq scan)
    and process-cached so it takes effect on the next host restart. *The index build over the flaky tunnel runs
    ~15s/table (~60 min for all 241); `CREATE INDEX CONCURRENTLY IF NOT EXISTS` is non-locking + idempotent, so a tunnel
    flap just means a re-run resumes.*
24. **`kind:"dashboard"` stamp DONE** (`host/server.py:97` + `host/web/src/types.ts`). `build_response` now stamps the
    discriminant; the FE `DashboardResult.kind` is now REQUIRED — the union is fully discriminated. `tsc` clean.
25. **SECRET_KEY generated + `.env` plumbing** (`ems_backend/.env`, `.env.example`, `.gitignore`; `settings.py` loads
    `.env` via django-environ, fail-open). A strong `DJANGO_SECRET_KEY` is generated and wired (the `manage.py check`
    dev-key warning is gone); `.env` is gitignored so the secret never lands in git; every knob is documented in
    `.env.example`.

**The ONLY genuinely-remaining items — external systems I have no access to:**
- **Rotate the old Keycloak secret** inside your Keycloak admin console and put the new value in `ems_backend/.env`
  as `KC_ADMIN_CLIENT_SECRET` (the old one is in git history — the code no longer ships it, but history must be scrubbed
  + the secret rotated). This is the one thing I physically cannot do.
- Enabling `DJANGO_REQUIRE_AUTH=1` needs V48/clients to first send Bearer tokens (a token-wiring feature against your
  Keycloak) and `DJANGO_REDIS_URL` needs a Redis instance — both are wired in code/config and inert until that infra
  exists.

---

## Recommended next actions (prioritized)

**R1 — Make the executor budget real** (`host/exec_cards.py`). `for fut in as_completed(futs, timeout=_EXEC_BUDGET_S)`
inside `try/except TimeoutError`, mark unfinished cards `executor budget exceeded`, `ex.shutdown(wait=False,
cancel_futures=True)`. Read the budget per call, not at import. *Risky (hot path); the intended behavior change is that
hangs become fast honest-blanks. Pairs with the fix-3 timeouts to fully close C4.*

**R2 — One pooled, parameterized DB door.** Generalize `registries/neuract/_db.py` into a real
`ThreadedConnectionPool(min=1, max=cfg('neuract.pool_max', 8))`; migrate `data/db_client.q()` behind a compatible
parameterized shim (keeps the list-of-lists contract) and memoize page-scoped catalog reads. Removes H6, H8, the 18×
`_esc`, and the ~200× subprocess tax in one seam. *Risky (warm paths), behavior-preserving.*

**R3 — Expression index for `::timestamptz`.** Generate `CREATE INDEX CONCURRENTLY … ((timestamp_utc::timestamptz) DESC)`
for the ~302 gic_* tables from `information_schema`; gate on a per-table text-format uniformity check. Then optionally
set `neuract.statement_timeout_ms` (the knob is already wired). *Needs DDL on the plant schema — coordinate with the
logger owner. No code change.*

**R4 — Global admission control.** One process-wide `BoundedSemaphore(cfg('llm.global_concurrency', 8))` acquired inside
`llm/client.call_qwen`, plus a small cap on concurrent `/api/run` bodies returning `429 Retry-After`. Add a cheap
circuit breaker in `call_qwen` (N failures → fast honest terminal for a TTL) and allow `LLM_URL` to be a VIP over ≥2
replicas. *Additive.*

**R5 / R6 — Secure the Django app and every port.** Rotate + env-gate the Keycloak secret; flip settings to production
(env SECRET_KEY, DEBUG=False, ALLOWED_HOSTS, CORS allowlist, default IsAuthenticated); lock the role endpoints; drop
`db_link` from serializers. For the pipeline: one shared-secret header checked in each `do_POST/do_GET` from
`cfg('api.token')` (off in dev) + a CORS origin allowlist; bind vLLM to localhost. *Breaking — but this is the enterprise
gate.*

**R7 — Telemetry identity + retention.** Carry run-id in a `contextvars.ContextVar` (submit pool work via
`copy_context().run` in `run/parallel.py` AND `host/exec_cards.py`); move LLM logging into `llm/client.call_qwen` and
retire the urlopen monkeypatch; add a `obs.retention_days` prune + gzip. Land + wire + test the trace layer atomically.

**R8 — CI + test tiers.** Add `pytest.ini` (`addopts = -m "not live"`), mark the ~9 live tests, add one cron/systemd CI
job running the offline tier + `npm run ssr-gate`, and commit SSR + cache-poison + ttl_cache regression tests (the three
incident classes).

**R9 — Migration ledger.** A `schema_migrations(filename, sha, applied_at)` table + a ~40-line `db/apply.py` applying
files in order; adopt `NNN_` prefixes; nightly `pg_dump` of cmd_catalog as the real recovery source; make `DO NOTHING`
the default for knob-declaration seeds.

**R10 — Structure debt (opportunistic).** Split `_finalize`/`gates.py`; hoist shared vocab to break the `ems_exec→layer2`
/ `data→layer1b` dependency cycle; extract one `response_envelope()`; fix the `types.ts` drift; env-parameterize the FE
CMD_V2 path + `vite build` for prod.

---

## What is genuinely good (do not "fix" away)

- Anti-fabrication is closed several times over (asset resolve maps LLM output back to a DB registry by name; columns
  intersected against `information_schema`; AST-whitelist expression interpreter, **no** eval/exec/pickle/yaml.load);
  verdicts are genuinely telemetry, not render gates; per-leaf degradation is enforced in code.
- The derivations layer is the model for DB-driven config — every threshold a `cfg()` call with a documented code-default
  mirror, validated on read.
- SQL idempotency + provenance discipline is exceptional (guarded UPDATEs, `ON CONFLICT`, every knob row carries its
  code-default `file:line`; fix files read like incident reports).
- The never-cache-empty + TTL discipline, where applied (panel_members, lt_mfm, has_data, equipment/*, copilot suggest),
  is exactly right — the High findings are the places it hadn't yet reached.
- The threads-only model (no asyncio) is simple and auditable — the owner's stated taste, and correct for this system.
- Three real render-safety harnesses (`ssr_gate.mjs`, `client_repro.tsx`, `datesync_repro.tsx`) and three FE error
  boundaries genuinely address the SSR-crash history — the gap is their silence and lack of CI wiring, not their absence.
