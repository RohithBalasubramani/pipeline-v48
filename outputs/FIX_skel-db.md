# FIX skel-db — presentation-numeric PRES leaves misclassified as DATA (DEBUG B6)

## Root cause
`validate/leaf_classify.py` classifies ANY numeric leaf as DATA unless its key is a member of
`vocab.element_chrome_keys` (per-leaf exempt) or `vocab.chrome_subtree_keys` (whole-object exempt).
Presentation-dimensional keys were missing from both rows, so `strip_to_placeholders` zeroed them in
`card_payloads.payload_stripped` (build-time) → the executor has no column to fill "rowHeight" → the leaf ships
`null` (cause `unbound_by_emit`), collapsing table row-height / column-fit / rail decimals / line-stack dim opacity.
Card 22 `layout={rowHeight:20,...}` was stored as `{rowHeight:0.0,...}`.

## The generic fix (AI-first: DB rows before code — NO classifier code change)
Two `cmd_catalog.app_config` vocab rows extended, in their canonical single-home seed files:

1. `vocab.chrome_subtree_keys` (home: `db/fix_ieee_limit_chrome_subtree.sql`) — added the OBJECT-valued
   presentation subtrees: **layout, fit, palette, dimopacity**. Subtree mechanism is correct because each is a
   whole object of presentation geometry/colour (dimOpacity `{line,stack}`, layout `{rowHeight,headerHeight,
   maxRowHeight}`, fit `{fit,fitMax,fitMin}`, palette `{colors…}`) — the entire subtree is kept byte-identical,
   including any future numeric sibling.
2. `vocab.element_chrome_keys` (home: `db/seed_vocab.sql`) — added the SCALAR numeric leaves that sit at the
   `pres` root (not under a subtree): **rowheight, headerheight, maxrowheight, fitmin, fitmax, minwidth,
   singlemodeminwidth, raildecimals**. Element mechanism is correct/required for minWidth/singleModeMinWidth/
   railDecimals (scalars, not objects); rowheight/headerheight/maxrowheight/fitmin/fitmax added as belt-and-braces
   (also covered by the layout/fit subtree keys) so a card that ever emits one standalone stays protected.

Both are lowercased (the classifier does `str(k).lower()` exact match). There is NO code default in
`leaf_classify.py` for these two accessors (they return `set()` on DB miss), so nothing to keep in sync there —
the seed files ARE the single home. Live rows updated by re-running the two idempotent seed files.

`payload_stripped` rebuilt via `scripts/build_stripped_payloads.py` (155 rows) after seeding.

## Why generic (all cards, not just card 22)
The added keys are GENERIC presentation concepts that recur across the catalog (distinct-card counts from
`card_payloads.payload`): layout 3, fit 2, palette 4, dimOpacity 2, minWidth/singleModeMinWidth/railDecimals 1.
None is a per-card/per-prompt branch; they are pixel/format geometry that is NEVER a measured value, so exempting
them can only KEEP chrome byte-identical — it can never strip a data leaf or fabricate a measurement.

## Rebuild diff — confined, zero DATA leaves changed (CAUTION check)
Before/after diff of `payload_stripped` (backup table `card_payloads_backup_fix_voltfix`): **59 leaves changed,
all CHROME/reference constants restored from a fabricated 0.0/absent to their real design default; zero measured
data leaves changed.** Two groups:
- **(a) my keys** (cards 20/22/24/26): layout.rowHeight 0.0→20, fit.fitMin 0.0→120, dimOpacity.line 0.0→0.4,
  minWidth 0.0→1240, singleModeMinWidth 0.0→900, etc. (railDecimals 0→0, no byte change but now classified chrome
  → no longer unbound_by_emit at exec.)
