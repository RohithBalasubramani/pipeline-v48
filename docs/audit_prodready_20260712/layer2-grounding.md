# Prod-readiness audit — lens: layer2-grounding

Date: 2026-07-12 (differential pass, post-refactor)
Scope: layer2/ (build.py, gates/, swap/, metadata_resolve, window_backfill, reconcile_slots, cross_domain, emit/) + grounding/swap_settle.py
Auditor: layer2-grounding lens subagent (read-only)

Findings appended incrementally below.

---

## State observations (no-finding context)

- **git**: the ENTIRE pipeline_v48 tree is untracked (`?? backend/layer2/pipeline_v48/` — git status from repo root
  /home/rohith/desktop/BFI). There is NO committed pre-split `layer2/gates.py` to diff against; gate-inventory
  comparison was reconstructed from ledger + importer surface instead (all referenced names resolve — see verified).
- **build.py**: 442 lines. `_finalize` (obs wrapper, build.py:59-74) + `_finalize_inner` (build.py:77-333, ~257 lines).
  The metadata produce→gate→enforce block IS extracted (`layer2/metadata_resolve.py`, re-exported at build.py:31), as
  the AUDIT_REPORT "Fixes Applied #20" claims. `_finalize_inner` is however still a ~255-line multi-concern
  sequence (envelope rescue → override → window backfill → consumer → coherence → roster gate → fields gate +
  partition → reconcile → no-op-morph partition → answerability/notes → zero-skeleton → feasibility → cross-domain →
  assemble+schema). Split is PARTIAL, not abandoned — concern-extractions continue (window_backfill/reconcile_slots/
  cross_domain/metadata_resolve all extracted today). fix_class=defer.

## OBS-1 (medium, safe) — wall_corpus_replay provenance still hashes the deleted layer2/gates.py

`tools/wall_corpus_replay.py:437` — `"walls_provenance": {"layer2/gates.py": _sha(os.path.join(ROOT, "layer2", "gates.py"))`.
After the gates.py→gates/ package split the file no longer exists; `_sha` returns None on OSError
(wall_corpus_replay.py:422-423), so every new baseline records `gates sha None` (render_md line 461 prints it), and
the tool's own acceptance standard ("diff per_rule ... after every wall change") loses its did-the-walls-change
provenance signal silently. Should hash `layer2/gates/walls.py` (+ siblings). Stale path refs also at lines 24, 185.

## OBS-2 (low, safe) — emit.py module docstring describes the retired 3-part prompt

`layer2/emit/emit.py:1-2` says "Composes the 3 atomic prompt parts (swap + metadata + data_instructions)" and line 6
says the placeholder lives "in data_instructions.md" — but `_system()` (emit.py:148-163) reads ONLY
`data_instructions_v2.md` (the always-v2 single contract; the trio was deleted per the panel-overview consolidation).
Doc drift on the fabrication-core entry file.

## OBS-3 (medium, safe) — lazy-config campaign half-applied in layer2/swap: knobs still boot-frozen

The refactor ledger (EXECUTED_AND_FOLLOWUPS.md lines 23-25) claims import-time cfg() freezes were converted to lazy
PEP-562 attrs so "a DB row edit + app_config.reload() reaches consumers without a process restart", and explicitly
notes gate_force_renderable reads feasibility knobs per call. But consumers that bind the lazy attr at THEIR import
re-freeze it for the process life:
- `layer2/swap/candidates.py:12` — `from config.swap import SIZE_TOLERANCE, SWAP_POOL_MAX` (module level)
- `layer2/swap/candidates.py:19` — `POOL_VERDICTS = tuple(... cfg("feasibility.pool_verdicts", ...))` direct
  import-time cfg() freeze (and `pool_verdicts` is not even in config/feasibility._LAZY)
