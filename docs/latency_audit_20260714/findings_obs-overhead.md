# Latency audit — LENS: observability/logging overhead on the hot path (2026-07-14)

READ-ONLY audit. Files: obs/*, host/notes.py, run/harness.py telemetry hooks, admin/, ems_exec/executor/degrade.py.
Baselines cited from the audit brief (mined 1,287 runs Jul 6-11; live admin /admin/api/latency).

## Architecture of the telemetry write path (verified by reading code)

Per DB query (data/db_client.py `_sql_trace` + ems_exec/data/neuract.py:44-51): every q()/neuract._run calls
`obs/sql_trace.record` which does TWO things synchronously on the calling thread:
1. `obs/db_tap.record` -> builds event (uuid4 span_id, trace-lock `attribute_db`, trace-lock `next_seq`) ->
   `bus.emit` -> 3 sink-gate cfg lookups + jsonl sink (json.dumps + os.makedirs + GLOBAL `_LOCK` + open/append/close
   of trace_<tid>.jsonl) + pg sink enqueue (put_nowait, buffered — OK).
2. sql_ jsonl leg: getattr run_id -> json.dumps rec -> os.makedirs -> open/append/close of sql_<rid>.jsonl.

Per LLM call, the SAME full bodies are captured THREE times:
1. obs/ai_log.py monkeypatches urllib.urlopen (line 107) — for every :8200 response it does resp.read(),
   json.loads(req.data) (full request incl. multi-KB prompt), json.loads(response), json.dumps(rec) and a
   synchronous append to ai_<rid>.jsonl — INLINE in the LLM-calling thread, INSIDE the wire-call wrapper.
2. llm/client.py:225/234 llm_tap.record(system=..., user=..., response_text=...) -> redact.bound(32KB caps) x3 +
   _bound_decision (repeated json.dumps until fits 24KB) -> jsonl sink write (~39KB/event measured) + pg enqueue.
3. sink_pg writer thread later INSERTs the same bounded bodies into obs_llm_calls (async, off hot path).

Sinks: sink_pg = buffered/threaded, bounded queue, drops on overflow — GOOD (off hot path).
sink_jsonl = SYNCHRONOUS, per event: json.dumps + os.makedirs + global threading.Lock + open()/write()/close().
sink_console = synchronous print to stderr with flush=True (skips kind=db/legacy) — journald bound.
obs/stage.py stage() = print to stderr (flush=True) + open/append/close pipeline_<rid>.jsonl + legacy_event -> bus
(ANOTHER jsonl+pg write) + failure fan-out — 4 write channels per stage() call.

## Measured per-run volumes (representative single-asset run r_48c83f28a2 / t_2aed84a..., Jul 14 02:45)

- trace_<tid>.jsonl: 695 events, 1,051,982 bytes — 636 db events (548KB), 12 llm events (471KB = 39KB avg),
  27 stage, 19 legacy, 1 trace.
- ai_<rid>.jsonl: 12 lines, 630,044 bytes (avg 52.5KB/LLM call — full request+response bodies).
- sql_<rid>.jsonl: 684 lines, 364,706 bytes.
- pipeline_<rid>.jsonl: 19 lines; failures: 4 lines; response_<rid>.json: 90KB.
- TOTAL synchronous jsonl bytes ~2.1MB per ordinary single-asset run, ~1,400 open/close cycles (636 db events x2
  files + misc), all json.dumps'd on hot-path threads.

Worst cases on disk (multi-asset compares / sweeps):
- trace_t_ed7e6dbe....jsonl: 38.2MB, 51,372 events (one execution!).
- ai_r_92a2bfb0ae.jsonl: 53.4MB, 1,176 LLM calls.
- sql_r_cad41b51b5.jsonl: 16.1MB, 31,938 queries.
- outputs/logs totals: ai_* = 710MB, trace_* = 610MB, sql_* = 239MB -> 1.6GB (3,349 files, dir dirent 200KB).

## Admin "notes MAX 28.6s" root cause (d)

admin/latency.py computes stage duration as ts-gap between consecutive pipeline_<rid>.jsonl lines. The "notes"
line is emitted by obs/notes.py record() at run/harness.py:384 — the PREVIOUS line is "reflect" (inside
_reflect_loop). Between them runs validate.build.payload_final (harness.py:366-371) which re-reads
card_payloads_for(cid, page_key) per final card from :5432. So the 28.6s max attributed to "notes" is NOT the
notes json write — it is the payload_final re-score (per-card cmd_catalog reads) + any stall. The notes write
itself is a small json.dump. avg 87ms ~= payload_final on a warm run. (Belongs to the validate lens but recorded
here because admin mislabels it as notes.)

(micro-benchmarks below)

## Micro-benchmarks (python3, this box: 64-core, Samsung 990 PRO NVMe, ext4; sinks redirected to scratchpad,
## pg sink stubbed to a queue — no DB writes; app_config loaded REAL from :5432, 371 keys, 11.5ms first load)

Per-DB-query telemetry stack (sql_trace.record = db_tap + trace-jsonl + sql_-jsonl):
- pure fn, everything off:                        1.1 us
- event build + sink gates only (obs.enabled off): 6.1 us
- + pg-sink enqueue (jsonl off):                   9.1 us
- + trace_<tid>.jsonl write (sql_ leg off):       23.8 us
- FULL path (both jsonl legs):                    36.6 us uncontended
- FULL path, 8 threads on one trace (real fan-out shape): 75.2 us/event  (2x — global locks: trace lock taken
  TWICE per event (attribute_db + next_seq) + sink_jsonl module-global _LOCK + sql_ file append)
- sql_ jsonl leg alone (no trace active):         12.9 us

Per-LLM-call telemetry:
- llm_tap.record (57KB system + 8KB user + resp, bounded, jsonl+pg): 158.7 us
- ai_log urllib tap body (json.loads 66.6KB request + loads response + dumps + append): 189.7 us
- obs.stage.stage() (stderr + pipeline_ jsonl + legacy event via bus + failure scan): 39.0 us

Replay capture (replay/hooks.py wraps EVERY q()/neuract read/LLM call/frame probe/exec card):
- coding.encode 2,000 rows x 8 cols (datetime+Decimal): 6.20 ms/query  (= 0.39 us/cell)
- coding.encode 50 rows x 8 cols: 0.13 ms
- content_key sha256 over 57KB prompt: 0.15 ms; over a SQL string: ~0 us
- coding.encode 90KB response dict: 1.58 ms
- write_bundle equivalent (665 events, 1.95MB + response): 13.5 ms — SYNCHRONOUS at the response boundary
  (host/server.py:191 run_traced(... captured(...)): store.write_bundle runs BEFORE the HTTP body is sent)

Postgres sink reference (obs_stage_events INSERT, rolled back): 0.05 ms/row single, 0.043 ms/row executemany —
and the sink is queue+batch+daemon-thread, so pg latency is OFF the hot path (drop-on-overflow, 30s backoff,
own connection). obs table growth: obs_db_queries 311,777 rows / 133MB; obs_llm_calls 3,442 rows / 56MB;
obs_stage_events 15k / 9MB; obs_traces 574 / 472KB.

## Per-run totals (arithmetic)

TYPICAL single-asset run (r_48c83f28a2: 700 queries / 5,778 rows / 12 LLM calls / 695 obs events / 665 replay events):
- db-query telemetry: 700 x 36.6us                  = 25.6 ms
- LLM telemetry: 12 x (159 + 190)us + writes        =  ~6 ms
- replay row encode: 5,778 rows x 8 x 0.39us        =  ~18 ms
- replay bundle write (2.2MB) at response boundary  = 13.5 ms
- response_<rid>.json (90KB) + notes + stage lines  =  ~4 ms
TOTAL ~ 67 ms = 0.18% of the 37.8s p50. HONEST HEADLINE: obs/logging is NOT where the p50 lives.

5-8-card panel page (brief: ~1,750 queries/run): 1,750 x 36.6us = 64ms + replay encode ~50ms + bundle ~20ms
+ llm ~20 x 0.5ms = 10ms → ~150 ms total. Recoverable: ~120 ms.

WORST multi-asset compare (RESPONSE_MULTI 410-441s; measured artifacts: 31,938 queries / 450,158 rows,
1,176 LLM calls / 53.4MB ai_ file, 51,372 obs events / 38.2MB trace file, 5,609 failures records):
- obs events: 51,372 x 75us (contended)             = 3.9 s
- replay row encode: 450k x 8 x 0.39us              = 1.4 s
- LLM body capture x3 sync copies: 1,176 x ~0.5ms   = 0.6 s
- failures appends: 5,609 x ~15us                   = 0.1 s
- bundle + events accumulation + bundle write       = 0.1-0.3 s
TOTAL ~ 5-6 s = ~1.3% of the 441s worst runs. Plus RAM: Recorder.events holds the encoded rows + FULL LLM
prompt/response bodies (unbounded — hooks.llm records verbatim system/user, NOT redact.bound) in memory for
the whole request → ~100-150MB extra heap on the worst runs → GC pressure on all threads (unquantified).

## (d) "notes MAX 28.6s" ROOT CAUSE — admin mis-attribution, not an obs write cost

Verified against pipeline_r_bb525a5212.jsonl / r_f3b19721cb / r_44796d791a: every notes-gap > 5s (n=5, 17.2-28.6s)
follows the sequence `reflect(reroute_on=hard_failure) → validate → 1a(reroute=True) → [GAP] → notes`. The gap is
the reflect loop's SECOND Layer-2 emit pass: run/harness.py _reflect_loop mints a loopN run_id
(ai_log.set_run_id(rid) at harness.py:116), so the re-pass's L2.card/layer2 stage lines land in
pipeline_<rid>loopN.jsonl — a DIFFERENT file. admin/latency.py computes stage duration as the ts-gap between
consecutive lines in ONE file, so the whole second emit wave (~1 full L2 pass, 17-29s) lands on the "notes" line.
obs/notes.py record() itself is a tiny json.dump (~us). FIX: emit a `reflect_pass` stage line into the BASE rid
file when the re-emit starts (1 line), or teach admin/latency.py to join loopN files. Metric correctness only —
but it currently HIDES the true cost of hard_failure re-routes (a full second L2 wave) under "notes".

## (f) degrade.note / failures channel frequency

ems_exec/executor/degrade.py note() → obs/errfmt.record_exc → obs/failures.record = one open/append/close +
json.dumps per record (~13-15us). Typical runs: 4 records. Validation-heavy runs: failures_r_99879f110d.jsonl =
5,609 records (no_reading 3,977, unbound_by_emit 921, unstripped_seed 667) ≈ 0.08s. Not material for latency;
the per-record open/close pattern folds into the buffered-sink rework below.

## (g) Python logging / journald

No per-query stdout/journal logging (db_client prints on ERROR only; sink_console SKIPS kind=db/legacy events).
stage() prints ~20 lines/run, sink_console ~40/run, flush=True each — v48-host user unit journals stderr
(PYTHONUNBUFFERED=1): 342 journal lines / 10 min around a live run = negligible. journald is not a factor.

## Fail-open confirmation

Every obs path is try/except-wrapped and never raises into the pipeline: bus.emit catches per sink; sink_pg is a
bounded queue that DROPS on overflow and backs off 30s on DB failure (jsonl/console still get events); jsonl/
failures/notes/sql_trace/ai_log all swallow exceptions; span records + re-raises the stage's own exception.
Proposals below keep that contract (telemetry-only changes; no AI decision touched; single-asset serve path
byte-identical — no response fields involved).

## FULL findings list (ranked; #1-#12 material, rest recorded for completeness)

1. REPLAY-SYNC — replay bundle persisted synchronously at the response boundary (replay/capture.py:81
   store.write_bundle inside captured(), which runs inside run_traced BEFORE host/server._send). Measured 13.5ms
   typical (2.2MB), worst bundles 4.7MB on disk (~30ms) + the events accumulation cost. Move write_bundle to a
   daemon writer thread (bundle is self-contained; manifest already carries status/error). Saving: 13-30ms every
   run, all scenarios, zero behavior risk (fail-open already tolerates a missed bundle).

2. REPLAY-ENCODE — replay/hooks.py db_q/db_rows call coding.encode(rows) on EVERY query's FULL result set on the
   querying thread (0.39us/cell): typical 18ms, worst multi-asset 450k rows = ~1.4s + ~50-100MB heap. Add
   replay.max_rows_per_event knob (e.g. 500; beyond → {digest, n_rows, "tape_partial": true} so replays of huge
   reads honestly TapeMiss to live) + replay.capture mode knob (on|errors_only|sample_1_in_N). Saving: ~1.4s on
   worst RESPONSE_MULTI, ~50ms on 5-8-card panel pages; RAM back.

3. DB-EVENT-DOUBLE-WRITE — every query is written to TWO jsonl files synchronously: trace_<tid>.jsonl (db_tap →
   sink_jsonl, ~860B/event) AND sql_<rid>.jsonl (sql_trace leg, ~530B/line) — obs_db_queries (pg) carries the
   same record a third time. 36.6us vs 23.8us with the sql_ leg off = 12.9us/query saved by folding the sql_ leg
   into the canonical event (tools/payload_diff + admin/sql_report read sql_<rid>.jsonl — they can read
   trace jsonl kind=db / obs_db_queries instead; run_id is already on the event). Saving: 0.4s worst runs,
   23ms panel page, disk -239MB.

4. JSONL-SINK-BUFFERING — sink_jsonl opens/closes trace_<tid>.jsonl per event under a module-global lock
   (open+write+close + os.makedirs each time), and failures.record/stage/sql_trace repeat the same pattern.
   Mirror sink_pg: bounded queue + daemon writer holding an open FD per active trace (close on trace end / idle).
   Removes ~15-20us/event from hot threads and the cross-thread serialization. Saving: ~1-2s on 51k-event worst
   runs, ~25ms panel page. Keep drop-on-overflow + fail-open.

5. DB-EVENT-SAMPLING — obs.db.min_ms knob: record full kind=db events only for queries >= N ms (e.g. 20-50ms) or
   errors; per-stage span rollups (n_queries/rows_returned) already preserve the counts for free. At median 4ms
   the executor's chatty small reads generate 90%+ of the 51k events. Cuts event volume ~10-20x → worst-run obs
   cost from ~3.9s to ~0.4s; also shrinks obs_db_queries growth (311k rows/133MB). Inspector keeps slow-query
   forensics (the ones that matter).

6. LLM-QUAD-CAPTURE — each LLM call's full bodies are captured FOUR times: (a) ai_log urllib monkeypatch
   (ai_<rid>.jsonl, 52.5KB avg, 190us + write), (b) llm_tap → trace jsonl (39KB avg, 159us), (c) replay hooks.llm
   event (UNBOUNDED verbatim system/user in RAM then bundle), (d) obs_llm_calls via pg sink (async). Worst run:
   1,176 calls → 53.4MB + ~40MB + ~50MB sync writes ≈ 0.6s + heap. Proposal: default V48_AI_LOG=0 (llm_tap+pg
   supersede it — same request/response + usage + params + decision; payload_diff's ai leg reads obs_llm_calls),
   and redact.bound the replay llm event's system/user to obs.llm.max_prompt_bytes (tape lookup is by
   content_key hash, which is computed BEFORE bounding — replay fidelity unaffected for the tape, and value/
   response stays full). Saving: ~0.6s worst runs, ~5ms typical; disk -710MB/period.

7. TRACE-LOCK-DOUBLE-ACQUIRE — every event takes the ONE shared trace lock twice (span.attribute_db, then
   event._base → trace.next_seq). 8-thread contention doubles per-event cost (75 vs 37us). Merge into one
   acquisition (attribute returns seq) or use itertools.count (GIL-atomic) for seq. Saving: ~0.5-1s on 51k-event
   runs; simplification elsewhere negligible.

8. NOTES-28.6s-MISATTRIBUTION — (see root cause above). Emit `reflect_pass` stage line in base rid file (or make
   admin join loopN). Zero latency saving; makes ~17-29s of hard_failure re-route L2 waves visible to the right
   owner (reflect/L2 lens). Metric integrity for every future latency audit.

9. AI_LOG-TAP-SCOPE — obs/ai_log.py monkeypatches urllib.request.urlopen GLOBALLY and string-matches ':8200' on
   EVERY urlopen in the process (incl. Storybook fetches, neuract HTTP if any). The non-matching path costs ~1us
   (fine), but the matching path does resp.read() + double json parse + dump inline in the LLM thread. Subsumed
   by #6 (default off); if kept, write via the sink_pg-style queue.

10. INSPECTOR-IN-HOST-PROCESS — /api/inspector (host/inspector_api.py) runs in the SAME process/GIL as live runs;
    its jsonl fallback parses trace files up to 38MB (json.loads per line ~ several SECONDS of pure GIL time)
    while pipeline threads run. Off the request path but ON the process. Move heavy inspector reads to the admin
    :8790 process (already file-backed) or a subprocess. Conditional saving: avoids multi-second GIL stalls of
    live runs during pg outages + inspector use.

11. OBS-PG-PURGE — daily DELETE over obs_* on the writer thread (sink_pg._purge). 311k-row deletes at 30-day
    retention are fine today; as volume grows the delete stalls the writer (queue backs up → drops, no pipeline
    impact — confirmed fail-open). Note only: switch to batched deletes if obs.db events stay unsampled.

12. RESPONSE_JSON + notes + pipeline_ files: response_<rid>.json 90KB (~2ms), notes json (~us), pipeline_ 19
    lines — all fine as-is once #4's buffered writer exists to fold them into.

DEAD ENDS checked (no time lost there):
- sink_pg is already buffered/threaded/batched with own connection; INSERT cost 0.04-0.05ms/row off-path.
- app_config cfg() is process-cached after one 11.5ms load — the 4 sink-gate lookups per event are dict gets.
- No fsync/flush-per-record anywhere in obs/ (page-cache appends on NVMe).
- sink_console skips kind=db/legacy; journald volume trivial (342 lines/10min).
- redact.bound caps stage/llm event fields (16KB/32KB) — events can't balloon (except replay's verbatim llm leg, #6).
- No per-card file writes in layer2/ or ems_exec/executor (grep clean).
- obs taps never touch prompt CONTENT → prefix-cache 0.0% is NOT caused by the obs layer (prompt-construction lens).
- host stderr → user journald via systemd unit; PYTHONUNBUFFERED=1 makes prints line-buffered syscalls, volume tiny.

KILL-SWITCH FLOOR (exists today, DB-tunable): obs.enabled=off drops per-query cost 36.6→6.1us + V48_SQL_TRACE=0
removes the sql_ leg (12.9us) + replay.capture=off removes encode+bundle. Full-off worst-run recovery ~5-6s,
panel page ~140ms — at the price of ALL forensics; the sampled/buffered proposals above recover ~90% of that
while keeping the inspector story intact.
