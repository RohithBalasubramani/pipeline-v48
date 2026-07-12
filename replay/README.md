# replay/ — the V48 replay engine

Full-fidelity per-request capture + deterministic re-execution + automatic side-by-side diff.
Design: `docs/REPLAY_ENGINE_DESIGN.md`. Identity: the obs `trace_id` (`obs/trace.py`, unique per
execution — NOT the prompt-hash `run_id`, which collides across executions of the same prompt).

## What every run stores (always-on, fail-open)

Every `/api/run` + `/api/frame` request writes `outputs/traces/<trace_id>/`:

- `request.json` — the exact POST body + path
- `cfg_snapshot.json` / `env_snapshot.json` — the app_config rows + filtered env the run actually saw
- `events.jsonl` — every LLM call (full prompts, parsed outcome, per `llm/client.call_qwen`), every SQL
  read with FULL ROWS (`data/db_client.q`, `registries/neuract/_db.rows|dicts`, `ems_exec/data/neuract._run`),
  the validate pandas probe, the unseeded narrative-insight call, and each card's executor fill
  (operative window + completed payload) — typed-encoded so injected rows keep their Python types
- `artifacts/pipeline_out_<run_id>.json` — the harness `out` dict per lane (1a/1b/validation/layer2)
- `artifacts/response.json` — the final HTTP response

Knobs (app_config, code-default fallback): `replay.capture` (on) · `replay.keep_traces` (300).

## Replaying

```bash
python3 -m replay.cli list                      # newest bundles
python3 -m replay.cli replay last               # pinned replay of the newest run
python3 -m replay.cli replay t_<id> --mode live # live re-run (fresh AI + DB), request + clock still pinned
python3 -m replay.cli replay r_<run_id>         # a run_id resolves to its newest bundle
python3 -m replay.cli compare t_<a> t_<b>       # diff any two bundles without re-running
```

- **pinned** (default): LLM + SQL + insight + frame-probe + cfg served from the tape; the wall clock is
  frozen to the original instant. Needs NO tunnel and NO vLLM. Any diff = a code-path change (or a tape
  miss — misses are first-class findings, never silent). `--strict` raises on the first miss instead.
- **live**: only the request, env and clock are pinned — shows model + data + config drift.
- `--pin llm,sql` — hybrid pinning for drift attribution (e.g. pin SQL, live LLM = pure completion drift).

Output: terminal summary + `outputs/traces/<replay_id>/replay/{comparison.json, report.html}` —
a self-contained side-by-side (original left, replay right) with per-section severity chips
(`IDENTICAL / DRIFT / DIVERGED / MISSING`), per-card payload diffs, prompt-drift excerpts, and
SQL added/removed/changed listings.

A replay never touches the original artifacts: legacy writers (`ai_/pipeline_/sql_<run_id>.jsonl`,
`response_<run_id>.json`, notes, failures) are redirected into the replay bundle's `legacy_logs/`.

## Known limits

- Warm-cache values of the ORIGINAL server process (TTL caches, payload_store) are not re-created;
  a fresh replay resolves through the tape-fed readers instead — residual differences surface in the
  compare rather than being masked.
- The narrative-insight cache (`_insight._CACHE`) can hide that call from the tape when it was warm at
  record time; a pinned replay then records a tape miss for it (and live-falls-back if :8201 is up).
- Original TIMEOUTS replay as their recorded classified failures — timing races are not re-run.
