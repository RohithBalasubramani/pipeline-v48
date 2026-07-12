# V48 Pipeline Observability — Design (2026-07-12)

## Goal

Every pipeline execution gets a **globally unique `trace_id`**; every stage emits a **structured,
queryable event** carrying: trace_id, stage, timestamp, latency, inputs, outputs, confidence,
AI prompt/response, token usage, DB queries + rows returned, validation results, degradation
state, warnings, errors. Storage is DB-driven (cmd_catalog `obs_*` tables) + JSONL fallback,
built for dashboards/analytics. **No scattered logging** — instrumentation attaches only at
stage boundaries and the two I/O choke points.

## Why the existing obs/ is not enough

- `run_id` is a **prompt hash** (`run/run_id.py`) — the same prompt collides across executions;
  it is a *replay key*, not an execution identity. It stays (consumers: `pipeline_<rid>.jsonl`,
  `ai_<rid>.jsonl`, `response_<rid>.json`, sweep tooling) — the new `trace_id` is the unique
  execution identity and each trace records the run_id(s) it covered (the reflect loop mints
  `loop2` run_ids; the trace stays constant).
- `obs/stage.py` events are flat console+JSONL lines — no latency, no parent/child, no AI
  prompt/tokens, no DB query capture, not SQL-queryable.
- vLLM responses already carry `usage` token counts — currently discarded by `llm/client.py`.

## Architecture (atomic-structure rule: one single-purpose file per concern)

```
obs/
  trace.py         trace context (contextvars): trace_id mint, run_id binding, thread-hop helpers
  span.py          stage_span() ctx-manager + @staged decorator: latency/status/error capture, accumulators
  event.py         THE event envelope builder (single schema definition)
  redact.py        size-bounding of inputs/outputs/prompts (queryable, never unbounded)
  bus.py           emit(event) fan-out to sinks; config-gated; never raises
  sink_console.py  human stderr line (existing look & feel)
  sink_jsonl.py    outputs/logs/trace_<trace_id>.jsonl append
  sink_pg.py       buffered background writer → cmd_catalog obs_* (batch INSERT, drop-on-overflow, fail-open)
  llm_tap.py       record one LLM call (prompt/response/tokens/latency/error) — called from llm/client.py ONLY
  db_tap.py        record one DB query (db/sql/rows/latency/error) — fed by obs/sql_trace.py record(), the ONE
                   funnel BOTH data/db_client.q AND ems_exec/data/neuract._run report through (as-built: the
                   concurrent admin-console session routed both choke points into sql_trace; db_tap forwards)
  middleware.py    host/server request/response wrapper: opens the root trace, emits request_received + response
                   (as-built: host/server._traced_captured composes run_traced with the replay capture session
                   for /api/run + /api/frame)
  query.py         dashboard/analytics reads + CLI (python3 -m obs.query ...)
  stage.py         EXISTING legacy stage log — additionally forwards each call into the active trace
                   as a `legacy.<name>` annotation (zero call-site edits; old telemetry becomes queryable)
db/obs_schema.sql  obs_traces, obs_stage_events, obs_llm_calls, obs_db_queries + indexes + dashboard views
db/seed_obs.sql    app_config knobs (all DB-tunable, code-default fallback)
```

## Stage taxonomy (canonical `stage` values ↔ code boundary)

| stage              | boundary (wrapped once)                                      |
|--------------------|--------------------------------------------------------------|
| request_received   | host/server.py `/api/run` + `/api/frame` (middleware)        |
| knowledge_gate     | knowledge/ems.py `ask()`                                     |
| page_selection     | layer1a route step (inside `run_1a`)                         |
| story_selection    | layer1a `build_stories` step (inside `_assemble`)            |
| asset_resolution   | layer1b `run_1b`                                             |
| story/layer2 parent| `run_2_all` (parent span)                                    |
| layer2_card_ai     | `layer2/build.run_card` (child span per card, card_id set)   |
| metadata_resolution| metadata produce/morph/consumer-bind step inside `run_card`  |
| executor           | host `assemble_cards` (parent) + `fill_one_card` (per card)  |
| validation         | validate `run_validate` (+ `payload_final` annotation)       |
| renderer           | host enrich/render-verdict application step                  |
| response           | middleware close (outputs: ok, card/verdict counts)          |

Sub-stages use dotted names (`executor.card`, `layer2_card_ai.card`) with `card_id` +
`parent_span_id` so a whole card's lifecycle is one indexed query.

## Trace propagation

- `contextvars` carry `{trace_id, run_id, span stack, accumulators}`.
- The pipeline's ONE concurrency primitive `run/parallel.py` copies the caller's context into
  each thunk (`contextvars.copy_context().run`) — every fan-out (1a∥1b, per-card L2 emits,
  executor card pool) inherits the trace with a 2-line change in one file.
- LLM/DB taps attach their records to the **active span** via the context accumulator; span
  close rolls them up (counts/tokens/rows) onto the stage event; full per-call rows go to
  `obs_llm_calls` / `obs_db_queries`.

## Failure semantics

Observability is telemetry, never a gate: every obs code path is fail-open (`except: pass`),
the PG sink is a daemon thread with a bounded buffer (overflow drops + counts, never blocks),
and a broken obs schema/DB degrades to JSONL+console silently. This mirrors the pipeline's
own fail-open conventions (`obs/failures.py`, `cfg()`).

## Knobs (app_config, code-default fallback)

`obs.enabled` (on) · `obs.sink.pg` (on) · `obs.sink.jsonl` (on) · `obs.sink.console` (on) ·
`obs.max_field_bytes` (16384) · `obs.llm.max_prompt_bytes` (32768) · `obs.buffer_max` (5000) ·
`obs.flush_interval_s` (2.0)

## Tests

`tests/test_obs_trace.py` covers the contract offline (identity, span capture, thread-hop nesting, taps, legacy
forward, redact, fail-open). `tests/conftest.py` stubs `obs.sink_pg.write` for the whole session so tests never
write trace rows into the production store (console + per-trace jsonl still exercise the real machinery).

## Dashboards / analytics

`db/obs_schema.sql` ships views: `obs_v_stage_latency` (p50/p95/p99 per stage),
`obs_v_trace_summary` (one row per execution), `obs_v_recent_errors`, `obs_v_token_spend`
(tokens per stage/day), `obs_v_card_funnel` (per-card verdict funnel). `obs/query.py` exposes
the same as a CLI for ops (`trace <id>`, `latency`, `errors`, `tokens`, `recent`).
