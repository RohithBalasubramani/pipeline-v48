# Observability Audit — pipeline_v48 (2026-07-12)

Lens: observability (obs/ sufficiency, logging practice, run/correlation ids, per-run records,
blank-leaf error visibility, LLM telemetry, metrics/alerts, :5433 flap detection).
All file:line references were read directly during this audit.

## 0. IMPORTANT CONTEXT — the obs/ layer was being rebuilt DURING this audit

The audit brief described `obs/` as 156 lines (ai_log, stage, failures, notes, trace). At audit time the
directory contained **19 files (~2,400 lines)** — `bus.py`, `event.py`, `span.py`, `redact.py`,
`sink_console.py`, `sink_jsonl.py`, `sink_pg.py`, `llm_tap.py`, `db_tap.py`, `middleware.py`, `query.py`,
`sql_log.py`, `sql_trace.py`, plus `db/obs_schema.sql` — **all with mtimes 2026-07-12 02:18–02:28, i.e.
written while this audit ran, and all untracked/uncommitted** (`git status`: `?? obs/bus.py …`,
`M llm/client.py`, `M data/db_client.py`). Files literally appeared between two consecutive directory
listings (sink_pg.py, span.py, db_tap.py, llm_tap.py, middleware.py, query.py, sql_log.py, sql_trace.py).

Everything below is a **snapshot as of 02:28**. Findings distinguish the *stable wired telemetry*
(ai_log/stage/failures/notes + host channels, in place since June) from the *in-flight trace layer*.

The new layer's design quality is genuinely high — shared event envelope (`obs/event.py`), size-bounded
redaction (`obs/redact.py`), reentrancy-guarded fan-out bus with per-sink knobs (`obs/bus.py`),
buffered/backoff PG sink with idempotent schema bootstrap (`obs/sink_pg.py` + `db/obs_schema.sql` with
`obs_v_trace_summary` / `obs_v_stage_latency` / `obs_v_token_spend` / `obs_v_card_funnel` views), and a
read-side CLI (`obs/query.py`). The findings below are mostly about the **last-mile wiring that is missing
at snapshot**, plus long-standing issues the new layer does not fix.

---

## F1 (HIGH) — The entire new trace/span/tap layer is inert: nothing opens a trace

- `obs/middleware.py:40` `run_traced(kind, request_fields, fn)` is the ONE intended entrypoint
  (`new_trace` at :44, `end_trace` at :60/:82). **Zero callers**: `grep -rn "run_traced\|new_trace"`
  outside `obs/` returns nothing; `host/server.py` mtime is Jul 9 (untouched by the build-out).
- Consequence chain, verified in code:
  - `obs/llm_tap.py:24-25` — `record()` returns immediately when `trace.current()` is None. So the newly
    added latency+token capture in `llm/client.py:166,171,179-181` (which finally reads the vLLM `usage`
    block and times each call) is **measured and then discarded** on every call today.
  - `obs/span.py:87-89` — `stage_span` yields an inert handle without a trace; no stage events are emitted.
  - `obs/sink_pg.py` never receives an event; the `obs_*` tables (`db/obs_schema.sql`) stay empty; the
    `obs/query.py` CLI (`recent`/`latency`/`tokens`/`card`) returns nothing.
  - `obs/db_tap.py` has **no caller at all** (data/db_client.py calls `sql_log`, not `db_tap`), so
    `obs_db_queries` and the per-span db rollups (`span.attribute_db`) can never populate even after a
    trace exists.
- Risk: the team ships believing "tokens/latency/trace are recorded" (the code comments in llm/client.py
  say so) while the store stays empty — the worst observability failure mode is telemetry you think you have.
- Fix: wrap `/api/run` and `/api/frame` handler bodies in `run_traced` (host/server.py:241), call
  `db_tap.record` from `data/db_client._sql_log` (or replace sql_log with it), and add one smoke test:
  POST /api/run → assert one `obs_traces` row + ≥1 `obs_llm_calls` row.

## F2 (HIGH) — Run-correlation id is a mutable process global under a threaded server; concurrent runs cross-label ALL file telemetry

