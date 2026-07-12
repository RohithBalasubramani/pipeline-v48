# Fixes — group `obs` (2026-07-12)

Owner files: `obs/ai_log.py`, `obs/notes.py`, `obs/retention.py` (NEW), `obs/sink_pg.py` (optional minimal).
Source findings: `docs/audit_prodready_20260712/obs-replay.md` (OBS-1, OBS-2/H15, OBS-4, OBS-5).

Status: COMPLETE — all 4 fixes applied, gates green. NOTE: :8770 host must restart to adopt (owner-scheduled,
per the audit's orchestrator note — no restart performed here).

## 1. OBS-1 (HIGH) — contextvar-backed run-id attribution — `obs/ai_log.py`

**What:** replaced the module-global `_RUN_ID` with `_RUN_ID_VAR` (a `contextvars.ContextVar`) plus a
`_RUN_ID_LEGACY` process-global fallback. `set_run_id(rid)` (public name kept — zero caller churn: host/server.py:341,
run/harness.py:116/232, tests/conftest.py:19, tests/test_foundations.py:43) now binds the contextvar for THIS context
AND refreshes the legacy global. New accessor `run_id()` resolves: context binding → `obs.trace.current_run_id()`
(the trace's last-bound run id) → legacy global → `"default"`.

**Consumer repoint WITHOUT editing consumer files** (they are other groups' property): every external reader uses
`getattr(ai_log, "_RUN_ID", "default")` — obs/sql_trace.py:28, llm/client.py:74, config/reason_templates.py:41,
layer1a/story_builder.py:47. A module-level `__getattr__` (PEP 562) now answers `_RUN_ID` with `run_id()`, so ALL
of them resolve through the contextvar with zero call-site edits. A direct `setattr` (tests/test_failures_fanout.py's
`monkeypatch.setattr(ai_log, "_RUN_ID", rid)`) creates a real module attribute that shadows the hook — test
semantics preserved (verified: both fanout tests pass; monkeypatch teardown leaves the pre-test value, byte-parity
with the old global's state in a test process).

**Why:** two concurrent /api/run requests cross-labeled ai_/sql_/failures_ jsonl records (the exact H14 failure);
the obs_* pg leg was already contextvar-correct, the jsonl legs (admin console :8790 + tools/payload_diff sources)
were not. Internal `_logged` reads switched to one `rid = run_id()` resolve so the record body and the `ai_<rid>.jsonl`
filename always agree.

**Healthy-path parity:** single-threaded run → `set_run_id` sets both homes, `run_id()` returns the same value the
global did. Plain threads (fresh context, no trace) fall back to the legacy global — identical to pre-fix behavior.

**Evidence:** scripted behavior check (7 assertions): default → set → two concurrent contexts isolated (r_a/r_b, no
cross-label, parent context untouched) → plain-thread legacy fallback → trace-bound fallback (`r_traced`) →
setattr-shadow/delattr-restore → `set_context_run_id` context-only (legacy untouched). All pass.

## 2. OBS-4 (MEDIUM) — fail-open notes writer — `obs/notes.py`

**What:** wrapped `record()`'s body in try/except (returns `notes` unchanged on any failure), mirroring the
obs/stage.py fail-open style. Docstring states the constraint (run/harness.py:305/:382 call it bare at the END of a
successful run).

**Why:** an unwritable outputs/ (disk full — plausible given OBS-2's unbounded 1.2 GB) made `record_notes` raise
into `run_pipeline` → handle_run 500 on an otherwise-successful run. Every sibling writer was already guarded.

**Evidence:** behavior check — `_DIR` pointed under a regular file (makedirs must fail): `record()` returned the
notes dict, no raise; empty-notes no-op unchanged. tests green (see gates).

## 3. OBS-2 / H15 (HIGH) — NEW `obs/retention.py` — age-based file-telemetry prune

**What:** new single-purpose module. `prune()` deletes, by mtime, per-run telemetry older than the window:
- `outputs/logs/`: ONLY the families `ai_*.jsonl, sql_*.jsonl, pipeline_*.jsonl, failures_*.jsonl, trace_*.jsonl,
  response_*.json` (host.log / cert artifacts / anything else untouched).
- `outputs/traces/`: ONLY `t_*` replay-bundle dirs (age-based; complements replay/store._prune's keep-newest-N).

`ensure_started()` spawns ONE named daemon thread (`obs-file-retention`): prune at start + every 6 h; idempotent
(lock + flag); never raises. Fail-open everywhere: config/DB error → window 0 → prune NOTHING; per-entry OSError
never stops the sweep. Deliberately NOT self-starting on import and NOT wired into host/server.py (that file is
another agent's — wiring `from obs import retention; retention.ensure_started()` at host boot is the follow-up).

**KNOB (for the docs/db group to seed — db/ is not this group's to edit):**
`cmd_catalog.app_config`: key=`obs.file_retention_days`, data_type=`int`, value=`14`
(code default 14 when the row is absent; `0`/negative = keep forever; read lazily via `config.app_config.cfg`).

**Why:** outputs/logs grew 485 MB → 1.2 GB / 865 → 1417 files in one day with NO retention; only the pg rows
(sink_pg._purge, obs.retention_days) and replay bundle COUNT were bounded. trace_<tid>.jsonl (sink_jsonl) is a new
unbounded writer as of today.

**Evidence:** sandboxed prune test — 6 old family files + 1 old `t_` bundle removed (returned 7); fresh files,
non-family old files (`host.log`, `keepme_old.txt`, `cert_results.jsonl`), fresh bundle, and an old NON-`t_` parked
dir all untouched; window 0 prunes nothing; `ensure_started()` twice → exactly one daemon thread. A real-knob pass
also ran incidentally in the test process: verified zero deletions (oldest real telemetry = Jul 6, inside 14 d).

## 4. OBS-5 (LOW) — sink self-connect attribution — `obs/sink_pg.py`

**What:** 5 guarded lines at the top of `_writer_loop()` (runs once in the writer thread): pin THIS thread's context
run id to `obs_sink` via the new `ai_log.set_context_run_id` (context-only — the process-global fallback is never
mutated). The sink's own `<pg_connect>` sql_trace legs now land in `sql_obs_sink.jsonl`.

**Why:** verified NOT fully harmless after fix 1 — the writer thread has no context binding and no trace, so it fell
through to the legacy global = whatever live run last called `set_run_id`, i.e. still polluting a real run's
sql_<rid>.jsonl. The pin is a redirect-to-dedicated-bucket rather than a skip (a true skip would require editing
data/db_client.py or obs/sql_trace.py — not this group's files); `sql_obs_sink.jsonl` is itself bounded by the new
retention family match (`sql_*.jsonl`).

## Gates

- `python3 -m py_compile obs/ai_log.py obs/notes.py obs/retention.py obs/sink_pg.py` — OK
- `python3 -c "import obs.ai_log, obs.notes, obs.retention, obs.sink_pg"` — OK
- `pytest tests/test_obs_trace.py tests/test_failures_fanout.py tests/test_foundations.py -q` (offline) —
  **25 passed, 2 deselected** (the live-marked ones)
- `pytest tests/test_replay_engine.py -q` — **21 passed** (sink/trace surface unchanged)
- Scripted behavior checks for OBS-1/OBS-2/OBS-4 as described above — all pass.

## Follow-ups for other owners

- host/server.py owner: call `obs.retention.ensure_started()` at boot (one line; module is inert until then).
- docs/db group: seed the `obs.file_retention_days` app_config row (spec above).
- Owner scheduling: :8770 restart required to adopt OBS-1/OBS-5 (and retention once wired).
- NOT touched (outside scope/ownership): the urlopen-monkeypatch retirement half of OBS-2 (needs llm/client.py +
  consumer migration decision), OBS-3 (db/obs_schema.sql indexes), OBS-6 (obs/event.py last-writer-wins run_id).
