# Database Audit — pipeline_v48 (lens: database) — 2026-07-12

Scope: `db/` (75 .sql + 1 .py seeder), `data/` access layer, `config/app_config.py` + `config/databases.py` + `config/neuract_dsn.py`, `registries/neuract/_db.py`, `ems_exec/data/neuract.py`, and the live cmd_catalog (:5432) / neuract (:5433 tunnel) databases (read-only inspection). All line numbers were read directly; all measurements were taken live during this audit.

**Live facts measured today:** neuract `gic_*` = **12,994,419 rows across 302 tables** (memory docs still say ~890k — the data has grown ~14x). cmd_catalog has 53 public tables + a 22-table `equipment` schema; `app_config` = 309 rows. Registry mirror last synced **2026-07-06** (6 days stale).

---

## CRITICAL

### F1. The `::timestamptz` cast defeats every time index — all hot-path reads are full seq scans of ever-growing tables

Every neuract time-series read orders/filters on `timestamp_utc::timestamptz` (`_tsexpr()`, `ems_exec/data/neuract.py:137-139`, used by `latest` :152, `latest_ts` :172, `window` :199/208/213, `series` :246, `bucketed` :309, `bucketed_raw_series` :339, `edge_count` :373-377, `bucketed_edges` :405-411; same cast in `layer1b/resolve/has_data.py:37` via `DATA_TS_CAST`). The live tables have a btree index on the **raw varchar** column only (`idx_gic_01_n3_ups_01_p1_ts ON ... USING btree (timestamp_utc)` — verified via pg_indexes). A cast on the column side makes that index unusable.

Measured on the live DB (gic_01_n3_ups_01_p1, 78,399 rows):

```
ORDER BY timestamp_utc::timestamptz DESC LIMIT 1  →  Seq Scan + Sort, cost 4857   (95 ms end-to-end)
ORDER BY timestamp_utc DESC LIMIT 1               →  Index Scan Backward, cost 0.50 (55 ms; ~0 query time)
```

Worse, `has_data.py:20-40 value_counts()` — which runs on **every 1b resolution** (TTL-cached only 120 s, `data/ttl_cache.py`) — UNIONs up to 40 such subqueries per chunk. Measured: **10 tables = 5,199 ms**; a full 40-table chunk extrapolates to ~20 s, growing linearly with retention. The comment at `has_data.py:21-22` ("ORDER BY the TS column DESC, btree-indexed → cheap") is factually wrong.

Blast radius: per-card fills in ems_exec do one `latest()` per panel member (`ems_exec/executor/members.py:97`) — a 14-member panel card is 14 seq scans; `bucketed_rolled` (`members.py:225-232`) is one seq scan per member per series. At 12 samples/5min the tables add ~1.2M rows/meter/year; latency degrades linearly and the SSH tunnel saturates. This is a guaranteed SLO outage at enterprise scale, and is already costing seconds today.

**Fix (lightweight, in order):**
1. Verify text-format uniformity per table (`SELECT DISTINCT length(timestamp_utc)` — today: 32/35 chars, single `+05:30` offset). Where uniform, order/filter on the **raw column** and keep the cast only in the SELECT list (`ORDER BY timestamp_utc DESC`; window bounds compared as ISO text rendered in the same offset). `_tsexpr()` is the single choke point; `neuract.ts_cast` is already a DB knob.
2. Or add expression indexes via an `IMMUTABLE` wrapper fn (`neuract.ts_imm(text) → timestamptz`; deterministic because values carry explicit offsets) across the 302 tables — requires DDL rights on the plant-owned schema, so coordinate with the logger owner.
3. For `value_counts`, replace the 40-way UNION of jsonb-of-whole-row probes with the raw-text `ORDER BY ... LIMIT 1` form; measured saving is ~40 ms/table today, unbounded later.

Severity: **Critical**. Safe-or-breaking: **risky** (behavior-preserving intent, but it rewrites the hottest read path; the raw-text ordering must be gated on the uniformity check).

---

## HIGH

### F2. No migration ledger or apply-order manifest for 75 hand-applied SQL files