- `obs/ai_log.py:8` `_RUN_ID = "default"` is a module global; `set_run_id` (:13-15) mutates it.
- Everything file-keyed reads that global:
  - `ai_<rid>.jsonl` — ai_log.py:49
  - LLM failure records — llm/client.py:73 `getattr(ai_log, "_RUN_ID", "default")`
  - `sql_<rid>.jsonl` — obs/sql_log.py:31 AND obs/sql_trace.py:20
- `run/harness.py:187` sets it per request; `run/harness.py:105-107` re-sets it mid-run for reflect loop 2.
- `host/server.py:346-354` is a `ThreadingHTTPServer` with daemon threads and a raised backlog explicitly
  because "a batch sweep hammers it" while "the live frontend polls" — i.e. concurrent /api/run is the
  DESIGNED load profile. Two concurrent runs → the second `set_run_id` wins → both runs' LLM/SQL/failure
  records land in ONE run's files.
- Evidence it already happens: `outputs/logs/ai_default.jsonl` is 3.3MB and `failures_default.jsonl`
  440KB — telemetry emitted while `_RUN_ID` was still "default" (CLI/pytest/knowledge traffic).
- The new `obs/trace.py` fixes identity correctly (contextvar, uuid4, `run/parallel.py:26` copies context
  into fan-out threads) — but the file sinks (`ai_log`, `sql_log`, `sql_trace`, llm failures) still key on
  the global, so the defect survives the rebuild as written.
- Fix: make run_id a contextvar (trace.py already stores `run_ids`; `trace.current_run_id()` exists at
  trace.py:86-90) and have ai_log/sql_log/sql_trace/failures read it with the global as fallback.

## F3 (HIGH) — Unbounded telemetry growth: 484MB / 855 files, no rotation, no retention, full prompt+response dumps

- Measured: `outputs/logs` = **484MB, 855 files** (~2 weeks of dev use). Largest single file:
  `ai_r_92a2bfb0ae.jsonl` at **40MB** — because `run/run_id.py:5-7` hashes the prompt, the SAME prompt
  re-run across days appends forever to the same file (collision by design).
- Per run the pipeline writes: `ai_<rid>.jsonl` (FULL request+response of every LLM call — a ~22K-token
  l2_emit prompt per card per run, ai_log.py:40-50), `pipeline_<rid>.jsonl`, `failures_<rid>.jsonl`,
  `response_<rid>.json` (the whole response, host/server.py:181-192), `notes/<rid>.json`, and now
  `sql_<rid>.jsonl` (one record per SQL statement — on the psql-per-query hot path, data/db_client.py:23-26).
  Once tracing is wired, `sink_jsonl` adds `trace_<uuid>.jsonl` — **one new file per HTTP request**
  (obs/sink_jsonl.py:17), an inode/file-count explosion under production traffic.
- Nothing rotates, compresses, ages out, or caps any of this. At enterprise scale this fills the disk and
  the failure will land on the same volume as cmd_catalog (local Postgres).
- Fix: one retention knob (`obs.retention_days`, cfg-driven per house style) + a daily prune (systemd timer
  or a check-on-write in the sinks); gzip ai_ files over N MB; consider run-scoped subdirectories.

## F4 (MEDIUM) — /api/health is a static 200; no dependency probes; no metrics surface; no alert hooks

- `host/server.py:216-217`: `/api/health` returns `{ok: True, sb_base}` unconditionally — it answers even
  when vLLM :8200 is down (every route fails closed), cmd_catalog is unreachable (cfg falls to code
  defaults silently) or the :5433 tunnel is dead. An orchestrator/load-balancer cannot distinguish
  "process up" from "service able to answer".
- `/api/site` (server.py:231-238) DOES do a real `SELECT 1` probe of the data DB — but it exists for the
  FE's green dot, is per-request, and probes only neuract.
- Nothing exports counters: no /metrics, no statsd; `obs/sink_pg.py:17` keeps a `DROPPED` counter that is
  never logged or exposed; stage/failure counts are only derivable by grepping jsonl.
- Fix (small, in-style): extend /api/health with per-dependency booleans (llm/catalog/data — each an
  existing cheap probe) + expose sink_pg.DROPPED and trace counts; optionally a /api/health?deep=1 to keep
  the cheap path cheap. That single endpoint is enough for uptime-kuma/cron alerting without adopting a
  metrics stack.

