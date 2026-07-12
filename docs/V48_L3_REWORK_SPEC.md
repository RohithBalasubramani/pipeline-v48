# V48 L3 Rework — the payload cleaner

> **SUPERSEDED (2026-07):** Layer 3 was retired; the deterministic clean/verify concern lives in
> `ems_exec/executor/` (fill + fab_guards) and `validate/render_verdict.py`. Kept for history.

**GOAL:** every card renders a COMPLETE, clean, crash-proof, real-or-"—" payload. L3 = deterministic clean/detect/verify
with a TARGETED AI repair (last, only on flagged problems, FIXES-not-INVENTS, cached). Determinism guarantees; AI does
heavy diagnosis/repair on a tiny targeted input.

## Pipeline — `run/layer3_all.run_card_l3(run_id, card_id, l1a, l1b, l2_out)` per card
```
clean() → detect() → repair(AI, only if problems) → verify_per_leaf() → cache()
```

### 1. `layer3/clean.py` — deterministic fill (does the bulk; NO AI)
Input: the card payload skeleton (`l2_out.exact_metadata`), the live `frame` (fetched here or passed), the grounding bag,
the CACHED leaf→frame-key mappings.
- **Fill each DATA leaf** from, in order: (a) the cached leaf→frame-key mapping; (b) the L2 `data_instructions.fields`
  (metric→column) + grounding slot→column bindings; (c) a cataloged derivation (reuse `apply.py` `_run_substitute_fn` +
  `ems_backend...derivations.registry.run` + `config.nameplates`); else (d) **honest "—" (None)**.
- **Fetch/verify** real values (reuse `apply.py` `_latest_row`/`_window_rows`/`verify_value` — reversed-CT, denorm, sign).
- **Strip every un-provenanced seed leaf** (`apply.all_data_leaf_paths` + `scrub_narrative`) — nothing seed survives.
- **Complete the shape:** every key the CMD_V2 component reads MUST exist (missing → null placeholder, never absent) → no
  `undefined.map`/`toLocaleString` crash.
- **null-safe.** Output: `filled_payload` + a `frame_manifest` (the real values available: {frame_key: value, semantic}).

### 2. `layer3/detect.py` — deterministic problem scan (NO AI)
Scan `filled_payload` vs `frame_manifest` for PROBLEMATIC entries only (most cards → 0 → skip AI):
- `unmapped_but_available`: a leaf is "—"/null but the manifest has a plausible real value (a MAPPING GAP).
- `wrong_unit` / `out_of_range`: value violates the slot's expected unit/range (from `config.quality_policy`/schema).
- `malformed` / `would_crash`: a shape the component would choke on (array where scalar expected, missing required child).
- `inconsistent`: e.g., a total that doesn't match its parts.
Returns `problems[] = {path, current, kind, hint}`.

### 3. `layer3/repair.py` (+ `prompt.py`, `schema.py`) — the AI repair (LAST; only if problems)
- AI sees ONLY `problems[]` + the `frame_manifest` (real values, NAMED) + minimal card context (title/story/slot).
- AI **FIXES** each problem — NEVER invents: for `unmapped_but_available` → NAME the `frame_key` that belongs in that
  leaf; for `wrong_unit`/`malformed` → the transform/structural fix. It may only NAME a manifest key or a structural op.
- Output = a small **PATCH**: `[{path, frame_key|op}]`. No raw numbers. (schema.py validates: every value ref is a
  manifest key or an allowed structural op; anything else dropped.)

### 4. `layer3/verify.py` — per-leaf verifier (deterministic)
For EACH patch entry: resolve `frame_key` → the REAL manifest value; if not in the manifest → **reject THAT entry only**
(leaf stays "—"). Apply the valid entries onto `filled_payload`. NEVER accept a raw AI number. → `final_payload`.

### 5. `layer3/cache.py` — learn the mappings
Persist the VALIDATED leaf→frame-key mappings (+ structural fixes) keyed by `(card_id, schema_fingerprint)` into
`cmd_catalog.render_spec` (reviewable/editable). `clean()` reads them first next time → the AI fires only on NOVEL gaps.

## Token handling (the whole point)
- Input ∝ #problems + manifest (small), NOT the payload. Output ∝ #fixes (a tiny patch). 0 problems → 0 AI tokens.
- Cold start is NOT "map everything": `clean()` seeds mappings from L2 `data_instructions` + grounding, so the AI only
  handles the RESIDUAL. Cached mappings → the AI stops firing → steady-state ≈ deterministic.

## CLEANUP — retire the redundant per-slot-verdict L3
- **DELETE/repurpose the AI-verdict path:** `layer3/emit.py` (the slot-verdict call), the old verdict `prompt.py`/
  `schema.py` (render_verdict/slot_decisions/suppress AI), `layer3/factsheet.py` (per-slot facts for that call). The old
  per-slot bind/blank is now DETERMINISTIC inside `clean()` (present→bind, none→"—") — proven 46/46 deterministic.
- **FOLD** `apply.py`'s fetch/verify/derivation/suppress/`all_data_leaf_paths`/`scrub_narrative` into `clean.py` (+ keep a
  thin `apply` shim if imported elsewhere).
- **ATOMIC:** `layer3/{clean,detect,repair,verify,cache,prompt,schema}.py` — one concern each. Update `run/layer3_all.py`
  to the new flow. Every threshold/mapping/reason stays in `config/*` (DB-driven, no hardcode).

## Verify (acceptance)
`build_response("energy and power for GIC-01-N3-UPS-01")`: every card → a COMPLETE payload (no missing keys), real values
where the frame has them (load% ~39.5, today energy ~2994), "—" for gaps, **ZERO seed literals**, no crash. L3 AI tokens
≈ 0 on clean cards, small on problem cards. Imports clean.

## Frontend (follow-up, not this pass)
Render each CMD_V2 component with the L3 `final_payload` VERBATIM (no per-card mapper) + a universal safe-render boundary
+ honest-blank tile; wire card #38 + all unwired. (The backend clean payload is the prerequisite; do it next.)
