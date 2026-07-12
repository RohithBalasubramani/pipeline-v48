# Prod-Readiness Audit — Lens: fixes-verification
**Date:** 2026-07-12 · **Auditor:** differential fixes-verification lens
**Scope:** verify every "Fixes Applied" claim in `docs/audit_2026-07-12/AUDIT_REPORT.md` (items 1–22 + the concurrent-session credits R2/R7/domain-kernel) against the code as it stands right now.
**Method:** READ-ONLY. Read every claimed file; `py_compile` on all touched modules (PASS); exercised TTLCache expiry behavior live (PASS); `pytest --collect-only -q` (PASS — matches the claim byte-for-byte). No DB writes, no server touches, no full pytest.

**Bottom line: 22 of 22 claims are PRESENT-and-correct.** Nothing claimed "Fixed"/"EXECUTED" is absent or reverted. Three small NEW findings (all low): one half-applied envelope stamp, one stale-doc drift caused by a fix landing AFTER the report was written, and one never-cache-empty nuance inside the brand-new admission-control code itself.

---

## Verification matrix

| # | Claim (AUDIT_REPORT.md §Fixes Applied) | Status | Evidence |
|---|---|---|---|
| 1 | `cfg()` never-cache-empty | **PRESENT-and-correct** | `config/app_config.py:21-57` — `_CACHE` set only on success (:40), failure returns `{}` uncached (:47), 5 s backoff (:23,:32), stderr log (:45), `_load.cache_clear` hook preserved (:57) |
| 2 | `ttl_cache` TTL-aware `get()` + eviction | **PRESENT-and-correct** | `data/ttl_cache.py:50-53` (get mirrors `__contains__`), :55-63 value-before-timestamp write, :65-76 purge-on-write. **Exercised live:** expired entry reads absent via both idioms AND is physically purged on next write |
| 3 | `conn_kwargs` connect_timeout + keepalives + opt-in statement_timeout | **PRESENT-and-correct** | `config/neuract_dsn.py:83-99` — `connect_timeout` default 5 (:94), keepalives 1/10/5/3 (:95-98), `statement_timeout` only when `neuract.statement_timeout_ms>0` (:84-86). Both pooled doors inherit via `data/neuract_pool._key/conn` (:36,:50) |
| 4 | neuract `_COLS_CACHE`/`_LOGGED_CACHE` → TTLCache + never-cache-empty | **PRESENT-and-correct** | `_LOGGED_CACHE = TTLCache()` `ems_exec/data/neuract.py:24`; `_COLS_CACHE` now the SHARED TTLCache in `data/neuract_pool.py:28,91-108` — caches only non-empty (`if cols:` :106-107); registries door upgraded too (`registries/neuract/_db.py:15,62`) |
| 5 | `copilot/starters.py` fallback not cached | **PRESENT-and-correct** | `copilot/starters.py:68-69` cache only non-empty success; :84-93 fallback returned WITHOUT `_CACHE=` assignment, with intent comment |
| 6 | `copilot/db.py` PGCONNECT_TIMEOUT | **PRESENT-and-correct** | `copilot/db.py:29` `PGCONNECT_TIMEOUT="5"` in subprocess env |
| 7 | `layer2/schema.py` dead no-op deleted | **PRESENT-and-correct** | file is a clean 24-line validator; zero `pass` tokens remain |
| 8 | `gate_template_dedup.py` removed, `gate_no_dup` covers it | **PRESENT-and-correct** | file absent from `layer2/swap/`; `gate_no_dup.py:6` `forbidden = set(template_card_ids) | set(already_chosen) | set(page_card_ids)`; removal noted `swap/decide.py:29` |
| 9 | `db/seed_conn_timeouts.sql` exists | **PRESENT-and-correct** | exists; `ON CONFLICT (key) DO NOTHING` (:26); knob keys (:12-22) byte-match the `cfg()` keys in `neuract_dsn.py:84-98` — no seed/code key drift |
| 10 | R1 executor budget real | **PRESENT-and-correct** | `host/exec_cards.py:222` deadline, :234 `as_completed(futs, timeout=…)`, :243-244 `except _FTimeout`, :245-252 finally marks unfinished (via `status_by_id` membership — exception-completed cards NOT mislabeled) + `ex.shutdown(wait=False, cancel_futures=True)`. Budget read per call, not import (`_exec_budget_s()` :20-21) |
| 11 | R4 LLM global admission, default-off | **PRESENT-and-correct** (one nuance → OBS-3) | `llm/client.py:113-125` `BoundedSemaphore` iff `llm.global_concurrency>0`, else `False` sentinel; :212-213 acquire w/ `llm.admission_wait_s` fail-open, :223-225 release-only-if-held in `finally`; `db/seed_llm_admission.sql:9,13,16` declares both knobs default 0/60 with `DO NOTHING` |
| 12 | payload_store + compare/detect never-cache-empty | **PRESENT-and-correct** | `host/payload_store.py:70` ("DB hiccup — do NOT cache") and :94 (cache only on read-success) for both `_skeleton_payload`/`_raw_default_payload`; `layer1b/compare/detect.py:38-41` alias index built LOCALLY, published only after the full read succeeds |
| 13 | R8 pytest.ini offline default | **PRESENT-and-correct** | `pytest.ini`: `addopts = -m "not live"`, `testpaths = tests`, `pythonpath = .`, `live` marker declared. **Measured:** `--collect-only -q` → `992/1029 tests collected (37 deselected) in 0.73s` — matches the claim exactly |
| 14 | R9 `db/apply.py` migration ledger | **PRESENT-and-correct** | `db/apply.py` — `schema_migrations(filename, sha256, applied_at)` (:37-39), sha256 (:47), `--status`/`--dry-run` (:84-85,:99,:111), records on apply (:121) |
| 15 | R3 `db/create_neuract_ts_indexes.py` dry-run generator | **PRESENT-and-correct** | dry-run by default, `--apply` explicit (:20-28); IMMUTABLE `ts_imm()` wrapper DDL (:41-43); `CREATE INDEX CONCURRENTLY`; per-table tz-offset uniformity gate (:61) |
| 16 | R5/R6 Django security (moved `ems_backend`) | **PRESENT-and-correct** | ALL in `/home/rohith/desktop/BFI/backend/ems_backend`: env `DJANGO_SECRET_KEY` fallback+warning (`backend/settings.py:30-32`), `DEBUG` default False (:35), env `ALLOWED_HOSTS` (:37), credentialed-wildcard CORS closed (:123-129 — allow-all ⇒ credentials=False), env DB creds (:159-163); kcauth secret env-only empty-default (`kcauth/keycloak_config.py:36`), **no stray secret literals anywhere in the tree** (swept); `db_link` gone from BOTH `lt_panels/serializers.py:55` and `assets/serializers.py:54` (comments only); `/healthz` (`backend/urls.py:25,:39`); `requirements.txt` present+pinned. **The old `pipeline_v45/ems_backend` path is a SYMLINK → `../../ems_backend`** — no stale duplicate, the fixes exist in the one real tree |
| 17 | R10 `types.ts` union + `api.ts` res.ok | **PRESENT-and-correct** (comment now stale → OBS-2) | `host/web/src/types.ts:136-151` `DashboardResult | KnowledgeResult` on `kind`; `api.ts:116,123,137,157` `if (!res.ok) throw` before `.json()` |
| 18 | CHANNEL_LAYERS / DEFAULT_PERMISSION env-driven | **PRESENT-and-correct** | `backend/settings.py:91-100` `DJANGO_REDIS_URL` → Redis else InMemory; :71-76 `DJANGO_REQUIRE_AUTH` → IsAuthenticated else AllowAny. Both default-inert |
| 19 | R8 live-test tail marks | **PRESENT-and-correct** | `pytest.mark.live` present in all 9 named files (orchestrator 1, layer1a_routing 4, layer1b_asset_resolve 4, available_pages 1, render_guarantee_50 2, foundations 2, column_basket 3, item21 1, reconcile_no_data 5); `V48_LIVE_CERT` gate on the matrix build (`test_render_guarantee_50.py:186`) |
| 20 | `_finalize_inner` split → `metadata_resolve.py` | **PRESENT-and-correct** | `layer2/metadata_resolve.py` exists; re-exported `build.py:31`; `_finalize_inner` measured **257 lines** (claim ~259); build.py now 442 lines |
| 21 | R3 paired code side (`ts_index_fn` knob) | **PRESENT-and-correct** | `config/neuract_dsn.py:52-58` + `ems_exec/data/neuract.py:112-121` — empty knob → byte-identical `::timestamptz`; set → `schema.ts_imm(col)` |
| 22 | `assets/` db_link closed, app KEPT | **PRESENT-and-correct** | `assets/serializers.py:54` removal comment, field gone; app directory still present (verify-before-dead outcome honored) |
| R2 | pooled `q()` + `V48_DB_ENGINE` rollback (concurrent session) | **PRESENT-and-correct** | `data/db_client.py:31` `_ENGINE` default `pool`, :54-56 psql rollback dispatch, COPY-CSV parity (:7-9), one-retry self-heal (:11,:155); `data/neuract_pool.py` is the shared pooled door |
| R7 | contextvar run-id + `run_traced` wired (concurrent session) | **PRESENT-and-correct** | `obs/trace.py:16-17` ContextVars, :86 `current_run_id()`; `host/server.py:155,167` `run_traced` wraps every request; context PROPAGATES into pools: `lib/parallel.py:30` + `host/exec_cards.py:232` `copy_context().run` (L2 fan-out routes through `run_parallel`, `run/layer2_all.py:69`) |
| dom | `domain/` kernel breaks ems_exec→layer2 cycle (concurrent session) | **PRESENT-and-correct** | `domain/{quantity_class,asset_3d,metric_affinity}.py` exist; `ems_exec/executor/measurable_resolve.py:233,253` import `domain.quantity_class`; `layer2/quantity_class.py` is a sys.modules facade; only remaining `layer2` mention in ems_exec is a prose comment (:272). `run/parallel.py` facade → `lib/parallel.py` intact |

