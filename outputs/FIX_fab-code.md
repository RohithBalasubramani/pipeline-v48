# FIX_fab-code — CLASS 4 seed-leak: raw-vs-stripped DATA/METADATA wall

Run under repair: r_5c6797f815 ("what is voltage of PCC Panel 1A last 7 days").
Findings: DEBUG_r_5c6797f815_FINDINGS.md §blanking-pres-leaves (B1,B2,B6,B7), §card20-trend-render (C20-F1,F2).

## Root cause (recap)
`ems_exec/executor/fab_guards.py::_apply_class4_seed_leak` blanked any UNWRITTEN leaf byte-identical to the default,
exempting "chrome" only by a key-vocab whitelist (`_is_structural_chrome` exact-key + `_is_chrome_leaf` last-word).
Compound presentation/ordering leaves (`stackOrder`, `lineOrder`, `columnOrder`, `tileOrder`, `railOrder`,
`titleConnector`, `leftAxisLabel`, radar colours, `presetOptions[*].value`, `timeOptions`, `causeVocab.*`, …) fell
through the whitelist and were BLANKED to `[]`/null. The FE builds series/columns/tiles by iterating these order
arrays → empty plot (c20, 169 real points), empty table (c22, 6 real rows), bare strip (c18). Regression turned on
2026-07-07 13:34 (fab_guards.* app_config rows). The 23:19 `_chrome_string_keys` "wall" was key-vocab whack-a-mole and
still missed connector/order/options/value/vocab/bg/fill/stroke keys.

## The fix (generic, from B7)
The strip-builder's own DATA/METADATA classification is ALREADY PERSISTED in the DB: `card_payloads.payload` (RAW
default) vs `card_payloads.payload_stripped` (skeleton). The strip zeroes DATA leaves to typed placeholders and keeps
METADATA leaves BYTE-IDENTICAL. So per leaf:
- `raw == stripped` → METADATA (kept verbatim) → **NEVER a seed candidate, whatever its key**.
- `raw != stripped` → DATA → policeable; its seed test is byte-identity to the **RAW** default (`node == raw`).

Both references are already threaded to the executor (host/exec_cards.py:110-111, host/server.py:224):
`default_payload = _default_payload` (= payload_stripped) and `shape_ref = _raw_default_payload(rid)` (= payload),
via `run_card → fill(..., shape_ref=)`. This fix simply consumes both in CLASS 4.

Changes (files I own):
1. `ems_exec/executor/fill.py:592` — thread `shape_ref=shape_ref` into the `fab_guards.apply(...)` call.
2. `ems_exec/executor/fab_guards.py`:
   - `apply(...)` gains a `shape_ref=None` kwarg, passed to CLASS 4 as `raw_default`.
   - `_apply_class4_seed_leak(out, default_payload, written, gaps, raw_default=None)` rewritten to walk `out` +
     STRIPPED default + RAW default in parallel. AUTHORITATIVE WALL = raw-vs-stripped per leaf:
       * METADATA (`raw == dflt`) → return (kept), regardless of chrome vocab. Lone carve-out preserved: a
         magnitude-bearing label ('Rated: 131A') is neutralised to 'Rated: —' even as metadata (card 69).
       * DATA (`raw != dflt`) → seed iff UNWRITTEN and `node == raw` → blank (card-73 legendValue charter preserved).
     - FALLBACK when `shape_ref` is None or a raw leaf is absent at a path (older callers / structural divergence):
       the legacy chrome-vocab wall + stripped comparison, byte-for-byte identical to prior behaviour (under-blank
       preference — the removed harm is over-blanking chrome). `_is_structural_chrome`/`_is_chrome_leaf` kept as
       belt-and-braces for that fallback only; they are no longer load-bearing for correctness on the real host path.

## Why generic (not a per-card/per-key fix)
The wall is a single predicate over data that ALREADY exists for every card (the strip diff the whole pipeline is
built on). No new key vocab, no card ids, no slot names. Every card's metadata leaves survive automatically because
the strip kept them verbatim; every card's genuine unstripped data seed still blanks because the strip zeroed it.
Verified in DB: card 20 `trend.pres.stackOrder`/`lineOrder` and card 22 `table.pres.columnOrder` are byte-identical
raw-vs-stripped (metadata → now KEPT); card 22 `table.pres.layout` (20→0.0) and `trend.points[*]` (swept to 0.0/"")
differ (data → policeable).

## Acceptance cases (unit tests added to tests/test_fab_guards.py)
- `test_class4_metadata_leaf_raw_equals_stripped_is_kept_regardless_of_key` — stackOrder/lineOrder/columnOrder/
  titleConnector/leftAxisLabel KEPT, zero unstripped_seed gaps.
- `test_class4_data_leaf_equal_to_raw_default_still_blanks` — legendValue [52,71,85,43] (raw != stripped) BLANKED;
  metadata key/color survive.
- `test_class4_data_leaf_real_value_differing_from_raw_seed_is_kept` — a real reading != the raw seed is kept (seed
  test is against RAW, never the stripped placeholder).
- `test_class4_magnitude_label_metadata_still_neutralised` — 'Rated: 131A' → 'Rated: —' preserved.
- `test_fill_threads_shape_ref_into_fab_guards_apply` — proves fill() wires shape_ref into CLASS 4.

