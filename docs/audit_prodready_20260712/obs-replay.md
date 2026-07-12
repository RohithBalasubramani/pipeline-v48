# Prod-readiness audit — obs/ + replay/ lens (differential)

Date: 2026-07-12. Auditor: obs-replay lens agent.
Scope: obs/ trace layer + replay/ engine, BOTH rebuilt today. Differential vs docs/audit_2026-07-12/observability.md, AUDIT_REPORT.md, refactor ledger, unused-dupes apply log.
Constraints honored: read-only, SELECT-only psql, no server restarts, no POST /api/run.

## Status: COMPLETE (2026-07-12 ~07:50 IST)

## Findings

### OBS-1 (HIGH) — AUDIT_REPORT's "R7 contextvar run-id implemented" claim is only HALF true: every legacy jsonl telemetry leg still reads the module-global `_RUN_ID`
- AUDIT_REPORT.md:236 ("Note: R7 (contextvar run-id + wired obs trace layer) was implemented by a concurrent session … `obs/trace.current_run_id()` is a contextvar") and :282 ("Done by the CONCURRENT session (verified…): §R7 (contextvar run-id + wired obs trace layer)").
- Reality: `obs/ai_log.py:11` `_RUN_ID = "default"` module global; `set_run_id` (:24-26) mutates it; record + FILE NAME both use it (:51, :60). `obs/sql_trace.py:28` `rid = getattr(_ai_log, "_RUN_ID", "default")`. `llm/client.py:74`, `config/reason_templates.py:41`, `layer1a/story_builder.py:47` — all `getattr(ai_log, "_RUN_ID", "default")`. NOTHING consumes `trace.current_run_id()` for jsonl attribution.
- So two concurrent /api/run requests still cross-label ai_<rid>.jsonl / sql_<rid>.jsonl / llm-failure records under the wrong run (the exact H14 failure). The obs_* pg leg is correctly contextvar-attributed; the jsonl legs the admin console (:8790, file-backed) and tools/payload_diff read are NOT.
- fix_class: safe (mechanical: back `set_run_id`/reads with a ContextVar; the trace already carries run_ids). But note :8770 must restart to adopt → flag for owner scheduling.

