# Concurrency Audit — pipeline_v48 (2026-07-12)

Lens: thread/async safety of caches, the layer2 emit cap, race windows between stages and files,
env-var parameter passing, and signal/shutdown handling. All line numbers below were read in this session.

Runtime model verified first: there is **no asyncio anywhere in the pipeline** (grep for `asyncio|async def`
returns nothing outside archives). Concurrency is entirely threads: `ThreadingHTTPServer` per-request threads
(host/server.py:346-354, copilot/server.py:119), `run/parallel.py` ThreadPoolExecutors for the 1a∥1b split and
the L2 fan-out, and an 8-worker ThreadPoolExecutor for the per-card executor fan-out (host/exec_cards.py:175).
So every module-level dict/cache in the tree is shared cross-thread state, and every finding below is judged
against that.

---

## CRITICAL

### C1. A half-dead :5433 tunnel wedges the whole host: no query timeouts anywhere, one shared connection, and the "budget" can't cut a hung card loose

**Files:** `config/neuract_dsn.py:60-69`, `ems_exec/data/neuract.py:22-66`, `registries/neuract/_db.py:19-65`,
`data/db_client.py:11-22`, `host/exec_cards.py:174-190`.

- `config/neuract_dsn.conn_kwargs()` (neuract_dsn.py:60-69) builds the psycopg2 kwargs for BOTH pooled doors
  (`ems_exec/data/neuract.py:42`, `registries/neuract/_db.py:38`) with **no `connect_timeout`, no
  `keepalives*`, no `options='-c statement_timeout=…'`**. The team already knows this failure mode:
  `config/databases.py:76-79` documents the half-dead tunnel ("SYN unanswered … blocked every psql/psycopg2
  connect for the OS TCP timeout (~2 min)") and fixed the *connect* phase with `PGCONNECT_TIMEOUT` — but that
  env dict is only injected into the **psql subprocess** (`data/db_client.py:15`), and databases.py:79 says it
  outright: "CONNECT-phase only — query runtime is never limited by this." `data/db_client.pg_connect`
  (db_client.py:26-32) even sets `connect_timeout=5`, proving the fix exists — it just never reached the two
  pooled psycopg2 doors that carry all executor traffic.
- Worse: both pooled doors keep exactly **one shared psycopg2 connection per DSN key**
  (`_POOL[key] = c`, neuract.py:44, _db.py:44) handed to every thread. psycopg2 serializes `execute()` on a
  per-connection lock, so when the tunnel goes half-open **mid-query** (established TCP, forwarding dead — the
  documented flap mode), the hung `cur.execute` holds the connection lock for the kernel's TCP retransmission
  timeout (~15+ min, no keepalives configured), and **every other executor thread blocks inside `_run()`
  waiting for that same lock** — not failing fast, not honest-degrading, just stuck.
- The wall-clock budget that is supposed to contain exactly this ("a slow card degrades to ok=False … instead
  of sinking every other card", exec_cards.py:15-17) is dead code — see H1. And `data/db_client.q()`
  (db_client.py:12-16) runs `subprocess.run` with **no `timeout=` kwarg**, so a psql query hung mid-execution
  blocks its caller thread just as indefinitely (1a/1b/validate all ride q()).
- Net effect: one tunnel flap during a query → every in-flight `/api/run` thread wedges, ThreadingHTTPServer
  keeps accepting and spawning more threads that immediately wedge behind the same connection lock, clients
  retry, threads pile up unboundedly. The degrade gate never fires because nothing *raises* — everything
  *waits*. This is the outage the whole honest-degrade architecture is designed to prevent, and it bypasses
  all of it.

**Fix (behavior-preserving except that hangs become fast failures):**
1. Add `connect_timeout` (5), `keepalives=1, keepalives_idle=10, keepalives_interval=5, keepalives_count=3`,
   and `-c statement_timeout=<cfg knob>` to `conn_kwargs()` — one file, both doors inherit.
2. Add `timeout=` to `subprocess.run` in `q()` (DB-knob-driven, generous default).
3. Optionally per-thread connections or a small real pool (see M5) so one bad socket cannot serialize everyone.

---

## HIGH

### H1. The executor "wall-clock budget" (ER-8) is dead code — `_FTimeout` is unreachable

**File:** `host/exec_cards.py:174-190`.

```python
deadline = time.time() + _EXEC_BUDGET_S
with ThreadPoolExecutor(max_workers=max(2, min(len(tasks), 8))) as ex:
    futs = {ex.submit(_fill, cid, o): cid for cid, o in tasks.items()}
    for fut in as_completed(futs):            # <-- NO timeout argument
        ...
        completed_by_id[cid] = fut.result(timeout=remaining or 0.01)
```

`as_completed(futs)` is called **without a timeout**, so it blocks until each future actually completes; it
only ever *yields completed futures*. `fut.result(timeout=…)` on an already-completed future returns
immediately — the `except _FTimeout: status='executor budget exceeded'` branch (lines 184-186) can never
execute. Additionally the `with ThreadPoolExecutor(...)` context exit joins all worker threads, so even a
correctly-timed loop would still block at dedent. The advertised guarantee ("a slow card degrades … instead
of sinking every other card", lines 15-17 and the docstring at 140-145) is false; combined with C1 a single
hung neuract read blocks the entire page response indefinitely. Also note `_EXEC_BUDGET_S` is read at import
time (line 18), freezing the DB knob at process start.

**Fix:** `for fut in as_completed(futs, timeout=_EXEC_BUDGET_S)` inside `try/except TimeoutError`, mark all
unfinished futures' cards `executor budget exceeded`, call `ex.shutdown(wait=False, cancel_futures=True)` and
do not re-join (accepting orphaned worker threads — which C1's timeouts then bound).

### H2. The never-cache-empty rule is violated in three caches that ride the flaky tunnel — the exact poison class "fixed permanently" on 2026-07-09

**Files:** `ems_exec/data/neuract.py:24-25, 72-104`; `registries/neuract/_db.py:21, 93-107`.

The member-cache-poison incident (panel cards blank for the whole process life after one tunnel flap) was
fixed with TTLCache + never-cache-empty in `data/lt_panels/panel_members.py` and `data/registry/lt_mfm.py`.
The same pattern survives, un-fixed, in the hottest executor path:

- `ems_exec/data/neuract.py:present_columns` — on a flap `_run` returns `[]` (line 59-66), so
  `cols = frozenset(); _COLS_CACHE[table] = cols` (lines 84-85). The `hit is not None` check (line 76-78)
  treats the empty frozenset as a valid hit **forever**. From then on `_existing()` sees zero present columns
  for that table → `latest()` returns all-None, `bucketed()`/`series()` return `[]` — every card for that
  asset honest-blanks **until server restart**. Identical symptom to the original 8-hour incident.
- `ems_exec/data/neuract.py:column_logged` (lines 96-104) — a flap caches `False` per (table,col) forever, so
  the reason channel permanently claims a live column is "not logged by this meter", violating the module's
  own F7 rule stated at lines 92-94 ("never claim a live column is unlogged").
- `registries/neuract/_db.py:present_columns` (lines 97-107) — same empty-frozenset-forever pattern;
  `table_exists()` (line 114-116) then answers False for the process life.

(These two dicts are also mutated from many threads without a lock — that part is benign under the GIL; the
poison is the defect.)

**Fix:** make all three `TTLCache()` **and** skip caching empty results (`if cols: _COLS_CACHE[table]=cols`)
— exactly the panel_members.py:121-123 pattern. Schema is stable per process, so a healthy table re-reads at
most once per TTL.

### H3. The layer2 emit concurrency cap is per-request, not per-process — concurrent users recreate the documented vLLM-contention false-timeout defect

**Files:** `run/layer2_all.py:41-49`, `run/parallel.py:14-26`, `host/server.py:346-354`.

`run_2_all` caps its own fan-out at `layer2.emit_concurrency` (default 4) via a **fresh ThreadPoolExecutor per
call** (layer2_all.py:48-49 → parallel.py:19). Nothing bounds the number of concurrent `run_2_all` calls:
`ThreadingHTTPServer` spawns an unbounded thread per connection (server.py:346-354 raises the backlog to 128
precisely to accept more), so N concurrent `/api/run` = up to 4×N in-flight ~22K-token emits on the one vLLM.
The comment block at layer2_all.py:41-46 documents that exactly this contention "starved [the biggest emit]
to a false timeout under a multi-page sweep" — and the operational workaround in memory is "sweeps need ≤2-3
page-concurrency", i.e. the invariant is currently enforced by operator discipline, not code. Enterprise
production is multi-user by definition; two users on heavy pages will reproduce the l2_emit timeout family,
and `timeout` is in `llm.no_retry_kinds`, so those cards hard-fail and can trigger whole-page re-routes
(harness.py:120-134,164-171) — burning even more vLLM capacity in a feedback loop. The same absence of global
admission control also means total threads per request ≈ 2 (1a∥1b) + 4 (L2) + 8 (exec) stacked on the request
thread, ×N requests, unbounded.

**Fix:** one process-global `threading.BoundedSemaphore(cfg("layer2.emit_concurrency", 4))` acquired around
the emit call itself (inside the thunk), so the cap means "in-flight emits per process" regardless of how many
requests fan out; add a small global cap on concurrent `/api/run` bodies (e.g. semaphore in `do_POST`) for
back-pressure instead of thread pile-up.

### H4. `obs/ai_log._RUN_ID` is a single module global behind a process-wide urlopen monkeypatch — any two concurrent runs cross-label all AI telemetry

**Files:** `obs/ai_log.py:8, 13-15, 40-50, 56`; `run/harness.py:107, 187`; `llm/client.py:71-74`.

`ai_log` monkeypatches `urllib.request.urlopen` process-wide at import (ai_log.py:56) and stamps every :8200
record with the module global `_RUN_ID` (line 40) into the file `ai_{_RUN_ID}.jsonl` (line 49).
`run_pipeline` mutates that global per request (`ai_log.set_run_id(run_id)`, harness.py:187) and again
mid-run for reflect attempt 2 (harness.py:105-107). Under the threaded host, request B's `set_run_id`
relabels every in-flight LLM call of request A — records land in the wrong file with the wrong run_id, and
`llm/client._record` attributes failures to `getattr(ai_log, "_RUN_ID")` (client.py:73), so failure telemetry
is mislabeled the same way. The multi-asset path makes this certain even for a single user: each class lane
calls `run_pipeline` with a different salted run_id sequentially, but a second browser tab or the sweep
harness (which runs page-concurrency 2-3) interleaves constantly. The certification/fabrication audits read
these files as ground truth — under any concurrency they are unreliable evidence.

**Fix:** replace the global with a `contextvars.ContextVar` (default "default"); in `run/parallel.py` and
`host/exec_cards.py` submit thunks via `contextvars.copy_context().run` so the run_id crosses pool threads.
`set_run_id` keeps its signature (sets the contextvar), so all call sites are untouched.

---

## MEDIUM

### M1. `host/payload_store.py` permanently caches `None` on a DB hiccup — plus the raw default is returned by reference

**File:** `host/payload_store.py:49-70, 83-95`.

- `_skeleton_payload`: on any `q()` failure `skel = None` (line 67-68) and **`_SKELETON_CACHE[render_card_id]
  = skel` caches that None forever** (line 69). A cmd_catalog blip during the first request for a card means
  that card's honest-blank skeleton is gone for the process life — the FE falls to the generic HonestBlank
  tier instead of the card's real component, the exact defect the skeleton exists to prevent (comment block
  lines 26-35). `_raw_default_payload` line 94 is identical (`_RAW_DEFAULT_CACHE[render_card_id] = pl` with
  pl=None on error): the shape oracle for yscale/xaxis/fab_guards and the dash policy silently disappears per
  card until restart. Same poison family as H2, on the *local* DB (rarer flap, same class).
- Aliasing: `_skeleton_payload` deep-copies on return (line 70) but `_raw_default_payload` returns **the
  cached dict itself** (line 95). It flows into `run_card(shape_ref=…)`, `card["shape_ref"]`
  (exec_cards.py:128,135) and `enrich.py:178`. I verified current consumers treat it read-only
  (`graft.py:22-25` deep-copies subtrees; yscale/norm_series/xaxis only append to local lists), so today this
  is safe **by convention only** — one future in-place mutation in any post-fill pass corrupts the shared
  default for every later request of that card, a classic cross-request heisenbug.

**Fix:** cache only non-None (`if skel is not None: _SKELETON_CACHE[...] = skel`) or switch both dicts to
`TTLCache`; return `copy.deepcopy(pl)` (or a frozen/immutable view) from `_raw_default_payload`.

### M2. `config/app_config._load` pins `{}` for the process life if cmd_catalog is down at first read — every knob silently reverts to code defaults

**File:** `config/app_config.py:18-24, 42-48`.

`@lru_cache(maxsize=1)` on `_load()` with `except Exception: return {}` means one failed first load (host
started while :5432 restarts, or during a reseed) caches the empty dict forever: every `cfg()` call in the
process — timeouts, emit caps, TTLs, feature flags, reason templates — silently answers the code default with
no telemetry and no self-heal, until someone calls `reload()` (nothing does at runtime) or restarts. This is
the same poison class as H2 applied to configuration, and it contradicts the self-healing philosophy the team
wrote into `data/ttl_cache.py`'s header. (lru_cache itself is thread-safe; the defect is lifetime, not
locking.)

**Fix:** on exception, record the failure and **don't** populate the cache (raise through a tiny wrapper that
retries next call, with a short in-module backoff timestamp so a dead DB isn't hammered), or give `_load` a
TTL like everything else. Keep fail-open per *call*, not per *process*.

### M3. `run_id = sha1(prompt)` collides across concurrent identical prompts — same-name artifact files are written concurrently

**Files:** `run/run_id.py:5-7`, `host/server.py:181-192, 339`, `obs/notes.py:20-22`, `obs/stage.py:16-18`.

Two users (or a sweep + a user) submitting the same prompt concurrently share one run_id by design
(run_id.py docstring: collides across executions). Consequences under concurrency:
- `_dump_response` (server.py:189-190) and `obs/notes.record` (notes.py:21-22) open the **same path with
  mode "w"** from two threads and stream `json.dump` into it — interleaved writes produce a corrupt JSON file,
  and the sweep/debug tooling explicitly "read[s] it FROM DISK" (server.py:184-186).
- `pipeline_<rid>.jsonl` / `failures_<rid>.jsonl` appends from both runs merge into one stream, so a replay of
  a run contains another run's stages with no way to split them.
The uuid4 `trace_id` that would fix identity exists in `obs/trace.py` but is unwired (see L2).

**Fix:** suffix run_id with a short random/monotonic token at `make_run_id` (keeping the prompt-hash prefix
for grep-ability), or write per-run files under `response_<rid>.<uuid>.json`. If deterministic replay keys
must stay, at minimum write to a temp file + `os.rename` (atomic) so concurrent writers can't interleave.

### M4. `ai_<run_id>.jsonl` is appended by up to 4 emit threads with ~100KB records and no lock — buffered text appends can interleave mid-record

**File:** `obs/ai_log.py:49-50`; producers `run/layer2_all.py:48-49` (4 concurrent emits per run).

Each log record embeds the full request+response — an L2 emit is ~22K tokens (~90KB+ JSON). The write is
`open(path, "a")` + one `f.write(line)` through a buffered `TextIOWrapper`; text/binary buffering flushes in
chunks, so a single logical line larger than the buffer is emitted as **multiple `write(2)` syscalls**, and
two threads appending simultaneously (guaranteed inside one run by the 4-way fan-out; across runs by M3) can
interleave chunks → corrupt JSONL lines in the primary AI-audit artifact. Small-record sinks
(`pipeline_*.jsonl`, `failures_*.jsonl`) usually fit one buffer and are lower-risk, same pattern.

**Fix:** one module-level `threading.Lock` around the open/write in `_logged` (and stage/failures for
symmetry), or write via `os.write` on an `O_APPEND` fd with the record pre-encoded as a single bytes object.

### M5. One pooled psycopg2 connection per DSN serializes the whole "parallel" executor fan-out

**Files:** `ems_exec/data/neuract.py:22-47`, `registries/neuract/_db.py:19-47`.

`_POOL` is `{dsn_key: connection}` — capacity one. The 8-worker card fan-out (exec_cards.py:175), the roster
interpreter's member reads, and every concurrent request all funnel through a single connection whose
`execute()` psycopg2 serializes internally. The parallelism [ER-8] pays thread overhead and gets sequential
DB throughput over one tunneled socket; a page of 8 history cards issues its bucketed reads strictly one at a
time. This is a scaling wall (latency × cards × users) independent of the hang in C1, and it is why C1's
head-of-line blocking takes the whole service down rather than one card.

**Fix:** `psycopg2.pool.ThreadedConnectionPool(minconn=1, maxconn=cfg("neuract.pool_max", 8))` per DSN key,
with getconn/putconn in `_run`/`rows`/`dicts`. Behavior-identical results; strictly more throughput.

### M6. `TTLCache` honors the TTL only through the `in` + `[]` idiom, never evicts, and stamps ts before value

**File:** `data/ttl_cache.py:31-53`; consumers `layer1b/resolve/has_data.py:26-28, 54, 98-100, 119`,
`data/lt_panels/panel_members.py:56-57`, `data/registry/lt_mfm.py:38-45…`.

- Only `__contains__` is TTL-aware. `.get(k)`, `.items()`, `.values()`, iteration, `len()`, and a bare
  `cache[k]` all serve **expired** entries silently. Today every consumer happens to use the blessed
  `if k in c: return c[k]` idiom (verified by grep), so this is a contract landmine rather than a live bug —
  the class is advertised as "a drop-in dict" (line 10) which is exactly what it is not.
- Expired entries are never deleted (`no deletion on expiry`, line 12) and `__delitem__`/`pop`/`clear` don't
  touch `_ts`. With bounded key spaces (mfm_ids) that's fine; `has_data.py` keys by `frozenset(tables)`
  (lines 26, 98) — every distinct table-set ever probed (each BFS level of each panel, each candidate set)
  accumulates values + timestamps for the process life. Slow leak in an always-on server.
- `__setitem__` writes `_ts[k]` then the value (lines 48-53): a reader between the two statements sees a
  fresh timestamp with the **old** value — returns just-expired data as fresh once. Benign in practice,
  worth a comment or ordering flip (value first, ts second keeps the entry expired until fully written).

**Fix:** override `get()` (delegate to `__contains__`), have `__setitem__` set value before ts, and
opportunistically purge expired keys on write (cheap, bounds memory). Document that iteration is not TTL-aware.

---

## LOW

### L1. No SIGTERM/graceful shutdown in either service; daemon threads die mid-write

**Files:** `host/server.py:346-364` (`daemon_threads = True`; `main()` handles only KeyboardInterrupt),
`copilot/server.py:117-121` (no handler at all; grep for `signal` across both services returns nothing).

systemd stop sends SIGTERM → default handler kills the process instantly; daemon request threads die
mid-flight, and `_dump_response`/`obs.notes` `json.dump` writes truncate (the sweep reads those files from
disk). Fine for a preview box, not for enterprise ops.
**Fix:** register a SIGTERM handler that calls `srv.shutdown()` from a helper thread and gives in-flight
handlers a bounded grace period; write artifacts via temp-file + `os.rename`.

### L2. The obs trace/bus/span layer exists but is unwired — and when wired, contextvars won't cross the thread pools

**Files:** `obs/middleware.py:1-8` ("host/server.py calls run_traced() around each request body" — it does
not; host/server.py imports only `obs.stage`/`obs.failures` transitively), `obs/trace.py:117-131`,
`obs/bus.py`, `obs/event.py`, `obs/span.py` (all present — note: an earlier subsystem map claimed
event/bus/span don't exist; that is wrong, I listed `obs/` and read bus.py and middleware.py).
Tree-wide grep shows `middleware`/`llm_tap`/`db_tap`/`sink_*` referenced only inside `obs/`. Concurrency
angle for the eventual wiring: `trace.py` keys the active trace on a `ContextVar`; `run_parallel` and the
exec pool submit plain callables, so spans created in 1a/1b/L2/exec worker threads will silently detach from
the request trace. **Fix when wiring:** submit via `contextvars.copy_context().run` in `run/parallel.py` and
`exec_cards.py` (same change H4 needs — do both at once).

### L3. PIPELINE_ASSET_ID env-pin: verified fixed (opt-in gated) — keep it that way

**File:** `layer1b/build.py:11-15`.

The v47 mechanism (process-global env var as a per-request parameter) is now honored only when
`V48_ALLOW_ENV_PIN=1` (CLI/trace runs), with the hazard correctly documented ("in the long-running host a
launch-time env value would otherwise silently pin EVERY request to one asset"). Tree-wide grep found **no
writer** of `PIPELINE_ASSET_ID` in v48 and no other `os.environ[...] =` mutations in the serving path
(copilot/db.py:27 builds a copied env dict for a subprocess — fine). No action; recording as a verified
non-finding so the panel doesn't re-flag it.

### L4. `data/equipment/edges._STATE` latches knobs at first call — including the failure default

**File:** `data/equipment/edges.py:31-60`.

`enabled()`/`_allowlist()` latch on first call; the `except Exception: _STATE["enabled"] = False` path means
a cmd_catalog blip at first touch latches the equipment-topology feature OFF for the process life (silent,
no self-heal — the anti-TTL pattern, though deliberately labeled "latched kill-switch"). Cheap fix: don't
latch the exception path (leave the key unset so the next call retries), keep latching real answers.
Everything else in `data/equipment/` is exemplary: failure-not-cached in `db.py:39-42`,
`edges._resolve`'s `(roster, cacheable)` split (edges.py:163-165), bridge's fail-open-without-caching
(bridge.py:63-80).

### L5. Minor cache races (benign, note only)

- `ems_exec/renderers/_insight.py:147-150,157`: unlocked module `_CACHE` with `clear()`-when-full — worst
  case a lost entry or duplicate LLM call (stampede) under concurrent narrations; results are deterministic
  so no corruption.
- `copilot/server.py:25-50`: the suggest cache is the model citizen — lock-guarded, never caches
  error/unavailable responses (lines 41-49). No action.
- `data/lt_panels/panel_members.py:126-132`: `_parent_ids` caches whatever `_registry_parents()` returns,
  including a fail-open **empty set**, under the TTL; a members result computed against that bad parents set
  (empty aggregates treated as leaves → under-recursed rosters) passes the non-empty check at line 121 and is
  cached for the TTL window. Self-heals in ≤ `cache.resolution_ttl_s`; acceptable by the design's own
  criteria, listed for completeness.
- `registries/neuract/_db.py:60-65` / `ems_exec/data/neuract.py:61-66`: the error path pops the pooled
  connection while other threads may still hold a reference — psycopg2 tolerates this (their next call fails
  and re-pools); benign.

---

## What is genuinely good here (so it doesn't get "fixed" away)

- `run/parallel.py` result-or-Exception isolation is clean and used consistently.
- The TTL + never-cache-empty discipline, where applied (panel_members, lt_mfm, has_data, equipment/*,
  copilot), is exactly right — H2/M1/M2 are about the three-plus places it *didn't* reach.
- `layer2_all`'s post-hoc deterministic swap-settle (layer2_all.py:55-64) is the correct way to resolve the
  parallel-emit collision race without cross-thread coordination.
- `run_pipeline_multi` deep-copies the shared 1a template per lane (harness.py:348) — no cross-lane aliasing.
- No asyncio means no event-loop/shared-client class of bugs at all; the threads-only model is simple and
  auditable, which is the project's stated taste.

## Top recommended order of work

1. C1 (timeouts/keepalives in `conn_kwargs` + `q()` subprocess timeout) — one small diff, kills the outage.
2. H1 (`as_completed(timeout=…)`) — makes the existing budget real.
3. H2 + M1 + M2 — finish the never-cache-empty campaign (grep-able pattern, ~4 small diffs).
4. H3 (global emit semaphore) + H4/L2 (contextvar run_id + copy_context in the two pools) — one PR, shared plumbing.
5. M3/M4 (artifact-file identity + append locking) — restores trust in the cert/sweep evidence under load.
