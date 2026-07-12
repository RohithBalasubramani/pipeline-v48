# V48 Replay Engine — Design (2026-07-12)

## Goal

Given any `trace_id`, re-execute that exact request and produce a **side-by-side comparison**
between the original run and the replay — prompt, AI inputs, AI outputs, page selection, asset
resolution, metadata, SQL, executor, validation, rendering — with differences highlighted and
classified automatically. Every production run stores enough to make a **deterministic replay**
possible (no live tunnel, no live vLLM needed in pinned mode).

Builds ON TOP of the observability layer (`docs/OBS_TRACE_DESIGN.md`): `trace_id` is the obs
execution identity (`obs/trace.py`, uuid4 — NOT the prompt-hash `run_id`, which collides across
executions). Obs answers "what happened" (size-bounded, roll-ups, dashboards); replay stores
**full-fidelity** bytes (unredacted prompts, actual SQL rows, resolved config) because replay
needs to *re-produce*, not just describe.

## Trace bundle (one dir per execution)

```
outputs/traces/<trace_id>/
  manifest.json        trace_id, kind(run|frame|replay), replay_of?, mode?, ts, git_sha, run_ids, prompt
  request.json         the exact POST body + path (what /api/run received)
  env_snapshot.json    filtered os.environ (V48_*, LLM_*, EMS_*, PG*, CATALOG_*, STORYBOOK_URL)
  cfg_snapshot.json    config.app_config._load() verbatim (the knob rows the run actually saw)
  events.jsonl         full-fidelity choke-point events (see kinds below), typed-encoded, ordered
  artifacts/
    pipeline_out_<run_id>.json   run_pipeline's full out dict (per lane: '', loop2, class:<cls>)
    response.json                the final HTTP response
  replay/              (replay bundles only) comparison.json + report.html
  legacy_logs/         (replay bundles only) redirected ai_/pipeline_/notes/response_ writes
```

### Event kinds (events.jsonl)

| kind      | seam (record + inject)                          | payload |
|-----------|--------------------------------------------------|---------|
| llm       | `llm/client.call_qwen` (outer boundary)          | stage, system, user, knobs(seed/temp/schema/max_tokens/timeout), outcome return/raise, parsed value, ms |
| sql.q     | `data/db_client.q`                               | db, sql, rows (csv lists) or raised error text, ms |
| sql.reg   | `registries/neuract/_db.rows`                    | sql, params, rows (typed-encoded) |
| sql.nx    | `ems_exec/data/neuract._run`                     | sql, params, rows (typed-encoded) |
| frame_probe | `validate/data_load.load_asset_frame`          | table, columns, limit → df(split json), cols, ordered |
| insight   | `ems_exec/renderers/_insight._narrate_sync`      | story, fields → result (this call is UNSEEDED temp-0.2 — replay MUST inject it) |
| exec_card | `host/exec_cards.fill_one_card` (record-only)    | card ids, operative window, completed payload — the executor diff anchor |
| tape_miss / tape_fuzzy | replay-time only                    | what didn't match the tape and what was served instead |

Rows are **typed-encoded** (`replay/coding.py`): datetime/date/Decimal survive the JSON
round-trip as the same Python types, so injected rows are indistinguishable from live reads.

## Capture (always-on, fail-open)

`host/server.py` wraps each `/api/run` + `/api/frame` in `obs.middleware.run_traced` (outer) +
`replay.capture.captured` (inner). `captured` attaches a `Recorder` to the active obs trace dict
(all fan-out threads reach it via the contextvars the trace already propagates; the executor pool
in `host/exec_cards.py` gets the same one-line `copy_context().run` fix as `run/parallel.py`),
snapshots cfg+env, runs the handler, then writes the bundle once at request end (buffered — no
per-event fsync on the request path). Knobs: `replay.capture` (on), `replay.keep_traces` (300,
oldest pruned, prune count logged). Every hook is fail-open: a broken recorder can never affect
a request.

## Replay (fresh process, `python3 -m replay.cli replay <trace|run_id|last>`)

Order matters (imports bake config):
1. load bundle; apply `env_snapshot` to `os.environ`
2. **pinned mode**: pre-seed `config.app_config._load` with `cfg_snapshot` (before other imports)
3. freeze `replay/clock.py` to the original request wall-clock (the five behavior-affecting
   `datetime.now` sites route through it: L2 window anchor fallback, asset-facts age string,
   executor freshness badge, host preset/range resolvers)
4. install the `Tape` (recorded events → keyed queues) on the replay context
5. redirect every legacy writer (`obs/ai_log`, `obs/stage`, `obs/notes`, `obs/failures`,
   `obs/sql_trace`, `host/server._dump_response`) into the replay bundle's `legacy_logs/` —
   a replayed prompt hashes to the SAME run_id, and would otherwise APPEND to the original
   `ai_<rid>.jsonl` and OVERWRITE `response_<rid>.json`
6. re-run the exact request through the SAME entry (`host/server.handle_run` / `handle_frame`),
   captured as a new bundle (kind=replay, replay_of=<orig>)

### Modes
- **pinned** (default): LLM + SQL + insight + frame-probe + cfg all served from the tape.
  Deterministic; no tunnel/vLLM needed. Isolates **code drift**: any diff means the code path
  changed (or the tape missed — misses are first-class findings, never silent).
- **live**: only the request (incl. the original resolved date_window) and the clock are pinned;
  AI + DB run live. Shows **model drift + data drift + config drift**.
- Per-kind pinning (`--pin llm,sql,...`) for hybrid diagnosis (e.g. pin SQL, live LLM =
  pure completion-drift view).

### Tape matching
Exact key first — llm: sha256(stage|system|user|schema|seed|temp); sql: sha256(door|db|sql|params).
Same key recurring → FIFO; queue drained → repeat last (idempotent reads). Miss → per-stage
ordered fallback (llm) with the prompt diff recorded as `tape_fuzzy`, else live fallback recorded
as `tape_miss`. Strict mode (`--strict`) raises instead. An original that RAISED (q() RuntimeError,
LlmError) re-raises the recorded error verbatim — the degrade-gate fingerprint branches reproduce.

## Compare + report

`replay/compare.py` aligns the two bundles into sections: request, ai_calls (per stage,
prompt-drift vs completion-drift separated), page_selection, asset_resolution, l2_metadata
(per-card swap/answerability/exact_metadata/data_instructions), sql (added/removed/changed rows),
executor (per-card completed payloads), validation, rendering (per-card verdicts + response
flags), notes/errors, timing (informational). Deep diffs reuse `tools/payload_diff/deep_diff.py`
(STRUCTURAL vs VALUE classification + emptied/filled honesty subkinds + numeric tolerance).

Every section gets a severity: `identical | drift (values) | diverged (structure/routing) |
missing`. Output: `comparison.json` (full, no silent truncation), `report.html` (self-contained
side-by-side, original left / replay right, changed paths highlighted, per-section chips),
and a terminal summary table.

## Non-goals / known limits

- Warm-cache state of the ORIGINAL process (TTL caches, payload_store permanent dicts) is not
  reproduced: replay is always a fresh process; values the original served from a warm cache
  were recorded per-event downstream (LLM prompts embed them; SQL that DID run is taped), and
  any residual difference surfaces in the compare rather than being masked.
- Concurrency interleaving is not replayed (results are dict-keyed; order doesn't affect output);
  original TIMEOUTS are replayed as their recorded classified failures, not re-raced.
- `/api/frame` traces capture + replay through the same seam (fill_one_card), single-card scope.