- **(b) pre-existing pending rebuild** (cards 47/61/62/65): IEEE-519 reference constants limitPct/scaleMaxPct/
  defaultLimit/limit (8/16/8/1), axis `domain` bounds, and warn/trip threshold text — governed by chrome_subtree
  keys **already present in the live row before I touched it** (limitpct/scalemaxpct/defaultlimit/axes/limit). The
  stale Jul-6 22:09 build had zeroed them (fabricating an "IEEE 519 Fail" badge + collapsed axes); the rebuild
  correctly restores them. Not caused by my edit — surfaced because `payload_stripped` was overdue for a rebuild.
Every changed leaf equals its `raw_default` and is design chrome. Spot-check: card 22
`payload_stripped.table.pres.layout = {"rowHeight":20,"headerHeight":28,"maxRowHeight":28}`, `minWidth=1240`,
`columns[0].fit={"fit":true,"fitMax":280,"fitMin":120}`.

## Verifier alignment (scripts/rescan_stripped_payloads.py)
`rescan_stripped_payloads.py` (the payload_stripped verifier) previously false-positived on `element_chrome_keys`
numeric leaves: its numeric-seed scan only exempted `chrome_subtree_keys`, so it flagged decimals/width/warn/trip/
from/to/legendValue/index (65 hits) that `leaf_classify` sanctions as chrome — the verifier disagreed with the
classifier it verifies. This was PRE-EXISTING (65 leaks on the OLD payload); my minWidth/singleModeMinWidth element
additions extended it by 2. Fixed by threading `vocab.element_chrome_keys` into `scan_classes` and exempting a
numeric leaf whose key is an element-chrome key (the SAME denylist leaf_classify uses). This cannot hide a real data
seed (a measured value never lives under a chrome key). After the fix rescan is fully GREEN:
`numeric=0 temporal=0 boolean=0 embedded=0 axis_strings=0 event_skeleton=0`, fixed-point 0, dict-broken 0.

## Acceptance cases
- card 22 table renders with real row height (20) and column fit bounds (was 0.0 → collapsed rows).
- card 21 railDecimals now chrome (0), no longer `unbound_by_emit` null.
- cards 20/24 line/stack dimOpacity restored (0.4/0.35) — trend/timeline dim styling honest.
- card 47 IEEE-519 verdict computed against real 8/16/8 limits (no fabricated "Fail" badge).
- Generic: any table/series/rail card's layout/fit/palette/dimOpacity/minWidth/railDecimals survives the strip
  byte-identical.

## Self-checks run
- `python3 -m py_compile` on both edited scripts + new test: OK.
- Rebuild: `build_stripped_payloads: rows built = 155`.
- Verifier: `rescan_stripped_payloads … RESULT: ZERO — all classes clean, idempotent, dictionaries preserved`.
- New focused test `tests/test_presentation_chrome_kept.py`: 2 passed (DB-free, monkeypatched vocab).
- Neighboring strip/classify tests (residual_seed_strip, stored_skeleton_retire_strip, strip_provenance_and_blank,
  fill_chrome_axes_preserved): 31 passed.

## Files changed
- `db/seed_vocab.sql` — element_chrome_keys += presentation-dimensional scalar keys.
- `db/fix_ieee_limit_chrome_subtree.sql` — chrome_subtree_keys += layout/fit/palette/dimopacity.
- `scripts/rescan_stripped_payloads.py` — verifier now exempts element_chrome_keys in the numeric-seed scan.
- `tests/test_presentation_chrome_kept.py` — new focused unit test (B6 lock).
- DB: live `cmd_catalog.app_config` two rows updated; `card_payloads.payload_stripped` rebuilt (all 155 rows);
  backup table `card_payloads_backup_fix_voltfix`.

## No classifier code change / no cross-file need
`validate/leaf_classify.py` unchanged — the fix is entirely DB-row-driven, exactly as the AI-first order prescribes.

## verify (adversarial) — VERDICT: UPHELD, generic, contract preserved; regression risk LOW

Re-derived the root cause and re-ran the checks independently. Evidence, not the implementer's word:

