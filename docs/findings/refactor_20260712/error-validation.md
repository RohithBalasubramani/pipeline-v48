# Refactor audit — ERROR HANDLING & VALIDATION (2026-07-12)

Scope: pipeline_v48 (archive/, outputs/, .claude/, artifacts skipped). Dimension: error handling & validation.
House rules honored: atomic-structure (proposals = new single-purpose files), AI-first, per-leaf degradation
(nothing below gates a card), DB-driven config, DB-driven dispatch (grepped strings, not just imports).

---

## A. Maps (context for the findings)

### A.1 What obs/ provides, and who bypasses it

| obs piece | surface | actual adopters |
|---|---|---|
| `obs/failures.py` | `record(stage, reason, card_id, group_id, detail, run_id)` → `outputs/logs/failures_<run_id>.jsonl` | `llm/client.py:_record`, `layer1a/story_builder.py:41`, `layer1b/build.py:32` — **3 call sites total** |
| `obs/stage.py` | `stage(run_id, name, **fields)` (+ `_failure_signal`) | `run/harness.py`, `run/layer2_all.py`, `run/reconcile_granularity.py`, `host/exec_cards.py` |
| `obs/trace.py` | `trace_warn`, `set_degradation`, spans | **unused by ems_exec / layer2 / host** (grep: no non-def hits) |
| `obs/ai_log.py` | urlopen monkeypatch → per-run LLM jsonl | llm/client (via import), ems_exec/renderers/_insight (side-effect import) |

Bypass channels found: `sys.stderr.write` (data/equipment/db.py:41, edges.py:70/94, host/multi_asset.py:50),
`traceback.print_exc()` (host/server.py:342), and ~96 fully-silent `except Exception: pass` blocks
(19 in `ems_exec/executor/fill.py` alone). The executor — the subsystem with the most failure modes — records
**zero** failures through obs.

### A.2 Validation pipeline end-to-end (who checks what, when)

1. **Pre-L2, one pass** — `validate/build.py:run_validate` (data availability per column over probe rows →
   `validate/data_validate.py` + `validate/null_gate.py` policy; payload supply-vs-demand over harvested defaults
   → `validate/payload_validate.py` with `validate/leaf_classify.py`; topology feasibility `_expected_gaps`).
   Verdicts are folded INTO the 1b basket (`_fold_into_basket`) so L2 consumes one truth.
2. **Emission conformance (post-emit, pre-fill)** — `layer2/gates.py` (`gate_exact_metadata` byte-identity +
   chrome, `gate_data_instructions` real-column binding + quantity gates, `gate_roster`) and
   `layer2/resolve/column_override.py` (non-gating repairs); `grounding/swap_settle.py` settles swap verdicts;
   `grounding/default_assemble.py` strips seeds to placeholders.
3. **Post-fill fabrication classes** — `ems_exec/executor/fab_guards.py` (epoch-leak / null-column-as-reading /
   no-source / seed-leak), slot-name-independent, whole-payload.
4. **Post-fill verdict telemetry** — `validate/render_verdict.py` (render|partial|honest_blank; telemetry only).

Verdict: the four stages are **intentionally distinct concerns** (probe vs emission vs filled payload) — not a
consolidation target. The real duplication is at the **predicate/vocab level below the stages** (findings 5, 6, 9):
the same micro-invariants ("this leaf is blank", "this key is a time axis", "this value is chrome") are
re-implemented with divergent hardcoded fallbacks.

### A.3 LLM parse implementations (distinct JSON-extract-and-repair paths)

1. `llm/client.py:171-196` — think-strip (`re.sub(r"<think>.*?</think>")` — requires an *opening* tag), brace
   extract `re.search(r"\{.*\}", DOTALL)`, `json.loads`, classified kinds, bounded repair-retry with error appended.
