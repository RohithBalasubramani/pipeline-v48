# AI Decision Inspector (2026-07-12)

Every AI decision in the V48 pipeline, fully disclosed per LLM call: **prompt** (system+user), **model**,
**temperature/seed/response_format/url/timeout** (`params`), **candidates** (the option set the stage materialized
before prompting), **selected**, **rejected**, **reasoning**, **confidence**, **latency**, **token usage**, and the
**raw final output**. Built ON TOP of the obs trace layer (see `OBS_TRACE_DESIGN.md`) — the inspector adds decision
semantics + a read API + a UI; storage/attribution stay the trace layer's.

## Where each piece lives (atomic)

```
obs/llm_tap.py          set_decision()/clear_decision() contextvar + `params`/`decision` on every llm record;
                        _bound_decision (knob obs.llm.max_decision_bytes, explicit truncation marker)
llm/client.py           builds `params` per call; passes it to both tap records; call_qwen clears the decision
                        context in a finally (one call = one decision, all attempts included)
obs/event.py            llm event `ai.params` + `ai.decision`
obs/sink_pg.py          obs_llm_calls INSERT includes params/decision (jsonb)
db/obs_schema.sql       obs_llm_calls.params/.decision + idempotent ALTER TABLE migration (re-applied on sink start)
obs/decision_view.py    READ-side: stage response JSON → {selected, rejected, reasoning, confidence} via a
                        declarative per-stage mapping (route/stories/asset_resolve/basket/l2_emit/knowledge_ems/
                        insight_narrator; unknown stages get a generic key sniff)
host/inspector_api.py   GET-shaping: traces list + trace detail, Postgres-first, per-trace jsonl fallback
host/server.py          GET /api/inspector/traces?n=…  ·  GET /api/inspector/trace?id=t_…
obs/middleware.py       /api/run response now carries `trace_id` (deep-link the inspector to THIS run)
host/web  …/InspectorView.tsx + api.ts + types.ts + CommandHeader INSPECTOR button + App.tsx #inspector hash view
tests/test_decision_inspector.py   offline contract (10 tests)
```

## The decision context per stage (what `candidates` means where)

| stage             | kind           | candidates declared at the call site                                  |
|-------------------|----------------|-----------------------------------------------------------------------|
| route             | selection      | live page specs `[{page_key,title}]` + metric/intent vocab            |
| stories           | generative     | none (card roster rides as context)                                   |
| asset_resolve     | selection      | the class-narrowed registry listing `[{name,class,load_group,has_data,aka}]` (ids stay hidden, matching the resolve-by-NAME contract) |
| basket            | selection      | the meter's real column dictionary `[{column,label,kind,unit,has_data}]` |
| l2_emit           | selection      | the slot's swap pool `[{card_id,title}]` (+card_id, gate_feedback_retry) |
| knowledge_ems     | classification | `dashboard / knowledge / off_scope`                                    |
| insight_narrator  | generative     | none — narrates a pre-judged story (direct :8200 POST, reports its own tap record in `_insight._post`) |

`selected/rejected/reasoning/confidence` are extracted at READ time from the stored response by
`obs/decision_view.py` (e.g. l2_emit → `swap_decision.action/swap_to_id`, reasoning = criterion+reason+data_note,
confidence = `swap_decision.confidence`; `keep` = the whole pool rejected). The stored record stays raw.

## Semantics / gotchas

- One `call_qwen` = ONE decision: every attempt (parse-retry, transport retry re-invocations) re-declares the same
  context via the stage's `_call()` closure; `call_qwen` clears the contextvar in a `finally`, so an un-annotated
  later call can never inherit a stale decision.
- Fan-out safe: `run/parallel` copies the context per thunk, so concurrent per-card L2 emits carry their own.
- Everything is fail-open telemetry — no capture path can raise into the pipeline; the UI/API are read-only.
- Candidate lists are size-bounded (`obs.llm.max_decision_bytes`, default 24576) by halving with an explicit
  `…[truncated] N more option(s)` marker + `candidates_total`, so "rejected" is never silently incomplete.
- Old obs_llm_calls rows (pre-2026-07-12) have `params/decision = NULL` — the view still extracts selected/reasoning
  from the response; candidates show empty.
- The copilot service (:8772/:8201) is OUT of scope by design (zero pipeline coupling); its calls are not traced.

## Adoption

Capture + API ride the normal process lifecycle: **restart the host server** (`python3 host/server.py`, :8770) to
serve `/api/inspector/*` and start recording params/decision; the vite FE (:5188) hot-reloads on its own. The pg
store migrates itself on the sink's next start (idempotent ALTER in db/obs_schema.sql — already applied manually to
the live cmd_catalog on 2026-07-12). Open the UI via the INSPECTOR button in the header or `#inspector` in the URL;
after a run, the inspector deep-links to that run's trace via the response's `trace_id`.

Verified 2026-07-12: 25 offline tests green + live E2E ("ups 2 incoming current trend" → 10 decisions: route over
18 pages, asset_resolve over 328 candidates confident-pin, basket over 71 columns conf 0.79, 5 per-card emits incl.
a 0.95-confidence swap with full reasoning) + Playwright walkthrough of the UI on spare ports.
