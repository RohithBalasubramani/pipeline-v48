# API-Design Audit — host (:8770), copilot (:8772), knowledge — 2026-07-12

Lens: REST semantics, error responses, status codes, input validation, host↔React contract,
long-request handling, timeouts, idempotency, CORS, cross-service consistency.

Files read in full: `host/server.py`, `host/assemble.py`, `host/multi_asset.py`, `host/exec_cards.py`,
`host/enrich.py`, `host/payload_store.py`, `host/web/src/api.ts`, `host/web/src/types.ts`,
`host/web/src/App.tsx`, `host/web/src/components/CmdCard.tsx`, `host/web/vite.config.ts`,
`copilot/server.py`, `copilot/generate.py`, `copilot/llm.py`, `copilot/starters.py`, `copilot/config.py`,
`knowledge/ems.py`, plus targeted reads of `ems_exec/data/neuract.py`, `run/layer2_all.py`,
`run/harness.py`, `run/run_id.py`, `data/db_client.py`, `layer1b/compare/detect.py`.

Overall: the API surface is small, coherent, and honest about degradation (per-leaf blanks, degrade
terminals, fail-open pre-flights), and the copilot's never-cache-failure rule is genuinely good.
The weaknesses cluster in four places: (1) the synchronous tens-of-seconds POST with no job handle,
no backpressure and no client timeout; (2) a completely open surface (no auth, CORS `*`, 0.0.0.0);
(3) a hand-maintained TS "mirror" contract that has already drifted from what the server sends, plus a
duplicated response builder that has already produced a behavioral divergence (multi-asset drops the
prompt-derived date window); (4) small-but-real HTTP-protocol and status-code sloppiness inherited
from hand-rolled stdlib servers.

---

## HIGH

### H1. Zero authentication + wildcard CORS on services bound to 0.0.0.0; /api/frame is an unauthenticated arbitrary-table read
- `host/server.py:203` sends `Access-Control-Allow-Origin: *` on every response; `host/server.py:358`
  binds `0.0.0.0`. `copilot/server.py:61` and `:119` do the same. No endpoint checks any credential.
- `/api/frame` (`host/server.py:252-294`) takes `asset_table`, `exact_metadata`, `data_instructions`
  straight from the request body and reads whatever table the client names. Injection is blocked —
  `ems_exec/data/neuract.py:126-134` (`_qtbl`/`_qcol`) does proper identifier quoting and columns are
  checked against `information_schema` (`neuract.py:74-90`) — but any origin on the network can read
  any table in the neuract schema, and `POST /api/run` triggers unbounded 35B-LLM spend per request.
- Why it matters: this is an industrial EMS heading to enterprise production. An unauthenticated
  compute-expensive endpoint plus telemetry read-out reachable from any browser on the LAN (CORS `*`
  means any website a plant operator visits can silently POST to it) is the single biggest gap.
- Fix (keeps simplicity): one shared-secret header checked in `Handler.do_POST/do_GET` (value from
  `cfg("api.token")`, off by default in dev), CORS origin allowlist from `cfg("api.cors_origins")`
  instead of `*`. Same three lines in the copilot. No framework needed.

### H2. Long-running /api/run is a single blocking POST; the server's own timeout mitigation (disk dump) is unreachable via the API
- A run takes tens of seconds (per-card LLM emits at up to 150s `l2_emit` timeout, executor budget 45s
  `host/exec_cards.py:18`). `/api/run` holds the connection the whole time.
- The server already anticipates client timeouts: `_dump_response` (`host/server.py:181-192`) persists
  the full response to `outputs/logs/response_<run_id>.json` "so a client timeout / disconnect never
  loses the per-run payload… the sweep + debugging read it FROM DISK". But `do_GET`
  (`host/server.py:215-239`) exposes only `/api/health`, `/api/assets`, `/api/site` — there is **no**
  `GET /api/run/<run_id>`. The mitigation exists for humans with shell access, not for the API client.