## F5 (MEDIUM) — Flap detection/alerting for :5433 is ad-hoc: bounded manual scripts, not services; flaps leave no persistent record

- Runtime handling is genuinely good: `run/degrade_gate.py:22-41` fingerprints outage-shaped layer errors
  into an honest `data_unavailable` terminal with a DB-driven reason; `data/ttl_cache.py` self-heals
  poisoned caches (120s TTL); `ops/db-tunnel.service` is a properly hardened systemd unit (keepalives,
  ExecStartPre port-free, backoff restart).
- But *detection* is manual and time-boxed:
  - `tools/tunnel_monitor.py:19-20` — polls with a real query but defaults to a **6-hour lifetime**
    (`TUNNEL_MONITOR_HOURS=6`), is started by hand (`nohup`), logs to a flat file, and was **not running**
    at audit time (`ps` empty). Its recovery action is re-running a cert sweep, not alerting.
  - `tools/stack_monitor.sh` — a campaign keep-alive that ALSO owns production restarts: host :8770,
    vite :5188 and ems_backend :8890 are restarted by this shell script via `setsid nohup` (not systemd
    units), logging to `outputs/logs/stack_monitor.log`, stopped by a `/tmp/stack_monitor.stop` sentinel.
    Not running at audit time either — i.e. today nothing restarts the host if it dies.
- A tunnel flap that self-heals (TTL expiry) is invisible afterwards: no counter, no event, no timeline an
  operator can consult to answer "how often does :5433 flap?" — only journalctl on db-tunnel.service and
  whatever requests happened to fail into `failures_*.jsonl` during the window.
- Fix: promote host/FE/ems_backend to systemd units (Restart=always) like db-tunnel; make the tunnel probe
  a tiny systemd timer that appends up/down transitions to a persistent log/obs event (unbounded lifetime);
  count degrade-gate activations as an obs event so flap frequency is queryable.

## F6 (MEDIUM) — THREE SQL telemetry recorders; two write different schemas into the SAME file

- `obs/sql_log.py` (called by `data/db_client.py:30-36`): record = `{ts: iso, run_id, source, sql[:500],
  params, ms, rows, ok, error}` → `outputs/logs/sql_<rid>.jsonl`.
- `obs/sql_trace.py` (called by `ems_exec/data/neuract.py:53-72`): record = `{ts: epoch float, db, sql
  (UNtruncated), rows, ms, params?, err?}` — **no run_id inside the record, no ok field** → the SAME
  `outputs/logs/sql_<rid>.jsonl`.
- `obs/db_tap.py`: the trace-linked third recorder (→ obs_db_queries) — currently uncalled (see F1).
- Consequences: a mixed-schema jsonl any consumer must special-case (`rec.get("ok")` vs `rec.get("err")`,
  iso vs epoch ts); untruncated SQL from sql_trace (some executor IN-lists are large); three copies of the
  same concern violates the owner's one-file-per-concern rule in the observability layer itself.
- Fix: collapse sql_log + sql_trace into one recorder with one record shape (both call sites keep their
  one-line hook), and make that recorder ALSO forward to db_tap when a trace is active.

## F7 (MEDIUM) — The executor's thread pool will orphan the trace: raw submit without context copy

- `obs/trace.py:3-4` (docstring) promises: "run/parallel.py copies the caller's context into every fan-out
  thread, so 1a∥1b, the per-card Layer-2 emits **and the executor card pool** all inherit the same trace."
- True for `run/parallel.py:26` (`ex.submit(contextvars.copy_context().run, fn)`), but the executor card
  pool does NOT use run_parallel: `host/exec_cards.py:175-176` does `ex.submit(_fill, cid, o)` on a raw
  `ThreadPoolExecutor` — no context copy. Once tracing is wired (F1), every neuract read and span inside
  the per-card fill will see `trace.current() is None` → uncounted, unattributed, absent from
  obs_db_queries/card funnel.
- Fix: submit via `contextvars.copy_context().run` in `_run_cards` (one-line change mirroring parallel.py),
  or route the executor fan-out through run_parallel.