- `layer2/swap/gate_confidence.py:2` — `from config.swap import MIN_CONFIDENCE`
- `layer2/swap/gate_vague_reject.py:2` — `from config.swap import VAGUE_CRITERIA`
- `layer2/swap/gate_force_renderable.py:28` — `FORCED_SWAP_CONFIDENCE = cfg(...)` at import (its feasibility reads
  ARE per-call via `_feas.` — only this one value stays frozen)
All are imported at boot (decide.py → build.py), so swap.min_confidence / swap.size_tolerance / swap.swap_pool_max /
swap.vague_criteria / feasibility.pool_verdicts edits do NOT reach a running :8770 despite the campaign claim.
(Same pattern exists outside my lens: layer1a/parse/template_feasibility_gate.py:13, layer1a/db_reads/
page_feasibility.py:8, layer1a/route.py:15 — flagged for the layer1a lens.)

DIFFERENTIAL against the prior lens (docs/audit_2026-07-12/code-quality-layers.md finding #5, which listed 7 frozen
sites) — current state per site:
- gates chrome vocab (`_CHROME`) — FIXED (lazy `_chrome_markers()`, layer2/gates/metadata.py:16-17)
- `_AFFINITY_MIN_TOK` — FIXED (per-call `_min_token_len()`, domain/metric_affinity.py:13-15)
- `layer2/swap/candidates.py:19` `POOL_VERDICTS` — STILL FROZEN
- `layer2/swap/gate_force_renderable.py:28` `FORCED_SWAP_CONFIDENCE` — STILL FROZEN
- `layer2/emit/instructions/consumer_binding/screen_map.py:12` `_PAGE_TAIL_ALIAS` — STILL FROZEN
- `layer2/emit/instructions/consumer_binding/domain.py:15` `RETIRED_ENDPOINTS` — STILL FROZEN
- `layer2/catalog/card_grid_size.py:5` `DEFAULT_VIEWPORT` — STILL FROZEN
So 2 of 7 sites were fixed; the ledger's blanket "Import-time cfg() freezes converted" reads as done but is ~30%
landed for the sites the original finding cited. Additionally the PEP-562 conversion of config/swap.py is
INEFFECTIVE for every one of its actual consumers (gate_confidence/gate_vague_reject/candidates all from-import the
values at module import — the cfg() read just moved from config-module import to consumer import, still boot-time).

## OBS-4 (low, safe) — build.py carries dead imports left by the metadata_resolve extraction

`layer2/build.py:9-10` (`produce, metadata_reference, undeclared_morphs`, `morphmap_apply`) and the
`gate_exact_metadata, enforce_exact_metadata, enforce_free_metadata` names in build.py:14-15 are no longer used
anywhere in build.py runtime code (all call sites moved to layer2/metadata_resolve.py today; remaining mentions are
comments). Unlike the deliberate byte-compat re-exports (build.py:26-31, explicitly `# noqa: F401` + commented),
these are unmarked leftovers; no external module imports them via `layer2.build` (checked every importer).
`gate_data_instructions`/`gate_roster` in the same import ARE still used (build.py:164, 145). Half-applied refactor
residue on the hot-path module.

## OBS-5 (medium, safe) — grounding/swap_settle.swappable_pool is dead code; the dead-code campaign kept it on a misread