- The FE (`host/web/src/api.ts:6-14`) uses a bare `fetch` with no `AbortSignal.timeout` and no retry
  discipline; `App.tsx:138` shows a spinner indefinitely. Any intermediary (nginx/ALB default ~60s)
  will kill the response; the pipeline still completes and burns the cost, the user sees a fatal error,
  and the only recovery is a full re-POST (full re-run).
- Fix (additive, no SSE ceremony needed): serve the dump — `GET /api/run/<run_id>` returning the
  persisted response (404 while pending or a `{status:"running"}` marker). Optionally have `/api/run`
  return `run_id` immediately via a `mode:"async"` flag. FE keeps working unchanged.

### H3. No admission control: the per-run L2 concurrency cap multiplies across concurrent requests, recreating the diagnosed vLLM-contention failure
- `run/layer2_all.py:41-49`: the fan-out is bounded **per call** — `run_parallel(tasks, max_workers=_cap)`
  with `layer2.emit_concurrency` (default 4). The comment itself records the failure mode: an unbounded
  fan-out "starved to a false timeout under a multi-page sweep".
- `host/server.py:346-354`: `ThreadingHTTPServer` with `daemon_threads = True` and backlog 128 accepts
  every connection and gives each its own thread. N concurrent `/api/run` requests → up to 4·N
  concurrent ~22K-token emits against the single vLLM :8200 — exactly the contention the team already
  certified against (memory: "sweeps need ≤2-3 page-concurrency"). There is no queue, no 429, no
  `Retry-After`; the API will accept load it is known to be unable to serve.
- Fix: one process-global semaphore around `run_pipeline`/`run_pipeline_multi` acquisition in
  `do_POST` (size from `cfg("host.max_concurrent_runs", 2)`); beyond it either queue (bounded) or
  return `429` with `Retry-After`. ~10 lines, DB-driven, matches the existing knob idiom.

### H4. Duplicated response assembly has already drifted: the multi-asset path silently drops the prompt-derived date window
- Single path: `host/server.py:113-116` defaults `date_window` from the 1a-extracted preset
  (`out["window"]`, populated at `run/harness.py:228-232`) so "energy last 7 days" initializes the FE
  date bar and gives the executor a real start/end.
- Multi path: `run_pipeline_multi` returns only `{layer1a, run_id, groups}` (`run/harness.py:352`) —
  no `window` — and `build_response_multi` (`host/multi_asset.py:54-130`) never calls
  `_window_from_preset`; it echoes the FE-passed `date_window` (`multi_asset.py:127`), which is `null`
  on a fresh "compare A and B last week" prompt. The lanes fill with `date_window=None`
  (`multi_asset.py:73` → `assemble_cards` → `exec_cards._date_window_for` returns `None`).
  Partial mitigation: L2's authored `consumer.range` may still widen reads via the executor's
  `_honor_range`, but `response.date_window` is null so the FE date bar shows the wrong window and the
  page-sync refetch seam starts from nothing.
- The two builders also hand-assemble the same ~25-key envelope twice (`server.py:137-178` vs
  `multi_asset.py:86-130`) with `asset_pending`/`validation_blocked` hardcoded `False` on multi —
  every future response field must now be added in two places or drift further.
- Fix: extract one `response_envelope(...)` used by both; thread the window preset through
  `run_pipeline_multi` (or apply `_window_from_preset(shared_1a...)` in `build_response_multi`).

