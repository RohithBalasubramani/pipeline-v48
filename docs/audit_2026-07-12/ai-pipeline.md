# AI-Pipeline Lens Audit — pipeline_v48 (2026-07-12)

Scope: the LLM machinery itself — `llm/` client (retry semantics, no_retry_kinds, timeouts, guided_json, budget),
prompt management across layer1a/1b/2, grounding/fabrication guards (bypass analysis, verdicts-as-telemetry),
determinism controls, the eval story, vLLM saturation behavior, and single-vLLM coupling.

All file paths relative to `/home/rohith/desktop/BFI/backend/layer2/pipeline_v48/`. Every line number was read in this
session. Live `cmd_catalog.app_config` was queried read-only on 2026-07-12: `llm.guided_json.route='on'`,
`llm.guided_json.asset_resolve='on'`, `llm.no_retry_kinds='timeout,truncated'`, `llm.seed=42`, `llm.temperature=0`,
`llm.timeout=120`, `llm.timeout.asset_resolve=60`, `llm.timeout.l2_emit=150`, `layer2.emit_concurrency=4`;
**no `llm.max_tokens` row, no `llm.timeout.route` row**.

## Overall assessment

This is one of the most carefully hardened LLM pipelines I have audited at this maturity: temp-0 + pinned seed with a
documented batching-nondeterminism rationale (llm/client.py:28-33), classified failure kinds with per-stage telemetry,
prompt-budget preflight, deterministic-failure fail-fast (`no_retry_kinds`), enum-grammar guided decoding on the two
routing-shaped calls, a generated (never hand-drifted) recovery-fn library, byte-identity metadata gates, a layered
honest-blank wall stack (L2 gates → cross-domain blanking → post-fill fab_guards), and verdicts that genuinely stay
telemetry (build.py's per-leaf partitioning is exemplary). The remaining enterprise risk is concentrated NOT in
fabrication (that door is closed several times over) but in **shared-capacity behavior and operability**: everything
assumes one lightly-loaded localhost vLLM, and the pipeline's own validation framework documents that >2-3 concurrent
runs manufacture failures.

---

## HIGH severity

### H1. No process-global admission control on the vLLM: the concurrency cap is per-run, the host is unbounded-threaded, and saturation timeouts are (by policy) never retried

**Evidence**
- `run/layer2_all.py:41-49` — the emit fan-out cap (`layer2.emit_concurrency`, 4) is applied per `run_2_all` call:
  `res = run_parallel(tasks, max_workers=_cap)` — a fresh `ThreadPoolExecutor` per run (`run/parallel.py:19`).
- `host/server.py:29,346-361` — `ThreadingHTTPServer` with `daemon_threads = True`: every concurrent `POST /api/run`
  gets its own thread and its own `run_pipeline` → its own 4-emit pool. `grep -rn "Semaphore" host/ run/ llm/` → no hits.
- `llm/client.py:142` and `layer2/emit/emit.py:210-217` — `timeout` is in `no_retry_kinds` (deterministic-failure
  policy), so a **contention-induced** timeout is treated like a deterministic one and permanently degrades that card
  for that response.
- The project's own words, `validation/config.py:3-8`: "*>2-3 concurrent runs CONTEND and manufacture fake 'llm
  timeout' failures (certified 2026-07-06: emit fan-out is capped inside the pipeline; page-level sweeps must stay
  <=2-3)*" — the eval harness must throttle itself to avoid breaking the system under test.

**Why it matters** — this is the scaling wall. At 4 concurrent users, ~16 in-flight ~21K-token emits split decode
throughput; the 150s `l2_emit` fail-fast fires; because `timeout` is never retried, users get pages with honest-blank
cards purely from co-tenancy. The no-retry-on-timeout rule is correct for the *deterministic* oversized-prompt case it
was built for (card-5 heatmap), but it silently also covers the *transient* saturation case, where the correct fix is
queueing, not failing.

**Recommendation** — add ONE process-global semaphore (DB knob, e.g. `llm.global_concurrency`) acquired inside
`llm/client.call_qwen` (or a tiny queue in front of it), so total in-flight vLLM calls are bounded regardless of how
many runs are active; keep the per-run cap for fairness. Optionally distinguish "timed out while queue was saturated"
(retryable once after acquiring a slot) from "timed out solo" (deterministic, fail fast). Safe/additive.

### H2. Single localhost vLLM instance is a hard SPOF with no health probe, no circuit breaker, no failover

