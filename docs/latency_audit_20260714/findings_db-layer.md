# Latency audit 2026-07-14 — LENS: DB layer (COMPLETE)

Read-only audit over data/db_client.py, data/neuract_pool.py, ems_exec/data/neuract.py, data/value_probe.py,
layer1b/basket/col_dict.py, validate/data_load.py, config/{databases,neuract_dsn,app_config,policy_read,reason_templates}.py,
obs_db_queries mining (311,757 rows), live EXPLAIN ANALYZE on :5433, psycopg2 RTT measurements, /proc env checks.

## Ground truth measured this session

### RTT / connect (psycopg2, warm, 15 samples)
- local :5432 (cmd_catalog): SELECT 1 p50 **0.01 ms**; connect ~1.5 ms
- tunnel :5433 (target_version1/neuract): SELECT 1 p50 **15.96 ms** (9.0-23.4); connect p50 **47.6 ms**
- q() overhead micro-bench (local, warm pool): **0.044 ms/call** incl obs jsonl append; 0.025 ms with V48_SQL_TRACE=0.

### obs_db_queries by db (last 2 days)
| db_name | n | p50 ms | p95 ms | max ms | total ms |
|---|---|---|---|---|---|
| target_version1 (q() over tunnel — value probes, col_dict, validate) | 4,107 | 3,841 | 28,068 | 104,608 | 46,483,402 |
| neuract (pooled exec/L2 door) | 102,239 | 49 | 191 | 2,576 | 6,959,685 |
| cmd_catalog (local q()) | 205,409 | 0 | 3 | 92 | 291,297 |

### Representative recent single-page traces (2026-07-14 ~02:00-02:45)
- t_2aed84a5: 636 q, 206.8s summed. '' stage target_version1 9 q = **184.3s** (value-probe chunks, avg 20.5s);
  executor.card neuract 364 q = 17.7s (avg 48.7ms); asset_resolution target_version1 9 q = 4.1s.
- t_0f16fca8: 747 q, 219.2s summed. '' stage 9 q = 184.1s; executor.card neuract 416 q = 29.8s.
- t_24da06f3 (cache-warm twin): 841 q, **1.2s total** — the delta between probe-cache HIT and MISS is ~185-205s.
- Per-card executor profile (t_0f16): cards did 75-149 queries each, 5.5-6.5s summed DB per card.
  Card 5: 32 window-open halves over 8 member tables x 2 column-sets (windowed-delta N+1 across members).

---

## FINDING DB-1 (BIGGEST): value_probe ORDER BY `::timestamptz` defeats both indexes -> 20-30s full-scan chunks
- `data/value_probe.py:73` builds `ORDER BY "timestamp_utc"::timestamptz DESC LIMIT 1` per table, UNION ALL x40/chunk.
- Live gic_* tables HAVE indexes: btree(timestamp_utc) on 295/302 tables; expression idx `neuract.ts_imm((timestamp_utc)::text) DESC` on 240/302. 14.7M rows total.
- Knob `neuract.ts_index_fn='ts_imm'` IS set (2026-07-12) and ems_exec/data/neuract.py honors it — value_probe does NOT (uses raw DATA_TS_CAST).
- EXPLAIN ANALYZE (gic_27_n2_600_kva_ups_02_tm, 255k rows):
  - current: **1,137.6 ms** Parallel Seq Scan + top-N sort (10,397 buffers)
  - ts_imm: **0.064 ms** Index Scan (13 buffers)
  - raw-text ORDER BY timestamp_utc DESC: **0.036 ms** via plain _ts index (covers 295/302 tables)
- obs: 4,107 probes/2d, avg 20-28 s per 40-table chunk, max 104.6 s, **46,483 s total**. Single-table probes
  (has_renderable_data) cost 3.9 s EACH in asset_resolution.
- These chunks run BOTH in asset_resolution (1b) and un-staged ('' — panel roster via data/lt_panels/panel_members
  tables_with_values over the full registry: 9 chunks = 184 s inside otherwise-normal traces).
