# Performance & Scalability Audit — pipeline_v48 (2026-07-12)

Lens: performance. All file:line references were read during this audit; the two benchmarks below were run live
against the local cmd_catalog DB and the neuract tunnel (:5433) from this machine.

**Measured facts used throughout:**
- `q()` psql subprocess round-trip (local cmd_catalog, `SELECT 1`): **~2.5 ms**; pooled psycopg2 same query: **~0.012 ms** (~200x).
- `EXPLAIN ANALYZE` on `neuract.gic_16_n2_bpdb_2_for_lamination_03_04_ng` (55,602 rows):
  - `ORDER BY "timestamp_utc"::timestamptz DESC LIMIT 1` → **Seq Scan + top-N sort, 25.7 ms, 1187 buffers** (the index `idx_..._ts` on the raw text column is NOT used because every query orders/filters through the `::timestamptz` cast).
  - `ORDER BY "timestamp_utc" DESC LIMIT 1` (plain text) → **Index Scan Backward, 0.32 ms, 4 buffers**.
- A real served response (`outputs/logs/response_r_02a78d58e2.json`): **309 KB for 10 cards**, of which `data_instructions` = **168 KB (55%)**, `render` = 56 KB, `payload` = 54 KB.
- `outputs/logs/` currently **485 MB, 865 files**, no rotation.

---

## P1 (CRITICAL) — The executor wall-clock budget is dead code: a hung neuract read blocks the request thread forever

**Files:** `host/exec_cards.py:174-190`

```python
deadline = time.time() + _EXEC_BUDGET_S
with ThreadPoolExecutor(max_workers=max(2, min(len(tasks), 8))) as ex:
    futs = {ex.submit(_fill, cid, o): cid for cid, o in tasks.items()}
    for fut in as_completed(futs):          # <- NO timeout kwarg: blocks until each future COMPLETES
        ...
        completed_by_id[cid] = fut.result(timeout=remaining or 0.01)   # future is already done here
    except _FTimeout:                       # <- unreachable
```

Two independent defects kill the ER-8 protection the comment at lines 15-18 claims:

1. `as_completed(futs)` is called **without a timeout**. It only yields futures once they complete, so
   `fut.result(timeout=remaining)` always runs on an already-completed future and returns instantly. The
   `_FTimeout` branch (line 184) is unreachable; `ems_exec.card_budget_s` (45 s) is never enforced.
2. Even if the result timeout fired, `with ThreadPoolExecutor(...)` calls `shutdown(wait=True)` on exit
   (line 175), which joins all worker threads — the request would still block on the slowest card.

This is compounded by the missing DB timeouts (P2): a card whose neuract read black-holes (the documented
:5433 tunnel-flap failure mode) holds its worker thread — and therefore the whole `/api/run` HTTP thread —
until TCP retransmission gives up (~15 min) or forever on a silently-dropped connection. `_Server` is a
`ThreadingHTTPServer` with `daemon_threads` and **no per-request timeout** (`host/server.py:346-354`), so hung
request threads simply accumulate. Under production traffic during a tunnel flap this is an outage: every new
prompt stacks another permanently-hung thread pile (1 request thread + up to 8 executor threads each).

**Fix (behavior-preserving for the healthy path):**
- `for fut in as_completed(futs, timeout=_EXEC_BUDGET_S):` and catch `concurrent.futures.TimeoutError` around the loop, marking all unfinished futures `executor budget exceeded`.
- Exit the executor without joining stragglers: create the pool outside `with` and call `ex.shutdown(wait=False, cancel_futures=True)`.
- Re-read the budget knob per call instead of at import (see P15).

---

## P2 (HIGH) — No connect/statement timeout on the neuract psycopg2 doors

**Files:** `config/neuract_dsn.py:61-69` (`conn_kwargs()` has **no** `connect_timeout`), `ems_exec/data/neuract.py:42` (`psycopg2.connect(**_dsn.conn_kwargs())`), `registries/neuract/_db.py:38` (same), `ems_exec/data/neuract.py:56-57` (`cur.execute` with no `statement_timeout` / socket timeout anywhere).

