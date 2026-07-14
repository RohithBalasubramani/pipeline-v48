# Latency audit — lens: perceived latency + delivery protocol + frontend
Date: 2026-07-14. READ-ONLY audit. Scope: host/server.py response protocol, host/web/* FE, vite config, picker/frame round trips.

## Ground-truth measurements taken in this audit

### A. Stage-span timeline of a real interactive run (trace t_2aed84a50d9b43a8b8ca1434dfbde5e3, run r_48c83f28a2, prompt "compare voltage and current for pcc 1 and 2", 2026-07-14 02:45)
```
   0.0 ->    0.3  knowledge_gate           (LLM 336ms)
   0.3 ->  184.6  ***  UNTRACKED GAP: natural_compare_ids pre-flight ***
                  = 8 SERIAL has_data batch probes on target_version1 (:5433/VPN),
                    14.4s + 19.7s + 23.8s + 26.6s + 26.8s + 27.6s + 19.3s + 26.1s = 184.3s
 184.6 ->  195.0  asset_resolution (10.4s — cache warmed by the probes above)
 184.6 ->  186.8  page_selection + story_selection
 196.3 ->  196.5  validation
 196.5 ->  290.4  layer2_card_ai (5 cards, emits done at +14.2/+21.8/+27.5/+36.6/+93.8s after L2 start)
 290.4 ->  296.1  executor (5 cards, 0.9-5.7s each, all START only after LAST emit)
 296.1            response
```
User staring at a spinner for 296s; the FIRST L2 emit was done at t=210.7 and its exec fill would take ~1s — a
streamed first card could have painted at ~212s; the page shell (page_key + layout + card list) was final at t=196.5.

### B. Cross-run distributions (cmd_catalog obs_stage_events, 302 traces, Jul 12-14)
- knowledge_gate→pipeline-start gap (= natural_compare pre-flight): p50 1.8s, **p90 188.3s, p99 523s, max 538s**.
- All-runs (sweep-contended incl.): shell-ready (validation end) p50 180.8s / p90 353s; first L2 emit p50 193s; response p50 210s / p90 392s.
- HEALTHY regime (pre-flight gap < 5s, n=97, avg 4.2 cards):
  - shell-ready: **p50 9.8s / p90 16.0s**
  - first L2 emit done: **p50 23.8s / p90 35.4s**
  - full response: **p50 42.0s / p90 81.6s**
  - exec tail (response − L2 end): p50 5.7s
- => In the healthy regime the browser could show the page shell at 9.8s (23% of e2e) and the first real card at
  ~25-27s (60% of e2e) instead of one paint at 42s.

### C. Picker round trip (pipeline_<rid>.jsonl files with PENDING then pinned re-POST; same run_id since make_run_id(prompt) is deterministic)
| file | leg1 (pending, no L2) | leg2 (pinned re-POST) | leg2 1a+1b re-run share |
|---|---|---|---|
| pipeline_r_f37fab9b3c | 4.4s | 22.1s | 6.1s (28%) |
| pipeline_r_13c9229793 | 3.9s | 34.8s | 1.4s (4%) |
| pipeline_r_f8601a2d04 | 6.2s | 13.2s | 1.7s (13%) |
| pipeline_r_fc900dffea | 225.8s | 273.9s | 209.6s (77%, contended) |
Leg2 re-runs 1a (route+stories+page_selection ≈ 3-4 LLM calls) and 1b from zero even though leg1 computed both for
the SAME prompt seconds earlier. Nothing is reused: handle_run → run_pipeline recomputes 1a; 1b is pinned (fast-ish)
but candidates/basket re-probe unless the 120s TTL cache still holds.

### D. /api/frame (date-control re-fetch): obs_traces kind='frame', n=262: **p50 1.68s, p90 7.9s, p99 16.1s, max 19.6s** per card.
DateSync fans out ONE POST PER is_history CARD on a single date pick (CmdCard.tsx effect). Browser HTTP/1.1
connection cap = 6 per origin → on an 8-card panel page, cards 7-8 queue behind the first 6. No spinner shown on
cards during re-fetch (old data stays; errors silently swallowed by `.catch(() => {})`).

### E. Response JSON sizes + compression (outputs/logs/response_*.json, n=403)
- largest: 490KB / 464KB / 454KB / 430KB / 409KB; typical single-asset 50-90KB.
- gzip ratios measured: 490KB→61KB (8.0x), 464KB→86KB (5.4x), 409KB→37KB (10.9x).
- host/server.py `_send` (line 198-207) does `json.dumps(...)` with **no Content-Encoding, no gzip**; Vite dev proxy
  does not compress either. On LAN this is ~10-50ms — small, but on any WAN/VPN path a 490KB body at 10Mbps = 390ms.
- keep-alive OK (protocol_version HTTP/1.1 + Content-Length set). ThreadingHTTPServer, backlog 128.

### F. Per-card payload sizes (response_r_48c83f28a2): payload 3-5KB, data_instructions 2-29KB, refetch bundle 3-4.5KB
per card. /api/frame re-POSTs card.payload + data_instructions + refetch — ~10-40KB upload per card; negligible on LAN.

### G. FE serving: v48-web.service runs **`npx vite` DEV MODE** in production use (ops/SERVICES.md port map).
- 211 static `@cmd-v2` deep imports in host/web/src; fill/ (25 modules) and cmd/components/ barrels use
  `import.meta.glob(..., { eager: true })` → the ENTIRE CMD_V2-touching module graph loads at startup.
- Dev mode = per-module on-demand transform + hundreds of sequential ESM requests on first load over LAN.
- A dist/ build EXISTS (Jul 12, assets 2.6MB, AdminApp code-split) but is not served.

### H. FE polling loops
- useSiteStatus: /api/site every 15s (CommandHeader) + every 12s while DataUnavailable shown. /api/site does a
  LIVE `SELECT 1` against neuract :5433 per poll — during a tunnel flap each poll can hang up to the psql connect
  timeout; two components can double-poll.
- PromptBar copilot: debounced 160ms, aborted, client-cached (healthy).
- Admin console (:5188/admin, own bundle) — separate polling (checked separately below).

### I. Serial pre-pipeline work on EVERY fresh prompt (handle_run, host/server.py:370-402)
knowledge gate LLM (~0.3-0.7s) → natural_compare_ids (asset_candidates + has_data probes; p50 1.8s, p90 188s) →
run_pipeline. All strictly BEFORE 1a∥1b start. The knowledge gate answer is discarded for dashboard prompts; the
natural-compare rows are recomputed by 1b again inside the pipeline (TTL cache is the only reuse).

### J. Multi-asset compare path (host/multi_asset.py build_response_multi)
- run_pipeline_multi: lanes per CLASS run SEQUENTIALLY (`for cls, members in by_class.items()` harness.py:409-416).
- Then per-ASSET assemble_cards also SEQUENTIAL (multi_asset.py:127-139): a 3-same-class-feeder compare = 1 lane
  (1a + L2 once) + 3 sequential executor fan-outs (each 5-10s+ for panel fills).
- compare_mode() = one more serial LLM call after ALL fills (line 146).
- RESPONSE_MULTI measured live: p50 142s / p90 683s. Streaming per-asset groups (or at least parallel assemble)
  directly attacks this.

---

## FINDINGS (perceived latency / delivery protocol / FE)

### S1. Progressive card streaming (SSE/NDJSON) — the single biggest perceived-latency lever
**Now:** one monolithic JSON after everything (host/server.py:285-286 handle_run → build_response → _send).
FE shows a text spinner (App.tsx RunningCard) for the whole p50 42s (healthy) / 210s (contended) / 142s-683s (multi).
**Mechanism of loss:** every already-finished artifact (1a page shell at ~10s, each L2 emit at 24-40s, each exec fill
0.9-5.7s) waits for the LAST card.
**Proposal (minimal-change):** a flag-gated `POST /api/run?stream=1` that emits NDJSON events over the same
ThreadingHTTPServer response (chunked; no new infra): `{"ev":"shell", page, layout, cards:[skeleton stubs], asset}`
after asset_gate; `{"ev":"card", card}` per enriched card as its exec fill completes; `{"ev":"done", ...full envelope}`
terminal (byte-identical to today's response for the non-stream path — contract preserved).
Requires: (a) run_2_all yields per-card completions (callback/queue instead of dict-join) OR keep L2 join and stream
only shell + per-exec-completion cards; (b) exec_cards._run_cards already uses as_completed → per-card hook is a
5-line seam; (c) App.tsx incremental state: `cards: Map<card_id, Card>` + CardGrid renders skeleton tiles for known
card_ids (HonestBlankTile already exists as the skeleton primitive); (d) enrich per card instead of batch (enrich is
per-card already: assemble.py:54 list-comp).
**Arithmetic (healthy single-asset p50):** shell at 9.8s (was 42s: −32s to first paint), first card at ~26s (−16s),
last card unchanged. Panel pages p90: shell 16s vs 81.6s (−65s to first paint). Multi-asset (see S7) benefits most:
first GROUP streams at lane-1 end (~40-60s) instead of p50 142s.
**Risk:** medium (new protocol beside pinned byte-identical path; NDJSON streams through the Vite http-proxy fine).

### S2. Early page-shell render (subset of S1, shippable alone)
1a+validate finalize page_key/layout/card list at p50 9.8s / p90 16s (healthy). Even without per-card streaming, a
two-phase response (shell event + final monolith) cuts blank-screen time by 32s p50 / 65s p90. Caveat measured:
granularity_reconcile / preflight_reroute / reflect can SWAP the page after first 1a (r_48c83f28a2 swapped at
+11.7s; reflect reroutes are rarer — reroute_on=hard_failure default) → stream the shell AFTER asset_gate (post
reconcile+preflight), and on a reflect re-route send a `shell_replace` event (rare: only hard emit failures).

### S3. Kill/overlap the natural_compare serial pre-flight (shared with the 1b lens, but it gates time-to-first-byte)
**Evidence:** knowledge_gate→pipeline gap p90 188s / p99 523s (302 traces); 8 serial ~23s has_data UNION probes on
:5433 measured in trace A. host/server.py:399 `natural_compare_ids(prompt)` runs strictly BEFORE run_pipeline.
**Proposal (my-lens angle):** (a) run natural_compare CONCURRENTLY with the optimistic single-asset 1a∥1b start —
promote to multi only if it returns ids (the single lane's L2 has not started by then: 1b asset resolution p50
10-22s > natural_compare healthy 1.8s); (b) share 1b's candidate probe instead of a second asset_candidates() call;
(c) at minimum stream a progress event so the user sees what is happening instead of 3 minutes of spinner.
**Arithmetic:** p90 fresh-prompt time-to-anything −186s (188.3s gap − ~2s overlap); p50 −1.8s.

### S4. Picker re-POST recomputes 1a from zero
**Evidence:** table C. Leg2 spends 1.4-6.1s (healthy; 28% of a 22s run) re-running route+stories+page_selection on
the IDENTICAL prompt leg1 just routed; run_id is even the same deterministic hash. Under contention this was 209s.
**Proposal:** host-side short-TTL (60-120s) cache {prompt → layer1a result + validation + 1b candidate_list} written
at the asset_pending return, consumed when the SAME prompt re-POSTs with asset_id/asset_ids (run_pipeline already
accepts layer1a= injection — the multi path uses it; harness.py:242 `(lambda: layer1a)`). AI-first preserved: the
cached 1a IS the AI's decision for that prompt.
**Arithmetic:** picker interaction leg2 −1.4-6.1s p50 (−28% on a 22s pinned run); contended tail −200s+.
The mechanism (layer1a injection) already exists and is test-covered for multi lanes.

### S5. Date-change re-fetch: no per-card pending state + HTTP/1.1 6-connection cap
**Evidence:** D. Each is_history card POSTs /api/frame (p50 1.7s, p90 7.9s); >6 cards queue: on an 8-card page two
cards start ~8s late in the worst case. Old payload stays visible with NO loading indicator (CmdCard.tsx:46-51),
errors silently dropped — the user cannot tell a card is stale, in-flight, or failed.
**Proposal:** (a) optimistic per-card spinner overlay while the frame fetch is in flight + an error badge on failure
(pure FE, ~20 lines in CmdCard); (b) batch endpoint `/api/frames` accepting N cards in ONE POST, server fans out via
the existing exec pool (breaks the 6-connection cap; 8 cards in one round trip; also 1 obs trace instead of 8);
(c) alternatively HTTP/2 via Caddy/nginx in front — heavier.
**Arithmetic:** 8-card page date change: today max(6 parallel) + queued 2 ≈ p90 7.9s + 7.9s ≈ 16s worst-lane;
batched server-side (pool of 8) ≈ max single ≈ 8s (−8s p90) + perceived spinners immediately.

### S6. /api/site poll does a live :5433 round trip every 15s per client
**Evidence:** server.py:233-240 `q(DATA_DB, "SELECT 1")` per poll; useSiteStatus polls at 15s (header) and 12s
(outage view). With the tunnel down each poll waits the full connect timeout serially in a handler thread.
**Proposal:** server-side memoize the liveness probe (TTL 5-10s) so N clients/tabs share one probe; short
connect/statement timeout for this probe specifically.
**Saving:** minor (protects handler threads + tunnel from N×4/min probes; probe measured 1-15ms healthy).

### S7. Multi-asset: sequential lanes + sequential per-asset assembles + trailing compare_mode LLM call
**Evidence:** J. harness.py:409 loops classes serially; multi_asset.py:127 loops assets serially; compare_mode
(1 LLM call ~0.5s) runs AFTER all fills at line 146. RESPONSE_MULTI p50 142s / p90 683s; slowest = 3-feeder compares.
**Proposal:** (a) parallelize per-asset assemble_cards (executor is thread-safe — same pool pattern);
(b) parallelize class lanes (each an independent run_pipeline with its own run_id — L2 emit cap is the shared
constraint, so gate lanes at 2); (c) fire compare_mode CONCURRENTLY with the fills (it only needs the prompt);
(d) with S1, stream group 1's cards while group 2 fills.
**Arithmetic:** 3 same-class feeders: 3 sequential assembles ≈ 3×5.7s exec ≈ 17s → parallel ≈ 6s (−11s);
2-class compare: 2 serial lanes ≈ 2×40s → ~45-50s parallel under emit-cap contention (−30s p50); compare_mode −0.5s.

### S8. Serve the built bundle (or prebundle CMD_V2) instead of Vite dev mode
**Evidence:** G. `npx vite` dev in the systemd unit; 211 @cmd-v2 static imports, eager glob barrels → first browser
load transforms + serves the entire graph module-by-module over LAN; dist/ (2.6MB, code-split) exists but unserved.
**Proposal:** `vite build && vite preview --port 5188` (or serve dist/ + proxies via Caddy). Keep dev mode for
development only. HMR-ignore for CMD_V2 is already in place, so dev-mode benefits are minimal for operators.
**Arithmetic:** first-load: dev mode measured (see below) vs <1-2s for the built bundle (2.6MB ≈ 0.2s at 100Mbps +
parse). Repeat loads cached either way. Also removes dev-server transform CPU competing with the pipeline.

### S9. No gzip on :8770 responses
**Evidence:** E. 490KB worst response, 8-10x gzip-compressible; _send writes identity encoding always.
**Proposal:** honor Accept-Encoding with gzip level 1-6 in _send (stdlib gzip, ~5 lines) or front with Caddy.
**Arithmetic:** LAN: −30-40ms on a 490KB multi response; VPN/WAN clients: −0.3-3s. Small but free. Low priority.

### S10. RunningCard shows zero progress
**Evidence:** App.tsx:233-246 — static "Building your real-time view…" for up to 11 minutes (p90 multi 683s).
**Proposal:** even without S1, a cheap `/api/progress?run_id=` poll reading the already-written
outputs/logs/pipeline_<rid>.jsonl stage records (PROMPT/1a/1b/validate/L2.card/exec) gives a live stage ticker
("routing page… authoring card 3/5… filling data…"). run_id is deterministic from the prompt (make_run_id) so the
FE can compute/receive it up front. File-backed, zero pipeline change.
**Perceived saving:** does not move wall clock but converts 42-296s of dead spinner into visible progress.

### S11. sessionStorage full-result save on every run — measured trivial (5-15ms at 490KB). Dead end, no action.

### S12. handle_run knowledge-gate LLM is serial for every fresh prompt
**Evidence:** I; measured 336ms in trace A (baseline ~0.7s). For dashboard-shaped prompts its answer is discarded.
**Proposal:** fire knowledge gate and 1a∥1b CONCURRENTLY; if the gate returns kind=knowledge, abandon the pipeline
lane (only 1b's first DB probe is spent by 0.7s); else join. AI-first: the gate still decides; only waiting overlaps.
**Arithmetic:** −0.3-0.7s p50 on every fresh dashboard prompt.

### S13. Exec fills start only after the LAST L2 emit
**Evidence:** timeline A: all 5 executor.card spans start at 290.4 (last emit end) though emits finished at
210.7-233.1; healthy-regime exec tail p50 5.7s. harness `_reflect_loop` joins run_2_all fully, then host
assemble_cards runs the exec fan-out.
**Proposal:** per-card pipelining — as each L2 emit completes, fill it (swap_settle is a post-pass over ALL emits;
either settle-then-fill per card with optimistic keep + re-fill the rare reverted swap, or restrict pipelining to
non-swapped emits). With S1 this is what makes cards stream at emit-pace; without S1 it still cuts the exec tail.
**Arithmetic:** e2e −3-5s p50 (exec tail 5.7s overlapped except the last card's own fill ~1-3s); with S1,
time-to-first-card follows first-emit (+~1-3s) instead of last-emit.

### S14. Vite proxy hop for /api — measured negligible (~0.5-2ms localhost). Dead end.

### S15. AssetResolution "resolved" popup requires a manual "Open dashboard" click after the pinned re-run
App.tsx:98 keeps `resolving=true` after a pick — the dashboard is READY behind the popup but the user must click
"Open dashboard" to reveal it. Human-time perceived latency on every picker flow.
**Proposal:** auto-dismiss on a successful pinned result (cards.length>0 && !asset_pending) with a toast. ~5 FE lines.
**Saving:** 1 click + reaction (~1-3s human) per picker interaction.

---

## Post-write additions (measured after first draft)

### S8 measurement (dev-mode first load, real browser, localhost, warm Vite cache)
Playwright load of http://localhost:5188: **250 module requests, 3.8MB transferred, load event 5.33s**,
FCP 468ms (the header shell paints early but card registry graph finishes at 5.3s — eager glob barrels).
Over LAN add per-request RTT × 250 (with 6-connection HTTP/1.1 parallelism ≈ +1-4s more). Built bundle (dist/
2.6MB, code-split AdminApp) would be ~0.3s transfer + parse on localhost, 1-2s LAN. Cold Vite (fresh server
restart, no transform cache) is materially worse — not measured (would require a service restart: out of scope).
=> S8 saving: first visit −3-8s; every hard refresh −2-5s.

### S16. Repeat-prompt recipe reuse (the "repeat prompts" scenario)
**Evidence:** run_id = make_run_id(prompt) is deterministic — the SAME prompt re-POSTed recomputes 1a (route/
stories/page_selection ~5-10s) and every L2 emit (p50 19.8s/card) even seconds later; only exec fill (data) is
freshness-sensitive. The multi-asset path already PROVES recipe reuse is sound: rebind_consumer re-points one L2
recipe at N assets, byte-tested. outputs/logs/response_<rid>.json even persists the full recipe today.
**Proposal (flag-gated):** TTL cache (e.g. 10-15min, DB knob) keyed (prompt, resolved asset, page_key) holding
{layer1a, layer2 recipe}; a hit skips 1a + L2 and runs ONLY assemble_cards (exec fan-out) on fresh neuract data +
enrich. AI-first: the cached artifacts ARE the AI's own decisions for that exact prompt; data is always re-read.
**Arithmetic:** repeat prompt p50 42s → exec+enrich ≈ 6-10s (**−32s**); panel pages p90 81.6s → ~12-15s.
Also directly serves the date-control "re-run same prompt" habit some users have instead of the date bar.

### Admin "1a" stage span — VERIFIED what it includes
The pipeline jsonl "1a" record is written AFTER run_parallel joins BOTH 1a and 1b (harness.py:254-282: stage()
calls follow the join loop). So admin /admin/api/latency stage "1a" = max(1a_route, 1b_asset_resolution) and its
p90 120s / max 415s is dominated by 1b's has_data probes — NOT by page routing (route LLM itself measured 0.5s,
stories 1.3-1.6s, page_selection 0.5-1.0s in traces). It EXCLUDES the natural_compare pre-flight (PROMPT record is
stamped inside run_pipeline, after the gap) — so the admin console UNDERSTATES user-perceived latency by up to
188s p90 on fresh compare-shaped prompts. The obs trace (request_received span) is the honest e2e clock.

### Admin console polling — checked: only ReplayPage uses setInterval (replay progress); traces/list pages are
on-demand. Not a latency factor.

### Dead ends checked
- sessionStorage save: 5-15ms worst. Not material.
- Vite /api proxy hop: ~0.5-2ms localhost. Not material.
- /api/frame request upload size: 10-40KB/card. Not material on LAN.
- PromptBar copilot: already debounced (160ms) + AbortController + client cache. Healthy.
- keep-alive on :8770: HTTP/1.1 + Content-Length present — keep-alive works; backlog 128 OK.
- FE JSON.parse of 490KB response: ~5-10ms. Not material.