There is no `schema_migrations` table in cmd_catalog (verified: 53 public tables, none is a ledger), no apply-all runner, no Makefile target (searched `tools/`, repo root). Each file's header carries its own `psql ... -f db/<file>.sql` line; which files have been applied exists only in git history and human memory. Order dependencies are real:

- `db/fix_derivation_binding_repairs.sql:2` — "RUN AFTER db/seed_derivation_binding_full.sql".
- `db/seed_rate_of_change_class.sql:29-44` — bare `UPDATE app_config ... WHERE key='quantity.unit_classes'`: if `seed_quantity_class.sql` was never applied, this silently updates 0 rows (no error, vocab silently absent).
- `db/render_guarantee_seed.sql:45` — `DELETE FROM metric_class;` before re-insert (destructive if applied alone against hand-edited rows).
- `db/fix_derivation_binding_repairs.sql:38` — `DELETE FROM derivation_binding WHERE metric IN (...)`; a later re-run of an older seed *could* resurrect deleted rows (checked: the current seed family happens not to overlap — by care, not by construction).

Disaster-recovery rebuild of cmd_catalog from `db/` is therefore undocumented and order-sensitive. This is the single biggest operational risk to the "DB rows are the product's business logic" design: the DB now *carries* per-card recipes, guard thresholds and vocab, but cannot be reproducibly rebuilt.

**Fix (deliberately lightweight — not a framework):** one `schema_migrations(filename text primary key, sha text, applied_at timestamptz)` table + a ~40-line `db/apply.py` that applies files in filename order and records them; adopt `NNN_` filename prefixes going forward; take a nightly `pg_dump` of cmd_catalog as the real recovery path (the dump, not the seed files, is the source of truth for current state). Safe.

### F3. Re-running a knob seed silently reverts operator-tuned values (`ON CONFLICT DO UPDATE` clobber)

Nearly all 42 app_config knob seeds use `ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value` (e.g. `db/seed_cache_ttl.sql:9`). Seeds double as both "declare the knob" and "set its current value", so any re-apply is a config rollback. The team has already been bitten: `db/roster_recipe_schema.sql:39` — "'on' re-derived FROM LIVE 2026-07-06 (the valve was flipped on in production; **seeding 'off' would silently disable the interpreter on re-run**)". They also already invented the correct pattern for two rows: `db/seed_equipment_topology.sql:1-3,19` uses `DO NOTHING` explicitly because "these two rows are operator state" — but only that file (and the ratings seed) does.

**Fix:** make `DO NOTHING` the default convention for knob **declaration** seeds (INSERT the key + note + initial value once); value changes ship as explicit dated `fix_*.sql` or operator edits. One grep-able sweep over the 42 files. Breaking (it deliberately changes what a re-run does).

### F4. The pooled psycopg2 doors have no connect timeout and no statement timeout — the documented half-dead-tunnel freeze is unfixed on the hottest path

`config/databases.py:76-79` documents the exact failure ("a HALF-DEAD tunnel ... used to block every psql/psycopg2 connect for the OS TCP timeout (~2 min)") and fixes it with `PGCONNECT_TIMEOUT=5` — but only for `q()`'s psql subprocess (env at `data/db_client.py:15`) and `pg_connect()` (`db_client.py:32`). The two pooled doors that carry **all per-card data reads and live metadata reads** connect with `psycopg2.connect(**_dsn.conn_kwargs())` where `conn_kwargs()` (`config/neuract_dsn.py:60-69`) has **no `connect_timeout`**: `ems_exec/data/neuract.py:42` and `registries/neuract/_db.py:38`. Grep confirms no other `connect_timeout`/`PGCONNECT_TIMEOUT` in the runtime path, and **no `statement_timeout` anywhere**; `q()`'s `subprocess.run` (`db_client.py:12-16`) also has no `timeout=` — a post-connect tunnel stall parks the thread forever.

Failure: tunnel half-dies (its historical behavior) → every card-fill thread blocks ~2 min in connect (or indefinitely mid-query) → layer2's pool (4) and the host's request threads exhaust → site-wide freeze — precisely the class the degrade-gate was built to convert into an honest `data_unavailable` in seconds.