### H5. The FE contract is a hand-maintained mirror that has already diverged; the knowledge variant is untyped and undiscriminated
- `host/web/src/types.ts:1` says "Mirror of host/server.py build_response()". The mirror is wrong:
  - `Card` requires `story_id`, `story_name`, `variant`, `storybook_url`, `component`, `key_roles`,
    `subcards` (`types.ts:60-67`) — none of these keys are emitted by `_enrich_card`
    (`host/enrich.py:201-246`). They are required, non-optional fields that are always `undefined` at
    runtime; TypeScript is certifying a shape the server never sends.
  - `RenderVerdict` documents itself as "the Layer-3 decision the FE safe-renderer obeys"
    (`types.ts:30`) and carries `slots` / `suppress_default_leaves` (`types.ts:37-38`) — the server
    always sends `slots: None` (`enrich.py:241`) and never sends `suppress_default_leaves`; the doc
    comment also contradicts the stated design principle (verdicts are telemetry, never render gates).
  - `/api/run` returns **two shapes**: the dashboard envelope and the knowledge envelope
    `{ok, prompt, kind, answer, refused}` (`host/server.py:320-323`). Only the knowledge variant
    carries a `kind` discriminator; the dashboard variant has none. `runPipeline` claims
    `Promise<PipelineResult>` (`api.ts:3`) and the app resorts to `(r as any).kind`,
    `(r as any).asset_pending`, `(r as any).answer` casts throughout `App.tsx:70-104`.
- No versioning anywhere: server and FE deploy from one repo today, but the response is also consumed
  by sweeps/tools from disk; a field rename is silently breaking.
- Fix: put `kind: "dashboard" | "knowledge"` on **both** variants; model `PipelineResult` as a
  discriminated union; delete the dead fields; add one contract test that asserts
  `set(_enrich_card(...).keys())` and `build_response(...).keys()` match a checked-in list the TS
  types are generated from (or at minimum reviewed against).

---

## MEDIUM

### M1. Error responses leak internals on the wire and into the UI
- `host/server.py:228, 294, 343`: every 500 body is `{"ok": false, "error": f"{type(e).__name__}: {e}"}`
  — exception class + message (paths, table names, DSN fragments, psql stderr via
  `data/db_client.py:19-21` RuntimeError text) ride to any caller. `copilot/server.py:100` same
  (`str(e)[:200]`). The 200 envelope also ships `errors: out.get("errors")` raw (`server.py:177`).
- The FE displays it verbatim: `api.ts:13` throws `body?.error`, `App.tsx:140-146` renders it.
- Fix: keep full detail in stderr/`obs` (already done), serve a stable
  `{ok:false, error:{code, message}}` with a safe message; gate raw detail behind `cfg("api.debug_errors")`.

### M2. Protocol violation: 204 response with a JSON body on OPTIONS (host)
- `host/server.py:212-213`: `do_OPTIONS` calls `self._send(204, {})` → writes body `b"{}"` with
  `Content-Length: 2` on a 204. RFC 9110/7230 forbid content (and Content-Length) on 204; with
  `protocol_version = "HTTP/1.1"` (`server.py:196`) and keep-alive, a strict client/proxy that ignores
  the body on 204 will read those 2 bytes as the start of the next response (connection desync).
- The copilot does `self._send(204, b"")` (`copilot/server.py:67-68`) — Content-Length: 0, mostly
  harmless but still nonconforming, and inconsistent with the host.
- Fix: send 204 with headers only (no body, no Content-Length), or just use 200 with `{}`.

### M3. No body-size cap and no socket timeout: trivially holdable/exhaustible stdlib servers
- `host/server.py:243-244`: `n = int(self.headers.get("Content-Length", "0")); self.rfile.read(n)` —
  a client can declare and stream an arbitrarily large body into memory. Same in
  `copilot/server.py:92-93`.
- Neither Handler sets `timeout` (BaseHTTPRequestHandler default is no socket timeout), and
  `daemon_threads=True` threads are unbounded (`host/server.py:352-353`, `copilot/server.py:119`): a
  slowloris client (open sockets, send nothing) pins one thread each, forever. Combined with H1
  (open network surface) this is a low-effort availability hole.
- Fix: `Handler.timeout = 30`; reject `Content-Length > cfg("api.max_body_bytes", 2_000_000)` with 413.
  Four lines per server, preserves the stdlib-only choice.

### M4. /api/frame round-trips server-known data through the client (`_default_payload` with seed numbers)
- `host/enrich.py:217-221`: every `is_history` card's response carries a `refetch` bundle including
  `"_default_payload": l2.get("_default_payload")` — the raw harvested default, which by the project's
  own doc "carries seed numbers" (`host/payload_store.py:78-80`). The FE posts it back on date change
  (`api.ts:25-30`), and the server trusts it (`server.py:264`).
