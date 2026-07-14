# Latency — "won't change output" cluster: IMPLEMENTED 2026-07-14

The proven-neutral fixes from the audit (same result, faster). Every one was verified byte-neutral before shipping and
is LIVE on :8770 (host restarted 2026-07-14). No CMD_V2 / render / payload-shape changes — pure DB/transport speed.

## Shipped

### 1. Probe ORDER BY -> knob-aware ts_imm index expression  (THE headline)
- **Files:** `config/neuract_dsn.ts_order_expr()` (new shared helper) wired into `data/value_probe.py`,
  `layer1b/basket/col_dict.py` (window_nonnull + latest_nonnull), `validate/data_load.py`.
- **What:** the three q()-path probes ordered by `"timestamp_utc"::timestamptz` which matched NO index (defeating both
  the raw btree and the live `ts_imm` expression index) -> seq scans. Now they emit `neuract.ts_imm("timestamp_utc")`,
  matching the index the executor already uses. Knob-driven (`neuract.ts_index_fn`, already = `ts_imm`).
- **Neutrality proof:** `ts_imm(t)` IS `SELECT t::timestamptz` (IMMUTABLE) -> identical ordering.
  `prove_probe_neutral.py`: 147 tables (all 38 non-gic novel shapes + all 100 missing-index + 60 gic sample) ->
  **0 mismatches, 0 errors**.
- **Measured:** full-registry `value_counts` (340 tables) **104.7s p50 -> 0.81s**; 376k-row transformer latest-row
  probe **~1.1s seq -> 0.458ms index** (EXPLAIN ANALYZE); the ~184s pre-pipeline gap on a cold panel page is gone.

### 2. Missing ts_imm expression indexes  (paired with #1)
- **File:** `db/create_neuract_ts_indexes.py` — broadened `_tables()` from `gic_%` only to every base table carrying
  the ts column (picks up dg_*, pqm_transformer_*, pcc_panel_*, air_compressor_*, *_feedbacks); **corrected the safety
  gate** `_uniform()` from "exactly one distinct offset" (a false-positive skip: the dg_* tables carry TWO explicit
  offsets +00:00/+05:30 and are safe) to the real precondition "every sampled value carries an explicit offset"
  (verified 0 offset-less rows). CREATE INDEX CONCURRENTLY IF NOT EXISTS (non-locking, idempotent).
- **Applied:** neuract ts_imm indexes 240 -> 285 (**+45**); 54 skipped = empty tables (no rows to index). The
  previously-false-skipped dg_1_mfm (203k rows) now index-scans in 0.326ms.

### 3. neuract connection pool  (removed the executor serialization)
- **File:** `data/neuract_pool.py` — replaced the SINGLE persistent psycopg2 connection (which serialized the entire
  8-way card fan-out behind one socket lock) with a checkout/checkin pool of N connections (mirrors the proven
  `db_client.py` cmd_catalog pool), sized by `V48_DB_POOL_N` (default 8). Public API (`run_read`) unchanged; every
  caller untouched.
- **Proof:** 8 concurrent `pg_sleep(0.5)` reads **0.57s wall** (was serializing to ~4.0s); 8 concurrent latest-ts reads
  all agree (correct under concurrency); healthy-path result byte-identical.

### 4. `_field_value` redundant NULL re-read
- **File:** `ems_exec/executor/fill.py` — re-read the single column only when it was NOT in the batched latest_row;
  a batched-but-NULL value now stays NULL without a provably-identical extra tunnel query. Byte-identical.

### 5. gzip on :8770 JSON
- **File:** `host/server.py._send` — gzip when the client sends `Accept-Encoding: gzip` (browsers do, and auto-
  decompress) and body >= 1KB. Decoded bytes identical (proved: plain vs `--compressed` md5 match); ~8-24x transport
  shrink on dashboard payloads; small bodies / non-accepting clients get today's exact bytes.

## Verification
- Full non-live pytest: **1024 passed, 5 skipped, 0 failed** (excluding one PRE-EXISTING broken collector,
  `tests/test_regress_store_never_cache_empty.py`, which imports the deleted `layer1b.compare` — unrelated).
- Live in-process smoke (new code, real vLLM + DBs): "voltage and current for PCC Panel 1" 5/5 real cards; "energy and
  power for GIC-01-N3-UPS-01" 4/4 real cards; 0 blanks, 0 errors, honest per-leaf gaps intact. Executor cards fill
  165-615ms each.

## Deliberately DEFERRED (not half-baked)
- **Executor UNION-ALL member batching + request-scoped read memo** (EXEC-2/3/5/7, DB-4/11): collapses the 28-member
  sequential per-card loops in `members.py` into batched statements. Byte-identical in intent but touches the carefully
  built member aggregation (present-column tolerance, reversed-CT pick_mover, section filters) — needs a deterministic
  replay/payload_diff oracle over saved panel recipes to PROVE per-member value identity. The connection pool (#3)
  already captured the cross-card serialization portion of this win; the remaining per-card round-trip batching is the
  next dedicated pass with the oracle.
- **obs per-query event sampling** (OBS-1/2/6): would cut telemetry volume but reduces the fidelity of the very obs
  tables this audit runs on — hold until the audit/tuning work settles.
- **Built FE bundle vs `npx vite` dev mode** (S8): an ops change to the live dev server (kills HMR the user relies on
  over Tailscale) — a deploy-mode decision for the user, not a silent flip.

## Not yet committed — changes are live in the working tree (systemd runs the tree); commit on request.

## Serving-side follow-ups tested 2026-07-14 (post-cluster)

### MTP speculative decode — TRIED, REVERTED (dead end on this checkpoint)
Cert replay of 12 real l2_emit prompts (mtp_baseline/mtp_mtp/mtp_revert.json): MTP = **0.59x — 41% SLOWER**
(149.5s -> 254.1s). Root cause: the checkpoint's mtp head is a FULL MoE layer (drafting costs ~a base step), so even
97-100% acceptance cannot win at num_speculative_tokens=1. Side finding: greedy temp0/seed42 is deterministic only
WITHIN one server process — across restarts kernel autotune FP diffs flip near-tie argmax (revert != baseline on 11/12).
Byte-identity certs for serving changes are therefore only valid within a server lifetime.

### Tuned fused-MoE kernel config — INSTALLED, measured a WASH (kept, zero-cost)
The untuned-MoE warning suggested headroom; borrowed upstream's tuned table for the same GB202 silicon
(`E=256,N=512,...RTX_PRO_6000_Blackwell_Server_Edition,fp8_w8a8,block_shape=[128,128]`), staged under this GPU's
Max-Q filename (provenance copy: ops/moe_configs/). Adopted on restart (journal: "Using configuration from ...").
Measured (moe_bench.py, 8 real emits, solo + cc4): solo 589 -> 590 chars/s; cc4 median 362 -> 367 chars/s; cc4
aggregate 299 -> 280-327 tok/s (noise). **No win** — at production batch sizes (1-4 reqs x 8 experts/tok) the MoE GEMMs
are memory-bandwidth/power-bound on the Max-Q card, so tile tuning doesn't move them. Kept (at-worst-equal, silences
the misleading "sub-optimal" warning); NOTE it lives in site-packages -> re-stage after any vllm upgrade.

**Conclusion: the serving-config family is exhausted.** Decode is ~150 tok/s/req solo, ~95 tok/s/req at cc4 —
bandwidth-bound. Remaining decode levers all reduce TOKENS or CALLS (L2 roster-DIFF diet, max_tokens cap, recipe
cache) or overlap work (lane parallelism, streaming shell) — all behavior-gated, per the audit roadmap.
