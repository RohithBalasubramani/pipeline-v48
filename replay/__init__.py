"""replay/ — the V48 replay engine: full-fidelity per-request capture + deterministic re-execution + side-by-side
diff. Rides the obs trace identity (obs/trace.py trace_id); stores what telemetry cannot (unredacted prompts, actual
SQL rows, resolved config) under outputs/traces/<trace_id>/. See docs/REPLAY_ENGINE_DESIGN.md.

One single-purpose file per concern [atomic-structure]:
  ids.py       trace-ref resolution (trace_id | run_id | 'last' → bundle dir)
  coding.py    typed JSON encode/decode (datetime/date/Decimal round-trip for injected rows)
  store.py     bundle dir layout: write/load manifest, request, snapshots, events, artifacts; list/prune
  recorder.py  the per-request Recorder (thread-safe buffer; attached to the active obs trace)
  hooks.py     THE choke-point API — record + optional tape-inject; fail-open, inert outside a session
  capture.py   captured(kind, request, fn): open session, snapshot cfg/env, run, persist bundle
  clock.py     now(tz): frozen to the original wall-clock during replay, datetime.now otherwise
  tape.py      recorded events → keyed queues; exact→fuzzy→live lookup with first-class miss records
  isolate.py   redirect legacy writers into the replay bundle (originals never clobbered)
  engine.py    replay(trace_ref, mode): env+cfg pin → clock freeze → tape → re-run handle_run → new bundle
  compare.py   original vs replay bundles → sectioned comparison dict (reuses tools/payload_diff)
  report.py    comparison → self-contained side-by-side HTML + terminal summary
  cli.py       python3 -m replay.cli  list | show | replay | compare
"""