**Evidence**
- `llm/config.py:4-5` — `LLM_URL = env or "http://localhost:8200/v1/chat/completions"`; one endpoint, five call sites,
  all through `call_qwen` (sync `urllib`, one-shot request, llm/client.py:158-164).
- No health-check or breaker anywhere in `llm/` — during an outage every request individually burns its full per-stage
  timeout (route: 120s base since there is no `llm.timeout.route` row) before `layer1a/route.py:98-107` raises
  fail-closed and `run/degrade_gate.py` converts it to the honest `data_unavailable` terminal.
- Memory/systemd notes confirm a single `vllm.service` box.

**Why it matters** — enterprise deployment means model restarts, GPU OOMs, upgrades. Today each of those is a full
product outage; worse, during the outage every incoming request holds a host thread for up to ~120s×stages before the
honest terminal, so the outage also consumes the host. The honesty story is excellent (no silent misroute — route.py's
fail-closed raise is the right call); the availability story does not exist.

**Recommendation** — (1) a cheap breaker in `call_qwen`: after N consecutive transport failures, fail instantly for a
TTL (both DB knobs) so outage requests return the honest terminal in milliseconds; (2) allow `LLM_URL` to be a
load-balanced VIP over ≥2 replicas — the seed-pinned determinism argument (client.py:28-33) holds per-server, so
document that replica variance is bounded by the same guided-json/gates stack. Safe/additive.

### H3. AI-call observability is not concurrency-safe: global `urlopen` monkeypatch + module-global run id + colliding prompt-hash run ids, and 486 MB of unrotated logs containing user prompts

**Evidence**
- `obs/ai_log.py:8,13-15,56` — `_RUN_ID` is a module global set by `set_run_id()`; `urllib.request.urlopen` is
  monkeypatched process-wide at import; every :8200 request/response (full prompts + completions) is appended to
  `outputs/logs/ai_<_RUN_ID>.jsonl`.
- `run/harness.py:187` (`ai_log.set_run_id(run_id)`) and `:105-107` (reset per reflect attempt) — with
  `ThreadingHTTPServer` (host/server.py:29), two concurrent runs race on `_RUN_ID`: run B's `set_run_id` relabels every
  in-flight call of run A. Under H1's multi-user reality, exactly the incidents you must debug produce cross-labeled logs.
- `run/run_id.py:5-7` — `r_ + sha1(prompt)[:10]`: the same prompt from two users at once shares one run id AND one
  jsonl file (append-interleaved), and re-runs append across days.
- Measured: `outputs/logs` = **486 MB, 868 files**, no rotation/retention anywhere; records include verbatim user
  prompts (PII/retention exposure at enterprise).

**Recommendation** — move logging into `llm/client.call_qwen` itself (it already owns the request/response and the
`stage` tag) keyed by a `contextvars` run id (`obs/trace.py` already has the contextvar pattern), delete the
monkeypatch; add a size/age-based retention knob for `outputs/logs`. Safe (telemetry-only change).

### H4. One cmd_catalog blip at first `cfg()` read silently pins EVERY LLM knob to code defaults for the process lifetime — including turning guided-json routing determinism back off

**Evidence**
- `config/app_config.py:18-24` — `_load()` is `lru_cache(maxsize=1)`; on any exception it caches `{}` **forever**.
- Consequences specific to this lens: `layer1a/route_schema.py:52` and `layer1b/resolve/answer_schema.py:41` read
  `llm.guided_json.*` with default `'off'` — the live DB says **'on'**, so a catalog outage at host start silently
  reverts the routing-determinism fix; `llm/client.py:59-65,135-143` — per-stage timeouts, `no_retry_kinds`, budget,
  seed/temperature all fall back the same way with zero telemetry.
- This is the same failure shape as the 2026-07-09 `panel_members` cache-poison incident, which was fixed with
  never-cache-empty + TTL (`data/ttl_cache.py`) — but `cfg()` did not get that fix.

**Recommendation** — apply the panel_members medicine to `_load()`: never cache an empty result on exception, and use a
TTL (reuse `cache.resolution_ttl_s` or a dedicated knob) so a flap self-heals; record one `obs.failures` entry when the
fallback fires. Safe.

---

## MEDIUM severity

### M1. 1a route is single-attempt fail-closed: one transient transport blip kills the whole request