## F8 (MEDIUM) — ai_log: process-wide urlopen monkeypatch with an import-order contract, a hardcoded ":8200" filter, and (soon) full duplication of llm_tap

- `obs/ai_log.py:56` replaces `urllib.request.urlopen` for the whole process at import; the docstring's
  contract is "Import FIRST" — a module imported before ai_log that captured the original urlopen silently
  bypasses logging; nothing verifies the ordering.
- `:36` matches the literal substring `":8200"` — pointing `LLM_URL` at another port/host (llm/config.py
  reads env `LLM_URL`) silently kills the entire LLM log with no error.
- Records carry ts/run_id/url/request/response only — no latency, no stage tag; token usage is recoverable
  (the raw vLLM `usage` block rides in `response`) but nothing aggregates it.
- Once F1 lands, every LLM call is recorded twice (ai_log full request/response file + llm_tap bounded
  prompt/response event), roughly doubling the disk cost in F3 for the same information.
- Fix: after llm_tap is live and verified, retire the monkeypatch (or gate it behind a debug knob) — the
  tap at the single call convention (llm/client.py) is strictly better placed.

## F9 (MEDIUM) — No log levels, no logging framework, non-uniform lines, run_id not inside stage records

- Zero `import logging` in pipeline code (verified tree-wide grep; only Django ems_backend has it).
  Everything is `print(..., file=sys.stderr)` + hand-rolled jsonl appends.
- `obs/stage.py:14` stderr lines have no timestamp (the jsonl twin has ts); `stage.py:18` writes
  `{"ts","stage",**fields}` — the run_id lives ONLY in the filename, so cross-run aggregation requires
  filename parsing; there is no severity field anywhere (ERROR is a field-name convention, stage.py:44).
- Four processes make up the runtime (host :8770, copilot :8772, vite :5188, ems_backend :8899/:8890) with
  four unrelated logging styles and no unified stream; host/copilot stdout goes wherever the launcher's
  nohup redirect pointed (tools/stack_monitor.sh start_host → outputs/logs/host_stdout.log).