---

## Findings (NEW — differential)

### OBS-1 · low · safe — multi-asset envelope missing the `kind:"dashboard"` stamp (half-applied fix)
`host/server.py:97` now stamps `"kind": "dashboard"` on the single-asset `build_response` envelope (closing the report's residual), but the duplicated multi-asset envelope `host/multi_asset.py:115-139` (`build_response_multi`) does NOT — it returns `ok/prompt/run_id/…/multi_asset:True` with no `kind`. Behavior is unbroken today (the FE treats any `kind !== "knowledge"` as dashboard, `types.ts:149-150`), but this is exactly the H20 envelope-drift class, and the comment on server.py:97 ("makes … DashboardResult non-optional") is only true for one of the two dashboard envelopes — making the discriminant required in types.ts would silently mistype every multi-asset response. **Fix (safe, 1 line):** add `"kind": "dashboard",` to the `multi_asset.py:115` dict.

### OBS-2 · low · safe — stale docs: the `kind` stamp is DONE but two docs still say it isn't
`host/web/src/types.ts:134-135` comment: "build_response does NOT currently stamp `kind` on the wire — the discriminant is optional until it does"; `docs/audit_2026-07-12/AUDIT_REPORT.md:310-311` "Genuinely remaining" still lists "The `kind:"dashboard"` server-side stamp … left to the session that owns host/". Both are now false — `host/server.py:97` stamps it (landed after the report was written, evidently by the host-owning session). Cross-session doc drift only; update both (and consider making `DashboardResult.kind` required once OBS-1 lands).

### OBS-3 · low · safe — the new admission-control sizing is itself vulnerable to the pinned-empty-config class
`llm/client.py:117-125`: `_ADMISSION` is sized ONCE from `cfg('llm.global_concurrency', 0)` on the first LLM call and "fixed for the process" (documented as deliberate, like a pool size). But `cfg()` fails open to the code default on a cmd_catalog blip — so if the FIRST LLM call of the process races a :5432 hiccup/reseed, an operator-enabled admission cap (row set to e.g. 4) resolves to 0 and pins `_ADMISSION=False` (disabled) for the process life, silently defeating the very back-pressure R4 added. Fail direction is open (no outage), but it contradicts the never-cache-empty campaign the same audit completed. **Fix (safe):** when `_ADMISSION is False`, re-resolve on a later call (only the False→sem transition; never resize a live semaphore).

---

## Positively verified OK (summary strings)

- Fix1 cfg() never-cache-empty + backoff + cache_clear hook — app_config.py:21-57
- Fix2 TTLCache TTL-aware get/eviction — exercised live: expired entry absent via both idioms AND purged on write
- Fix3 conn_kwargs connect_timeout=5/keepalives/opt-in stmt-timeout — neuract_dsn.py:83-99; seed keys byte-match code keys
- Fix4 shared _COLS_CACHE TTLCache never-cache-empty (neuract_pool.py:91-108) + _LOGGED_CACHE TTLCache (neuract.py:24); registries door upgraded too
- Fix5 starters fallback returned uncached — starters.py:84-93
- Fix6 PGCONNECT_TIMEOUT=5 — copilot/db.py:29
- Fix7 layer2/schema.py clean; no dead no-op
- Fix8 gate_template_dedup.py gone; gate_no_dup.py:6 folds template_card_ids into forbidden
- Fix9 seed_conn_timeouts.sql present, DO NOTHING, keys match
- Fix10 R1 budget real: as_completed(timeout)+cancel_futures+per-call budget; exception-completed cards not mislabeled (status_by_id membership)
- Fix11 R4 semaphore default-off; release-only-if-held correct; seed rows 0/60 DO NOTHING
- Fix12 payload_store (:70,:94) + compare/detect (:38-41) never-cache-empty
- Fix13 pytest.ini offline default; measured collection 992/1029, 37 deselected, 0.73s — matches claim exactly
- Fix14 db/apply.py ledger (sha256, --status, --dry-run, record-on-apply)
- Fix15 ts-index generator dry-run default, IMMUTABLE ts_imm, CONCURRENTLY, uniformity gate
- Fix16 ALL Django security fixes present in the MOVED /home/rohith/desktop/BFI/backend/ems_backend; old pipeline_v45 path is a symlink (no stale duplicate); no stray secret literals
- Fix17 types.ts union + api.ts res.ok (4 sites)
- Fix18 CHANNEL_LAYERS/DEFAULT_PERMISSION env-driven, default-inert
- Fix19 live marks in all 9 named test files + V48_LIVE_CERT gate
- Fix20 metadata_resolve.py extraction; _finalize_inner 257 lines; build.py 442
- Fix21 ts_index_fn knob wired end-to-end, default byte-identical
- Fix22 assets/ db_link removed; app kept per verify-before-dead
- R2 pooled q() default + V48_DB_ENGINE=psql rollback + CSV parity + one-retry self-heal
- R7 contextvar trace + run_traced wired + copy_context propagation in BOTH pool seams (lib/parallel.py:30, exec_cards.py:232)
- domain/ kernel real; layer2.quantity_class + run/parallel are sys.modules facades; ems_exec imports domain
- py_compile PASS on all 19 touched modules; server.py:97 kind stamp confirmed live in build_response
