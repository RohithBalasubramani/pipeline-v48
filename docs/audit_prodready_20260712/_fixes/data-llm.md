# Fixes — group: data-llm (2026-07-12)

Owned files: `data/db_client.py`, `data/neuract_pool.py`, `llm/client.py`.
Gates run: `py_compile` on all three (PASS); import smoke `python3 -c "import data.db_client, data.neuract_pool, llm.client"` (PASS); offline pytest on every test file referencing db_client / llm.client (`test_foundations, test_llm_truncation_budget, test_item17_guided_json, test_route_guided_json, test_decision_inspector, test_replay_engine` → 62 passed; `test_layer2_card, test_layer2_slot_catalog_series, test_layer2_swap_gates, test_prompt_corpus, test_reflect_honest_terminal, test_swap_metric_affinity, test_equipment_ratings, test_equipment_topology, test_asset3d_dg_seed, test_render_guarantee_50` → 115 passed, 5 skipped; 0 failures). Behavioral verification script (scratchpad `verify_data_llm_fixes.py`) exercised all four fixes — ALL PASSED, incl. one live SELECT-only read against cmd_catalog.

---

## 1. data/db_client.py — [data-layer OBS-1, MEDIUM]

**What:** `_q_pool()` — moved `conn, fresh = _checkout(db)` inside a try; a checkout failure (fresh `pg_connect` when the pool is empty) now routes through `_q_fail(db, sql, t0, e)` like every other failure path.

**Why:** a raw `psycopg2.OperationalError` escaping from checkout bypassed (a) the documented `RuntimeError("DB error (db): ...")` contract (`_q_psql` and both retry paths already honor it), (b) the replay tape — `replay/hooks.py:97` records failures with `except RuntimeError` only, so a pinned replay could not reproduce the degrade branch, and (c) `_q_fail`'s per-query `_sql_trace(err=...)` record.

**Fingerprint safety:** `run/degrade_gate.py` re-exports `is_outage_error` from `data/outage.py`, which substring-matches case-insensitively; `_q_fail` embeds `str(exc)[:300]` in the RuntimeError message, so `"connection to server"` / `"timeout expired"` / `"connection refused"` survive the wrap (verified in the script: `is_outage_error()` returns True on the wrapped message).

**Evidence:** monkeypatched `pg_connect` to raise `connection to server ... timeout expired` → `_q_pool` raised `RuntimeError("DB error (db): ...")`, outage fingerprint matched, and the `[db error - ...]` stderr + per-query trace fired. Healthy path untouched (live `SELECT 42` byte-identical).

## 2. data/db_client.py — [data-layer OBS-2, LOW]

**What:** `_run_on()` COPY branch — `copy_sql = sql.rstrip().rstrip(";")` before wrapping in `COPY (...) TO STDOUT (FORMAT csv)`. COPY branch only; the plain-execute fallback takes `sql` verbatim.

**Why:** engine parity trap — `psql --csv -c "SELECT 42;"` works but `COPY (SELECT 42;) TO STDOUT` is a Postgres syntax error, so a semicolon-terminated read flips working/erroring on the `V48_DB_ENGINE` rollback env var. Zero current callers pass `;` (audit AST scan), so healthy-path behavior is byte-identical.

**Evidence:** live against cmd_catalog: `q("cmd_catalog", "SELECT 42;")` → `[['42']]`, `"SELECT 42 ;  "` → `[['42']]`, `"SELECT 42"` unchanged. (Before the fix the first two raised under the default pool engine — verified live in the audit.)

## 3. data/neuract_pool.py — [data-layer OBS-4, LOW]

**What:** `drop()` — the popped connection is now captured and `close()`d (guarded, errors ignored) OUTSIDE `_LOCK`, so the FD is released immediately instead of lingering until GC. WHEN drop is called is unchanged (still every `run_read` exception — the OBS-4 identity-check half is out of this brief's scope).

**Why:** FD linger on every tunnel-flap/SQL-error drop; closing outside the lock avoids adding close latency to the shared `_LOCK` (the OBS-3 serialization concern).

**Evidence:** fake conn in `_POOL` → `drop()` popped it AND called `close()` exactly once; drop on an empty key remains harmless.

## 4. llm/client.py — [fixes-verification OBS-3, LOW]

**What:** `_admission_sem()` — the `False` (disabled) sentinel now re-resolves `llm.global_concurrency` on later calls; ONLY the `False → BoundedSemaphore` transition is permitted (a live semaphore is returned as-is, never resized or replaced). Header comment updated to document the changed sizing rule.

**Why:** `cfg()` fails open to the code default (0) on a cmd_catalog blip, so if the FIRST LLM call of the process raced a :5432 hiccup, an operator-enabled cap (row = 4) pinned `_ADMISSION = False` for the process life — silently defeating R4's back-pressure. Same never-cache-empty class the audit campaign closed everywhere else.

**Default-off byte-identical:** knob 0 (or absent) still yields no semaphore, no admission wait, fail-open — only difference is the disabled path re-reads the (success-cached) cfg dict per call, which is a dict lookup.

**Evidence:** stubbed `_cfg`: knob 0 → `False` on first and second call; knob flips to 4 → `BoundedSemaphore` created; knob then changed to 9 → SAME semaphore object returned (never replaced). Offline llm tests (test_llm_truncation_budget, test_item17_guided_json, etc.) all pass.

---

## Skipped (out of ownership / scope)

- **data-layer OBS-3** (shared `_LOCK` serializes both neuract doors across `psycopg2.connect`) — flagged "risky (hot-path lifecycle)" by the audit and not in this brief's fix list; left untouched.
- **data-layer OBS-4 second half** (`run_read` drops on ANY exception incl. pure SQL errors; keyed pop can evict a healthy replacement) — brief explicitly says do NOT change WHEN drop is called; identity-checked drop would change the `drop(readonly)` signature used by both facades (files not owned).
- **data-layer OBS-5** (unbounded concurrent connections in pooled q()) — owner-gated capacity policy per the audit.
- **data-layer OBS-6/OBS-7, fixes-verification OBS-1/OBS-2** — files not owned by this group (`docs/findings/...`, `host/multi_asset.py`, `host/web/src/types.ts`).
