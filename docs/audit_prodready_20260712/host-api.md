# Prod-Readiness Audit — host-api lens — 2026-07-12 (differential)

Scope: host/ + HTTP APIs (:8770). Differential over docs/audit_2026-07-12/api-design.md +
AUDIT_REPORT.md (C/H findings + Fixes Applied) + refactor ledger. Only NEW issues, regressions
between today's concurrent changes, half-applied refactors, and untrue "fixed" claims are recorded.
Read in full: host/server.py, exec_cards.py, enrich.py, multi_asset.py, notes.py, assemble.py,
asset_lanes.py, inspector_api.py, payload_store.py (targeted), run/harness.py, obs/middleware.py,
obs/stage.py, replay/capture.py+store.py, data/db_client.py, host/web/src/{types.ts,api.ts,App.tsx}.

Status: COMPLETE.

---

## Verified OK (positive checks — today's fix claims that ARE true)

- **R1 executor budget is real** — `as_completed(futs, timeout=max(0.0, deadline-now))` in
  try/except TimeoutError (host/exec_cards.py:234-244); unfinished cards honest-blanked
  `executor budget exceeded` in `finally` (:246-251); `ex.shutdown(wait=False, cancel_futures=True)`
  (:252). Budget-exceeded card flows to enrich with completed=None → `_skeleton_payload` structure-
  preserving blank + `run_why` reason (host/enrich.py:149-153,199). **Contextvars are copied into the
  pool** per task: `ex.submit(contextvars.copy_context().run, _fill, cid, o)` (exec_cards.py:232), so
  `executor.card` spans nest correctly.
- **H16 closed (run_traced wired)** — `_traced_captured` wraps BOTH `/api/run` and `/api/frame`
  (host/server.py:150-168, 252, 257); signatures match `obs/middleware.py:40 run_traced(kind, fields, fn)`
  and `replay/capture.py:41 captured(kind, request, fn, ..., path=)`. Fail-open import guard present.
- **H20 FIXED** — the multi-asset path now applies the prompt-derived date window:
  host/multi_asset.py:90-94 calls the shared `host/notes.window_from_preset(lane0.get("window"))`;
  the lane is a full run_pipeline result which carries `out["window"]` (run/harness.py:250, 277).
  The helper's home move to notes.py also kills the server↔multi_asset lazy back-import cycle.
- **Dump-then-send is safe** — `_dump_response(resp)` runs before the return in both handle_run legs
  (server.py:347, 364) and never raises (whole body in try/except pass, server.py:140-147). Disk-full
  loses only the dump, never the HTTP response. (H15's real residue is retention — see OBS-6.)
- **Fixes-Applied #12 TRUE** — payload_store never-cache-empty: `ok` flag guards the cache write on
  both `_skeleton_payload` (host/payload_store.py:70-72) and `_raw_default_payload` (:94-100).
- **R2 landed in code** — `data/db_client.py:32` default engine is `"pool"` (pooled psycopg2, CSV
  parity, self-heal retry-once) with `V48_DB_ENGINE=psql` rollback. `/api/site`'s per-poll probe (api
  M7) is substantially mitigated once :8770 restarts onto this code (running process predates it).
- **Knowledge-gate run-id leak fix present** — `make_run_id(prompt)` + `ai_log.set_run_id(_rid)` BEFORE
  the gate's LLM call (server.py:337-338); knowledge terminal gets a `knowledge` stage record + a
  run_id'd response dump (server.py:342-347). `knowledge.ems.ask` returns exactly the consumed
  `{kind,answer,refused}` shape (knowledge/ems.py:68-79).
- **RC1 special dispatch on /api/frame is type-correct** — `handling_classes` returns int keys
  (layer2/catalog/card_handling.py:22), matching `.get(int(render_card_id))` (server.py:289).
- **Replay bundles are bounded** — `replay.keep_traces=300` prune on every persist (replay/store.py:48,
  81-94). The only telemetry store with retention.
- **/api/inspector routing hygiene** — exact path match via `u.path.rstrip("/")`, `n` clamped 1..200,
  400 on missing id (server.py:226-234). jsonl fallback path traversal is blocked in practice (the
  `trace_` prefix glues to the first path component; pg reads are parameterized, inspector_api.py:27,141).