**Fix:** add `connect_timeout` (reuse `PG_CONNECT_TIMEOUT`/a cfg knob) to `conn_kwargs()`; add `options='-c statement_timeout=<knob>'` for the two pools; add `timeout=` to `q()`'s subprocess.run. Risky (hot path; failing fast is the intended behavior change).

### F5. The "pool" is one shared connection per DSN — all concurrent reads serialize through it

Both `_POOL` dicts are keyed by frozen DSN kwargs, so they hold **exactly one** psycopg2 connection each (`ems_exec/data/neuract.py:22-47`, `registries/neuract/_db.py:19-47`; diff confirms they are near-twins). psycopg2 connections serialize concurrent `execute()`s. With `layer2.emit_concurrency=4`, multi-card pages, and F1's 40 ms+ seq scans, every concurrent card fill queues head-of-line behind one socket over the SSH tunnel. Also a single wedged connection wedges everything until the next error pops it.

**Fix:** `psycopg2.pool.ThreadedConnectionPool(min=1, max=cfg('neuract.pool_max', 4-8))` behind the same `rows()/_run()` signatures; and fold the two near-twin modules into one shared door (the `_LOCK/_POOL/_key/_conn/_run` block is copy-pasted). Risky (hot path), behavior-preserving.

### F6. `cfg()` pins an empty config forever on first-load failure — the exact cache-poison class the team eradicated elsewhere

`config/app_config.py:18-24`: `_load()` is `@lru_cache(maxsize=1)` and returns `{}` on any DB error — and lru_cache **caches the `{}`**. If cmd_catalog is unreachable when the long-running host takes its first request, all 309 DB knobs silently revert to code defaults for the whole process life, even after the DB recovers. Any knob whose DB value deliberately differs from the code default (operator overrides, staged flips like `equipment.topology.panel_allowlist`, every `fix_*.sql` that changed a value without a code change) silently changes behavior with zero telemetry. This contradicts the 2026-07-09 poison-permanent-fix philosophy applied to every other cache (`data/ttl_cache.py:1-15`, never-cache-empty in `data/lt_panels/panel_members.py:62-67,121-122`).

**Fix:** never cache the failure result — on exception return `{}` *without* populating the cache (drop lru_cache for an explicit `_CACHE` dict or a TTLCache), optionally add a TTL so knob edits self-apply like everything else. Safe.

---

## MEDIUM

### F7. Three key-value knob stores implement the same abstraction

Verified live: (a) `app_config` — 309 rows, typed `data_type`; (b) `data_quality_policy` carrying **generic non-quality knobs** as key/txt_value rows — 9 live rows of `scope_map.*` / `page_tail_alias.*` / `placeholder.*` (pattern documented in `db/seed_endpoint_resolve_policy.sql.retired:8-31`); (c) `viewer_policy` scalar knobs smuggled as `page_key='__knob__:<key>'` rows (`db/round2_config_schema.sql:12-17`; 3 live rows, e.g. `__knob__:viewer.rating_vocab`). Three lookup conventions, three documentation homes, three failure modes for the same "named scalar" concept. New engineers must learn which store a knob lives in.

**Fix:** fold (b)'s generic rows and (c)'s `__knob__` rows into `app_config` with sections (`scope_map`, `viewer`); keep `data_quality_policy` strictly numeric data-quality policy. Breaking (readers + rows move; small, mechanical).

### F8. `derivation_binding`'s net state is spread across 8+ files and cannot be reconstructed from any one of them

Files mutating the one table: `render_guarantee_schema.sql:59-64` (CREATE), `derivation_expression_schema.sql:10-12` (ALTER add expression/scope), `seed_derivation_binding_expressions.sql`, `seed_derivation_binding_full.sql`, `seed_derivation_binding_fnless_metrics.sql`, `seed_derivation_binding_gap6.sql`, `fix_derivation_binding_repairs.sql` (UPDATEs + `DELETE` :38), `fix_derivation_binding_loadpct.sql`, plus per-card `seed_card64_derivedkey_bindings.sql` / `seed_card41_loss_eff_proxy.sql` / `seed_card72_energy_reliability_metrics.sql`. Each is individually idempotent and well-commented, but "what should this table contain" has no canonical home. Same accretion pattern (milder) on `card_fill_recipe` (seed + patch_rtm_rail_recipes + patch_rtm_card7_policy + fix_ups_recipe_derivations + fix_card42... + seed_agentb_fill_fixes).

