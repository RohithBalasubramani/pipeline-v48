# Fix log — group: small-code

Date: 2026-07-12 ~08:15 IST. Implements layer2-grounding OBS-1/2/4/5, layer1a-1b OBS-5, config-db OBS-1.
Freshness: every file Read in full immediately before editing; layer2/build.py mtime checked twice (07:56:48,
i.e. >15 min old at edit time — outside the concurrent-session window the brief specifies).

## 1. tools/wall_corpus_replay.py — [layer2-grounding OBS-1]
- **What**: `walls_provenance` hashed the deleted `layer2/gates.py` (post gates.py→gates/ split), so every new
  baseline recorded `gates sha None`. Added `_sha_pkg(dirpath)` (sorted `.py` basenames, contents concatenated into
  one sha256, first 16 hex — stable; None on OSError/empty, matching `_sha`'s fail-soft) and pointed the
  `"layer2/gates.py"` provenance value at `_sha_pkg(ROOT/layer2/gates)`. The output field NAME is kept (per brief)
  so old/new baselines diff key-for-key; an inline comment explains the historical key.
- Also fixed the two stale path refs the finding names: docstring line 24 (`layer2/gates.py` → `layer2/gates/`)
  and the `_RULE_MAP` comment line 185 (`mirrors layer2/gates/ reason texts` — verified `reused across distinct
  scalar slots` lives in `layer2/gates/honest_blank.py:107`).
- **Test**: py_compile OK; end-to-end smoke `--max-files 2 --fresh-only` to scratchpad →
  `walls_provenance: {'layer2/gates.py': 'db9b765f8cf824ab', 'layer2/quantity_class.py': 'daf40d134a6a794c'}` and
  the md renders `gates sha db9b765f8cf824ab` (was None). Committed baseline outputs NOT overwritten.

## 2. layer2/emit/emit.py — [layer1a-1b OBS-5 + layer2-grounding OBS-2]
- **What**: (a) added `encoding="utf-8"` to both inline prompt opens (`data_instructions_v2.md` at `_system()` and
  `_MORPHMAP_PROMPT`) — kills the locale-dependent decode divergence vs the prompt_load house default (systemd C
  locale would mangle non-ASCII prompt bytes); `errors="replace"` kept, zero logic change. (b) rewrote the stale
  module docstring: "Composes the 3 atomic prompt parts (swap + metadata + data_instructions)" → the always-v2
  SINGLE contract (`prompts/data_instructions_v2.md`, retired trio subsumed, morphmap PART 2 override as the only
  optional composition), and fixed the HARDENED bullet's `{{RECOVERY_LIBRARY}}` filename (`data_instructions.md` →
  `data_instructions_v2.md`; the bullet already correctly describes generation from
  `ems_exec.derivations.registry.catalog()`).
- **Test**: py_compile OK; `import layer2.emit.emit` OK; `tests/test_emit_prompt_budget.py` +
  `tests/test_residual_layer2_emit.py` pass (in the 50-passed run below).