- **natural-compare preflight is fail-open + telemetried** — any exception → `[]` → single path →
  degrade gate (multi_asset.py:32-70); decisions logged via `_tel`.
- **R10 FE half real** — api.ts checks `res.ok` before `.json()` via `httpError` (api.ts:9-14);
  `PipelineResult` is a discriminated union. (Server half NOT done — see OBS-1.)
- **Host package integrity** — all host/*.py compile; every lazy import in server.py/multi_asset.py
  resolves from repo root (registry_for_picker, named_full_rows, resolve_compare, roster_stats,
  display_dash.apply(payload, default), config.endpoints.HOST_PORT=8770).

**Known-open, unchanged, NOT re-reported** (still exactly as prior lens recorded): 204-with-body
(server.py:189, M2), startswith routing + no 405 (server.py:192-255, L1), /api/frame client-fault →
500 (server.py:289,301-303, L2), no body-size cap / socket timeout (server.py:242, M3), `cfg("api.token")`
NOT implemented anywhere (H12/R6, owner-gated), /api/frame arbitrary-neuract-table read has no
allowlist (H12), `_default_payload` client round-trip (M4), knowledge+compare preflights serialized
before the pipeline (M6), envelope `ok` semantics drift + duplicated ~20-key envelope builders (H4/M8 —
H20's window leg fixed, the extraction of one `response_envelope()` still not done; multi still
hardcodes `asset_no_data:False` at multi_asset.py:135 so a dark asset in a compare loses its notice).

---

## Findings (new / changed / untrue-claims)

### OBS-1 — R10 marked "completed" but the server never stamps `kind:"dashboard"`; types.ts now asserts a required field the wire lacks  [MEDIUM, safe]
- `host/web/src/types.ts:134-138`: comment says *"build_response stamps kind:'dashboard' on the wire
  (server.py:97), so the discriminant is REQUIRED ... [R10 completed 2026-07-12]"* and declares
  `kind: "dashboard"` as a required field.
- Reality: neither `build_response` (host/server.py:95-133) nor `build_response_multi`
  (host/multi_asset.py:115-156) emits any `kind` key; server.py:97 is `"run_id"`. Only the knowledge
  envelope carries `kind` (server.py:345).
- AUDIT_REPORT.md:271 honestly recorded "the server doesn't yet stamp kind — left optional + flagged",
  but the types.ts written by the concurrent FE session drifted PAST that: the TS contract now certifies
  a shape the server never sends (the exact H21 defect class re-introduced the same day it was audited).
- Runtime survives by accident: App.tsx:85,88 branches `r.kind !== "knowledge"` (undefined passes); any
  future `r.kind === "dashboard"` check silently fails.
- Fix (safe, 2 lines): add `"kind": "dashboard"` to BOTH envelope builders — and note this is itself a
  live demonstration of the H4 duplicated-envelope risk (every field lands in two places).

### OBS-2 — handled 500s are traced as status="ok": run_traced never sees the HTTP code or the `error` (singular) envelope  [MEDIUM, safe]
- `handle_run`/`handle_frame` catch every exception and return `(500, {"ok": False, "error": "..."})`
  (host/server.py:301-303, 366-368) — so `fn()` never raises into the middleware.
- `obs/middleware.py` status logic: `status = "error"` only if `t["errors"]` non-empty OR
  `resp.get("errors")` (plural) truthy; else degraded/ok. The 500 envelope's key is `error` singular,
  and the HTTP code rides in the `box` closure (server.py:159-168) invisible to run_traced.
- Result: a request that 500s (e.g. a raised exception between spans in build_response, or any
  /api/frame parse fault) lands in obs_traces / the Inspector as `status="ok"` unless an inner span
  happened to append to trace errors. Failure telemetry (the layer this was all built for TODAY) under-
  counts exactly the worst outcomes.
- Fix (safe): in `_traced_captured`, pass the code into the summary (e.g. stamp `resp["_http_code"]`
  or have run_traced accept an outcome hint); or in middleware treat `resp.get("error")` /
  `resp.get("ok") is False` as error status.

### OBS-3 — /api/inspector is a NEW unauthenticated cross-origin surface serving full prompts + raw LLM outputs  [MEDIUM, owner-gated]
- Built today (not present in any prior lens doc): `GET /api/inspector/trace?id=…` returns, per AI call,
  `prompt_system`, `prompt_user`, raw `response`, params, candidates/rejected reasoning
  (host/inspector_api.py:155-167) — behind CORS `*` (server.py:179) with no credential on 0.0.0.0:8770.
- This materially widens H12: previously an attacker could spend LLM tokens and read neuract tables;
  now the complete prompt/decision/response history of every user is readable from any browser on the
  LAN. The `cfg("api.token")` knob (R6) is still not implemented (grep: zero hits outside docs).
- Fix: fold into the R6 token gate when it lands (owner-gated); interim cheap step: gate /api/inspector
  behind a `cfg("inspector.enabled")` knob or bind-scope it.

### OBS-4 — trace_id is stamped on the wire copy AFTER the disk dump is written; dumps can't join obs traces  [LOW, safe]
- Order: `handle_run` → `_dump_response(resp)` (server.py:364) runs INSIDE `fn()`; only afterwards does
  `run_traced` do `resp.setdefault("trace_id", …)` (obs/middleware.py:70-72). So
  `outputs/logs/response_<run_id>.json` — the client-timeout recovery artifact and payload_diff input —
  lacks `trace_id`, and the dump↔trace join falls back to prompt-hash run_ids, which collide across
  executions (H14).
- Fix (safe): stamp `resp["trace_id"] = obs.trace.current()["trace_id"]` in handle_run/handle_frame
  before `_dump_response` (setdefault in middleware already yields to a handler-set value).

### OBS-5 — budget race discards real results: futures that finish inside the timeout window are marked "executor budget exceeded"  [LOW, safe]
- host/exec_cards.py:243-252: after `_FTimeout`, the `finally` sweep marks every cid not in
  status_by_id as budget-exceeded — including a future that COMPLETED between as_completed's raise and
  the sweep (`fut.done()` true, payload available, discarded). Page renders that card as a skeleton
  though its data was fetched.
- Fix (safe, honest): in the finally loop, harvest `fut.done() and not fut.cancelled()` results before
  marking the rest budget-exceeded.

### OBS-6 — H15 status update: unrotated log growth ACCELERATED same-day (485MB→1.2GB, 865→1428 files); retention still absent  [MEDIUM, safe]
- `du outputs/logs` now: **1.2G / 1428 files** vs the morning audit's 485MB/865. Every /api/run and
  /api/frame writes response dumps + pipeline/ai jsonl + obs trace jsonl; the 30k-prompt validation
  sweeps multiply this. Replay bundles are the ONLY pruned store (replay.keep_traces=300,
  replay/store.py:81). Disk has 1.3T free so not imminent — but the doubling rate is now measured, and
  the growth writers gained two new families today (trace_<tid>.jsonl, obs pg fallbacks).
- Fix (safe): one retention sweep (age/count cap) over outputs/logs mirroring replay/store._prune;
  R7's retention item remains open.

---

## Direct answers to the lens questions

- **run_traced wiring**: done and correct (both endpoints, fail-open). Knowledge gate + natural-compare
  preflight both inside the traced body — good.
- **H15 dump-before-send**: the dump precedes the send but is exception-proof; disk-full silently loses
  the dump only. Not a request-breaking defect (see Verified OK); the retention half is OBS-6.
- **R1**: present and correct, including contextvars into the pool (see Verified OK); one low-severity
  race (OBS-5).
- **kind:"dashboard" (R10)**: still missing server-side; now contradicted by the FE types → OBS-1.
- **H20 multi-asset date window**: FIXED, verified end-to-end (notes.window_from_preset ← lane.window
  ← harness out["window"]).
- **Envelope duplication**: still two hand-built envelopes (~20 keys each); window drift closed, `ok`
  semantics + `asset.asset` shape + hardcoded `asset_no_data:False` still drift; no shared
  response_envelope() extracted (known H4, unchanged).
- **HTTP hygiene / api.token / /api/frame allowlist**: all unchanged from the prior lens — 204-with-body,
  startswith routing, frame 500-on-client-error, no token knob, no table allowlist (see known-open list).
