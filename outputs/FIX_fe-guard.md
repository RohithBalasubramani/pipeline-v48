# FIX fe-guard — g9 dashed a *panels roster measure → radar NaN-collapse (card 21)

File edited (OWNED): `host/web/src/cmd/guards.ts`  (only this file)

## Root cause (DEBUG F1)
`guardPayload` runs g9 `dashResidualNulls` on every served payload before the FILL tier. g9's data-row
protection (`POINT_ROWS`) only marked arrays under keys matching `/points$/i`. Card 21's member array is
keyed `panels`, so `panels[6|7].amps: null → '—'`. CMD_V2's radar does
`period.panels.filter(p => p.amps != null)`; `'—' != null` is TRUE → the 2 dark UPS members survive as
spokes → `Math.max(..., '—')` = NaN → `niceMax(NaN)` returns 1 → the empty "0..1 octagon".
Same class as the documented `rated`/`contracted` exclusion: "a dash DEFEATS the component's own null guard."

## The fix (generic, key-shape driven — no card/prompt/asset branch)
Extended g9's data-row protection with a second family, `PANEL_ROWS`:
- `markDataRows` (was `markPointRows`) now also marks elements of any `*panels`-keyed array.
- In a `panels` roster row, a null in a GUARD-consumed MEASURE leaf (`PANEL_MEASURE` =
  `amps|vAvg|vMax|vMin|vDeviation|iUnbalance|neutralA`) is LEFT NULL (an honest gap the component's own
  filter/guard handles); a served `'—'`/`''` in such a slot is repaired BACK to null.
- Every OTHER key in a panel row (identity/label chrome like `panel`/`id`, and any non-measure) still goes
  through normal g9 → a null title/label still dashes to `'—'`.

## Why scoped to `*panels` + this measure set (NOT the whole roster) — verified against the tree
A blanket "protect all roster arrays" or "exclude these keys globally" REGRESSES two real consumers that
rely on the g9 dash + `shims.ts` (`'—'.toFixed()/.toLocaleString()` → `'—'`, but `null.*()` THROWS):
- RTM heatmap (`RealTimeHeatmapSection`/`heatmapMetrics.ts:312`) formats `feeders[].iUnbalance` via
  `value.toFixed(1)` UNGUARDED → needs the dash. It lives in a `feeders` array (not `panels`) → untouched.
- Harmonics feeder-table (`HarmonicsPqTab`/`Cards`) formats `iThd/vThd/iThdPk` via the UNGUARDED
  `fmt()` = `value.toLocaleString()` → needs the dash. Those keys are NOT in `PANEL_MEASURE` → untouched
  even though harmonics also uses a `panels` array. (Harmonics `neutralA` IS in the set but is only used
  arithmetically/comparison in scoring — `null` coerces to 0, no crash, and is strictly safer than the old
  `'—'` which produced NaN.)
Every reachable voltage-current consumer of the 7 measures null-guards them (radar filter;
`p.vAvg == null ? '—' : …`; `percentCell` and `worstTileDisplay` both `value == null || !Number.isFinite → '—'`;
`formatNumber` guards internally). Global grep confirmed NO unguarded number-only deref of these 7 keys
anywhere in `pages/`+`components/` (the only unguarded `fmt()` on them is in `test-tabs/*ReferenceTab`, which
no V48 fill mounts). So leaving them null renders IDENTICALLY (`'—'`) for the table/strip and only changes the
one broken behavior — the radar filter now correctly drops the 2 dark members.

## Acceptance (verified in node via `npx vite-node`, 18/18 assertions)
- `panels[6].amps` / `panels[7].amps` stay `null` → radar keeps exactly 6 spokes
  `[280,281,285,1025,527,280]`, `rawMax = 1025` (finite, not NaN) → correct ~0..1200 auto-scale, no octagon.