**Root cause fixed (upheld=true).** `leaf_classify._chrome_subtree_keys()`/`_chrome_element_keys()` both return
`_vocab_keys(...)` with NO code default (confirmed lines 36-48) — the seed rows ARE the single home, no code drift.
Live rows now carry the added keys (psql: chrome_subtree_keys += layout/fit/palette/dimopacity; element_chrome_keys
+= rowheight/headerheight/maxrowheight/fitmin/fitmax/minwidth/singlemodeminwidth/raildecimals). Spot-check of the two
table-layout cards: raw `layout={rowHeight:20,headerHeight:28,maxRowHeight:28}` == payload_stripped byte-identical
(feeder-pq-table-card AND other-panels); other-panels minWidth 1240, singleModeMinWidth 900, fit0 {fit,fitMax:280,
fitMin:120} all restored. The strip→null→unbound_by_emit chain is broken at its source.

**Generic (is_generic=true).** Pure structural presentation vocabulary (layout/fit/palette/dimOpacity + pixel/format
scalars). Zero per-card/per-prompt/per-asset branch; classifier consults the DB rows uniformly. element_value_keys ∩
new element_chrome_keys = ∅ (no key is both fillable and chrome).

**Contract preserved (contract_preserved=true).**
- Backup diff (card_payloads_backup_fix_voltfix vs live): exactly 59 changed leaves, ALL chrome/reference constants
  (domain×12, limitPct×8, scaleMaxPct×8, defaultLimit×4, warn/tripText.value×6, fitMin/fitMax×8, rowHeight/
  headerHeight/maxRowHeight×6, dimOpacity line/stack×4, minWidth/singleModeMinWidth/limit×3). ZERO genuine measured
  data leaves altered (no vAvg/current/kw/total/panels touched). skel-db "must not alter DATA leaves" — HOLDS.
- rescan verifier still does its job after the el_keys exemption: constructed test — a genuine seed vAvg=233.7 under a
  data key is STILL flagged `numeric`; chrome numbers under rowheight/minwidth/decimals are exempted. The exemption
  mirrors the SAME denylist leaf_classify uses, so verifier==classifier; a real measurement never lives under a chrome
  key. Full rescan: 155 rows, all classes 0, fixed-point 0, dict-broken 0, null 0 → GREEN.
- Over-exempt guard: test `strip.stats.total` genuine measurement still DATA (honest-strips to 0). New unit test 2/2.

**Scope/ownership note (not a defect).** Changed files (seed_vocab.sql, fix_ieee_limit_chrome_subtree.sql,
rescan_stripped_payloads.py, test) differ from the stated owned list (leaf_classify.py, build_stripped_payloads.py),
and needs_cross_file was left empty. BUT leaf_classify.py was correctly NOT modified (AI-first: DB rows before code),
and FIX_fab-code.md line 70 explicitly DISCLAIMS "validate/leaf_classify vocab + rebuild payload_stripped — owned
elsewhere" to skel-db. So no parallel-agent collision exists on these files. fab-code's `raw==stripped` metadata wall
in fact DEPENDS on this rebuilt payload_stripped being chrome-correct — complementary, not conflicting.

**Regression risk: LOW.** Additive vocab + chrome-only payload_stripped rebuild + verifier alignment. Two things the
integrator should KNOW (neither a blocker): (1) the rebuild's blast radius is wider than the two B6 vocab edits — it
also restored pre-existing-pending IEEE/axis/warn-trip chrome on cards 47/61/62/65 governed by axes/limit keys already
live but stale in the Jul-6 skeleton (correct anti-fabrication restore, verified all-chrome); (2) palette/limit/axes as
whole-subtree keys now keep their numeric leaves byte-identical, slightly overriding rescan's mixed-tier "palette
numbers are data" intent — correct since these are presentation/config containers, never measurement homes.

No must_fix defects.