**Evidence** — `llm/client.py:165-167` (transport failures are never retried inside the client);
`layer1a/route.py:96-102` (empty result → RuntimeError → honest terminal). Contrast `layer1b`: both LLM calls get
`retry_once` (`layer1b/guardrail/retry_one.py`, used at `asset_resolve.py:157` and `column_basket.py:67`), and the L2
emit has a bounded transport retry (`emit.py:210-217`). The single most load-bearing call in the pipeline is the only
one with zero transport retry.

**Recommendation** — wrap the route `call_qwen` in the same `retry_once` (transport-shaped failures only), keeping the
fail-closed raise after the bounded retry. Safe.

### M2. `degrade_gate` conflates vLLM saturation with a data-source outage in the user-facing cause

**Evidence** — `run/degrade_gate.py:22-35`: the fingerprint list includes bare `"timed out"` and the route's
`"llm transport/parse failure"` string; both map to `data_unavailable` with a `reason_template` sentence about the
data source. An `llm.timeout.route`-less 120s vLLM contention timeout therefore renders to the user (and to ops
dashboards) as "data unavailable" when the data stack was healthy and the LLM was saturated — the wrong runbook.

**Recommendation** — split the cause: LLM-shaped fingerprints → `llm_unavailable` (own reason_template row), DB/tunnel
fingerprints → `data_unavailable`. Telemetry/wording only. Safe.

### M3. The L2 emit — the largest, most defect-prone call — has no guided decoding; envelope drift is absorbed by after-the-fact rescue heuristics

**Evidence** — `layer2/emit/emit.py:209` passes no `schema`/`json_schema`; determinism/validity rely on the prose
envelope (`layer2/prompts/data_instructions_v2.md:116-117`) plus repair code: nested `answerability`/`data_note`
hoisting ("29 across the log archive", `layer2/build.py:442-449`), shape-keyed morphs routing (`build.py:387`), and the
gate-failure re-prompt (`build.py:758-779`). Meanwhile the guided seam is built, live-probed, and switched ON for
route and asset_resolve (`route_schema.py`, `answer_schema.py`; DB rows read today). The same determinism problem is
thus solved three different ways across the three layers.

**Recommendation** — a flag-gated `llm.guided_json.l2_emit` schema constraining the Layer2CardOutput envelope
(top-level keys, `swap_decision.action` enum, `fields[].kind/source` enums — leave free-text values unconstrained),
A/B-verified offline with the existing `tools/replay_*` pattern before flipping, watching xgrammar compile cost on the
48.7K-char system prompt. Safe (default off).

### M4. Multiplicative retry stack with no per-card attempt budget or deadline

**Evidence** — per emit: client parse-retry (`llm/client.py:139,191-195`, ×2 attempts) × emit transport retry
(`emit.py:210-217`, ×2) → up to 4 calls; gate-failure re-prompt re-runs `emit()` (`build.py:773`) → up to 8; a swap
adds a full re-emit for the target (`build.py:737-753`) with its own retry stack. Worst case ≈ 8-12 × ~21K-token calls
for ONE card, each up to 150s, with no counter, no deadline, and no telemetry of total attempts per card.

**Recommendation** — thread a small attempts/deadline budget through `emit()` (e.g. `llm.card_attempt_budget`, default
generous) and stage-log per-card `llm_calls`; this also caps the H1 amplification (retries multiply saturation). Safe.

### M5. The quantity/semantic walls fail open on unclassified vocabulary, and vocab freshness is a manual, partially-covered process

