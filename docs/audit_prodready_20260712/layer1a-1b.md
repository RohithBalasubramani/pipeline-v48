# Prod-Readiness Audit — Lens: layer1a / layer1b (post-refactor differential)

Date: 2026-07-12
Auditor: subagent lens `layer1a-1b`
Scope: layer1a/ (partition move, parse clamps, template_feasibility_gate), layer1b/ (how.py vocab, transient_retry adoption, retry_one deletion, compare/detect never-cache-empty, member_scope constants), llm/prompt_load.py uniformity, normalize.py/build.py regressions.
Mode: DIFFERENTIAL vs docs/audit_2026-07-12/*, docs/findings/refactor_20260712/*. READ-ONLY.

## Verified OK (positive checks of today's claims)

- `layer1b/guardrail/retry_one.py` really deleted; zero importers; no stale `retry_one.cpython-*.pyc` in `layer1b/guardrail/__pycache__/`. Only a historical mention in `llm/transient_retry.py:5` docstring (fine).
- `partition/` → `layer1a/partition/` move complete: no remaining root-level `from partition ...` imports anywhere; root `partition/` dir gone; importers = layer1a/build.py, layer1a/partition_inputs/*, tests/test_partition_groups.py.
- D8 `llm/prompt_load.py` adopted by all four prior `_load_prompt` clones (layer1a/route.py:11,30; layer1a/story_builder.py:3,12; layer1b/resolve/asset_resolve.py:16,36; layer1b/basket/column_basket.py:3,31) — each keeps a 2-line local shim delegating with its own `_HERE`. Remaining independent prompt readers: layer2/emit/emit.py:20 (`_P` prompts dir — its own layer, joined not loaded via load()) and knowledge/ems.py:46 (zero-coupling by design).
- `llm/transient_retry.py` marker contract adopted in BOTH layer1b LLM calls: asset_resolve.py:29,173-175 (`on_error="marker"` + `retry_transient_result`) and column_basket.py:10,78-80; llm/client.py:84-85 implements the `_llm_error` marker; llm/client.py:187 sources `no_retry_kinds` from the D10 home.
- `layer1b/compare/detect.py:36-46` never-cache-partial fix present: index built locally, published only after the FULL read succeeds; failure returns `{}` WITHOUT caching so a tunnel flap self-heals.
- member_scope constants: all 4 ledger-claimed sites import OUTGOING/INCOMER (host/enrich.py:10,220; host/exec_cards.py:14,137,187; layer2/emit/panel_members_block.py:12,79,110; ems_exec/executor/members.py:18,132).
- `layer1b/how.py` frozensets adopted at the 3 ledger-claimed set-literal sites (layer1b/schema.py:2, layer1b/compare/resolve_names.py:26, run/harness.py:14).

Additional positive checks:
- Partition edge sources correct post-move: card_link (partition_inputs/card_link.py:6-8), card_combo_member JOIN card_combo (card_combo.py:6-9), page_control host+affects_cards (page_control.py:6-13), cards.interdependency prose (interdependency_prose.py:12), page_layout_cards orphan rescue (partition/fallback_edges.py:6-8). All 5 tables confirmed present in cmd_catalog (to_regclass probe, SELECT-only).
- parse/ has NO dead modules post prompt-v2/morph-map adoption: all five (granularity_reconcile, metric_intent_defaults, page_key_fallback, window_default, template_feasibility_gate) are imported by layer1a/route.py:21-24 + run/reconcile_granularity.py.
- template_feasibility_gate.py logic correct: `>= thr` drop, unknown/zero counts → frac 0.0 kept (lines 16-21), all-disqualified → least-unrenderable single fallback (lines 41-45, never empty for non-empty specs).
- All 50 layer1a/, layer1b/, llm/ modules py_compile clean AND import clean (`IMPORT_FAILURES: NONE`).
- pinned-path member_scope parity present (asset_resolve.py:77-84 stamps member_scope on the pinned asset).
- ENV-PIN guard coherent (layer1b/build.py:34-35, V48_ALLOW_ENV_PIN=1 required; API asset_id unaffected).
- 1b contract validator wired annotate-only (layer1b/build.py:48-55) with llm_failed floor-degradation telemetry; marker-contract tests updated incl. a deterministic fail-fast case (tests/test_stage_telemetry_item15.py:50-72).
- lib/parallel home + run/parallel sys.modules facade intact; resolve_names imports the home directly (resolve_names.py:19).
- tests/test_layer1a_routing.py, test_stage_telemetry_item15.py, test_partition_groups.py all collect cleanly (18 collected).

## Findings

### OBS-1 — MEDIUM (safe): PEP-562 lazy-config refactor is defeated by top-level `from` imports in layer1a — the "DB edit reaches consumers without restart" claim is NOT true for the 1a routing gates
The refactor ledger + module docstrings (config/feasibility.py:12-13, config/intents.py:3-4, config/swap.py:3-4) claim "each access re-reads cfg(), so a DB row edit + app_config.reload() reaches consumers without a process restart (import-time binding pinned the boot-time value)". But a top-level `from module import NAME` triggers `__getattr__` ONCE at import and pins the boot value for process life:
- `layer1a/parse/template_feasibility_gate.py:13` — `from config.feasibility import TEMPLATE_MAX_UNRENDERABLE_FRAC` (used line 34)
- `layer1a/db_reads/page_feasibility.py:8` — `from config.feasibility import UNRENDERABLE_VERDICTS` (spliced into SQL line 16)
- `layer1a/parse/metric_intent_defaults.py:3` — `from config.intents import INTENT_DEFAULT, INTENT_VOCAB`
- `layer1a/route.py:15` — `from config.metrics import METRIC_VOCAB` (prompt vocab line 79 + guided-json enum line 104)

Concrete split-brain: route.py reads `intents.vocab` LIVE via cfg() (lines 80, 95) while the clamp uses the PINNED boot `INTENT_VOCAB` — add an intent to the DB row and the router/grammar can emit it but `clamp_metric_intent` silently rewrites it to `INTENT_DEFAULT`. Same for `feasibility.template_max_unrenderable_frac` / `feasibility.unrenderable_verdicts` / `metrics.vocab`: knob edits need a restart, exactly what the refactor claimed to have fixed. The correct pattern already exists in-tree: `layer2/swap/gate_force_renderable.py:24-25` (`from config import feasibility as _feas  # read per call`) and function-level imports (window_default.py:21, route_schema.py:55).
Cross-ref for the layer2 lens (same class, out of my lane): layer2/swap/gate_confidence.py:2 (MIN_CONFIDENCE), layer2/swap/candidates.py:12 (SIZE_TOLERANCE, SWAP_POOL_MAX), layer2/swap/gate_vague_reject.py:2 (VAGUE_CRITERIA) — all lazy attrs pinned at import.
Fix (safe, behavior-preserving at boot): switch to module-attribute access or function-level from-imports.

### OBS-2 — LOW (safe): layer1b/how.py adoption is PARTIAL — the frozenset consumers were rewired, but every producer and single-value comparison still uses raw string literals
how.py claims to be "the ONE declaration of the 1b resolution `how` vocabulary", but only the 3 set-literal sites were rewired (schema.py:2, resolve_names.py:26, harness.py:14). Raw literals remain at: producers — layer1b/resolve/no_data_gate.py:43 (`"how": "no_data"`), ambiguous_candidates.py:56 (`"ambiguous"`), pinned_skip.py:22 (`"user-choice"`), asset_resolve.py:214 (`"empty"`), host/multi_asset.py:141 (`"user-choice"`); comparisons — layer1b/build.py:24-25, layer1b/schema.py:27,29, run/harness.py:311, validate/build.py:51, validate/report.py:27. Additionally layer1b/compare/resolve_names.py:167 emits `how: "error"` in compare `resolutions` telemetry — a value NOT in how.ALL (telemetry-only, never schema-validated, but undeclared in the vocabulary home).

### OBS-3 — LOW (owner-gated): how.py (new today) canonizes the DELETED collision gate's `how` value as a live state
`HOW_COLLISION_GATE = "collision_gate_fullname"` (how.py:19) is documented as a live "deterministic full-name pin (user spelled a colliding row out in full)" and included in RESOLVED_WITH_DATA (how.py:26), but NO producer exists — the name-collision gate was deleted 2026-07-09 (asset_resolve.py:188-195 "REMOVED"; member-cache-poison memory). The prior audit flagged the stale validator/comment leftovers (code-quality-layers §16); today's new central file EXTENDS that confusion by re-describing the value as live in the canonical home (also resolve_names.py:22-24 comment). Owner call: tombstone the constant's docstring as legacy-accepted-only, or drop it from RESOLVED_WITH_DATA/ALL after confirming no replayed/stored payloads carry it.

### OBS-4 — LOW (defer): one member_scope raw literal remains — host/server.py:273
`member_scope = refetch.get("member_scope") or "outgoing"` — the only code site not rewired to `layer1b.resolve.member_scope.OUTGOING`. host/server.py was deliberately skipped by the refactor (a concurrent session owns it — ledger Batch 4 "SKIPPED deliberately"). Defer to that session; one-line fix when quiet.

### OBS-5 — LOW (safe): D8 (one prompt loader) incomplete vs its own audit spec — the 2 inline variants remain, one with a locale-dependent decode divergence
The audit spec (CODEBASE_AUDIT_UNUSED_DUPES §D8) targeted "`_load_prompt` ×4 (+2 inline variants)". The ×4 delegate now (verified), but: `layer2/emit/emit.py:163,166` still opens data_instructions_v2.md / morphmap prompt inline with `errors="replace"` and NO `encoding="utf-8"` — on a non-UTF-8 locale (systemd C locale, py3.12) prompt bytes decode differently from the prompt_load house default (U+FFFD mangling instead of correct UTF-8); `knowledge/ems.py:46` keeps its inline open (encoding but no errors — byte-strict; arguably fine for the zero-coupling layer). Prompt loading within layer1a/1b itself IS uniform.

### OBS-6 — LOW (safe): layer1a/schema.py hardcodes the intent enum — a 4th copy of the intents vocabulary
`_INTENTS = {"trend", "distribution", "snapshot", "table", "events"}` (layer1a/schema.py:3) duplicates the DB-driven `intents.vocab` (config/intents.py:9) — plus route.py's two inline cfg defaults (route.py:80,95). Editing the DB row makes the (currently test-only, ledger follow-up #12) `validate_layer1a_output` flag valid intents as contract problems. Fold into the planned validator wiring: read INTENT_VOCAB lazily instead.

### OBS-7 — LOW (safe): stale pre-move path in docstring
`layer1a/partition/group_detect.py:1` docstring still says "partition/group_detect.py" (the pre-move root path); siblings coupling_lookup.py/fallback_edges.py were updated to the layer1a/ path.

## Summary
No critical/high regressions in layer1a/1b. Today's refactor claims verified TRUE for: retry_one deletion, transient_retry marker adoption, D8 (the named ×4), D9, D10, detect.py never-cache-partial, member_scope constants (4/5 sites), partition move. Claims NOT fully true: PEP-562 lazy config (OBS-1 — the one medium), how.py "ONE vocabulary" (OBS-2/3), D8 vs its own wider spec (OBS-5).

