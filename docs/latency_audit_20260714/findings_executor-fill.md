# Latency audit — LENS: executor / data fill (2026-07-14)

Scope: ems_exec/executor/*, ems_exec/renderers/*, ems_exec/data/neuract.py, data/neuract_pool.py,
host/exec_cards.py, host/multi_asset.py, /api/frame. READ-ONLY audit; all numbers measured live
(obs_* tables on :5432, timings on :5433) on 2026-07-14.

## Headline mechanism (the whole lens in one paragraph)
Executor latency is ~100% DB-round-trip latency, not CPU (all post-fill passes measured 2-3ms each).
Every neuract read costs ~25ms floor (16ms SSH-tunnel RTT + ~9ms exec, measured). Panel-aggregate
cards issue **hundreds of sequential single-purpose queries** (card 14 = 686 queries, 616 of them
single-column window-endpoint reads = 48.5s of its 52.7s span), and ALL threads of the 8-way card
fan-out serialize on **ONE shared psycopg2 connection** (data/neuract_pool.py `_POOL` keeps exactly one
conn per DSN), so a 4-panel-card page's exec wall = the sum of every card's queries (verified: summed
card walls 141.5s == summed query latency 141.6s in trace t_10ca41775..., executor parent clipped at
the 45s budget). Fixes are multiplicative: (1) a real N-connection pool, (2) query batching/dedup
inside the roster fan-out, (3) request/TTL memoization across slots+cards+frames, (4) parallel lanes.

## Measured baselines gathered this audit
- :5433 tunnel `SELECT 1` RTT: med 15.9ms (15.1-18.6).
- window-endpoint query (`WHERE ts_imm >= X ORDER BY ts_imm ASC LIMIT 1`): 21-25ms wall, 8.7ms server
  (seq scan OK on small tables; ts_imm expression indexes exist; 373 tables, 22.6M rows total,
  biggest table 375k rows).
- bucketed 30d hourly, 1 column: 38ms. Same scan with 6 columns: 35ms → multi-column is FREE.
- UNION ALL batching 28 tables × (first+last) in ONE statement: 165ms vs 971ms as 56 sequential
  queries (uncontended) — 5.9×; vs ~24.6s at observed production pacing (616 × 40ms).
- edge_count LAG scan: 163ms full-table (273k rows), 83ms windowed 7d.
- obs executor.card spans (n=1909): p50 1.04s / p90 6.8s / p99 26s / max 52.7s.
  By handling: panel_aggregate n=457 p50 6.08s p90 17.2s (median 106 queries, p90 253);
  run_card n=1358 p50 816ms (median 35 queries — also pure round-trip bound: 35×25ms≈875ms);
  narrative_ai p50 889ms; asset_3d p50 59ms.
- neuract per-query in executor stage: avg 75ms / med 58ms (INCLUDES single-conn lock wait);
  cmd_catalog local avg 0.7ms (negligible).
- frame traces (/api/frame, one card each): n=262 p50 1.68s p90 7.9s max 19.6s.
- executor parent span: p50 1.12s p90 7.7s max 45001ms (= budget clip).

## FINDINGS (ranked)

### F1. Single shared neuract connection serializes the whole 8-way card fan-out  [BIGGEST STRUCTURAL]
- Evidence: data/neuract_pool.py:27 `_POOL: dict = {}` maps (readonly, dsn)→ONE psycopg2 conn;
  run_read (line 80-96) executes on that one conn from all 8 exec threads (host/exec_cards.py:250
  max_workers≤8). psycopg2 serializes concurrent cursors per connection.
- Proof: trace t_10ca417759b44007b72f9e900e1cc2dd — 4 panel cards ALL started 08:55:19.665; summed
  card walls 48.4+34.5+32.0+26.6 = 141.5s; summed neuract query latency = 141.6s over 1204 queries.
  Per-query "latency" med 58ms vs 25ms uncontended = lock wait is being measured. Executor budget
  (45s) fired; card 14 harvested late at 48.4s.
- Proposal: psycopg2 `ThreadedConnectionPool(min=2, max≈8-12)` in data/neuract_pool.py (same DSN,
  keepalives, drop-broken semantics); size ≥ host exec pool. Flag-gate V48_DB_POOL_N.
- Saving arithmetic: page exec wall = Σ(all cards' queries)×~40ms today. 4-card panel page: 1204
  queries → wall ~45s. With 8 conns: wall ≈ slowest card's own queries (686×25ms ≈ 17s pre-batching)
  → **-28s exec wall on the 4-panel-card page**, and /api/frame bursts stop queueing behind runs.
- Effort: small. Risk: low (semantics preserved; caps server conns).

### F2. member_delta reads 4 sequential endpoint queries per member per delta key; batchable to O(1)/slot
- Evidence: energy_registers.py:62-83 member_delta → member_delta_pair(import)+(export), each
  `_nx.window(tbl,[col])` = 2 queries (ASC+DESC) → 4/member/key. neuract.py window() (175-207)
  ALREADY accepts a column list — but callers pass one column at a time.
  Card 14 recipe (cmd_catalog card_fill_recipe): slot1 scalar {activeKwh delta, range this-month},
  slot2 entries {activeKwh+reactiveKvarh deltas}, slot3 entries SAME element again + prepare_ctx
  panel_kwh (members.py:185-203, run window) → predicted ~672 endpoint queries; observed 686 total,
  616 endpoint reads costing 48.5s of the 52.7s worst span (obs_db_queries shapes: 308 ASC + 308 DESC,
  med 33-40ms, p90 190-210ms).
- Proposal (layered, all AI-first-safe — recipes untouched):
  a) member_delta_pair for a paired register reads BOTH registers in ONE window() call → 4→2 queries.
  b) roster prepare: gather ALL delta columns referenced by the roster per (window) and read each
     member's first+last row for the full column set in ONE pair → 2 queries/member/window.
  c) UNION ALL across members (measured 165ms for 28 tables first+last): → 2 statements per
     (window, colset). Card 14 has 2 windows (run, this-month) → ~4-8 statements total.
- Saving arithmetic: 616 queries × ~40ms ≈ 24.6s (uncontended ~15.4s) → ~4-8 statements × ~165ms ≈
  0.7-1.3s. **-40s+ on the worst panel-power card (52.7s → <5s); -10s+ p50 on panel_aggregate cards
  (p50 6.1s, median 106 queries → ~15).**
- Effort: medium. Risk: medium (must keep per-member honest-null semantics; UNION ALL leg easily
  verified vs sequential results; flag-gate).

### F3. Duplicate query executions: identical element evaluated per slot, per card, per frame — no memo
- Evidence: card 14 slots 2 & 3 have byte-identical element+range+role_filter → _eval_elements
  (roster_eval.py:53-58) re-runs the full 28-member × 2-delta-key read (224 dup queries). Trace-wide:
  1204 neuract queries, only 337 DISTINCT sql_texts; 867 re-executions carrying 114.6s of the 141.6s
  recorded latency (params differ only across the few distinct windows). 4 panel cards on the SAME
  panel each independently re-run resolve() + rows() (28 latest reads) + panel_kwh (112 queries).
- Proposal: TTLCache (30-60s, keyed (table, col/colset, window-tuple)) on member_delta_pair +
  members.rows + panel_kwh + bucketed_rolled reads in members.py/energy_registers.py — same
  never-cache-empty pattern already used for present_columns. Within-run state memo for
  _eval_elements keyed (id(element_spec)-equivalent json, window, rf, ro) in _roster_state.
- Saving: ~867 × 40ms ≈ **-35s summed query time on the 4-panel-card page** (wall -8-15s combined
  with F1); on /api/frame synced date-change (4 panel cards re-POST), members are read ONCE not 4×.
- Effort: small-medium. Risk: low (TTL bounded staleness = the pattern the codebase already accepts
  for present_columns/panel_members; 30s stale panel latest-row is within sampling cadence).

### F4. _context_vals recomputes panel_kwh from scratch (~112 queries) though agg_row already holds it
- Evidence: roster_eval.py:76-85 `_context_vals` calls `_members.panel_kwh(state["pairs"], ...)`;
  prepare_ctx already computed the identical value into `agg_row[energy_col]` (roster.py:169-177).
  Fires whenever any reducer/sankey names context (panel_kwh) — 28 members × 4 queries ≈ 4.5s.
- Proposal: `state["_context_vals"]` reads `state["agg_row"].get(energy_col)` when present.
- Saving: **-4.5s on sankey/reducer panel cards that reference panel context**. Effort: config-tiny.

### F5. bucketed() is one-column-per-query; multi-column scan measured FREE
- Evidence: neuract.py:282-304 bucketed(table, col, ...) — one GROUP BY scan per column.
  fill._bucketed_values (series_fill.py:20-55) → per FIELD; members.bucketed_multi (members.py:275-348)
  → per key × per member; bucketed_rolled_members → per member. Measured: 6-col 30d hourly scan 35ms
  ≈ 1-col 38ms. series() (neuract.py:213) already implements the multi-column form.
- Proposal: group bucketed reads per (table, window, sampling) → ONE multi-col query: in fill()
  (group the card's bucketed fields), and in bucketed_multi (group the avg-kind specs per member).
- Saving: a 3-key × 28-member trend card: 84 → 28 queries ≈ **-2.2s/card**; a 6-series single-asset
  history card: 6 → 1 queries ≈ -0.2s/card; multiplies with F1/F3.
- Effort: medium. Risk: low (same SQL family; per-column honest-degrade preserved by padding).

### F6. Multi-asset compare fills assets SEQUENTIALLY (host/multi_asset.py:127-138)
- Evidence: `for group in groups: for asset in assets: assemble_cards(...)` — each assemble_cards
  runs the full _run_cards fan-out; 3-feeder compare = 3 sequential executor rounds. RESPONSE_MULTI
  p50 142s, slowest 410-441s (8-12 cards × 3 assets). Exec share ≈ 3 × per-asset exec (p50 1.1-7.7s,
  panels ≫).
- Proposal: ThreadPool over assets (lanes independent by construction — recipe is authored once,
  rebind_consumer is pure); requires F1 pool to be effective.
- Saving: exec stage of a 3-asset panel compare ≈ 3×15s → ~15s (**-30s**); with F2/F3 the absolute
  numbers shrink but the 3× → 1× ratio stands.
- Effort: small. Risk: low (cards already run in a pool; same per-card seam).

### F7. /api/frame date-change re-runs the FULL member fan-out per card, serialized
- Evidence: host/server.py:289-341 handle_frame → fill_one_card (same seam as initial serve; no
  cross-frame reuse). FE fires one POST per synced card (host/web/src/api.ts:150). frame traces
  p50 1.68s / p90 7.9s / max 19.6s PER CARD; a synced date change on a 4-panel-card page = 4
  concurrent frames that serialize on the single conn → settle time ≈ Σ ≈ 4×6s ≈ 24s worst.
- Proposal: F1+F3 fix most of it (pool un-serializes; TTL memo keyed (mfm_id, window, colset) makes
  frames 2..N nearly free). Optionally a page-level /api/frames batch endpoint to cut N×HTTP+
  re-prepare overhead (FE change; flag-gated).
- Saving: date-change settle on a panel-overview page **~24s → ~2-3s** (first frame pays the batched
  reads, the rest hit the memo).

### F8. panel_kwh + agg_row + rows() re-run per card on the same panel (renderer path too)
- Evidence: renderers/panel_aggregate.py:209-232 (recipe-less path) — resolve + rows(28 latest) +
  agg_row + _panel_energy_kwh (28×4 endpoint queries) + _fill_bucketed_series (per declared series ×
  28 members) + _fill_rolled_load_factor rolls _KW AGAIN even when _fill_bucketed_series just rolled
  the same column (no per-render cache: roster.py path and renderer path both).
- Proposal: per-render memo of rolled series keyed (col, window, sampling, role_filter) inside the
  render; plus the F3 TTL for cross-card.
- Saving: one duplicated 28-member roll ≈ 28×38ms ≈ **-1.1s per recipe-less panel card** with a
  load-factor leaf; rows/panel_kwh dedup counted under F3.

### F9. Event KPIs: LAG scans per member per flag column
- Evidence: neuract.py:347-405 edge_count/bucketed_edges — LAG over raw rows; measured 83ms (7d
  window) / 163ms (full table 273k rows). bucketed_multi kind='event' loops members sequentially
  (members.py:313-317); fill kind='event' with window=None (snapshot card) = full-table scan.
- Proposal: (a) always push a sensible start bound for snapshot event counts (e.g. freshness window)
  where the semantic allows — needs owner sign-off since 'lifetime' counts are a real contract;
  (b) batch per (col, window) across members via UNION ALL of per-table LAG subqueries;
  (c) parallelize under F1.
- Saving: 28-member event-timeline card: 28×83-163ms ≈ 2.3-4.6s → ~0.3s batched (**-2 to -4s/card**).

### F10. rows(): 28 sequential latest() reads — batchable to ONE statement
- Evidence: members.py:114-127 loop; obs card-14 span shows 24 × 22-col `ORDER BY ts_imm DESC LIMIT 1`
  totalling 1.8s (contended). UNION ALL 28-table endpoint measured 165ms.
- Proposal: one UNION ALL statement (per-table col padding handled by building per-table SELECT lists
  from the shared present_columns cache).
- Saving: **-1.5s per panel card** (before F1; still -0.5s after). Subsumed by the F2 batching family.

### F11. freshness.apply issues latest_ts per card — identical across a page on one table
- Evidence: freshness.py:127 `_nx.latest_ts(asset_table)` per card; card-14 span shows 3 single-col
  DESC LIMIT 1 reads ≈ 0.4s (contended). 8-card single-asset page = 8 identical queries.
- Proposal: TTLCache(10-30s) keyed table in neuract.latest_ts.
- Saving: (N-1)×~30-150ms/page ≈ **-0.2 to -1s per page**, more under contention. Effort: tiny.

### F12. _field_value NULL fallback re-queries latest() per field for a column already batch-read
- Evidence: fill.py:203-205 — `raw = latest_row.get(col); if raw is None: raw = _nx.latest(table,[col])`
  — when the batched latest row legitimately holds NULL for col, this re-asks the SAME question,
  one query per null raw field (~25-150ms each).
- Proposal: only fall back when `col not in latest_row` (i.e. it wasn't in the batched read), not on
  a NULL value.
- Saving: 1-5 queries/card on partially-dark meters ≈ **-0.1 to -0.5s/card**. Effort: tiny.
  (Behaviour note: today's re-read can only return the same latest row — provably identical result.)

### F13. Exec budget (45s) fires on QUEUE time, not card work — spurious honest-blanks add retry latency
- Evidence: exec_cards.py:242-284 — budget measured against wall while queries queue on the single
  conn; trace t_10ca...: executor span exactly 45001ms, card 14 harvested at 48.4s only via the
  done-check race. Cards that would finish in 5s uncontended blank as 'executor budget exceeded' →
  user re-runs → more load.
- Proposal: F1/F2/F3 shrink wall below budget; optionally scale budget on outstanding-query depth.
  (No change to the honest-degrade contract.)

## Dead ends / non-findings (measured, do not pursue)
- CPU post-fill pass chain: yscale 3.3ms, view_select 2.5ms, display 2.0ms, trend_badge 2.4ms,
  sweep_sankeys 1.9ms per ~100KB card payload (incl deepcopy) → whole ~15-pass chain ≈ 20-40ms/card.
  Fusing passes is NOT worth complexity; per-leaf degradation stays untouched.
- present_columns / column_types / column_logged caching: already TTL-cached (120s), shared pool
  cache; introspection ~39-51ms first-touch per table — fine.
- ts_imm expression indexes: present on gic_* tables (673 indexes); endpoint queries are already
  index-eligible; small tables seq-scan by choice (8.7ms) — no index work needed for LIMIT 1 shapes.
- cmd_catalog reads in exec path: avg 0.7ms local — negligible.
- obs sql_trace overhead: rides local cmd_catalog, sub-ms — negligible.

## Scenario roll-ups (estimated, after F1+F2+F3+F5)
- Cold 5-8-card panel-overview page: exec wall today ~45s (budget-clipped; Σ queries 141s) →
  ~2-4s (batched, pooled, memoized). ≈ **-40s p50 on that page's exec stage.**
- Cold single-asset dashboard (8 run_card cards, median 35 q/card ≈ 280 q serialized ≈ 7-11s exec):
  → pooled (÷8) + multi-col bucketed + F12 ≈ 1-2s. ≈ **-5 to -9s.**
- Multi-asset 3-feeder compare: -30s from lane parallelism (F6) on top of the above.
- /api/frame date change on panel page: ~24s settle → ~2-3s (F1+F3). Single-card frame p50 1.68s →
  <0.5s for memo-hit cards.
