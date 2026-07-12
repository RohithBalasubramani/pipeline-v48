# admin/ — V48 internal admin dashboard (observability console)

Read-only console over the pipeline's existing per-run artifacts, plus a replay launcher.
Everything is keyed by **run_id** (`r_<10-hex>`, deterministic `sha1(prompt)` — see `run/run_id.py`);
every view links run_ids to the trace viewer.

**Server:** stdlib-only `ThreadingHTTPServer` (same pattern as `host/server.py`), port **8790**
(env `V48_ADMIN_PORT`). Run: `python3 admin/server.py`. The FE lives in `host/web/src/admin/`
(Vite `/admin` route; dev proxy `/admin/api` → `:8790`).

## Data sources (all existing, except sql_*)

| source | file | trace id |
|---|---|---|
| stage timeline | `outputs/logs/pipeline_<run_id>.jsonl` | filename only |
| LLM calls (full req/resp + usage tokens) | `outputs/logs/ai_<run_id>.jsonl` | in-row + filename |
| failures / defect records | `outputs/logs/failures_<run_id>.jsonl` | in-row + filename |
| full /api/run response (cards, render verdicts, leaf coverage, validation) | `outputs/logs/response_<run_id>.json` | in-row |
| reflect notes | `outputs/notes/<run_id>.json` | in-row |
| SQL executions (`obs/sql_trace.py`) | `outputs/logs/sql_<run_id>.jsonl` | filename only |
| validation harness sessions | `outputs/validation/sessions/<sid>/` | parsed.run_id per case |

Noise filter: real runs match `r_[0-9a-f]{10}`; `default` / `pytest` / `r_test_*` files are dev noise
(surfaced only under `sink=all`). `pipeline_*.jsonl` rows carry NO run_id (filename only) and use
epoch-float `ts`; `ai_*`/`failures_*`/`sql_*` rows carry run_id and ISO `ts`.

## Modules (atomic-structure: one concern per file)

- `config.py` — paths, port, host-API base, run-id regex, date-param parsing
- `store.py`  — (path, mtime, size)-keyed parse cache + run-file enumeration; the ONE disk door
- `runs.py`   — per-run summary + the recent-runs listing (date filter, text query, pagination)
- `trace.py`  — the full per-run trace (stages w/ derived durations, AI calls, SQL, failures, notes,
                cards w/ render verdicts, validation) + single-AI-call detail
- `ai_usage.py` — token/call extraction per ai_* file (cached) + usage aggregates + heaviest calls
- `sql_report.py` — SQL execution listing/aggregates from sql_* files
- `coverage.py` — per-leaf coverage (leaf_stats real/data/undeclared) + verdict mix, by run/page/day
- `latency.py` — stage-duration stats (p50/p90) + end-to-end elapsed trend + slowest runs
- `failures_report.py` — failure aggregates by reason/stage + error search
- `assets_log.py` — asset-resolution events (1b + asset_gate stage lines ⋈ response.asset)
- `validation_log.py` — per-run validation verdicts + column/card summaries + harness sessions
- `explorer.py` — pipeline explorer: fixed stage graph w/ per-stage aggregates + page/asset drill-downs
- `replay.py` — replay launcher: re-POST a past prompt to host `/api/run` in a background thread;
               predicted run_id = `make_run_id(prompt)`; in-memory registry of launches
- `search.py` — prompt search over run summaries
- `server.py` — HTTP surface + routing (mirrors host/server.py Handler conventions)

## HTTP API (all GET unless noted; all list endpoints accept `from`/`to` ISO dates)

```
GET  /admin/api/health                → {ok, logs_dir, n_runs}
GET  /admin/api/runs?from&to&q&page_key&limit&offset&sink   → {ok, total, runs:[RunSummary]}
GET  /admin/api/run/<run_id>          → {ok, trace: Trace}
GET  /admin/api/run/<run_id>/ai/<idx> → {ok, call} (full request/response bodies)
GET  /admin/api/run/<run_id>/response → the raw persisted response doc
GET  /admin/api/explorer?from&to      → {ok, stages:[StageAgg], pages:[PageAgg], assets:[AssetAgg]}
GET  /admin/api/coverage?from&to&page_key → {ok, totals, by_page, by_day, honest_blanks}
GET  /admin/api/latency?from&to       → {ok, stages:[StageLat], by_day, slowest:[RunSummary]}
GET  /admin/api/failures?from&to&reason&stage&q&limit → {ok, total, by_reason, by_stage, recent}
GET  /admin/api/ai-usage?from&to      → {ok, totals, by_day, by_stage, by_model, heaviest}
GET  /admin/api/sql?from&to&run_id&q&source&slow_ms&limit → {ok, total, by_source, slowest, recent}
GET  /admin/api/assets-log?from&to&how&q → {ok, by_how, events}
GET  /admin/api/validation?from&to    → {ok, runs:[ValidationRow], sessions:[SessionSummary]}
GET  /admin/api/search/prompts?q&from&to → {ok, runs:[RunSummary]}
GET  /admin/api/search/errors?q&from&to&reason&stage → {ok, total, hits}
POST /admin/api/replay {prompt, asset_id?, asset_ids?, date_window?} → {ok, replay_id, run_id}
GET  /admin/api/replays               → {ok, replays:[ReplayRow]}
```

`RunSummary` = {run_id, ts (ISO, last activity), prompt, page_key, page_title, asset, asset_class,
asset_how, ok, asset_pending, data_unavailable, degrade, cards, rendered, partial, blank,
elapsed_ms, n_failures, n_ai_calls, prompt_tokens, completion_tokens, n_sql, has:{response,ai,
failures,notes,sql,pipeline}}.

## Notes

- Big-file safety: `ai_*.jsonl` rows can be MBs. `ai_usage.py` extracts a small per-call summary
  once per (path, mtime, size) and caches it; full bodies are only read by the single-call detail
  endpoint. Previews are truncated server-side.
- Stage durations are derived: stage lines are end-markers, so `dur(rec_i) = ts_i − ts_{i−1}`
  within a run file. Parallel lanes (1a∥1b, L2.card fan-out) make this approximate — the trace
  viewer labels it "since previous event".
- SQL logging: `obs/sql_trace.py` (part of the obs event-bus build) appends
  `{ts (epoch), db, sql, rows, ms, params?, err?}` keyed by `obs.ai_log._RUN_ID` in the filename.
  Hooked at BOTH choke points: `ems_exec/data/neuract.py:_run` and `data/db_client.py:q`.
  Kill switch: env `V48_SQL_TRACE=0`.
- A parallel obs build (obs/bus.py event envelope `v48.obs.v1` → console/jsonl/pg sinks, llm_tap
  with per-call stage+latency+usage, obs/query.py over `obs_*` Postgres views) is landing alongside
  this console. This admin server stays file-based on the proven legacy sinks; the PG views can be
  added as a richer source once that build settles.
- Replay: a page run is LLM-bound (up to ~300 s) — launches run in daemon threads with a 540 s
  timeout against `V48_HOST_API` (default `http://localhost:8770`); keep concurrency ≤2
  (vLLM contention manufactures fake timeouts — see memory v48-l2-fanout-concurrency-cap).
- The admin server never opens a DB connection; it reads files only.