- The server can already derive this value itself: `_raw_default_payload(render_card_id)`
  (`payload_store.py:76-95`) is a per-process cache used two lines away as `shape_ref`
  (`exec_cards.py:128,135`). The round-trip bloats every response (a full default payload per history
  card), puts fabrication-source numbers on the wire (render-safe today, but one FE regression away
  from a seed leak), and lets a client substitute an arbitrary "default" that the dash policy then
  treats as type-proof (`server.py:289`).
- Fix: drop `_default_payload` from `refetch`; on `/api/frame` resolve it server-side from
  `render_card_id`. The server already has back-compat fallback parsing (`server.py:259-265`), so the
  change is additive and old clients keep working.

### M5. POST /api/run is expensive and non-idempotent, and the run identifier collides by design
- A retry (client timeout, double-click, proxy retry) re-runs the full LLM pipeline. There is no
  in-flight dedupe even though `run_id` is a deterministic prompt hash — `run/run_id.py:5-7`
  (`sha1(prompt)[:10]`) — which would make dedupe trivial.
- The same collision makes `run_id` useless as an API handle across executions: two runs of the same
  prompt share a `run_id`, and `_dump_response` overwrites the same file (`host/server.py:186-190`).
  Knowledge responses have no `run_id` at all so they all overwrite `response_default.json`
  (`server.py:186` fallback `"default"`).
- Fix: short-TTL in-flight map keyed by the prompt hash (piggyback concurrent identical POSTs on one
  run); give each execution a unique suffix (`r_<hash>.<n>` or the existing uuid trace_id) for dumps
  and the response, keeping the hash as the replay key.

### M6. Every fresh prompt pays a serialized knowledge-LLM call + compare resolve before the pipeline starts
- `host/server.py:316-333`: for any request without a pinned asset, the handler first awaits
  `knowledge.ems.ask` (one full 35B call, `knowledge/ems.py:75`), then `natural_compare_ids`
  (registry probes + per-name 1b resolves when the lexical detector fires,
  `host/multi_asset.py:36-47`), and only then calls `build_response` → `run_pipeline`. Both
  pre-flights are sequential latency added to a synchronous API whose main body already takes tens of
  seconds.
- The one-call knowledge design is an explicit user directive, so keep the single call — but it does
  not have to be serial: run `knowledge.ems.ask` concurrently with `run_pipeline`'s 1a∥1b stage and
  discard the loser (dashboard kind → keep pipeline; knowledge kind → cancel/ignore pipeline result),
  or fold the route decision into 1a's existing guided_json call. Worst-case latency drops by a full
  LLM round-trip.

### M7. /api/site liveness probe spawns a psql subprocess per poll per client
- `host/server.py:231-238` runs `q(DATA_DB, "SELECT 1")`; `data/db_client.py:12-22` shells out to a
  fresh `psql` process per call. The FE polls `/api/site` every 15s per tab
  (`host/web/src/components/CommandHeader.tsx:24-29`). At enterprise client counts this is constant
  subprocess + tunnel-connection churn for a boolean, and a half-hung tunnel (connect ok, query hangs)
  blocks the handler thread — `PGCONNECT_TIMEOUT` guards connect only, there is no statement timeout.
- Fix: cache the liveness bool server-side with the existing `data/ttl_cache.py` (e.g. 10s TTL), and/or
  probe via the pooled psycopg2 door (`registries/neuract/_db.py`) with a statement timeout.

### M8. Inconsistent envelopes and status semantics across the three surfaces
- Host errors: `{ok:false, error}`; copilot suggest error: `500 {error, autofill:"", suggestions:[]}`
  (`copilot/server.py:100`); copilot starters failure: **200** `{starters:[], error}`
  (`copilot/server.py:79`); copilot health: `{ok:true, model_up, ...}` where `ok` is always true even
  with the model down (`copilot/server.py:71-74`); host health: `{ok, sb_base}` with no dependency
  info (`host/server.py:216-217`).