`grounding/swap_settle.py:47` `swappable_pool()` has ZERO callers tree-wide (grep over all of pipeline_v48 incl.
tests: only its def + a docstring mention at layer2/swap/candidates.py:9). The LIVE pool filter is the inline
re-implementation in `candidates.pool` (candidates.py:76: `is_registered(cid)`/`has_default(cid, page_key)`).
The dead-code campaign explicitly KEPT it: docs/findings/refactor_20260712/dead-code.md:83 removed `swappable_ids`
with the rationale "only `swappable_pool` is consumed (`layer2/swap/candidates.py:9`)" — but candidates.py:9 is a
DOCSTRING, not a call. Risk: swap_settle.py:4-7 presents swappable_pool as THE pool filter ("before the AI ever sees
the pool"), so a future policy edit there silently does nothing in production, and the two copies (its metric
re-rank vs candidates' rank-then-truncate) can drift. Fix: route candidates.pool through it, or delete it and fix
both docstrings. (Also a category-(d) note: the campaign's "verify before calling code dead" check accepted a
docstring hit as consumption.)

## OBS-6 (medium, defer) — _finalize_inner remains a ~257-line multi-concern function

State-of-the-deferred-item report (see State observations above): AUDIT_REPORT Fixes #20's BODY is accurate
("`_finalize_inner` is now ~259 lines" — measured 257, build.py:77-333), though its HEADING "split finished"
overstates: only the ~65-line metadata block moved. ~12 sequential concerns remain inline. The extraction pattern
(window_backfill/reconcile_slots/cross_domain/metadata_resolve) is established and active today — treat further
splitting as owned/deferred, not abandoned.

---

## Verified OK (positive confirmations)

- gates split lost nothing observable: 6 single-purpose modules {metadata, basket, walls, honest_blank,
  data_instructions, roster} + facade `layer2/gates/__init__.py` re-exports every name any module/test imports
  (25 names); live import of the full facade surface succeeds; enforce_honest_blank wired inside
  gate_data_instructions (gates/data_instructions.py:4). (No git HEAD baseline exists — tree untracked.)
- swap: `gate_no_dup.ok` folds template_card_ids ∪ already_chosen ∪ page_card_ids into `forbidden`
  (layer2/swap/gate_no_dup.py:6); `gate_template_dedup` fully gone (only the historical comment decide.py:29).
- {{RECOVERY_LIBRARY}} still generated from `ems_exec.derivations.registry.catalog()` (emit.py:76,91) with the
  per-card basket/nameplate/breaker filter; fail-open to an honest "(recovery library unavailable...)" line.
- no_retry_kinds honored: `llm/transient_retry.retry_transient` refuses retry for kinds in `llm.no_retry_kinds`
  (default timeout,truncated); emit uses it (emit.py:212-225); one shared reader `no_retry_kinds()` (dedup D10).
- Always-v2 prompt path: `_system()` reads only `data_instructions_v2.md`; layer2/prompts/ contains exactly that one
  file; ROSTER markers present (prompt lines 100/109); {{LIVE_ENDPOINTS}}/{{RETIRED_ENDPOINTS}} placeholders present
  (68-69); the morphmap envelope-rewrite target substring exists verbatim (prompt line 117).
- grounding/swap_settle: pool-filter policy (renderer-registration + recoverable default) IS enforced on the live
  path (candidates.pool:76) before AI/enforcer see the pool; `settle()` wired in run/layer2_all.py:13;
  is_registered empty-policy fail-open intact (swap_settle.py:43).
- metadata_resolve.py is a faithful delegation (produce/morphmap_apply/gates), no duplication of emit/metadata/*;
  build.py re-exports all extracted helpers byte-compatibly (build.py:26-31) and every external importer
  (tests/tools/run/profiler/outputs) resolves.
- window_backfill/_cross_domain/_reconcile_slots: all lazy in-function imports resolve (config.neuract_dsn,
  ems_exec.data.neuract, replay.clock, config.reason_templates, config.windows.ensure_nonzero_span/site_tz,
  config.metrics.quantity_family/slot_semantic_label, domain.metric_affinity, config.gates_vocab).
- `_blank_cross_domain_leaves` matches _cross_domain_fields' (slot, source) keying exactly (fn for derived, column
  otherwise) and blanks per-leaf only (cross_domain.py:67-84).
- layer2/quantity_class.py sys.modules-alias facade to domain/quantity_class works (import smoke).
- No dangling `layer2.emit.data` (renamed to instructions) imports anywhere; py_compile clean over all of layer2/,
  grounding/, tools/wall_corpus_replay.py.
- Lazy-config fixes that DID land: gates chrome vocab (gates/metadata.py:16) and swap.affinity_min_token_len
  (domain/metric_affinity.py:13) read per call.