## 3. grounding/swap_settle.py — [layer2-grounding OBS-5] delete dead `swappable_pool`
- **Verify-before-dead (grep proof)**: `rg -n swappable_pool` across ALL of /home/rohith/desktop/BFI (incl.
  pipeline_v48 tests/, scripts/, sweep/, outputs/, hidden files) → only (a) its own `def` (swap_settle.py:47),
  (b) a DOCSTRING mention `layer2/swap/candidates.py:9` (no call — the dead-code campaign's misread), (c) prose in
  docs/audit + outputs/*.md reports. Zero code consumers anywhere. The LIVE pool filter is the inline
  `is_registered(cid)` / `has_default(cid, page_key)` in `layer2/swap/candidates.pool`.
- **What**: deleted `swappable_pool()` (and its section banner); removed the now-orphaned
  `from grounding import default_assemble` import (used only by the deleted fn — verified single use at old line
  62); rewrote the module docstring so job "1. POOL FILTER" no longer claims this module enforces it — it now
  points at `layer2/swap/candidates.pool` as the live enforcement (via `is_registered()` here +
  `default_assemble.has_default`) with a deletion tombstone. `is_registered`/`registered_card_ids`/`settle`/
  `_revert`/`_confidence` byte-untouched.
- **Test**: py_compile OK; `import grounding.swap_settle` OK; `tests/test_layer2_swap_gates.py` (uses `settle` +
  `is_registered`) and `tests/test_swap_metric_affinity.py` pass.
- **Not done here (ownership)**: the second docstring the finding names — `layer2/swap/candidates.py:9` still
  says "grounding.swap_settle.swappable_pool" — candidates.py is NOT in this group's file list → skipped, needs a
  one-line docstring fix by its owner.

## 4. db/render_guarantee_schema.sql — [config-db OBS-1] endpoint_policy zombie CREATE
- **What**: block-commented the live `CREATE TABLE IF NOT EXISTS endpoint_policy` (lines 72-81) with the SAME
  RETIRED banner convention as db/round2_config_schema.sql's live_window_policy/limit_override scrub: tombstone
  points at db/retire_unused_tables_20260712.sql (APPLIED, owner-authorized) + archive/db_snapshots_20260712/.
  DDL kept inside `/* ... */` for the historical record. A from-scratch `db/apply.py` rebuild no longer resurrects
  the dropped table. NO live-DB touch.
- **Test**: n/a (declarative SQL, now inert); visual diff only — every other statement byte-identical.
- **Not done here (ownership)**: `scripts/seed_schema_and_endpoints.py:9` stale docstring (same finding's
  secondary note) — file not owned → skipped.

## 5. layer2/build.py — [layer2-grounding OBS-4] dead-import removal ONLY
- **Mtime gate**: 07:56:48 vs edit at ~08:14 → >15 min, outside the concurrent-session skip window (checked twice).
- **What**: removed the unmarked leftovers of the metadata_resolve extraction: line 10
  (`from layer2.emit.metadata.producer import produce, metadata_reference, undeclared_morphs`), line 11
  (`from layer2.emit.morphmap.producer import apply as morphmap_apply`), and trimmed the gates import to
  `from layer2.gates import gate_data_instructions, gate_roster` (dropping `gate_exact_metadata`,
  `enforce_exact_metadata`, `enforce_free_metadata`).
- **Proof each name is dead in build.py**: per-name grep — `produce`/`morphmap_apply` remaining hits are comments
  (lines ~199/205/320/365: "produce()/morphmap_apply already shipped…"); `undeclared_morphs` remaining hit is a
  KWARG name in the obs span (`sp.set_outputs(... undeclared_morphs=len(...))`, line 69), not the import;
  `metadata_reference`/`gate_exact_metadata`/`enforce_exact_metadata`/`enforce_free_metadata` appear ONLY on the
  import lines. `gate_data_instructions` (line 165) and `gate_roster` (line 146) still used → kept.
- **Proof no external consumer imports these via layer2.build**: `rg "from layer2.build import|layer2\.build\."`
  tree-wide → importers pull only run_card, _page_card_ids, _seedfree_default, _finalize,
  _backfill_default_window, _range_delta, _reconcile_slots, _cross_domain_fields (all still exported; the
  deliberate `# noqa: F401` re-export block at lines 26-32 untouched).
- **Test**: py_compile OK; `python3 -c "import layer2.build"` OK; offline swap/emit suite green.

## Gate summary
- `python3 -m py_compile tools/wall_corpus_replay.py layer2/emit/emit.py grounding/swap_settle.py layer2/build.py` → OK
- `python3 -c "import layer2.emit.emit, grounding.swap_settle, layer2.build"` → OK
- `pytest tests/test_emit_prompt_budget.py tests/test_layer2_swap_gates.py tests/test_residual_layer2_emit.py
  tests/test_swap_metric_affinity.py -q` → **50 passed, 1 skipped, 0.62s**
- wall_corpus_replay live smoke (scratchpad outputs) → gates sha now real (db9b765f8cf824ab), key unchanged.

## Skipped (ownership)
- `layer2/swap/candidates.py:9` docstring still references the deleted `grounding.swap_settle.swappable_pool` —
  file not owned by this group.
- `scripts/seed_schema_and_endpoints.py:9` stale "seeds endpoint_policy" docstring (config-db OBS-1 secondary) —
  file not owned by this group.