- FIX (small): use the knob-aware ts expression in value_probe (and see DB-5 for the twin sites); backfill the 62
  missing _tsimm indexes with the existing db/create_neuract_ts_indexes.py.
- SAVING: 40-table chunk 25 s -> ~0.1 s. Panel page with full-registry roster (9 chunks): **-184 s**.
  Typical cold single-asset run (1 chunk + 1-2 single-table probes): **-25..-35 s**. Kills the 1b live p95 200 s tail.

## FINDING DB-2: value-probe cache is per-SET (frozenset key) + 120 s TTL -> repeat prompts & multi-asset re-pay full probes
- `data/value_probe.py:61,89` `_VAL_CACHE[frozenset(tables)]` — two overlapping table-sets share NOTHING; a 3-feeder
  compare probing {A-set},{B-set},{C-set} re-scans overlapping tables per lane. TTL = cache.resolution_ttl_s = 120 s
  (app_config row), so any prompt >2 min after the last pays the full probe again (t_24da 1.2 s vs t_2aed 206.8 s).
- FIX: cache per TABLE (dict per table -> count), assemble sets from per-table entries; only probe the misses.
  CONFIG-ONLY mitigation available today: raise cache.resolution_ttl_s (one UPDATE) — with DB-1 fixed the TTL can stay.
- SAVING (with DB-1 unfixed): repeat-prompt within-session **-20..-185 s** per expiry; multi-asset compare lanes stop
  re-probing overlap. With DB-1 fixed this drops to noise but still removes ~0.1-0.5 s per re-probe + 16 ms RTT floors.

## FINDING DB-3: neuract "pool" is ONE shared connection -> whole executor DB leg serializes
- `data/neuract_pool.py:27` `_POOL: dict` keyed by (readonly, conn kwargs) — exactly 1 psycopg2 conn for all executor
  threads (+1 readonly for registries). psycopg2 serializes concurrent cursors per connection.
- Evidence: neuract door p50 **49 ms**/query vs measured raw RTT 16 ms and index-backed reads that EXPLAIN at <1 ms
  server-side; avg rises with per-trace query count (queueing). t_0f16: 416 exec queries = 29.8 s summed on one socket
  — the exec DB leg is literally sequential.
- FIX (small): real checkout/checkin pool (mirror db_client._q_pool), size ~= layer2.emit_concurrency + 2 (knob).
- SAVING: 5-card DB-heavy page: 5 cards x ~6 s summed serialized ≈ 25-30 s of exec-stage DB wall -> parallel 4-6 lanes
  AND per-query latency back to ~20-25 ms: ≈ (30 s x 25/60)/4 ≈ **3 s** -> **-15..-25 s wall on DB-heavy exec**;
  typical page **-3..-6 s**. Also helps /api/frame refetches (same door).

## FINDING DB-4: window() = 2 round trips; windowed-delta fans out per member x per column-set (N+1)
- `ems_exec/data/neuract.py:175-207` window() issues first-row + last-row as SEPARATE queries (top-2 obs shapes:
  17,463 + 17,463 calls/2d, avg 72 ms each, 2.51M ms combined).
- Aggregate cards call window() per MEMBER table: card 5 = 32 halves over 8 tables x 2 col-sets. A 28-member panel
  card = 56+ round trips just for windows.
- FIX (small): (a) UNION ALL first+last in ONE statement (-1 RT per window); (b) batch across member tables with
  UNION ALL branches (-2N+1 RTs per aggregate leaf). Same rows returned; per-leaf degradation unchanged (each branch
  tagged by table, missing branch = honest None).
- SAVING: 28-member card: 56 RTs x ~50 ms -> 2 RTs x ~120 ms ≈ **-2.5 s per aggregate card**; typical 5-card page with
  ~72 window calls: -72 x ~25 ms (post-pool) ≈ **-1.8 s summed, -0.5..-1 s wall**.

## FINDING DB-5: col_dict samples + validate reads use the same cast-defeating ORDER BY
- `layer1b/basket/col_dict.py:39,61` and `validate/data_load.py:40` build `ORDER BY "timestamp_utc"::timestamptz DESC`
  (raw DATA_TS_CAST). On a 255k-row table that's ~1.1 s per read (measured shape); on small tables 60-100 ms.