- This is survivable for a single-box product (the owner's simplicity preference is legitimate), but at
  minimum: put run_id/trace_id inside every jsonl record, timestamp the stderr lines, and adopt a severity
  field — all achievable inside the existing custom sinks without adopting a framework.

## F10 (MEDIUM) — No per-stage/per-card latency in the wired telemetry; executor and L2 stages are timing-blind

- The only duration recorded today is response-level `elapsed_ms` (host/server.py:135,141).
- `host/exec_cards.py:183-189` — per-card exec stage records `ok`/`why` but no duration; a card that took
  44s of the 45s budget is indistinguishable from a 0.2s card.
- `run/layer2_all.py:66-73` — `L2.card` records swap/conforms/gap but no emit latency; LLM stage timeouts
  are tuned by DB knobs (llm.timeout.l2_emit etc.) with no measured distribution to tune them against.
- Per-stage latency is reconstructable only by diffing `ts` between adjacent pipeline_<rid>.jsonl lines.
- The span layer (obs/span.py latency_ms; obs_v_stage_latency p50/p95/p99 view) is exactly the right fix —
  but see F1/F7; and until it lands, add `ms=` to the exec and L2.card stage records (two one-line changes).

## F11 (MEDIUM) — Copilot service is a telemetry blackout; knowledge-layer runs have no run identity

- `copilot/server.py:102-103` — `log_message: pass` silences ALL access logs; remaining visibility is three
  startup `print()`s (:112-120). Its LLM (:8201) is invisible: ai_log filters ":8200" and copilot never
  imports obs. No health probe of :8201 is exported (there is `llm.is_up()` used only at warmup).
- Knowledge-layer answers: `host/server.py:319-323` builds a response with NO run_id and calls
  `_dump_response` → keyed "default" (server.py:186) → every knowledge turn overwrites/mixes in
  `outputs/logs/response_default.json`; the knowledge LLM call is visible only as an unattributed
  ai_default.jsonl line (stage="knowledge_ems" exists in llm failures only).
- Fix: mint a run_id (or open a trace) for knowledge turns; give copilot a minimal stage-style jsonl and
  include :8201 in whatever health surface F4 produces.

## F12 (LOW) — sink_pg loses telemetry silently by design and never reports it

- `obs/sink_pg.py:44-45` queue overflow → `DROPPED += 1`; `:99-101` ANY insert failure drops the whole
  batch (`DROPPED += len(batch)`) and backs off 30s; `_bootstrap` failure (:72-76) is swallowed. All
  acceptable choices for telemetry — except `DROPPED` is a module global nobody logs, exports, or alerts
  on, so sustained PG-sink failure looks identical to healthy operation.
- Fix: emit a periodic console/jsonl line when DROPPED grows; include it in /api/health (F4).

## F13 (LOW) — profiler/ is half-built dead scaffolding

- `profiler/__init__.py:1-15` advertises 8 modules (spans, attach, logmine, stats, report, charts, live,
  cli); only spans/stats/report exist (221 lines total); tree-wide grep shows **zero importers** outside
  the package. Its promised capability (per-stage p50/p95/p99) is now the obs layer's job
  (obs_v_stage_latency).
- Fix: delete (after the owner's verify-before-dead check) or fold anything salvageable into obs/query.

## F14 (LOW) — Blank-leaf "why" is excellent at the response level but not queryable in aggregate

- Positive: the per-leaf story is one of the strongest parts of the wired system. `host/enrich.py:163-199`
  merges executor per-leaf gap records + L2 emit gaps, words reasons per-leaf → per-metric → whole-asset
  (F3-guarded so a data-bearing meter is never blamed as dark, enrich.py:37-50,192-197), and serves
  `render.gaps` + `render.reason` + `fill_why` + `data_note`/`l2_answerability` per card. With
  `response_<rid>.json` on disk an operator CAN answer "why is this leaf blank" for a specific run.
- Gap: reasons live only inside per-run JSON blobs. "Which leaves blank most often this week / did blanks
  spike after the reseed?" requires ad-hoc scripts over 855 files. `obs_v_card_funnel`
  (db/obs_schema.sql:154) is positioned to fix this once stage events carry verdict/gap fields per card —
  worth making the enrich verdict an explicit span/stage output when wiring F1.

## F15 (LOW) — degrade_gate fingerprint "timed out" is broad

- `run/degrade_gate.py:29` — `"timed out"` matches any layer exception containing those words, including a
  statement-timeout on a logic-bad query, which would be absorbed as `data_unavailable` (infra) instead of
  surfacing as a real error. The docstring (:20-21) explicitly intends logic errors to stay loud. Low
  severity because 1a/1b/validation exceptions are overwhelmingly transport-shaped, but the honest-terminal
  path can mask a genuine defect class.

## Minor notes (not ranked)

- `obs/__init__.py` docstring ("failure logging (NO reloop/NO re-route)") and `obs/stage.py:3` ("fill →
  frames") predate the current architecture — stale one-liners in the layer an operator reads first.
- `obs/event.py:2` says "Four kinds share one envelope" then lists five.
- Once sink_console is live, span lines will print alongside the legacy `stage()` stderr lines —
  double-printing per stage until legacy call sites are forwarded (event.legacy_event exists but nothing
  calls it yet).
- ai_ logs contain full prompts (DB schema, asset names, site vocabulary). Internal-only today; worth a
  policy note before any multi-tenant deployment.
- The tests `tests/test_failures_fanout.py` / `tests/test_stage_telemetry_item15.py` exist for the wired
  layer — good; the new trace layer has no tests at snapshot (expected, mid-build).

## Overall assessment

The *wired* observability (stage jsonl + failures fan-out + notes + response dumps + honest per-leaf
blank reasons + degrade-gate machine reasons) is unusually strong on **per-run debuggability** — a single
run is fully replayable from disk. It is weak on exactly the enterprise axes: correlation under
concurrency (F2), retention (F3), health/alerting (F4, F5), latency/token accounting (F10, F1), and
cross-run aggregation (F14). The brand-new trace/span/PG layer addresses most of these on paper and is
well designed, but at snapshot it is 0% operational (F1) and carries forward the global-run-id defect
(F2), a context propagation gap (F7), and a triplicated SQL recorder (F6). The highest-value next hour of
work is wiring `run_traced` + `db_tap` + the exec-pool context copy, then adding retention and a
dependency-aware /api/health.