**Fix:** periodic consolidation step — dump the live table as the new dated canonical seed (`pg_dump --table=derivation_binding --data-only`), retire the superseded fix files to `db/applied/`. Pairs with F2's ledger. Safe.

### F9. SQL is built by f-string everywhere `q()` is used; the escaping helper is copy-pasted 18 times

`q()` (`data/db_client.py:11-21`) shells out to `psql -c` and cannot parameterize; 71 files import it. Escaping is ad-hoc per caller: **18 separate `def _esc`** definitions (grep verified: config/schema_map.py:52, config/metric_class.py:27, config/reason_templates.py:53, config/nameplates.py:285, layer2/emit/metadata/asset_3d.py:228, data/equipment/kitpreview.py:157, data/equipment/ratings.py:40, grounding/*.py, ems_exec/derivations/expressions.py:14, …) plus `$k$..$k$` dollar-quoting in partition/fallback_edges.py. Identifier interpolation is separate again (`has_data.py:37` interpolates table names inside `"{t}"`). Most interpolated values are registry/DB-sourced (low injection likelihood), but some flow from LLM emit output (e.g. `rating`/`page_type` in `layer2/emit/metadata/asset_3d.py:98-99`), and one forgotten `_esc` is a syntax-error-shaped outage (or worse) waiting on a name containing `'`.

**Fix:** a parameterized local-catalog door already exists as a pattern (`registries/neuract/_db.py` — pooled, `%s` params); add a cmd_catalog twin and migrate the config readers to it (also removes the 3.2 ms-per-query subprocess tax measured vs 0.01 ms pooled — 300x); keep `q()` for scripts/seeder. One shared `esc()` in the interim. Risky (touches ~30 call sites on warm paths), behavior-preserving.

### F10. Mirror-first registry has no staleness guard — last synced 6 days ago, manual re-run only

`registry_sync_meta` (live): all `registry_*` tables synced **2026-07-06 17:59** (today is 07-12). `scripts/sync_neuract_registry.py:1-12` says "Re-run whenever the plant DBs change" — a human-memory trigger. The mirror is the primary source for routing/topology (`data/registry/lt_mfm.py:2-6` — "no request-time read rides the flaky :5433 tunnel"), so a meter added/rewired/renamed in the plant registry silently does not exist for the pipeline until someone remembers to sync; nothing reads `synced_at` at runtime, no health surface, no cron.

**Fix:** cron the sync (it is already atomic per table) + expose `max(synced_at)` age on the host health endpoint + stderr-warn when older than a `registry.max_staleness_h` knob. Safe.

### F11. Two parallel member-resolution stacks; the executor's one rides the live tunnel at request time

`data/lt_panels/panel_members.py` (used for coverage) walks the **local mirror** via `data/registry/lt_mfm.py`. But `ems_exec/executor/members.py:36-38 resolve()` gets the actual member list from `registries/neuract/members.py`, which reads the **live** `lt_mfm_*` edge tables over :5433 (`registries/neuract/_db.py` → `neuract_dsn`). So one card's members come from live neuract while its coverage denominator comes from the mirror — they can diverge whenever the mirror is stale (F10) or the tunnel flaps (members=[] while mirror says expected=14 → wrongly "0 of 14 reporting"). It also contradicts lt_mfm.py's own stated directive that request-time metadata never rides the tunnel.

**Fix:** point `registries/neuract/members.py` membership reads at the mirror-first accessors (or have `executor/members.resolve` consume `panel_members`/`outgoing_feeders` directly), keeping live as fallback exactly like lt_mfm.py does. Breaking (changes the executor's membership source; needs a sweep re-cert).

### F12. `seed_schema_and_endpoints.py` TRUNCATEs before deriving, non-transactionally, from the flaky tunnel

`db/seed_schema_and_endpoints.py:81` runs `TRUNCATE schema_slot_map` as its own psql invocation (q() = one subprocess per statement, so no wrapping transaction), then `:84 _cols()` reads live neuract via `q("target_version1", ...)` which **raises** on tunnel failure — crash after the TRUNCATE leaves `schema_slot_map` empty until a successful re-run (readers like `config/schema_map.py` then return `{}`/None for every slot → every routed mapper honest-blanks fleet-wide). Same shape for `endpoint_policy` at :104. Additionally a renamed representative table only warns and *skips the whole fingerprint* (:85-87).

**Fix:** derive rows first, then emit `BEGIN; TRUNCATE ...; INSERT ...; COMMIT;` as one q() call (psql -c is a single implicit transaction). Safe.

### F13. V48 config tables have no FKs and no vocab CHECKs — integrity is convention-only

`pg_constraint` (live): FKs exist only on the V47-era tables (cards, card_component_usage, contract_*, page_layout_cards, card_controls, card_combo_member — 12 total). None of the V48 tables reference anything: `card_fill_recipe.card_id`, `card_rendering.card_id` (`db/roster_recipe_schema.sql:5,15`), `endpoint_policy.page_key`, `metric_class.page_key`, `card_feasibility`, `card_handling`, etc. `app_config.data_type` has no CHECK (live \d shows only the pkey), and `_cast` (`config/app_config.py:27-39`) silently returns the code default on a bad value — a typo'd `data_type`/unparsable value is invisible. Today the data is clean (verified: 0 orphan card_ids in card_fill_recipe and card_rendering; data_type values all in-vocab) — but only because the same few people hand-apply everything; at team scale a typo'd card_id row just silently never matches.

**Fix:** add the cheap FKs (`card_fill_recipe.card_id → cards(id)`, `card_rendering.card_id → cards(id)`), a CHECK on `app_config.data_type IN ('number','int','bool','json','text')`, and (optionally) a `db/validate.sql` invariant script run after applies. Risky (future bad writes start failing loudly — that is the point).

### F14. has_data chunk fail-open fabricates "data-bearing" for 39 innocent tables when 1 table in the chunk is bad

`layer1b/resolve/has_data.py:41-53` (`value_counts`) and `:110-118` (`tables_with_data`): a **non-outage** chunk error (e.g. one ghost table name — and the registry is known to carry 14 ghost-table rows, `data/registry/lt_mfm.py:12-13` / F11 sync note) fails the whole 40-table UNION, and the handler marks **every table in the chunk** as data-bearing (`counts[t] = VALUE_MIN` / `live |= set(part)`). Genuinely empty/never-wired meters in that chunk then pass the has-data gate and get offered/resolved — a fabricated resolution signal in a zero-fabrication pipeline (downstream leaf gates catch the payload, but routing/picker behavior is already wrong).

**Fix:** on chunk failure, retry per-table (binary-split or singly) so only the actually-bad table gets the fail-open treatment. Risky (resolution outcomes change in the error case — deliberately).

### F15. Table-per-meter fan-out has no local rollup — panel/overview reads scale O(members × leaves) over the tunnel

The plant schema is table-per-meter (302 gic_* tables) and V48 correctly does not fight that. But every aggregate consumer re-reads members one table at a time: `ems_exec/executor/members.py:86-97` (one `latest()` per member), `bucketed_rolled` :225-232 (one bucketed scan per member per series), `has_data` UNION probes per candidate set. There is no "latest row per meter" rollup anywhere local, despite the registry mirror precedent proving the pattern (sync_neuract_registry.py). Combined with F1/F5 this is the scaling wall for panel-overview pages (the 24-card pages in the memory docs).

**Fix (additive, no schema fight):** a tiny `meter_latest` local cache table (mirror-style: one sweep every N seconds writes 302 latest rows into cmd_catalog) serving `latest()`/has_data probes; per-member history reads stay live. Safe.

### F16. The roster_spec JSONB DSL is unvalidated business logic in DB rows

`db/seed_roster_recipes.sql` (623 lines) encodes per-card fill programs in a compact JSON DSL (`{"b":"col","c":...,"q":...,"r":2}`, `$same_as_slot`, modes elements/aggregates/sections — :7-48 for card 2) whose vocabulary lives in a docs file and whose interpreter is `ems_exec/executor/roster*.py`. This satisfies the AI-first/no-per-card-builders principle *by relocating* the per-card logic into rows — which is fine and editable-without-deploy, but there is no schema validation: a typo'd binding key (`"b":"cols"`) or misspelled slot is discovered only as an honest-blank leaf at render time. The principle itself creates the gap: code would have failed at review/test time; rows fail silently in production.

**Fix:** a JSON Schema for `roster_spec` + a test that validates every live `card_fill_recipe` row against it and against the interpreter's actual vocab (introspected from roster_eval), run in the suite. Safe.

---

## LOW

### F17. TTLCache never evicts; frozenset-keyed caches grow without bound

`data/ttl_cache.py:12-15` ("No deletion on expiry") + `__setitem__` :48-53 only ever adds; `has_data.py` keys `_CACHE`/`_VAL_CACHE` by `frozenset(tables)` (:26,:98) — every distinct candidate set ever seen stays resident (value dicts of up to 302 entries) for the life of the long-running host. Slow leak, not a correctness bug. Fix: opportunistic purge of expired keys on set (a 3-line loop) or a max-entries bound. Safe.

### F18. `timestamp_utc` is a misnomer: it stores +05:30-offset ISO text of varying length

Live sample: `2026-07-12T02:25:11.230047059+05:30`, lengths 32 and 35. Any future code assuming UTC or naive lexicographic ordering (the F1 raw-text fix!) must first normalize/verify format; sub-second lexicographic ties can mis-order across differing fraction lengths. Document it where `DATA_TS_COL` is defined (`config/databases.py:20-21`) and gate the F1 fix on a per-table uniformity check. Safe.

### F19. Plaintext DB password knob in app_config

`config/neuract_dsn.py:39` reads `cfg("neuract.password", ...)` — when production moves off trust-auth, a live credential will sit as a plaintext app_config row that is also routinely SELECTed/dumped by seeds and audits. Keep credentials in env/secret store; leave only host/port/db in app_config. Safe.

### F20. Schema/seed boundary blur + minor hygiene

- `db/roster_recipe_schema.sql:31-41` mixes CREATE TABLE with app_config INSERTs (a "schema" file that mutates knobs on re-run — interacts badly with F3).
- Most knob upserts do not touch `updated_at` on conflict (e.g. seed_cache_ttl.sql:9 sets value+note only), so `updated_at` lies about freshness for re-applied rows.
- `db/__pycache__/` is untracked (gitignored — verified), so not a repo hygiene issue; fine to delete locally.
- The `.sql.retired` rename convention is actually good — keep it, but move retired files to `db/retired/` so the live directory is the apply set (helps F2's runner).

---

## What is genuinely good (keep)

- **Idempotency discipline is unusually strong**: guarded UPDATEs (`IS DISTINCT FROM`, `WHERE ... = '"[Circular]"'::jsonb` in fix_hpq_circular_payloads.sql:17), `ON CONFLICT` upserts, `IF NOT EXISTS` schema — nothing found that double-inserts on re-run (spot-checked seed_rate_of_change_class, seed_asset_tap_layout, seed_asset_backend_strategy: UPDATE-only, safe).
- **Provenance comments** are exceptional — every knob row carries its code-default mirror file:line in `note`; fix files read like incident reports.
- **`registries/neuract/_db.py`** is the right client design (pooled, parameterized, read-only session) — the fix for F9 is "more of this", not something new.
- **The registry mirror + sync-meta stamping** is the right pattern for the flaky tunnel; F10/F15 are about finishing it, not changing it.
- The **fail-open telemetry / fail-fast data split** and never-cache-empty poison fixes (panel_members.py) are principled — F6 is the one spot the principle missed.

## Measurements appendix

| Probe | Result |
|---|---|
| psql subprocess q(), local | 3.2 ms/query |
| pooled psycopg2, local | 0.01 ms/query |
| q() over :5433 tunnel (connect per call) | 54 ms/query |
| latest-row with `::timestamptz` cast (78k rows) | 95 ms (Seq Scan+Sort, cost 4857) |
| latest-row raw-text ORDER BY | 55 ms (Index Scan Backward, cost 0.50) |
| value_counts UNION pattern, 10 tables | 5,199 ms |
| neuract gic_* total | 12,994,419 rows / 302 tables |
| registry mirror last sync | 2026-07-06 (audit date 2026-07-12) |