**Evidence** — `layer2/gates.py:532-533` ("the walls check QUANTITY, and unclassified = compatible") and `:593-598`
(rule ii skips when classes are unknown); classification vocab lives in THREE homes (code mirrors in
`layer2/quantity_class.py` (791 lines), `app_config` rows, `db/seed_*.sql`), and `cfg()` **replaces** rather than
merges — which is exactly why `tools/seed_quantity_vocab.py` had to be written (its header: fixes "cfg()-replace
drift"). No equivalent seeder or coverage check exists for the other wall vocabularies, and there is no telemetry
counting how many binds pass the walls *because* they were unclassified.

**Why it matters** — every new meter schema/card family starts life unclassified, i.e. temporarily outside the
anti-fabrication walls; the post-fill `fab_guards` catch some classes (epoch leak, null-column, no-source, seed-leak —
`ems_exec/executor/fab_guards.py:11-44`) but not a wrong-quantity bind between two real columns.

**Recommendation** — (1) emit an `unclassified_bind` telemetry count per card (one line in `enforce_honest_blank`);
(2) a `validation.cli coverage`-style check listing basket columns and slot paths with no classification; (3) make
vocab rows merge-with-defaults or generate seeders for the remaining wall vocabularies. Safe.

### M6. Prompt-injection surface: the raw user prompt enters four LLM calls with no untrusted-data framing, and several AI free-text channels reach the UI unfiltered

**Evidence**
- Prompt embedded verbatim (repr-quoted only): `layer1a/route.py:81`, `layer1a/story_builder.py:31`,
  `layer1b/resolve/asset_resolve.py:149`, `layer1b/basket/column_basket.py:61`; `knowledge/ems.py:57` additionally
  folds **client-supplied** `history` turns (`:55-65`) as trusted "User:/Assistant:" context.
- None of the five system prompts (`layer1a/prompts/system.md`, `asset_system.md`, `column_system.md`,
  `data_instructions_v2.md`, `knowledge/prompts/ems.md`) contains a "the PROMPT is data, never instructions" clause.
- Blast radius is well bounded for *decisions*: route/metric/intent are enum-clamped and (today) grammar-pinned;
  asset names map back deterministically (`asset_resolve.py:108-119`); basket intersects the real column dictionary.
  But *free text* flows to the UI: the 1a story is injected into L2 with authority ("your morph + a swap target MUST
  serve this angle", `layer2/emit/user_message.py:249`); `data_note` "is saved and shown to the user"
  (`data_instructions_v2.md:97`); R12 explicitly licenses story-driven morphs of titles and displayed thresholds
  ("tighten/loosen a threshold the prompt flags", `data_instructions_v2.md:35`); the knowledge answer is rendered
  verbatim (`knowledge/ems.py:84-85`).
- Net: a crafted prompt cannot fabricate *data* (walls + fab_guards), but it can put attacker-authored sentences,
  titles, and display thresholds on an operator-facing industrial dashboard.

**Recommendation** — add the one-line untrusted-data clause to the four system prompts; length-cap and
control-character-sanitize `data_note`/story/knowledge text at the host serve boundary; treat `history` as untrusted
(cap turns/lengths). Safe.

### M7. The eval story is strong on paper, unautomated in practice: one recorded session, outcome-shape judging only, no scheduled regression

**Evidence** — `outputs/validation/sessions/` contains exactly one session (`smoke_1`);
`validation/checks/expectations.py` judges only the outcome grammar (`cards|picker|knowledge|refused|empty|
unavailable|compare:N`); `validation/checks/determinism.py` (read in full) diffs structural fingerprints only, runs
sequentially, and is invoked manually; content-correctness certification (the 18-page sweeps, per-leaf REAL/EMPTY
diffing) lives in docs/agent worklogs, not in a runnable harness. The 97-file pytest suite is unit/contract level.
Positive: `tools/wall_corpus_replay.py` is a real gate-change regression harness; the corpus generator is
deterministic (seed=48).

**Why it matters** — every prompt file, vocab row, and knob is mutable without a code deploy (by design), so the
regression surface moves *without commits*; nothing runs nightly to notice.

**Recommendation** — a cron (the stack already has `tools/stack_monitor.sh` precedent) running
`validation.cli generate+run+report` on a pinned ~30-case corpus + `determinism` at repeats=2, diffing `report.json`
against the previous night; extend expectations with per-case `expected_page_key` (already derivable from the corpus
template) so silent routing drift is caught mechanically. Safe.

### M8. No per-stage token/latency accounting; completion length unbounded (no `llm.max_tokens` row); budget is a chars/4 estimate

**Evidence** — `llm/client.py:135-137` (`max_tokens` only if the row exists — it does not, verified live), `:148`
(budget = `(len(system)+len(user))//4`); the vLLM `usage` block is captured raw inside `ai_*.jsonl` (obs/ai_log.py:47)
but nothing aggregates tokens/latency per stage/run — `obs/stage.py` records none, so capacity planning for H1/H2 has
no data. A runaway completion today is bounded only by the 150s timeout.

**Recommendation** — read `usage` in `call_qwen` (it already parses the response) and stage-log
`{stage, prompt_tokens, completion_tokens, ms}`; seed a conservative `llm.max_tokens` row. Safe.

---

## LOW severity

### L1. Prompt assembly by string surgery is fragile (though test-guarded), and prompts are unversioned/unfingerprinted
`layer2/emit/emit.py:171-193`: ROSTER marker cutting, `{{RECOVERY_LIBRARY}}`/`{{LIVE_ENDPOINTS}}` replacement
(silently no-ops if the placeholder is renamed — `if _LIB_PLACEHOLDER in out:` at :182), and the morphmap envelope
substring rewrite (`'"exact_metadata":{"_morphed":[]}' → '"morphs":{}'`, :193). Tests DO pin the substrings
(`tests/test_morphmap_dp_gate.py:200-254`, `tests/test_residual_layer2_emit.py:202,228-231`), which is why this is Low
not Medium. Still: no runtime telemetry when a placeholder is absent, and no prompt-content fingerprint in the AI
logs, so correlating a behavior change to a prompt edit requires diffing 48.7K-char blobs.
**Fix**: hash the composed system prompt into the `ai_log` record (one field); assert-else-record placeholders. Safe.

### L2. Basket LLM call value is unmeasured
`layer1b/basket/column_basket.py:35-67`: the shipped basket is `logged floor ∪ AI` capped; the deterministic floor
plus `probable` machinery may already carry most of the value — one candidate LLM call per run (plus retry) could be
saved, but ONLY after measuring overlap from the existing `ai_*.jsonl` corpus. Efficiency question, not a defect.

### L3. Knowledge lane: transport failure silently misroutes a concept question into the card pipeline; history is client-trusted
`knowledge/ems.py:69-86` — fail-open to `kind='dashboard'` means a vLLM hiccup turns "what is THD?" into a routed
dashboard (confusing, though harmless); the marker mechanism (`on_error='marker'`) exists in the client but is not
used here to distinguish outage from a genuine dashboard verdict. Covered partly by M6 for the history surface.

### L4. Truthiness parsing of flag rows is re-implemented per file
`llm/client.py:100`, `layer1a/route_schema.py:31`, `layer1b/resolve/answer_schema.py:33` share one `_ON` tuple style,
while `asset_resolve.py:58` and `knowledge/ems.py:32` use off-list checks (`!= 'off'`) — an `'On '`-with-space row
behaves differently across files. One `config.app_config.flag(key, default)` helper would end the class.

---

## Explicitly checked and found sound (no finding)

- **Verdicts are telemetry, not render gates** — verified end-to-end: `build.py:525-545` partitions field-level gate
  issues into `_per_leaf_gaps` (never `conforms=False`); `gates.py:711-722` carves out honest-none/gate-emptied cards;
  `gate_roster` backfills the recipe truth rather than blocking (`gates.py:834-836`); `_reconcile_slots` is
  "TELEMETRY ONLY" (`build.py:226-235`). The per-leaf degradation rule is genuinely enforced in code.
- **Guard-bypass hunt** — the historical `$ctx`/group bypass is closed (`gates.py:527-534`); cross-domain binds are
  blanked, not merely noted (`build.py:639-657`); undeclared morphs revert (`build.py:414-427`); swap targets are
  pool/page/template-clamped (`data_instructions_v2.md` PART 1 + `layer2/swap/`); post-fill `fab_guards` add four
  slot-name-independent class killers. The only systemic hole found is the unclassified-vocab fail-open (M5) and the
  by-design free-text channels (M6).
- **Determinism mechanics** — temp 0 + pinned seed DB-driven with code defaults (`client.py:127-134`); guided-json ON
  in the live DB for both routing calls; `resolve_page_key` recovery becomes unreachable under the grammar
  (route_schema.py rationale). Deterministic re-route (`route_to`) avoids a second LLM call.
- **Timeout/no-retry design for the deterministic case** — truncation-before-parse-success ordering and the grown-
  retry budget check (`client.py:146-156,174-176`) are correct and unusually careful.
- **Prompt/gate vocab anti-drift where it was engineered** — the recovery library is generated from the executor's own
  registry (`emit.py:60-118`); metric/intent enums are substituted from the same config the clamps read
  (`route.py:76-80`); `config.gates_vocab` is shared by prompt and gate (`build.py:516-520`).

## Suggested priority order
1. H1 global LLM admission control (+ M4 attempt budget) — the scaling wall.
2. H3 concurrency-safe AI logging + retention — prerequisite for debugging everything else at load.
3. H4 cfg() never-cache-empty + TTL — one-line-ish, closes a silent-determinism-loss incident class.
4. H2 breaker + replica story for vLLM.
5. M1/M2 route retry + cause split (small, high honesty value).
6. M7 nightly validation cron; M5 unclassified-bind telemetry; M3 guided emit envelope (flag-gated); M6 injection framing; M8 usage accounting.