- obs: `SELECT to_jsonb(t) ... ORDER BY ::timestamptz DESC LIMIT 2` at 63 ms (small table) in asset_resolution;
  validate max 119 s baseline is partially this shape on big tables.
- FIX: same knob-aware expression as DB-1. SAVING: **-0.1..-2.2 s per 1b table sample; validate tail -1..-100 s** on
  large-table cards (validate reads LIMIT n rows but pays the sort).

## FINDING DB-6: per-table information_schema probes ~78 ms each, ~35/run -> one 35 ms bulk fetch
- present_columns/column_types (`data/neuract_pool.py:99-138`) probe information_schema per TABLE (TTL 120 s);
  obs: 2,791 (executor.card) + 1,736 (layer2_card_ai.card) calls/2d at avg 70-75 ms; t_0f16 paid 35 calls = 2.8 s.
- Measured: bulk `SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema='neuract'`
  = **34.6 ms** for the whole schema (all 302 tables); single-table probe = 14.2 ms solo, 70-78 ms under load.
- FIX (small): schema-wide prefetch into the shared TTL cache on first miss (one query per TTL window), keep
  never-cache-empty per table. SAVING: **-2..-3 s per cold 5-card page**; removes 4,500 tunnel RTs/2d.

## FINDING DB-7: cmd_catalog per-leaf policy/template reads — 24k-25k repeats of constant keys
- obs 2d: data_quality_policy placeholder.scalar 24,059x / placeholder.narrative 23,746x / scrub.provenance_tokens
  23,736x / scrub.* 8-9k each; reason_template 'unbound_by_emit' 25,029x. Still live (20h: 2,947 + 1,739x2).
- Mega-traces (multi-card, 07-12 04:11): 13,704 catalog queries inside layer2_card_ai.card; 18,175 total = 53 s summed.
  q() is 0.044 ms warm-solo but obs shows ~2.9 ms avg under thread contention (pool lock + GIL) -> ~13 s wall spread.
- Sources: grounding/default_assemble.py:51,73,95,133; ems_exec/executor/scalar_tile_fill.py:45; graft.py:97 — via
  config/policy_read.txt() which checks app_config FIRST (process-cached) and only falls through because these keys
  live ONLY in data_quality_policy. config/reason_templates.py:12 has no cache at all.
- FIX: CONFIG-ONLY for policy keys — INSERT the hot keys into app_config (canonical home; policy_read serves them from
  the process cache, zero code change). reason_templates needs a tiny TTL/lru cache (code, ~5 lines).
- SAVING: worst multi-card traces **-10..-13 s**; typical page **-0.5..-2 s** (contention removal), plus removes
  ~40k queries/day of load.

## FINDING DB-8: 62 gic tables missing the _tsimm index (and 7 missing even the text _ts index)
- 302 gic_* relations: 240 have _tsimm, 295 have _ts. Every knob-aware read on the 62 non-tsimm tables seq-scans.
- FIX (ops/config): run db/create_neuract_ts_indexes.py to completion. SAVING: same per-read arithmetic as DB-1
  (1,137 ms -> 0.06 ms on 255k rows) for any card resolving to those tables.

## FINDING DB-9: neuract.statement_timeout_ms = 0 (unlimited) — unbounded tail
- config/neuract_dsn.py:81-84: knob exists, deliberately off pending index work. Observed max: 104.6 s single query.
- FIX (config-only, AFTER DB-1/5/8): set neuract.statement_timeout_ms ~= 15000. Converts pathological tails into the
  honest-degrade path in 15 s. SAVING: p99 tail capping — **-90 s on the worst runs** (215 s probe tails to 15 s).

## FINDING DB-10: per-flag-column LAG scans — one full-window scan per edge column
- `edge_count`/`bucketed_edges` (ems_exec/data/neuract.py:347-405) scan the whole window per COLUMN with LAG.
  obs: 4,552 + 2,190 edge scans/2d at 55-74 ms. An events card with 5 flag columns = 5 scans of the same rows;
  edge_count + bucketed_edges on the same (table,col,window) = 2 scans of identical data.