- `build_response`'s `ok` field means only "1a produced cards" (`host/server.py:138`) — it is `true`
  on `data_unavailable` and `asset_pending` responses, and the FE never reads it (`api.ts` checks only
  HTTP `res.ok`). A meaningless field in the contract invites someone to trust it.
- Fix: one convention: `{ok, error:{code,message}}` on failures everywhere; either give `ok` a real
  meaning (page servable) or delete it; align the two health shapes
  (`{ok, deps:{db, llm}}`-ish, still tiny).

---

## LOW

### L1. Path routing by `startswith` and no 405s
- `host/server.py:216,220,231,252,296` and `copilot/server.py:71,75,89` route with
  `self.path.startswith(...)`: `/api/frames`, `/api/healthz`, `/copilot/suggestx` all match unintended
  handlers; `GET /api/run` → 404 (should be 405 + Allow); `POST /api/health` → 404. Exact-match on the
  parsed path (they already import `urlparse` at `server.py:222`) fixes it in a few lines.

### L2. Client-fault errors on /api/frame surface as 500
- `host/server.py:279` `int(render_card_id)` and the rest of the parse live inside the catch-all
  `except → 500` (`server.py:292-294`). A malformed `refetch.render_card_id` ("abc") or non-dict
  `date_window` is a client error but is reported as a server fault — wrong signal for monitoring and
  for retry policies. Validate and return 400 with a field name.

### L3. `starters._CACHE` pins the deterministic fallback forever after one cold-start model outage
- `copilot/starters.py:71-91`: on LLM failure the fallback roster is assigned to `_CACHE` and returned
  on every later call until process restart — the exact cache-poison class the suggest cache explicitly
  refuses 30 lines away (`copilot/server.py:41-49`) and that the pipeline fixed with TTLCache
  (memory: member-cache poison). Cache the fallback with a short TTL (or don't cache it at all).

### L4. Dead wire fields still in the contract
- `frames` / `frame_status` / `live_frame` are always empty/None (`host/server.py:126,172-174`;
  `host/multi_asset.py:124-126`) yet remain in the response, in `types.ts:119-121`, and are threaded
  through `App.tsx:129-130` → `CardGrid` → `CmdCard.tsx:48-50` ("the `frame` arg is inert now").
  `sb_base` (`server.py:142`) is served per-response for a vestigial Storybook feature. Back-compat is
  moot when FE and server ship together from one repo — prune on the next contract touch.

### L5. FE fetch robustness details
- `api.ts:12-13`: `await res.json()` runs before the `res.ok` check — a proxy's HTML 502 becomes a
  confusing `SyntaxError` instead of "HTTP 502".
- `runPipeline`/`fetchCardFrame` create no `AbortController` (contrast: the copilot typeahead does,
  `PromptBar.tsx:57,94`), so an abandoned run/date-scrub keeps server work and sockets alive; a page
  date pick fans out one `/api/frame` POST per history card (`CmdCard.tsx:63-68`) with client-side
  staleness guarded but no request coalescing.
- `/copilot/suggest` accepts unbounded `text` (`copilot/server.py:93-94`) straight into the
  per-keystroke LLM prompt — cap it (the UI can't produce it, but the API shouldn't rely on that).

### Noted, judged acceptable (no finding)
- `/api/frame` as a POST-shaped read: fine — the payload is far too large for a GET, and idempotent
  in effect.
- 200-with-degrade (`data_unavailable`, `asset_pending`) instead of 4xx/5xx: defensible and
  consistently implemented — these are application states, not transport failures, and the FE handles
  them explicitly.
- Copilot's never-cache-failure suggest cache and honest `source:"unavailable"` empty result are the
  right call and a model for the rest of the surface.
- The `refetch` bundle concept itself (stateless per-card re-fetch) is a clean design; only its
  `_default_payload` passenger is flagged (M4).