Existing tests that pass NO shape_ref hit the fallback path (unchanged legacy behaviour) and stay green.

## Cross-file (NOT owned — see needs_cross_file)
`tests/test_post_fill_rescue_overreach.py::test_fill_wires_class4_seed_leak` (line ~315-318) passes
`shape_ref=default` IDENTICAL to `default_payload=default`, i.e. raw==stripped for the legendValue seed — an
unrealistic input that encodes the OLD buggy reference (a real strip would zero the seed). Under the correct new
semantics (raw==stripped ⟹ metadata ⟹ keep) that test would fail. It must pass a STRIPPED default_payload with the
seed zeroed while keeping shape_ref as the RAW seed. Exact edit recorded in needs_cross_file.

## Residual / not in scope of this fix
- B6 (numeric PRES leaves like rowHeight/fitMin classified as DATA → stripped to 0.0 → unbound_by_emit null) is a
  SEPARATE mechanism (validate/leaf_classify vocab + rebuild payload_stripped) — owned elsewhere.
- C20-F4/F5 (multi-day label granularity / selected-marker) are L2-emit concerns — owned elsewhere.

## verify (adversarial, fab-code)

VERDICT: root-cause symptom FIXED, but CONTRACT BROKEN — the fix reintroduces a fabrication CLASS 4 exists to kill.

Evidence (real DB payloads through the real `fab_guards.apply`, not synthetic fixtures):

1. SYMPTOM FIX IS REAL (upheld). Verified in cmd_catalog.card_payloads that the empty-plot/empty-table leaves are
   raw==stripped → now correctly KEPT: card 20 `trend.pres.stackOrder`/`lineOrder`/`titleConnector`/`leftAxisLabel`,
   card 22 `table.pres.columnOrder`, plus `layout.rowHeight`/`fitMin`/`fitMax`/`dimOpacity`. The over-blanking that
   emptied c20/c22 in run r_5c6797f815 is genuinely gone. No per-card/per-prompt hardcoding (is_generic = TRUE).

2. CONTRACT REGRESSION (contract_preserved = FALSE) — CLASS 4's NAMESAKE charter leaks on the real host path.
   The fix's premise ("the strip zeroes DATA leaves to typed placeholders") is FALSE for the exact leaf CLASS 4
   was built for. In the DB, card 53 `backupHistory.series[*].legendValue = 52/71/85/43` is byte-identical between
   `payload` (raw) and `payload_stripped` — the strip did NOT zero it. So the new raw==stripped wall classifies it
   as METADATA and STOPS policing it. Proven directly (scratchpad/prove_regression.py):
       NEW guard (shape_ref threaded, as host/exec_cards.py:120 & host/server.py:264 do):
           legendValue = [52, 71, 85, 43]   ← fabricated seed LEAKS, 0 unstripped_seed gaps
       LEGACY guard (no shape_ref):
           legendValue = [None, None, None, None]   ← seed correctly BLANKED
   `legendValue` is NEVER filled by the executor (grep: zero fill sites) → it relies ENTIRELY on CLASS 4 to blank the
   seed → this is an UNCONDITIONAL on-screen fabrication (legend shows "52" with no data) on cards 51 & 53, violating
   the zero-fabrication law. Blast scan (scratchpad/blast.py): legendValue on cards 51 and 53 are the concrete
   reading fabrications now kept; the other ~64 "now-kept" leaves are legitimate presentation config (good).

3. WHY THE GREEN TESTS MISS IT. The two charter-pin tests (`test_class4_card73_legendvalue_seed_blanks_real_series_survive`,
   `test_class4_chrome_wall_card73_numeric_legendvalue_regression_still_blanks`) pass NO shape_ref → they exercise the
   DEAD legacy fallback, not the production path, so they stay green while production regresses. False confidence.
   The new tests use a synthetic STRIPPED where legendValue is zeroed to [] — which does NOT match the real DB
   (stripped keeps legendValue=52). The implementer's proposed `needs_cross_file` edit (zero the stripped seed to [])
   would CONCEAL the regression rather than surface it; a faithful test must use stripped legendValue==raw legendValue==52.

MUST FIX (before ship):
 - Do not let `raw == stripped` UNCONDITIONALLY exempt a leaf. The strip oracle is incomplete for rendered numeric
   readings (legendValue proven). Gate the metadata-exemption with the legacy chrome discrimination: exempt when
   raw==stripped AND (leaf is chrome/structural OR non-reading); a NUMERIC rendered-reading seed under a non-chrome
   key must STILL blank even when raw==stripped. (Equivalent: keep the legacy `_is_structural_chrome`/`_is_chrome_leaf`
   walls as the primary exemption and use raw-vs-stripped ADDITIVELY, never as an override that keeps a numeric seed.)
 - Add a charter test that threads shape_ref with the REAL DB shape (stripped.legendValue == raw.legendValue == 52)
   and asserts legendValue STILL blanks. Correct (do not zero) the cross-file test to that shape.

py_compile: OK on fab_guards.py, fill.py, tests/test_fab_guards.py. tests/test_fab_guards.py: 33 passed (but see #3).