- FIX (small): multi-column LAG in one pass (SELECT LAG over several cols), and derive total from the bucketed sums
  in the caller. SAVING: events-heavy card with 5 flags: 10 scans x ~60 ms -> 1-2 x ~90 ms ≈ **-0.4..-0.5 s/card**.

## FINDING DB-11: latest_ts freshness re-read per card for the same table
- `latest_ts` shape (`SELECT ts_imm(...) ORDER BY ... DESC LIMIT 1`): 1,857 calls/2d avg 108 ms (executor.card) +
  1,776 avg 71.5 ms (layer2_card_ai.card). Multi-card pages re-ask the same table's newest ts per card.
- FIX: 15-30 s TTL cache keyed by table (freshness tolerance >> 30 s). SAVING: 5-card single-asset page: 8-10 calls
  -> 1: **-0.5..-0.9 s**.

## Verified NON-findings / dead ends
- psql SUBPROCESS spawns (brief item b): the live host runs the pooled engine — /proc/<pid>/environ of both
  host/server.py processes has NO V48_DB_ENGINE override; default in db_client.py:31 is 'pool'; the systemd unit sets
  only V48_HOST_PORT/PYTHONUNBUFFERED. The mined 10,982 spawns predate the 2026-07-12 pool ship. Remaining spawners:
  ops/tunnel_monitor.py (1 psql per 90 s, monitoring), copilot/db.py + copilot/has_data.py (BUILD-time only, not the
  typeahead request path), db/apply.py + replay/store.py + payload_diff (tooling). No hot-path spawns remain.
- Residual non-ts_imm executor casts in obs stopped at 2026-07-12 07:41 = pre-knob traffic, not ongoing.
- obs sink is batched (sink_pg.py daemon, 2 s flush, 500/batch executemany) — no per-query INSERT amplification.
  jsonl append per query measured at ~0.02 ms — negligible.
- app_config cfg() is process-cached on success with never-cache-empty — not a per-call query.
- Connection churn: only 72 <pg_connect> records/20h (avg 28.7 ms) — keepalives + connect_timeout already configured
  (config/neuract_dsn.py conn_kwargs); churn is a non-issue.
- Wide fetches: latest()/window() select only requested columns; the 21-col selects are legitimate card needs.
  to_jsonb(SELECT *) reads are LIMIT 1-2 — row width immaterial next to the sort cost (fixed by DB-1/5).
- db_client q() pool for :5432/:5433 catalog reads: checkout/checkin with max 6 idle — adequately sized; q() call
  overhead 0.044 ms warm.
- has_data EXISTS probes (tables_with_data): 15 ms per 40-table chunk — already cheap, no action.
- existing_tables information_schema.tables read: 16 ms, cached — fine.

## Scenario arithmetic (all DB findings combined)
- COLD single-asset dashboard (5-8 cards): DB-1 -25..-35 s (probe chunks) + DB-3 -3..-6 s + DB-4 -1 s + DB-6 -2.5 s
  + DB-7 -1 s + DB-11 -0.7 s ≈ **-33..-46 s** off e2e p50 37.8 s class runs whose 1b/exec DB legs dominate.
- 5-8-card PANEL-OVERVIEW page (28-member roster): DB-1 kills the un-staged 184 s roster probes -> **-180 s p95**;
  DB-4 -2.5 s/aggregate card; DB-3 -10..-20 s exec wall.
- MULTI-ASSET 3-feeder compare (RESPONSE_MULTI p50 142 s, worst 410-441 s): DB-1+DB-2 remove per-lane probe replays
  (**-60..-185 s** on worst runs); DB-3/DB-4 scale x3 lanes ≈ -6..-15 s.
- /api/frame date re-fetch: no 1b; window pairs + buckets ~30-80 q x 36 ms ≈ 1.5-3 s -> DB-3+DB-4 ≈ **-1..-2 s**.
- REPEAT prompt within 2 min: already ~1 s DB (cache-warm). >2 min: DB-2 TTL/per-table cache keeps it warm: **-20..-185 s**.