Contrast: the psql path sets `PGCONNECT_TIMEOUT=5` (`config/databases.py`, verified by `data/db_client.py:15`
routing through `conn_env`), and `data/db_client.pg_connect` passes `connect_timeout` explicitly
(`data/db_client.py:30-32`). The two pooled psycopg2 doors — which carry ALL executor and registry reads — have
neither a connect timeout nor `options='-c statement_timeout=...'`. A black-holed tunnel connection therefore
hangs `cur.execute()` indefinitely, which is exactly the input that makes P1 an outage instead of a degrade.
The seq-scan queries of P3 also become unbounded-time queries at 10x data.

**Fix:** add `"connect_timeout": 5` and `"options": "-c search_path=... -c statement_timeout=<cfg knob>"` to
`conn_kwargs()`; add TCP keepalive kwargs (`keepalives=1, keepalives_idle=30, keepalives_interval=10,
keepalives_count=3`) so a dead tunnel is detected in seconds. All DB-driven via cfg with code defaults.

---

## P3 (HIGH) — `::timestamptz` cast defeats the btree index: every latest-row / window / has_data read is a full seq scan

**Files:** `ems_exec/data/neuract.py:137-139` (`_tsexpr()` = `"timestamp_utc"::timestamptz` used by `latest` :152, `latest_ts` :172, `window` :199-214, `series` :236-247, `bucketed` :300-311, `bucketed_raw_series`, `edge_count`, `bucketed_edges`, `bucketed_delta`); `layer1b/resolve/has_data.py:35-37` (per-table latest-row probe with the same cast, its comment "btree-indexed → cheap" is **wrong**); `validate/data_load.py:26-27`.

Measured (see header): 25.7 ms seq-scan+sort vs 0.32 ms index scan on a 55k-row table — **~80x**, growing
linearly with table size (10x meters/history → 250 ms+ per read). Every WHERE clause (`tsx >= %s::timestamptz`)
has the same problem, so even a "last 24 h" bucketed read scans the entire table. Multiply by:
- the panel fan-out (P5): dozens to hundreds of such reads per panel page;
- the 1b `value_counts` sweep: latest-row probe across the whole registry (~250 tables) in UNION-ALL chunks of 40 (`has_data.py:31-40`), re-run every `cache.resolution_ttl_s`=120 s per process → a periodic multi-second full-registry scan storm;
- `column_logged` full-column scans (P11).

Note: plain text ordering is NOT a safe substitute — `validate/data_load.py:14-16` documents that neuract mixes
`+00:00`/`+05:30` offsets, so text order ≠ time order. The correct fix is an **expression index**.

**Fix:** one-time DDL script: `CREATE INDEX CONCURRENTLY ... ON neuract."<t>" ((timestamp_utc::timestamptz) DESC)`
for the ~250 gic_* tables (generate from `information_schema`). No code change; every read path above becomes an
index scan, including the WHERE-clause window filters.

---

## P4 (HIGH) — The "connection pool" is a single shared connection: all parallel card fills serialize at the DB door

**Files:** `ems_exec/data/neuract.py:22-47` (`_POOL: dict` keyed by frozen DSN kwargs → **one** psycopg2 connection per identical DSN; `_conn()` always returns the same object), `registries/neuract/_db.py:19-47` (identical pattern for metadata reads).

The host fills cards with an 8-worker ThreadPoolExecutor (`host/exec_cards.py:175`), and psycopg2 connections
are thread-safe only by *serializing* command execution — so all 8 "parallel" card fills funnel their queries
one-at-a-time through one connection over the SSH tunnel. Cross-request it is worse: 100 concurrent users in
the same process share that one connection for every executor read. The parallel fan-out buys concurrency for
Python-side work only; DB wall-clock (which is most of it, see P3/P5) is strictly sequential.

**Fix:** replace the single-connection dict with `psycopg2.pool.ThreadedConnectionPool` (min 1 / max = cfg knob,
e.g. `neuract.pool_max` default 8) keyed the same way; `_run` does getconn/putconn. Keep the drop-broken-conn
behavior. This is a contained change in the two `_db` doors.

---