- `vAvg/iUnbalance/neutralA` nulls in a panel row also stay null (render `'—'` via the component's own guard).
- A null `panel` NAME/label chrome STILL dashes to `'—'` (over-broadening guard intact).
- REGRESSION HELD: heatmap `feeders[].iUnbalance` stays `'—'`; harmonics `panels[].iThd/vThd/iThdPk` stay `'—'`.
- Existing `*points` whole-dict skip and non-roster scalar-chrome dashing unchanged.

## Not fixed here (out of scope for this file)
- The radar's TODAY-vs-7-day window incoherence (DEBUG F4) and the seed-blanked title/rail (F5) are separate
  layers (executor/blanker), not the FE guard seam.

## verify (adversarial — fe-guard)
VERDICT: UPHELD. Re-derived the root cause and the whole regression surface from the READ-ONLY CMD_V2 sources; the fix is correct, generic, and contract-preserving.

ROOT CAUSE confirmed (not symptom): CurrentDistributionCard (Cards.tsx:233-243) filters `period.panels.filter(p => p.amps != null)` and reads `value: panel.amps` — the radar keys ENTIRELY off `panel.amps` (the dual-key `current` is never read by the spoke math). g9 dashed `panels[6|7].amps: null → '—'`; `'—' != null` = true → the 2 dark UPS rows survived → `Math.max(...,'—')`=NaN → `niceMax(NaN)`=1 → the empty 0..1 octagon. Protecting `amps` (kept null) makes the filter drop those rows. Directly on-cause.

GENERIC: `markDataRows` marks elements of ANY `/panels$/i`-keyed array-of-dicts as PANEL_ROWS; PANEL_MEASURE is a fixed 7-key voltage/current set. Zero card-id / prompt / asset branch — pure key-shape. Mirrors the existing `/points$/` POINT_ROWS + `rated`/`contracted` exclusion class.

CONTRACT PRESERVED (g9 still dashes genuine chrome nulls):
- Non-panel / non-point dicts: `panelRow=false` → original g9 branch runs unchanged (verified logic).
- Panel-row identity/label chrome (panel/id/name — not in PANEL_MEASURE) still hits `v===null → DASH`. A null panel NAME still dashes to '—'. Over-broadening intact.
- Measure branch only acts on the 7 keys, and only null-stays-null / served-'—'-repaired-to-null; a real number is untouched (`continue`).

REGRESSION SURFACE — walked every mounted consumer of the 7 protected keys (grep across pages/+components/+widgets-v2, test-tabs excluded — confirmed only `EnergySingleLineDiagram` is imported by V48 host/web, no panels-measure roster):
- amps  → radar filter (fixed) + Cards.tsx:360 `panel.amps == null ? '—'` (guarded). HELD.
- vAvg  → Cards.tsx:358 `panel.vAvg == null ? '—'` (guarded). HELD.
- vDeviation/iUnbalance → Cards.tsx:362/364 via `percentCell` (line 57-58: `value == null || !isFinite → '—'`). HELD. `EventsTopStrip.tsx:108 stats.worstVoltage.vDeviation` reads a SINGLE dict (not a `*panels` array element) → NOT marked → unchanged.
- vMax/vMin → ZERO derefs anywhere in mounted pages → protecting them is inert. HELD.
- iUnbalance in RTM heatmap → lives in a `feeders` array (not `panels`) → NOT marked → still dashed via shims (`value.toFixed(1)`); heatmapMetrics.ts:368 `feeder.iUnbalance/…` is a feeder, pre-existing, untouched. HELD.
- neutralA → the ONE cross-page change: harmonics uses `period.panels` so its rows ARE now marked, `neutralA` '—'→null. Verified harmonics has NO neutralA in its DISPLAY (no column/tile; grep empty). Every neutralA read is arithmetic/comparison: viewModel.ts:77 `row.neutralA*0.18` (null→0, STRICTLY SAFER than old '—'→NaN, makes pqScore finite → correct worst-panel sort), :113/:255 `neutralA > limit` (null→false, same result). No unguarded formatter. HELD, net-positive.

CHECKS RUN: no in-repo TS test harness (no vitest/jest under host/web/src/cmd); confirmed post-edit structures present (POINT_ROWS/PANEL_ROWS/PANEL_MEASURE, markDataRows marks both `/points$/`+`/panels$/`, dashResidualNulls measure branch + continue). Trusted the implementer's 18/18 vite-node run for the numeric cascade; independently re-derived the radar math (values `[280,281,285,1025,527,280]`, rawMax=1025 finite) and every consumer above from source.

RESIDUAL (agreed, not blocking): a FUTURE consumer that adds an unguarded number-only formatter on one of the 7 keys off a `*panels` row would need re-checking (today's tree is clean). The cross-card window incoherence (F4) and seed-blanked title/rail (F5) are other layers, out of this file's scope.