### OBS-2 (HIGH, half-applied H15) — urlopen monkeypatch NOT retired, and outputs/logs has NO retention and grew 485 MB → 1.2 GB / 865 → 1417 files
- R7 prescribed "move LLM logging into llm/client.call_qwen and retire the urlopen monkeypatch; add a obs.retention_days prune + gzip".
- llm_tap IS live in llm/client.py (:45, :220, :230) — the duplication is now real: every vLLM call is logged TWICE (ai_log tee + llm_tap → pg/jsonl sinks). `obs/ai_log.py:67` still does process-wide `urllib.request.urlopen = _logged` at import.
- Retention exists ONLY for: obs_* pg rows (sink_pg._purge, obs.retention_days default 30, sink_pg.py:77-96) and replay bundles (replay/store.py:81 `_prune`, replay.keep_traces). outputs/logs (ai_/sql_/pipeline_/failures_/trace_/response_ files) has NO prune: measured 1.2G / 1417 files today (du). trace_<tid>.jsonl (sink_jsonl.py:17) is a NEW unbounded writer added today.
- fix_class: safe (a prune of outputs/logs mirroring sink_pg's knob; retire/gate the monkeypatch behind a knob after confirming payload_diff/admin migrate to llm_tap sources).

### OBS-3 (MEDIUM) — sink_pg daily retention purge has no supporting index and runs synchronously in the single writer thread
- `db/obs_schema.sql:103-111`: the only ts-bearing indexes are composites `(stage, ts DESC)` / `(stage, ts_start DESC)` — the purge's `DELETE … WHERE ts < now() - N days` (sink_pg.py:88-90) cannot use them (leading column is stage).
- Volume measured NOW: obs_db_queries = 106,332 rows in the last 6 h (psql) → ~0.4-0.5 M/day → ~15 M rows at the 30-day window. The daily DELETE will seq-scan that.
- `_purge` runs inline in `_writer_loop` (sink_pg.py:119) between batches; a multi-minute DELETE stalls inserts → the 5000-cap queue overflows → `DROPPED` events (fail-open holds, but telemetry silently gaps exactly once a day at scale).
- fix: add `obs_db_queries(ts)` / `obs_llm_calls(ts)` / `obs_stage_events(ts_start)` / `obs_traces(started_at)` plain indexes (started_at one exists) OR batch the purge (`DELETE … LIMIT` loop). fix_class: safe (DDL is IF NOT EXISTS-style additive; goes through the bootstrap file).

### OBS-4 (MEDIUM) — obs/notes.py breaks the obs fail-open contract: unguarded disk write called bare from the harness
- `obs/notes.py:20-25`: `os.makedirs` + `open(...,"w")` + `json.dump` with NO try/except. Call sites `run/harness.py:305` and `:382` are bare (not inside any try).
- Failure scenario: outputs/ unwritable (disk full — plausible given the unbounded 1.2 GB outputs/logs, OBS-2) → `record_notes` raises at the END of an otherwise successful run_pipeline → handle_run 500s. Every sibling (failures/stage/sql_trace/sinks) is guarded; notes is the one writer that can sink a request.
- fix_class: safe (wrap the body in try/except, telemetry-only semantics like obs/stage.py).

### OBS-5 (LOW) — pg sink self-observation leaks `<pg_connect>` records into an unrelated run's sql_ jsonl
- `sink_pg.py:51-53` connects via `data.db_client.pg_connect`, which records a `<pg_connect>` sql_trace (db_client.py:233-235). In the sink's writer thread there is no trace (db_tap correctly no-ops) but the JSONL leg (sql_trace.py:28) keys off the process-global `_RUN_ID` → the sink's own reconnects land in whatever run's sql_<rid>.jsonl is current. Cosmetic pollution; folds into the OBS-1 fix. (The docstring "never data.db_client.q" is technically honored — pg_connect is a connection factory, not q().)

### OBS-6 (LOW) — per-event run_id attribution is last-writer-wins across parallel multi-asset lanes
- `obs/event.py:26` stamps every event with `t["run_ids"][-1]`; the multi-asset path binds the envelope run_id (run/harness.py:402) and each parallel lane binds its own — events from lane A emitted after lane B binds carry B's run_id. trace_id/span tree stay correct; only the legacy-join column is approximate. Telemetry nuance, note-only.

## Verified OK (positive verification of today's builds/claims)

- run_traced IS wired for BOTH POST endpoints: host/server.py:252 (/api/frame) and :257 (/api/run) via `_traced_captured` (:150-168); fail-open — if obs/replay imports break, the request runs bare.
- trace_id globally unique: `t_<uuid4.hex>` (obs/trace.py:23); replay engine mints a fresh one (replay/engine.py:37). run_id stays a separate legacy replay key, bound via bind_run_id.
- Context propagation REAL in both pools: lib/parallel.py:30 and host/exec_cards.py:232 submit via `contextvars.copy_context().run`; live smoke-test in this audit: children of run_parallel saw the caller's trace_id. run/parallel facade intact (tests import it fine).
- pg sinks WRITE and data IS flowing post-restart: obs_traces/obs_stage_events/obs_llm_calls/obs_db_queries = 22/2668/679/106k rows; newest trace rows 07:29-07:38, newest llm call 07:40 vs wall clock 07:41; host/server.py restarted 07:35:27, listening :8770; /api/inspector/traces serves source=pg. All 5 obs_v_* views exist.
- Fail-open discipline holds in the sink chain: bus.emit guards each sink + itself (obs/bus.py); sink_pg enqueues only (put_nowait, bounded 5000, 30 s backoff, DROPPED counter); db_tap/_IN_TAP + bus/_IN_BUS reentrancy guards break the cfg()→q()→tap loop.
- Pooled q() engine feeds obs + replay IDENTICALLY to the psql engine: the replay seam wraps `_q_raw` (data/db_client.py:44-50) ABOVE the engine switch; `_q_pool` and `_q_psql` both call `_sql_trace` on success/fail (:167,:171,:180,:198,:201); the connect phase is traced as `<pg_connect>` (:233-235). NO hook exists only on the legacy engine.
- Replay tape coverage complete — no un-taped pipeline seam found: llm (llm/client.py:129-143), sql.q (db_client), sql.nx (ems_exec/data/neuract.py:37-39), sql.reg/sql.regd (registries/neuract/_db.py:27-37), frame_probe (validate/data_load.py:22-24), insight, exec_card anchor (host/exec_cards.py:126-132), pipeline_out artifacts (run/harness.py:306,383). Knowledge gate rides call_qwen (knowledge/ems.py:89) → taped + stage_span'd. Equipment bridge (data/equipment/db.py:29) and panel_members (data/registry/lt_mfm.py:24, data/value_probe.py:13) ride q() → taped. pg_connect raw-cursor callers = validate (taped) + obs/profiler tooling only.
- Recorder rides the shared trace dict (replay/recorder.py:33-45) so fan-out threads record with zero plumbing; capture persists once at request end; env snapshot redacts credentials (replay/capture.py:15-16,28); engine restores env/cfg/clock before pipeline import and always expects a fresh process.
- Retention IS implemented for the pg store (obs.retention_days default 30, sink_pg._purge daily) and replay bundles (replay.keep_traces default 300, store._prune) — the gap is ONLY outputs/logs (OBS-2).
- llm_tap decision capture: contextvar set/clear per call (llm/client.py:146-149), candidates halve-with-marker size bounding (llm_tap.py:55-74), prompts bounded at obs.llm.max_prompt_bytes (32 k), tokens from usage, params ride obs_llm_calls.params.
- Offline tests green: tests/test_obs_trace.py 15 passed (0.13 s), tests/test_replay_engine.py 21 passed (0.38 s); every obs/ + replay/ module py_compiles and imports clean.

## Notes for the orchestrator
- OBS-1/OBS-2 fixes need a :8770 restart to adopt — schedule with the owner alongside the pending pooled-engine restart.
- A live pinned replay was NOT executed (writes obs_* rows + bundle dirs; DB writes forbidden for this lens). Structural + unit-level verification only.
- Concurrent sessions are actively firing runs (sql_pytest.jsonl newest; second host on :8771; a third host process mid-start at audit time) — transient, not findings.