## P5 (HIGH) — Panel-aggregate N+1: per-card × per-member × per-register sequential queries, re-done for every card on the page

**Files:** `ems_exec/executor/members.py:88-101` (`rows()` — one `latest()` per member in a sequential loop), `:159-177` (`panel_kwh` → per member `member_delta`), `:359-380` + `:430-443` (`member_delta` on a paired register = **2 registers × `window()`**, and `window()` itself runs **2 queries** — `ems_exec/data/neuract.py:198-215`), `:236-258` (`bucketed_rolled_members` — one `bucketed()` per member, sequential), `:283-356` (`bucketed_multi` — specs × members queries, sequential); `ems_exec/executor/roster.py:146-169` (`prepare_ctx` resolves + reads members **per card**); `ems_exec/renderers/panel_aggregate.py:200-217` (same fan-out again for the legacy path).

Per panel card with M members: ~M latest-row reads + M×4 window-boundary reads for energy + M bucketed reads
per trend series. A panel-overview page has ~5 such cards and **nothing shares member rows across cards within
a request** (only `panel_members` *resolution* is TTL-cached — `data/lt_panels/panel_members.py:34`). With
M=14 that is roughly 300–700 queries per page, all sequential per card, all through the single shared
connection (P4), each a seq scan today (P3). This is the slowest page family and the reason the 45 s budget
exists — and the budget is broken (P1).

**Fix order:** (1) P3 index makes each read ~100x cheaper; (2) share the `(members, member_rows)` pair per
(mfm_id, window, scope) in a request-scoped memo threaded through ctx so 5 cards do the fan-out once;
(3) batch per-member latest-rows into one UNION-ALL statement (the `has_data.py:34-38` pattern already does
this) and parallelize member bucketed reads once P4 gives real connections.

---

## P6 (HIGH) — No global LLM admission control: per-run caps do not compose across users; vLLM contention is the first thing that breaks at 100 concurrent users

**Files:** `run/layer2_all.py:47-49` (`layer2.emit_concurrency` = 4 is **per run**), `run/parallel.py:17-19` (pool per call), `layer2/build.py:713, 736-739, 766-779` (1-3 emits per card: emit + swap-target re-emit + gate retry), `layer2/emit/emit.py:209-217` (plus one bounded transport retry), `host/server.py:316-319` (knowledge call per fresh prompt), `layer1a/route.py:96`, `layer1b/resolve/asset_resolve.py:157`, `layer1b/basket/column_basket.py:68`, `ems_exec/renderers/_insight.py:122-131` (narrative cards call vLLM synchronously during fill, 8 s timeout).

One prompt ≈ 8–20 LLM calls (route + resolve + basket + knowledge + 5-8 emits of ~22K tokens each + retries +
narrative). The 2026-07-06 cert already established that **uncapped concurrent emits starve each other into
false timeouts** on the single :8200 vLLM — that is why `emit_concurrency=4` exists. But the cap is created
inside each `run_2_all` call: N concurrent `/api/run` requests spawn N×4 in-flight 22K-token emits plus their
route/knowledge calls. At 100 users the vLLM queue explodes, every emit crosses its 150 s fail-fast edge,
`conforms=False` hard-fails trigger reflect re-routes (`run/harness.py:120,164-174`) which *double* the LLM
load exactly when the system is saturated. This is the first hard wall at scale.

**Fix:** a process-wide `threading.BoundedSemaphore` in `llm/client.call_qwen` sized by a cfg knob
(`llm.global_concurrency`, default ~8), so total in-flight vLLM requests are bounded regardless of user count;
optionally shed load (fast 503 with honest reason) when the wait exceeds a knob. Keep the per-run cap.

---

## P7 (HIGH) — Schema/logged caches poison permanently on a tunnel flap — the exact bug class already fixed with TTLCache, not applied here

**Files:** `ems_exec/data/neuract.py:76-86` (`present_columns` caches the result of `_run(...)` which returns
`[]` **on any error** (`:59-66`) → an empty `frozenset()` is cached for process life → every subsequent read of
that table pads all columns to None → the whole asset renders permanently honest-blank until restart);
`:89-104` (`column_logged` caches `False` on error the same way); `registries/neuract/_db.py:93-107` (same
poison in the metadata door); `ems_exec/executor/fab_guards.py:201-218` (`_ROWS_CACHE` caches an outage as
`False` permanently — safe direction, but stale).

