# Production-Readiness Audit — Data Layer (post-R2)

- Date: 2026-07-12
- Lens: data-layer (differential vs docs/audit_2026-07-12/database.md + refactor ledger + unused-dupes apply log)
- Scope: data/db_client.py, data/neuract_pool.py, ems_exec/data/neuract.py, registries/neuract/_db.py,
  data/outage.py, data/value_probe.py, data/ttl_cache.py, data/equipment/*, data/lt_panels/*
- Status: COMPLETE (7 findings + 1 differential status note; verification record below)

## Findings

### OBS-1 (medium, safe) — pooled q(): fresh-connect failure escapes unwrapped, bypassing the RuntimeError contract, the replay tape and the per-query SQL trace
`data/db_client.py:149` — `conn, fresh = _checkout(db)` sits OUTSIDE the try. When the pool is empty and
`pg_connect` fails (tunnel down / cmd_catalog blip), the raw `psycopg2.OperationalError` propagates:
- engine parity breaks: `_q_psql` (:195-199) and the pool retry path (:158-165 via `_q_fail`) always raise
  `RuntimeError("DB error (db): ...")`; the first-connect path raises a different type. Even INTERNALLY
  asymmetric: a retry-connect failure is wrapped (:160), a first-connect failure is not.
- `replay/hooks.py:97` `db_q` records failures with `except RuntimeError` only → a traced request that degraded
  on a connect failure gets NO `sql.q outcome=raise` event and no tape entry — a pinned replay cannot reproduce
  the degrade branch (the exact contract db_client.py:45-47 claims).
- `_q_fail`'s per-query `_sql_trace(err=...)` (:180) never runs (only the `<pg_connect>` record fires).
Degrade-gate fingerprints still match (psycopg2 wording carries "connection to server"/"timeout expired"), so
prod behavior is honest — this is telemetry/replay/parity. Fix: move `_checkout` inside the try, or wrap its
failure via `_q_fail`. Safe (aligns types with the documented contract).

### OBS-2 (low→medium latent, safe) — pool engine breaks on trailing-semicolon SELECTs where the psql engine worked (verified live)
`data/db_client.py:119` wraps reads as `COPY (sql) TO STDOUT` — `COPY (SELECT 42;) TO STDOUT` is a Postgres
syntax error. Verified live against cmd_catalog: `q(db, "SELECT 42;")` returns `[['42']]` under
`V48_DB_ENGINE=psql` and RAISES under the default pool engine. AST scan of every q()/eq_q()/first_row() call
site: ZERO current callers pass `;` (so nothing is broken today), but any future seeder/script habit of
semicolon-terminated SQL flips from working to erroring depending on the engine env var — an invisible parity
trap for the rollback story. Fix: `sql.rstrip().rstrip(';')` before the COPY wrap (only for the COPY-able
branch). Safe, behavior-preserving. Otherwise CSV parity verified byte-exact live (NULL→'', bool t/f, embedded
comma/newline, jsonb, arrays, dates, leading comments, WITH).

### OBS-3 (medium, risky) — D1 side effect: BOTH neuract doors now share ONE global lock, and psycopg2.connect runs INSIDE it — flap stalls serialize across metadata + time-series reads
`data/neuract_pool.py:26` one module-level `_LOCK`; `conn()` (:45-60) holds it across `psycopg2.connect`
(connect_timeout 5s). Pre-D1 each door had its OWN lock (git HEAD `registries/neuract/_db.py:19` +
`ems_exec/data/neuract.py` `_LOCK`), so the two doors could fail/reconnect in parallel. Post-D1, during a
tunnel flap every thread entering EITHER door queues behind one lock while each queued thread burns its own 5s
connect timeout — worst case ≈ 5s × queued threads (executor fan-out + registry reads), vs the advertised
"fails in ~5 s". R1's executor budget bounds the request, but the F4 fast-fail claim degrades to fast-fail ×
serialized. Fix: per-key locks, or connect OUTSIDE the lock (double-checked insert). Risky (hot-path lifecycle).

### OBS-4 (low, safe) — neuract_pool.drop() never closes the popped connection and can pop a healthy replacement
`data/neuract_pool.py:63-69` pops the keyed conn without `.close()` (FD lingers until GC), and `run_read`
(:86-88) drops on ANY exception — including pure SQL errors (e.g. a bad `%s::timestamptz` param) — so thread A's
SQL error can pop the healthy shared conn; if thread B already reconnected, a second failing thread pops B's
NEW healthy conn (keyed pop, not identity-checked). Churn + FD linger only, no correctness break; same shape
existed pre-D1 (extraction was faithful). Fix: `drop(conn)` by identity + close it. Safe.

### OBS-5 (medium, owner-gated) — pooled q() has no upper bound on concurrent connections (deviates from the R2 rec it implements)
`data/db_client.py:61-67` `_checkout` opens a NEW connection whenever idle is empty — only the IDLE side is
capped (`V48_DB_POOL_MAX`=6, :37). The audit's own fan-in figure (~70 q() callers, AUDIT_REPORT R2 recommended
`ThreadedConnectionPool(min,max)`) means a burst can open O(threads) simultaneous connections per db (incl.
target_version1 over the :5433 tunnel via value_probe), all but 6 closed on checkin. Postgres max_connections
(default 100) is shared with backend2/Django/scripts/concurrent sessions. Not load-tested here (forbidden);
static read only. Fix: a bounded semaphore around checkout or ThreadedConnectionPool. Owner-gated (capacity
policy).

### OBS-6 (low, safe) — ledger stale on executed items D1 and ttl_cache move
`docs/findings/refactor_20260712/EXECUTED_AND_FOLLOWUPS.md:114-118` still lists follow-up #2 (ttl_cache → lib/)
and #3 (D1 neuract pool dedup) as "recommended, NOT executed" — both ARE executed (`data/ttl_cache.py` is a
facade; `data/neuract_pool.py` live with both facades repointed; APPLY_LOG second pass records D1). Anyone
working from the ledger would re-attempt them. Fix: annotate the two entries as done. Safe (doc edit).

### OBS-7 (low, safe) — F14 half-applied: `sb_base` still emitted + typed with zero FE consumers
The F14 scope line (APPLY_LOG_unused_dupes_audit.md:102) names `frames`/`live_frame`/`sb_base` as the dead wire
fields; the executed pass removed frames/live_frame/frame_status but `sb_base` is still emitted per response
(`host/server.py:102`, `host/multi_asset.py:120`) and declared (`host/web/src/types.ts:91` "dashboard branch
only") with NO consumer anywhere in host/web/src (grep-verified). Keep it on /api/health (:195 — useful ops
info), drop it from the run responses + types. Safe.

### STATUS — H9/F15 panel-aggregate N+1: UNCHANGED (differential note, not a new finding)
`ems_exec/executor/members.py:95-101` still one `latest()` per member (N queries), `panel_kwh`→`window()` per
member (2 queries each; :440), `bucketed()` per member per series (:250, :333). A 14-member panel card with
energy + one rolled series ≈ 14 + 28 + 14 ≈ 56 sequential queries, all serialized through the ONE shared
neuract connection (F5 also unchanged: `neuract_pool._POOL` holds exactly one conn per key). Both were already
recorded (database.md F15/F5, AUDIT_REPORT consensus #4) and remain open — no regression, no fix.

## Verified OK

- D1 dedup IS executed: `data/neuract_pool.py` exists; both `ems_exec/data/neuract.py:18,47,61` and
  `registries/neuract/_db.py:15,42,49,64` delegate pool lifecycle + `present_columns` to it. No drift possible —
  the pool mechanics live once. (Ledger follow-up #3 line 116 is stale — it still shows D1 as deferred, but
  APPLY_LOG second pass records it executed.)
- F4 fix real: `config/neuract_dsn.py:94-98` carries `connect_timeout` (knob default 5) + TCP keepalives; both
  doors inherit via `conn_kwargs()`; opt-in `statement_timeout` (:84-86).
- TTL/never-cache-empty on schema probes: shared `present_columns` in `neuract_pool.py:91-108` only caches
  non-empty (`if cols:`); `_LOGGED_CACHE` (ems_exec/data/neuract.py:24) and `_COLS_CACHE` are TTLCache.
- `lib/ttl_cache.py`: TTL-aware `.get()` (:50-53), value-before-ts write (:55-62), opportunistic purge (:65-76) —
  audit fix #2 real; `data/ttl_cache.py` is a clean re-export facade.
- q() fail-loud preserved on both engines: `_q_fail` raises RuntimeError (db_client.py:175-181), psql engine raises
  at :199; no path returns [] on error.
- Pooled q() connection lifecycle: discard-on-exception (:153), retry-once only for stale POOLED conns
  (`not fresh and _connection_dead`, :154), fresh-connect failure raises immediately — matches docstring.
- value_probe outage-vs-bad-chunk split intact (data/value_probe.py:53-58, 89-93); "timeout expired" fingerprint
  present in data/outage.py:20 to match the psycopg2 connect_timeout wording.
- panel_members never-cache-empty intact (data/lt_panels/panel_members.py:62-67, 121-122) on TTLCache.
- Pooled q() ADOPTED live: :8770 owned by PID 561102 started 07:35 (db_client.py pooled engine written 06:44),
  no V48_DB_ENGINE override in its env → default 'pool' active. /api/health ok. (:8771 is a second deliberate
  host instance, not a port clash.)
- CSV parity verified LIVE byte-exact between engines: NULL→'', bool t/f, embedded comma+newline, jsonb, arrays,
  dates, leading -- comments, WITH CTE. Only divergence found = trailing semicolon (OBS-2).
- Non-COPYable q() callers: exactly 2 (scripts/seed_schema_and_endpoints.py:81 TRUNCATE, :91 INSERT) — DML, no
  result rows, so the `_psql_str` fallback's jsonb/datetime formatting quirk has no live consumer.
- Module-level dict-cache sweep: every remaining plain-dict cache on a resolution path is disciplined —
  data/equipment/db.py:24 + edges.py:31-33 + ratings.py:37 + bridge.py:21 cache SUCCESS only (failures
  explicitly not cached, local :5432, clear_cache() hooks); layer1b/compare/detect.py:33-45 got the
  never-cache-partial fix (2026-07-12); config/derivation_binding._topo_cache falls to a code-default wall;
  ems_exec/renderers/_insight._CACHE is bounded (2048). No poisonable process-life cache found on a tunnel path.
- D7 pg_bool / D12 first_row+json_cell homes real and adopted (layer2/catalog/{feasibility,card_controls,
  card_grid_size,card_data_recipe}.py import from data.db_client; raw_on_error semantics preserved per copy).
- data/outage.py fingerprints cover the psycopg2 shapes the pooled engines emit ("timeout expired",
  "connection to server", "connection refused"); value_probe raise-on-outage / fail-open-on-bad-chunk intact.
- q() thread-safety: checkout/checkin under one lock, a connection is used by exactly one thread between
  checkout and checkin, discard-on-exception, retry-once only for stale pooled conns. No shared-cursor use.
- ems_exec/data/neuract.py parameterizes all VALUES (%s) and quote-escapes identifiers (_qtbl/_qcol);
  registries door fully parameterized (F9's cited good pattern preserved through D1).