2. `ems_exec/renderers/_insight.py:98-132` — own `_strip_think` (handles a **dangling `</think>` with no opener**,
   which client.py's regex does not), bare `json.loads`, `except Exception: return None`, own content-hash cache.
   Same :8200 endpoint as client.py — bypasses classification/telemetry/no_retry/prompt-budget entirely.
3. `copilot/` (:8201, decoupled by design) — `llm.chat` returns raw text; **each caller** re-implements
   try/`json.loads`/swallow: generate.py:58, aliases.py:104, starters.py:64, build/metrics.py:33.

layer1a/parse/* and knowledge/ do NOT parse raw LLM text (they consume `call_qwen` dicts) — good.

### A.4 Retry/timeout policy locations

- `llm/client.py` — per-stage DB timeouts, parse-retry honoring `llm.no_retry_kinds` (default `timeout,truncated`),
  prompt-budget preflight. Transport failures never retried *inside* the client.
- `layer2/emit/emit.py:210-218` — outer transport retry (`llm.transport_retry`) that **checks the marker kind
  against the same `llm.no_retry_kinds` row**. Policy-correct.
- `layer1b/guardrail/retry_one.py` — blind falsy-retry. **Does not know failure kinds** → Finding 1.
- `config/ems_backend.py` — EMS fetch retry/backoff knobs (separate concern, fine).

---

## B. Findings

### F1. `retry_once` retries deterministic LLM failures (timeout/truncated/over_budget), violating the no-retry rule
- **File**: `layer1b/guardrail/retry_one.py:13-17` (call sites `layer1b/resolve/asset_resolve.py:157`,
  `layer1b/basket/column_basket.py:68`)
- **Evidence**:
  ```python
  res = call() or {}
  if res:
      return res, False
  res = call() or {}
  ```
  Both call sites use `call_qwen(..., on_error="empty")` (default), so a `timeout` comes back as `{}` —
  indistinguishable from transient transport — and IS re-sent, doubling the wall-clock hang (the exact
  anti-pattern fixed in layer2 emit: "never retry a deterministic LLM failure — doubles the hang", and the exact
  check `layer2/emit/emit.py:215` performs via `_llm_error not in no_retry`). `over_budget` (also deterministic —
  same prompt, same estimate) is likewise retried.
- **Refactor**: extract emit.py's policy loop into ONE single-purpose `llm/transient_retry.py`
  (`retry_transient(fn)` — call with `on_error="marker"`, retry only when `_llm_error` kind is absent from
  `cfg("llm.no_retry_kinds")`, bounded by `cfg("llm.transport_retry",1)`); adopt in layer1b (both sites) and
  layer2/emit; delete `retry_one.py`. `llm_failed` = `bool(res.get("_llm_error"))` keeps the callers' contract.
- **Risk**: low (failure path only; healthy path byte-identical). **Behavior-preserving**: NO (by policy intent:
  a timed-out asset_resolve/basket call stops being retried).
- **Tests guarding**: `tests/test_stage_telemetry_item15.py` (retry_once), `tests/test_llm_truncation_budget.py`
  (no_retry kinds), `tests/test_layer1b_basket_logged_floor.py`.

### F2. `config/app_config._load` permanently caches `{}` on a transient DB error — the already-diagnosed cache-poison class
- **File**: `config/app_config.py:18-25`
- **Evidence**:
  ```python
  @lru_cache(maxsize=1)
  def _load():
      try:
          return {r[0]: (r[1], r[2]) for r in q(CMD_CATALOG, "SELECT key, value, data_type FROM app_config")}
      except Exception:
          return {}
  ```
  One :5432 blip at first `cfg()` call in the long-running host server ⇒ EVERY DB knob (llm timeouts,
  `llm.no_retry_kinds`, fab_guards valves, gates chrome vocab, null-gate mode, multi_asset.enabled…) silently
  degrades to code defaults for the whole process life. This is byte-for-byte the defect class fixed on 2026-07-09
  for panel_members ("never-cache-empty + TTL", `data/ttl_cache.py`), and `copilot/server.py:41-45` already
  documents the same never-cache-error rule for its suggest cache. app_config is the LAST poisonable cache.
- **Refactor**: replace `lru_cache` with the established pattern: a module-level dict that stores **only successful
  reads** (on error return `{}` WITHOUT caching, so the next `cfg()` re-probes; optionally a short TTL backoff via
  `data/ttl_cache.TTLCache` to avoid a query per cfg() during an outage). `reload()` keeps its contract.
- **Risk**: medium (config appearing mid-process after an outage changes knob values mid-run — that is the intended
  self-heal, but callers that cached `cfg()` results at import keep the stale default → see F9).
- **Behavior-preserving**: NO in the failure mode (that is the point); healthy path identical.
- **Tests guarding**: `tests/test_config_cast_integrity.py`; cfg consumers across
  `tests/test_layer2_quantity_const_gates.py`, `tests/test_validate_null_gate.py`, many others.

### F3. The executor's pass pipeline swallows every exception with zero telemetry (19 silent `except Exception: pass` in fill.py; serve catch-all too)
- **File**: `ems_exec/executor/fill.py` (e.g. 240, 393-394, 446-447, 456-457, 465-466, 478-479, 490-491, 512-513,
  530-531, 539-540, 553-554, 567-568, 572…), `ems_exec/serve/run.py:100-110`
- **Evidence**:
  ```python
  out = _yscale.apply(out, shape_ref=shape_ref)
  except Exception:
      pass
  ```
  (repeated for roster, roster_gaps, norm_series, xaxis, view_select, display, freshness, trend_badge…) and
  `run.py:100` `except Exception:` → silent re-fill with `{"fields": []}`. Per-leaf degradation is correct
  (a pass failure must not crash the card — house rule 3), but a **systemically broken pass is invisible**: if
  `yscale.apply` regresses and throws on every card, all charts silently lose y-scales and nothing reaches
  obs/failures — the same "silent fail-open hides an outage" defect llm/client.py was explicitly hardened against
  (its docstring, lines 4-5). obs/trace.trace_warn / set_degradation exist for exactly this and have zero adopters.
- **Refactor**: one single-purpose `ems_exec/executor/degrade.py` with
  `run_pass(name, fn, fallback, *args, **kw)` — try/except that returns `fallback` AND calls
  `obs.failures.record("ems_exec." + name, "pass_exception", card_id=ctx.get("card_id"), detail=fmt_exc(e))`
  (never raises, mirroring llm/client `_record`). Mechanically replace the try/except blocks in fill.py and
  serve/run.py. Output payloads byte-identical; only telemetry added.
- **Risk**: low. **Behavior-preserving**: YES.
- **Tests guarding**: `tests/test_fill_reason_not_logged.py`, `tests/test_post_fill_rescue_overreach.py`,
  `tests/test_seam3_seed_and_period.py`, `tests/test_residual3_fixes.py`, `tests/test_fab_guards.py`.

### F4. Three failure-logging channels + the `f"{type(e).__name__}: {e}"` string duplicated ~15×
- **File**: `host/server.py:343` (representative; also 228, 294), `host/exec_cards.py:188-189`,
  `run/harness.py:45,85,111,176,314`, `run/layer2_all.py:18,64`, `run/reconcile_granularity.py:31,44`,
  `data/equipment/db.py:41`, `data/equipment/edges.py:70,94`, `host/multi_asset.py:50`
- **Evidence**: `return self._send(500, {"ok": False, "error": f"{type(e).__name__}: {e}"})` — the identical
  format string hand-rolled at 15+ sites; data/equipment logs failures to `sys.stderr.write(...)` and
  host/multi_asset.py:50 to stderr too, so those failures never land in `failures_<run_id>.jsonl` where every
  runbook looks (memory: sweeps mine outputs/logs).
- **Refactor**: add `obs/errfmt.py` with `fmt_exc(e) -> "TypeName: msg"` and `record_exc(stage, e, **ids)`
  (delegates to `obs.failures.record`, never raises). Replace the stderr writes in data/equipment and
  host/multi_asset with `record_exc` + keep the stderr line if operators rely on it (additive first).
- **Risk**: low. **Behavior-preserving**: YES (string output identical; telemetry added).
- **Tests guarding**: `tests/test_stage_telemetry_item15.py` (stage telemetry), `tests/test_equipment_3d.py` /
  `tests/test_equipment_ai_context.py` (data/equipment fail-open contract).

### F5. The "blank leaf" predicate is re-implemented 8× with drifting semantics
- **Files**: `ems_exec/executor/gaps.py:28-35` (`_blank_val`, list-aware), `ems_exec/executor/roster_gaps.py:38-39`
  (`_blank`, adds `== []`), `ems_exec/executor/roster.py:242-259` (`_const_is_blank` + inline `v not in (None,"","—")`),
  `ems_exec/executor/scalar_mean_fill.py:24-25`, `ems_exec/executor/scalar_tile_fill.py:30-36` (adds 0.0
  placeholder), `ems_exec/executor/xaxis.py:75-76` (string-list variant), `ems_exec/executor/roster_modes_sankey.py:36-42`
  (DB-knob sentinel list), `host/enrich.py:83` (`in (None, "", "—")`)
- **Evidence**:
  ```python
  # gaps.py          return v is None or v == "—" or v == ""
  # roster_gaps.py   return v is None or v == "—" or v == "" or v == []
  # scalar_tile_fill if v is None or v == "—" or v == "": return True  (+ placeholder 0.0)
  ```
  The em-dash sentinel (`METRIC_PLACEHOLDER`) is a cross-layer contract with the FE; today changing it means
  editing 8 files, and each copy already disagrees on lists/`[]`/0.0. render_verdict and fab_guards each add their
  own blank notions on top.
- **Refactor**: one `ems_exec/executor/blank.py`: `DASH = "—"`; `is_blank_scalar(v)`;
  `is_blank(v, *, empty_list=False, all_none_list=False)`; keep the two intentional extensions
  (tile-placeholder-0.0, sankey DB-sentinel list) in their owning modules but built ON the shared scalar predicate.
  `trend_badge.DASH` / `freshness.DASH` import from it. Pure mechanical substitution, truth tables preserved
  per site.
- **Risk**: low. **Behavior-preserving**: YES.
- **Tests guarding**: `tests/test_render_verdict.py`, `tests/test_fab_guards.py`, `tests/test_layer2_roster.py`,
  `tests/test_residual3_fixes.py`, `tests/test_enrich_reason_per_leaf.py`.

### F6. Four divergent "time-axis key" predicates around one DB vocab, each with its own hardcoded fallback set
- **Files**: `ems_exec/executor/series_fill.py:100-115` (`_is_time_field`: kind='time' ∨ column∈{ts,time,timestamp,
  timestamp_utc} ∨ vocab `time_axis_keys`), `ems_exec/executor/fab_guards.py:79-123` (vocab ∪ literal token tuple
  `"axisstart","axisend","axisstartms",...`), `layer2/emit/slot_catalog.py:218-228` (vocab ∪ `"timestamp" in k` ∨
  `endswith(("startms","endms"))`), `validate/render_verdict.py:28-37` (separate vocab row
  `verdict_scaffold_keys` with a hardcoded default that silently supersets the others + scale keys)
- **Evidence**: `slot_catalog.py:228`: `return k in _time_axis_keys() or "timestamp" in k or k.endswith(("startms", "endms"))`
  vs `fab_guards.py:85`: `..."axisstart", "axisend", "axisstartms", "axisendms", "startms", "endms")`. Adding a new
  time-axis leaf key to the `time_axis_keys` DB row does NOT reach render_verdict (different row) and reaches
  fab_guards/slot_catalog only partially (their literal unions differ) — the same invariant, four truths.
- **Refactor**: one accessor in `config/vocab.py` — `time_axis_keys()` returning the normalized DB set with the
  ONE shared code-default token set; each consumer keeps its documented *extra* predicate explicitly
  (`kind=='time'`, column names, scale keys via a separate `verdict_scaffold_keys` row that now *includes*
  `time_axis_keys()` instead of copying it). Do NOT merge consumer semantics (per-consumer extras stay) — only the
  vocab read + fallback set are unified.
- **Risk**: medium (the fallback sets currently differ; unification must be the exact union per consumer to stay
  behavior-identical — write a table of each consumer's effective set first). **Behavior-preserving**: YES if the
  per-consumer effective sets are reproduced exactly; verify with a set-equality unit test per consumer.
- **Tests guarding**: `tests/test_fab_guards.py`, `tests/test_render_verdict.py`,
  `tests/test_layer2_quantity_const_gates.py`, `tests/test_indexed_family_derived_sparkline.py`.

### F7. Three LLM POST/parse stacks; the :8200 narrator bypasses all client hardening; think-strip logic diverges
- **Files**: `ems_exec/renderers/_insight.py:106-132`, `copilot/llm.py:13-34`, vs `llm/client.py`
- **Evidence**: `_insight._post` posts to the SAME :8200 endpoint as `call_qwen` but with none of the hardening —
  no failure classification, no obs.failures record (`except Exception: return None` at 131), no `no_retry_kinds`,
  no prompt budget; and its `_strip_think` handles a dangling `</think>` (line 99-103) that client.py's
  `re.sub(r"<think>.*?</think>")` (line 171) does not — two parsers, two bug surfaces. copilot's 4 callers each
  hand-roll try/`json.loads`/swallow (generate.py:58, aliases.py:104, starters.py:64, build/metrics.py:33).
- **Refactor**: (i) extract the reply-parse into `llm/parse.py` — `extract_json(text) -> (obj|None, kind, detail)`
  containing the UNION think-strip (opening-tag AND dangling-close) + brace extract + classified errors; adopt in
  client.py and _insight.py. (ii) route `_narrate_sync`'s failure through `obs.failures.record("insight", kind)`
  (telemetry only; fallback contract unchanged). (iii) copilot stays endpoint-decoupled by design (memory: "zero
  pipeline coupling") — give it ONE local `copilot/parse.py` used by its 4 callers instead of importing llm/.
  Do NOT collapse `_post` into `call_qwen` blindly: _insight is a certified byte-faithful backend2 port with
  temperature 0.2 and its own cache — only the parse + telemetry are shared.
- **Risk**: medium (insight is certified-port code; parse union must be proven equivalent on both tag shapes).
  **Behavior-preserving**: YES (request payloads untouched; parse union strictly widens acceptance only for the
  dangling-tag case client.py already self-heals via brace-extract — assert equality on a replay corpus).
- **Tests guarding**: NONE for `_insight` in tests/ (test gap — add before touching); `tests/test_llm_truncation_budget.py`
  and `tests/test_foundations.py` for client.py; `copilot/tests/` for copilot.

### F8. API error envelope drift across the three HTTP servers (and error-in-200)
- **Files**: `host/server.py:198-343` vs `copilot/server.py:56-100` vs `host/exec_cards.py:188`
- **Evidence**: host uses `{"ok": bool, "error": str}` (400/404/500); copilot uses `{"error": str}` with no `ok`,
  and `/copilot/starters` returns errors as **HTTP 200** (`server.py:79: self._send(200, {"starters": [], "error": ...})`);
  per-card exec status uses a third key (`exec_cards.py:188: {"ok": False, "why": ...}`). The FE already papers over
  the drift — `host/web/src/api.ts:33: throw new Error(body?.error || body?.why || ...)` — which is how key drift
  fossilizes.
- **Refactor**: document ONE envelope (`{"ok": bool, "error"?: str}`; errors carry a non-2xx status unless the
  payload is a per-item partial like starters — then `ok: false` + 200 is explicit, not accidental) in
  `docs/contracts/`; add `ok` to copilot's `_send` error bodies (additive — existing `error` key kept, FE untouched);
  keep exec-status `why` (it is a per-card telemetry field, not an HTTP envelope) but note the alias in the contract.
- **Risk**: low (additive fields only). **Behavior-preserving**: YES for the additive step (key additions; the
  starters status-code change would NOT be — defer it and mark it in the contract).
- **Tests guarding**: `tests/test_render_guarantee_50.py`, `tests/test_multi_asset.py`,
  `tests/test_fe_data_note_serve.py`, `copilot/tests/`.

### F9. `layer2/gates.py` reads its chrome vocab at import time — frozen against reload() and vulnerable to F2's poison
- **File**: `layer2/gates.py:14-15`
- **Evidence**:
  ```python
  _CHROME = cfg("gates.chrome_markers",
                ["=>", "function(", "function (", "React.", "onClick", "px solid", "rgba("])
  ```
  Every other gate/guard knob in the tree is read lazily per call (`fab_guards._guard_on`,
  `render_verdict._scaffold_keys`, `null_gate.null_gate_mode`); gates.py alone materializes at import, so
  `app_config.reload()` never reaches it and an import-before-DB-up (F2) pins the code default for the process
  life of the long-running host. (The same import-time pattern exists across `config/*.py` module constants —
  flagged to the config-dimension auditor; this finding covers only the validation-gate instance.)
- **Refactor**: move the read inside `_is_chrome` (or a `_chrome_markers()` fn), mirroring `_scaffold_keys()`.
  One-line mechanical change; per-call cfg() is a cached dict lookup, no perf cost.
- **Risk**: low. **Behavior-preserving**: YES (healthy path identical; DB edits start taking effect after reload,
  which is the documented intent of the knob).
- **Tests guarding**: `tests/test_layer2_card.py`, `tests/test_layer2_per_leaf_payload_partition.py`,
  `tests/test_power_plausibility_knobs.py`.

### F10. ~15 private `_cfg` clones + 67 inline try-import wrappers guard an import that should simply be safe
- **Files**: `llm/client.py:51-56`, `obs/bus.py:10`, `obs/event.py:17`, `obs/sink_pg.py:22`,
  `ems_exec/renderers/_insight.py:33-37`, `ems_exec/executor/fab_guards.py` (per-knob try blocks),
  `data/ttl_cache.py:23-28`, `ems_exec/derivations/nameplate.py`, `ems_exec/derivations/power.py`, etc.
  (15 files define `def _cfg(`; 67 sites wrap `from config.app_config import cfg` in try/except)
- **Evidence**:
  ```python
  def _cfg(key, default):
      try:
          from config.app_config import cfg
          return cfg(key, default)
      except Exception:
          return default
  ```
  `cfg()` itself is already fail-open ("never raises, never blocks import" — its docstring); the only thing the 67
  wrappers guard is `config/app_config`'s import-time dependency on `data.db_client` (psycopg2). Making THAT import
  lazy (inside `_load`) makes `from config.app_config import cfg` unconditionally safe, after which every clone is
  dead weight that can be deleted module-by-module.
- **Refactor**: move `from data.db_client import q` / `from config.databases import CMD_CATALOG` into `_load()`;
  add one `config/safe.py` note documenting that importing `cfg` is always safe; delete the local `_cfg` clones
  mechanically (each is a strict no-op after the change).
- **Risk**: low. **Behavior-preserving**: YES.
- **Tests guarding**: `tests/test_config_cast_integrity.py`, `tests/test_foundations.py`, plus every knob-reading
  suite (`tests/test_power_plausibility_knobs.py`, `tests/test_validate_null_gate.py`).

---

## C. Non-findings (checked, intentionally left alone)

- **No bare `except:` anywhere** in live code — discipline is good on that axis.
- **validate/ vs gates vs fab_guards vs render_verdict staging** — defense-in-depth by design, different data at
  each stage (probe frame → emission → filled payload); consolidating stages would violate the pipeline contract.
  The null-column invariant IS checked twice (validate/data_validate probe null-rate pre-L2; fab_guards CLASS 2
  whole-table `column_logged` post-fill) but with deliberately different windows and different consequences
  (basket verdict vs leaf blank) — documented here, not proposed for merging.
- **copilot's separate LLM client** — decoupling from the pipeline model is a recorded design decision; only its
  internal parse duplication is flagged (F7-iii).
- **`layer2/emit/emit.py` transport-retry loop** — policy-correct today; F1 proposes hoisting it to llm/ so
  layer1b can share it, not changing it.
- **copilot suggest cache** (`copilot/server.py:41-50`) — already implements never-cache-error; cited as the
  in-repo precedent for F2.