This is byte-for-byte the "member cache poison" family that was root-caused on 2026-07-09 and fixed with
`data/ttl_cache.TTLCache` + never-cache-empty in `panel_members`/`has_data`/`lt_mfm` — but the executor's own
hottest caches were not converted. One flap during a page fill → that meter's schema is "empty" for the
process life; the per-leaf degradation mandate turns it into a permanently blank page that "self-heals" only
on restart.

**Fix:** never cache an empty result when `_conn()` returned None or `_run` errored (distinguish "table truly
has no columns" from "read failed"), and/or swap the plain dicts for `TTLCache()`. Small, mechanical, matches
the established fix pattern.

---

## P8 (MEDIUM) — payload_store caches None permanently on a DB hiccup; skeleton/raw-default never refresh

**Files:** `host/payload_store.py:51-70` (`_skeleton_payload`: on any exception `skel = None` and line 69
`_SKELETON_CACHE[render_card_id] = skel` — a cmd_catalog hiccup at first touch pins that card's skeleton to
None until restart → every "L2 skipped" render of that card falls to the generic machine-reason blank instead
of its real component); `:83-95` (`_raw_default_payload` same: None poisoning, and additionally the executor
loses its shape oracle → yscale/norm/graft passes silently degrade). Also: a `card_payloads` reseed requires a
server restart (both caches are process-lifetime with no TTL/no reload hook).

Secondary concurrency-hygiene note: `_raw_default_payload` returns the **shared cached dict without a copy**
(line 95) while `_skeleton_payload` deepcopies (line 70). The raw default is handed to 8 concurrent fill
threads as `shape_ref`/dash reference (`host/exec_cards.py:135`, `host/enrich.py:178`); any accidental mutation
cross-contaminates all future requests for that card.

**Fix:** don't cache the None-on-exception case (only cache a real row or a proven-absent row), or use
`TTLCache`; return a copy (or an immutable proxy) for the raw default.

---

## P9 (MEDIUM) — Response bloat: 55% of the wire payload is `data_instructions` the FE barely reads; date changes re-upload it all

**Files:** `host/enrich.py:227` (`"data_instructions": l2.get("data_instructions")` served verbatim per card),
`:217-221` (refetch bundle embeds `_default_payload` per history card); measured: 309 KB response for 10 cards
with `data_instructions` = 168 KB (see header). The FE reads only `consumer.endpoint` / `is_history` / dash
vocab from it (`host/web/src/cmd/*`), plus `/api/frame` needs it re-posted. On a page-level date change,
**every** history card independently re-fetches (`host/web/src/components/CmdCard.tsx:63-66`), each POSTing its
full payload + data_instructions + `_default_payload` back to the server — for a 10-card page that is ~10
parallel ~20-30 KB uploads per date pick, plus the server-side re-fill.

**Fix:** serve a whitelisted `data_instructions` subset (consumer + fields' slots/labels needed for reasons),
or move the full object under a debug flag; key `/api/frame` re-fetch by `run_id`+`card_id` against the
server-side `_dump_response` copy instead of round-tripping the payload through the browser.

---

## P10 (MEDIUM) — psql subprocess per query on hot paths; L2 re-reads the same catalog rows per card

**Files:** `data/db_client.py:11-21` (every `q()` = fork/exec psql + fresh TCP connect; ~2.5 ms local minimum,
more via the tunnel; 57 import sites); `layer2/catalog/catalog_row.py:5-20` (**7-8 separate `q()` calls per
card**, uncached: handling/recipe/contract/controls/size/feasibility/payload), `layer2/build.py:20-22` +
`:730` (`_page_card_ids` — the same page-constant query re-run **inside run_card for every card**),
`layer2/catalog/contract.py:11-27` (3 q() calls itself). A single prompt spawns roughly 50–120 psql processes;
100 concurrent users → thousands of forks/second against a parent process with a large heap (page-table copy
cost) plus connection churn on the catalog DB.

**Fix:** (1) route `q()` through a pooled psycopg2 door (the `registries/neuract/_db.py` pattern — it already
exists) keeping the same list-of-lists contract; (2) memoize page-scoped lookups (`_page_card_ids`,
catalog_row per card_id) in a TTLCache — the catalog is nearly static; (3) as a bonus this closes the ad-hoc
f-string SQL interpolation that `q()` forces on callers.

---

## P11 (MEDIUM) — `_asset_has_logged_data` can run ~70 full-table scans for a dark meter, inside the serve path

**Files:** `host/enrich.py:37-50` (loops **all** present columns calling `column_logged` per column), invoked at
`host/enrich.py:192-196` for every card whose fill produced zero real leaves; `ems_exec/data/neuract.py:101`
(`SELECT 1 ... WHERE col IS NOT NULL LIMIT 1` — for an all-NULL column this scans the entire table before
returning empty). A went-silent meter with a deep table: ~70 columns × full scan (25 ms+ each today, P3) ≈
seconds, serialized on the shared connection, during `_enrich_card` (which runs sequentially per card —
`host/assemble.py:35-40`). Results are cached per process afterwards (with P7's poison caveat).

**Fix:** one query instead of ~70: `SELECT <col IS NOT NULL bool_or aggregates> FROM t` over a bounded recent
slice (e.g. newest 1000 rows via the P3 index), or reuse 1b's `value_counts` latest-row probe which answers the
same "is anything logged" question in one read.

---

## P12 (MEDIUM) — Multi-asset compare is fully sequential: lanes × assets multiply wall-clock

**Files:** `run/harness.py:344-351` (`run_pipeline_multi`: `for cls, members in by_class.items()` — each lane
runs a full `run_pipeline` including its L2 LLM fan-out, one after another), `host/multi_asset.py:67-78`
(`build_response_multi`: nested `for group / for asset` — each `assemble_cards` is a full executor fan-out,
sequential per asset). A 3-class, 6-asset compare = 3 sequential LLM authoring passes + 6 sequential page
fills; with a 45 s executor budget each (were it enforced), worst case is minutes.

**Fix:** run lanes via `run_parallel` (the primitive exists) — class lanes are independent by construction
(the shared template is injected, `harness.py:194-198`); same for per-asset `assemble_cards`. Respect the P6
global LLM semaphore so parallel lanes don't recreate the contention problem.

---

## P13 (MEDIUM) — The knowledge gate adds a full serial LLM round-trip to every fresh dashboard prompt

**Files:** `host/server.py:316-323` (every request without a pinned asset runs `knowledge.ems.ask` BEFORE the
pipeline), `knowledge/ems.py:68-86` (one `call_qwen` with the full prompt file), `llm/client.py:59-65` (default
timeout 120 s for an unconfigured stage). The common case is `kind='dashboard'` — i.e. the answer is "proceed" —
yet the user pays the routing model's full latency serially, before 1a/1b even start, and a saturated vLLM
(P6) can stall the gate for minutes with `on_error` falling open to dashboard anyway.

**Fix:** start `run_pipeline` in parallel with `ask()` and discard the pipeline result on a knowledge/off_scope
verdict (the pipeline is read-only, so wasted work is the only cost — and it is the rare case); or set a short
`llm.timeout.knowledge_ems` row (the plumbing already exists) so the gate can never cost more than ~5 s.

---

## P14 (MEDIUM) — Unbounded artifact growth on the request path: outputs/logs at 485 MB and climbing per prompt

**Files:** `host/server.py:181-192` (`_dump_response` writes 200–300 KB JSON per run, called on every /api/run:
line 339), `obs/ai_log.py:39-50` (full request+response of every LLM call appended to `ai_<run_id>.jsonl` —
`ai_pytest.jsonl` is already 5.7 MB), `obs/stage.py` / `obs/failures.py` (more per-run jsonl), `run/run_id.py`
(prompt-hash run_id collides by design → repeated prompts append forever to the same files). Measured: 865
files / 485 MB with no rotation, no TTL, no size cap. At production request rates this fills the disk in weeks;
disk-full then breaks the fail-open telemetry AND any code that writes (response dump precedes the HTTP send).

**Fix:** a small retention sweep (age/size-based) run on server start or a cron; cap per-file size for the
collide-by-design jsonl sinks; make `_dump_response` valve-guarded by a cfg knob.

---

## P15 (MEDIUM) — Config knobs freeze at process start: `cfg()` cache is process-lifetime and pins `{}` on a first-load failure

**Files:** `config/app_config.py:18-24` (`@lru_cache(maxsize=1)` `_load`, `except Exception: return {}` — a
cmd_catalog outage at first touch silently pins EVERY knob to code defaults until restart; nothing ever calls
`reload()` in the server), `host/exec_cards.py:18` (`_EXEC_BUDGET_S = cfg(...)` evaluated at **import time** —
the one knob the budget system depends on cannot be tuned without restart, unlike the per-call cfg reads
everywhere else). The stated philosophy ("editing the row changes behavior with no code change") only holds
until first read; the TTL philosophy adopted for resolution caches was not applied to the config cache itself.

**Fix:** make `_load` a TTLCache (e.g. 60 s) and never cache the `{}` failure case; move `_EXEC_BUDGET_S`
inside `_run_cards`.

---

## P16 (LOW) — ai_log mislabels concurrent runs and buffers every LLM response twice

**Files:** `obs/ai_log.py:8` (`_RUN_ID` module global), `:32-53` (each :8200 response fully `read()` into
memory, JSON-parsed a second time, appended synchronously inside the LLM call path), `run/harness.py:187` +
`:107` (`set_run_id` per run/attempt). Two concurrent `/api/run`s in the one process overwrite `_RUN_ID`, so
LLM calls are logged under whichever run set it last — the per-run ai_*.jsonl replay files become unreliable
exactly when debugging concurrent-load problems (the situation you most need them for). Cost is minor; the
attribution loss is the real issue.

**Fix:** carry the run id in a `contextvars.ContextVar` (the pattern `obs/trace.py:131` already uses) set by
`set_run_id`, falling back to the global for non-request contexts.

---

## Smaller notes (not counted as findings)

- `run/parallel.py:17` default `max(2, N)` workers — fine for the 2-thunk 1a∥1b split; every other fan-out passes a cap.
- `_insight.py:70-71,147-150` cache is content-hashed on the story values — with live data the hash changes every run, so in production it is effectively a per-call vLLM hit inside the fill path (bounded by the 8 s timeout). Acceptable, but worth knowing the cache rarely hits outside tests.
- `ems_exec/executor/fill.py:232` one deepcopy per card payload — fine.
- `series`/`bucketed` with `start=end=None` (non-history default reads latest-row only, so open-ended scans are rare; the wildcard/family passes can issue one `bucketed()` per series leaf — same column re-reads are possible but uncommon).
- `host/server.py:231-238` `/api/site` runs a psql subprocess per poll — if the FE polls it frequently, route through the pooled door (P10).
- FE `guards.ts`/`display_dash.py` deep walks are O(payload) per card — negligible next to DB/LLM.
- `grounding/schema_fingerprint._CACHE`, `registries/neuract/topology._CACHE` — bounded by table/edge count, fine; `copilot/starters._CACHE` fine.
- Committed stray artifacts (`host/web/src/App.tsx.tmp.*`, `outputs/emit_correctness_battery.py`) — other lenses' territory.

## What breaks first

1. **100 concurrent users:** the vLLM queue (P6) — 8-20 calls/prompt × N users with only per-run caps; emits
   start timing out at 150 s, hard-fails trigger reflect re-routes that double the load. Simultaneously the
   stdlib server accumulates threads (1 + up to 8+4 per request), and all executor DB reads serialize through
   ONE psycopg2 connection (P4).
2. **A tunnel flap under load:** P1+P2 turn it into piled-up permanently-hung request threads (outage), and
   P7 leaves schema caches poisoned after recovery (blank pages until restart).
3. **10x meters/history:** P3 — every latest-row read is a linear scan (already 25 ms at 55k rows), the
   120 s-TTL registry sweep becomes a multi-second stampede, and panel pages (P5) hit hundreds of such scans.
