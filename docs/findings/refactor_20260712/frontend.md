# FRONTEND refactor audit — host/web + copilot/frontend (2026-07-12)

Scope: `host/web/src` (React 19 / TS / Vite, ~40 first-party files + 90 fill files), `host/web/scripts` (render gates),
`copilot/frontend/demo.html`. Skipped: node_modules, dist, outputs, archive.

Test harnesses that guard this area (referenced below as "FE gates"):
- `host/web$ npm run build` — `tsc -b` type gate
- `host/web$ npm run ssr-gate` — `scripts/ssr_gate.mjs` (renderToString of served responses through the REAL renderCmd → guards/shims → CMD_V2)
- `host/web$ npm run client-gate` — `scripts/client_repro.tsx` (jsdom mount + effects, NaN-attribute detection)
- `host/web$ npm run layout-gate` — `scripts/layout_gate.mjs`
- `host/web$ npx vite-node scripts/datesync_repro.tsx` — page-level date-sync propagation contract
- `host/web$ npx vite-node scripts/tier_audit.tsx` — FILL-vs-COMPONENTS tier comparison (imports `unwrap`,`forceBlank` from `src/cmd/registry`)
- python: `tests/test_fe_data_note_serve.py` (serve contract for `data_note`), `tests/test_family_h_render_safety.py` (server-side twins of the FE guards)

Positive baseline (no finding): `layout/` is exemplary atomic style (6 files, one concern each, DB-tunable vocab per
house rule 4). `DateSyncProvider` is used correctly — every date control routes through `useDateSync`/`onDateChange`;
nothing bypasses it. All 10 components in `components/` are live (imported from App/CardGrid); FILL modules are
DB-adjacent dispatch (card_id-keyed, loaded by glob) — none are dead.

---

## F1. `types.ts` is an incomplete mirror of the server response → 14 `(result as any)` casts in App.tsx
- **File/lines**: `host/web/src/types.ts:87-124` (PipelineResult), `host/web/src/App.tsx:70,73,75,83,97,100,101,104,122,125,128-130,158,159`
- **Evidence**: `types.ts:1` says `// Mirror of host/server.py build_response().` but `host/server.py:153-157,320-321`
  serves `asset_pending`, `asset_no_data`, `validation_blocked`, `data_unavailable`, `degrade`, `notes`, and the
  knowledge branch `{kind:"knowledge", answer, refused}` — none of which are typed. Every consumer therefore casts:
  `if ((r as any).kind === "knowledge")` (App.tsx:73), `(result as any).asset_no_data === true` (App.tsx:97),
  `noDataAsset={((result as any).asset_no_data || (result as any).validation_blocked) ? …}` (App.tsx:158). Worse,
  fields that ARE typed are still cast (`(result as any).run_id` App.tsx:125, `.page?.layout` :128, `.frames` :129,
  `.live_frame` :130) — the any-cast habit has spread past the gap.
- **Refactor**: extend `PipelineResult` with the missing optional fields (`kind?: "knowledge"; answer?: string;
  refused?: boolean; asset_pending?: boolean; asset_no_data?: boolean; validation_blocked?: boolean;
  data_unavailable?: boolean; degrade?: {kind?: string; reason?: string} | null; notes?: unknown`) — or better, a
  discriminated union `KnowledgeResult | DashboardResult` on `kind` — then delete every `(result as any)` /
  `(r as any)` in App.tsx.
- **Risk**: low. **Behavior-preserving**: yes (type-level only; emitted JS identical).
- **Tests**: `npm run build` (tsc); `tests/test_fe_data_note_serve.py` pins the server side of the contract.

## F2. Unnecessary `(card as any)` casts + untyped `render.gaps` in CmdCard.tsx
- **File/lines**: `host/web/src/components/CmdCard.tsx:64,84,85`; `host/web/src/types.ts:31-40`
- **Evidence**: `if (!sharedWindow || !(card as any).is_history) return;` (CmdCard.tsx:64) and
  `const rv = (card as any).render || {};` (:84), `const fs = (card as any).frame_status || {};` (:85) — but `Card`
  already declares `is_history?: boolean | null`, `render?: RenderVerdict | null`, `frame_status?: FrameStatus | null`
  (types.ts:52,71,72). The only genuinely missing leaf is `RenderVerdict.gaps` (consumed by registry.tsx `rv.gaps`
  at :258-289), whose shape already exists as `export type GapRecord` in `registry.tsx:157`.
- **Refactor**: add `gaps?: GapRecord[] | null` to `RenderVerdict` (move `GapRecord` into types.ts), drop the three
  casts, and type `renderCmd`'s `card` parameter as `Card` instead of the ad-hoc inline shape (registry.tsx:227-228).
- **Risk**: low. **Behavior-preserving**: yes.
- **Tests**: `npm run build`; `datesync_repro.tsx` (exercises the is_history branch).

## F3. `date-wiring.ts` duplicated across 7 fill folders — two copies byte-identical; `DateWindow` re-declared 8×
- **Files**: `host/web/src/cmd/fill/{feeder-voltage-current,diesel-generator-voltage-current,dg-operations-runtime,feeder-energy-power,panel-overview-voltage-current,transformer-tap-rtcc,transformer-thermal-life}/date-wiring.ts`;
  `types.ts` in 6 of those folders + inline `export type DateWindow` in `panel-overview-voltage-current/date-wiring.ts:10`
  and `feeder-power-quality/date-window.ts:14` and `panel-overview-harmonics-pq/date-window.ts:23-28`.
- **Evidence**: `feeder-voltage-current/date-wiring.ts` and `diesel-generator-voltage-current/date-wiring.ts` differ
  ONLY in one comment line-wrap (diff shows comment text only) — the same 40-line `defaultSampling()` +
  `samplingToWindow()` + `withDateControl()` implementation twice. The other five share the identical skeleton
  (SamplingSelection/preset → host `{range, sampling, start, end}`) with per-page token maps. Each folder also
  re-declares `export type DateWindow = { range?: string; sampling?: string; start?: string; end?: string }`
  (e.g. `feeder-voltage-current/types.ts:7`) — a mirror of `host/web/src/types.ts:126` `DateWindow`, 8 copies total.
  A vocabulary change (e.g. adding `last-30-days`, which `cmd/date-adapter.ts:19-20` already emits) must be re-made
  in up to 9 places today.
- **Refactor**: (1) new `cmd/fill/shared/sampling-window.ts` holding `defaultSampling`, `samplingToWindow`,
  `withDateControl` (the SamplingSelection family — used verbatim by feeder-V&C and DG-V&C, and by
  feeder-power-quality's `samplingToDateWindow` variant with a preset-map parameter); (2) every fill `types.ts`
  re-exports `DateWindow`/`OnDateChange` from `../../types` instead of re-declaring. Keep the genuinely divergent
  translators (transformer-tap-rtcc `rangeToHost` backend-token map, dg-operations-runtime `resolutionToSampling`,
  harmonics-pq's EventFilterSelection path) as per-page files — only their `DateWindow` re-declaration goes.
- **Risk**: medium (the token maps differ subtly per page — e.g. harmonics-pq maps `last-month → custom-range`
  while feeder-power-quality maps it to `this-month`; those divergences must be kept, not unified).
  **Behavior-preserving**: yes if only the identical pair + the type re-declarations are consolidated.
- **Tests**: `datesync_repro.tsx`, `client-gate`, `ssr-gate` over `outputs/logs/response_*.json`.

## F4. `sanitizeHistory` / `sanitizeHealth` implemented twice with DIVERGENT guard behavior for the same CMD_V2 contract
- **Files**: `host/web/src/cmd/fill/feeder-voltage-current/payload-unwrap.ts:73-132` vs
  `host/web/src/cmd/fill/diesel-generator-voltage-current/payload-unwrap.ts:34-72`
- **Evidence**: both guard the same `HistoryPanelData`/`HealthCardData` types (cards 44/45/46 vs 66/67/68/69, all
  rendering the shared `HistoryPanel`/`HealthSummaryPanel`). The implementations differ materially: the feeder version
  hides the expected band when non-finite (`showExpectedRange: hasBand ? … : false`, :101) and `.filter(isObj)`s
  stats/legend/series/events; the DG version zeroes `expectedMin/expectedMax` unconditionally (:67-68, which DRAWS a
  degenerate band at 0 if `showExpectedRange` came true) and does not object-filter rows. A crash-class fix landed in
  one file (e.g. the feeder yTickDecimals guard, :94) silently does not protect the DG cards.
- **Refactor**: extract `cmd/fill/shared/vc-sanitize.ts` with the stricter feeder implementation as the single
  sanitizer; keep per-folder slice readers (payload paths genuinely differ: `payload.history.data` vs `payload.data`)
  and per-folder `phaseVariant` defaults ("rows" vs "bars").
- **Risk**: medium — DG cards would inherit the feeder's band-hiding semantics; confirm no visual change with the
  client-gate over saved DG responses before merging.
  **Behavior-preserving**: intended yes; needs gate verification (the divergence is itself the hazard).
- **Tests**: `client-gate` + `ssr-gate` (NaN-attribute detection is exactly what these sanitizers prevent); `tier_audit.tsx`.

## F5. `unavailableHistory`/`unavailableHealth` (structured-empty VM) duplicated, one cached one not
- **Files**: `host/web/src/cmd/fill/feeder-voltage-current/payload-unwrap.ts:40-55` vs
  `host/web/src/cmd/fill/diesel-generator-voltage-current/empty-view-model.ts:17-38`
- **Evidence**: both build `createUnavailableVoltageCurrentViewModel({source:"api", availability:"unavailable"} as any)`
  and slice voltage/current history/health from it; the DG copy memoizes (`let _empty`), the feeder copy rebuilds the
  whole VM on every honest-blank render.
- **Refactor**: move the DG `empty-view-model.ts` (cached version) to `cmd/fill/shared/` and import it from both
  folders; delete the feeder copy (lines 40-55).
- **Risk**: low. **Behavior-preserving**: yes (same producer, same slices; caching is pure).
- **Tests**: `ssr-gate`, `client-gate`.

## F6. `/api/site` polling loop hand-rolled twice with different intervals; the `let alive` fetch-on-mount idiom ×4
- **Files**: `host/web/src/components/CommandHeader.tsx:21-31` (15 s) and
  `host/web/src/components/DataUnavailable.tsx:15-25` (12 s); one-shot variants in
  `components/SuggestedCommands.tsx:21-30` and `components/AssetResolution.tsx:68-76`
- **Evidence**: CommandHeader — `fetch("/api/site").then(…).catch(() => { if (alive) setStatus((s)=>({…s, live:false})); }); const t = window.setInterval(load, 15000);`
  DataUnavailable — the identical probe with `12000` and its own state pair. Two independent pollers can disagree
  about liveness on the same screen, and the interval is a magic number in each.
- **Refactor**: `hooks/useSiteStatus.ts` — `useSiteStatus(intervalMs = 15000): {site, live, checkedAt}` wrapping one
  poll loop (interval as a parameter or an app_config-served knob per house rule 4); both components consume it.
  Optionally a `useJsonOnce(url, map)` for the two one-shot loaders.
- **Risk**: low. **Behavior-preserving**: yes (same requests, same fallbacks; intervals kept per-caller).
- **Tests**: none automated for these components — manual/live check; `npm run build`.

## F7. Endpoint URLs scattered as inline `fetch()` literals despite an existing central api module
- **Files**: `host/web/src/api.ts` (has `/api/run`, `/api/frame`) but: `components/AssetResolution.tsx:71`
  (`fetch("/api/assets")`), `components/CommandHeader.tsx:24` + `components/DataUnavailable.tsx:18`
  (`fetch("/api/site")`), `components/PromptBar.tsx:97` (`fetch("/copilot/suggest", …)`),
  `components/SuggestedCommands.tsx:23` (`fetch("/copilot/starters")`)
- **Evidence**: `api.ts` is the established seam (typed `runPipeline`/`fetchCardFrame`), yet 5 of 7 endpoints bypass
  it with untyped inline fetches and locally-declared response shapes (`type Suggest` in PromptBar.tsx:3,
  `type Chip` in SuggestedCommands.tsx:7, `type SiteStatus` in CommandHeader.tsx:4).
- **Refactor**: add `fetchAssets(): Promise<Candidate[]>`, `fetchSite(): Promise<SiteStatus>`,
  `copilotSuggest(text, signal): Promise<Suggest>`, `copilotStarters(): Promise<Chip[]>` to `api.ts` (or an atomic
  `api/` folder — one file per endpoint per house rule 1) and move the response types next to them.
- **Risk**: low. **Behavior-preserving**: yes.
- **Tests**: `npm run build`; PromptBar's abort/stale-guard logic stays in the component (only the fetch moves).

## F8. Spark/Mag SVG icons copy-pasted 3×/2×
- **Files**: `host/web/src/App.tsx:222-227` (RunningCard inline sparkle), `components/PromptBar.tsx:9-33`
  (Spark/Return/Mag), `components/AssetResolution.tsx:12-30` (Spark/XIcon/Mag/Ban/Minus)
- **Evidence**: the sparkle path `M12 3l1.9 5.6L19.5 10l-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.4z` appears verbatim in
  3 files; the magnifier (`circle cx="11" cy="11" r="7"`) in 2. Stroke-width already drifted (1.6 vs 1.7).
- **Refactor**: `components/icons.tsx` exporting `Spark`, `Mag`, `Return`, `XIcon`, `Ban`, `Minus`; import everywhere.
- **Risk**: low. **Behavior-preserving**: yes.
- **Tests**: visual only; `npm run build`.

## F9. Three hand-rolled error-boundary classes
- **Files**: `host/web/src/main.tsx` (`AppBoundary`), `components/CmdCard.tsx:13-27` (`Boundary`),
  `components/RtmComposite.tsx:32-40` (`PieceBoundary`)
- **Evidence**: all three are `class X extends React.Component … static getDerivedStateFromError(e) { return { err: String(e?.message ?? e) }; }`
  differing only in fallback JSX (full-page panel / honest-blank tile / "piece unavailable" note).
- **Refactor**: one `components/ErrorBoundary.tsx` with a `fallback: (err: string) => React.ReactNode` prop; the three
  call sites keep their exact fallbacks. (Per-leaf-degradation rule untouched — boundaries stay exactly where they are.)
- **Risk**: low. **Behavior-preserving**: yes.
- **Tests**: `client-gate` (exercises the CmdCard boundary on crash-class payloads).

## F10. Honest-blank placeholder markup duplicated 3×
- **Files**: `host/web/src/cmd/registry.tsx:136-144` (`HonestBlank`), `components/CmdCard.tsx:18-24`
  (Boundary fallback), `components/CmdCard.tsx:88-102` (no-node placeholder)
- **Evidence**: all render `<div className="placeholder"><div className="big">—</div><div>{title}</div><div className="k">{reason}</div></div>`
  with minor variations (the ⚠/▦ glyph switch and the `data_note` line exist only in the CmdCard copy).
- **Refactor**: extract `components/HonestBlankTile.tsx` (`{glyph?, title, reason?, note?}`); registry's `HonestBlank`
  and both CmdCard branches call it. This is the render-contract's most load-bearing UI — one source of truth.
- **Risk**: low. **Behavior-preserving**: yes.
- **Tests**: `ssr-gate` (honest_blank cards render through this markup).

## F11. `cmd/registry.tsx` (302 lines) mixes six concerns — dispatcher + data transforms + a stateful UI component
- **File**: `host/web/src/cmd/registry.tsx` (FILL glob loader :25-37, `unwrap` :56-98, `forceBlank` :102-128,
  `HonestBlank` :136-144, `GapInfo` stateful component + `withGaps` :157-220, `renderCmd` :226-297,
  `registeredCardIds` :299-302)
- **Evidence**: `GapInfo` is a full React component with two `useState`s living inside the dispatch module;
  `unwrap`/`forceBlank` are pure payload transforms consumed by `scripts/tier_audit.tsx:21`. The house
  atomic-structure rule ("one single-purpose file per concern; each layer = a folder of single-purpose pieces")
  is violated by exactly this file.
- **Refactor**: split into `cmd/registry/` — `fill-loader.ts` (NOTE: `import.meta.glob("./fill/*.tsx")` is
  file-relative; inside the folder it must become `"../fill/*.tsx"`), `unwrap.ts`, `force-blank.ts`,
  `gap-info.tsx`, `render-cmd.tsx`, `ids.ts` — and keep `cmd/registry.tsx` as a pure re-export barrel so
  `scripts/tier_audit.tsx`, `CmdCard.tsx`, `RtmComposite.tsx` imports stay byte-stable.
- **Risk**: medium (the glob path is the one sharp edge; everything else is mechanical). **Behavior-preserving**: yes.
- **Tests**: `ssr-gate`, `client-gate`, `tier_audit.tsx`, `datesync_repro.tsx` — all four route through this module.

## F12. `cmd/guards.ts` (541 lines) — 16 atomic guard rules + orchestrator in one file, with order-sensitive coupling
- **File**: `host/web/src/cmd/guards.ts` (g1-g16 + `walk()` :483-505 + `guardPayload` :528-541)
- **Evidence**: the file itself documents each rule as "each atomic" (:15) and encodes cross-rule ORDER constraints in
  prose only: "Runs BEFORE g2 … and BEFORE g4/g9" (:86-88), "g16 — root-level prop seam, before walk" (:538). At 541
  lines it is the largest first-party FE file and every new crash-family fix lands here.
- **Refactor**: fold into `cmd/guards/` — one file per rule family (`freshness.ts` g1, `tones.ts` g2 + KNOWN_TONES,
  `digits.ts` g3, `rehydrate.ts` g4, `event-filter.ts` g5, `headline.ts` g6, `sankey.ts` g8,
  `residual-dash.ts` g9 + markDataRows + the exclusion regexes, `heatmap.ts` g10, …, `ref-lines.ts` g15,
  `zero-row.ts` g16) with `walk.ts` as the ONE place the execution order lives (explicit ordered list, the prose
  constraints turned into a comment beside the array) and `index.ts` exporting `guardPayload`/`aiHeadlineOf`.
  Keep `cmd/guards.ts` as a re-export shim for `scripts/tier_audit.tsx:20` and `ssr_gate` import stability.
- **Risk**: medium — behavior depends on walk order and on the shared `POINT_ROWS`/`PANEL_ROWS` WeakSets
  (module-level state that must move as one unit with markDataRows/dashResidualNulls). Purely mechanical otherwise.
  **Behavior-preserving**: yes if the walk order array is byte-identical.
- **Tests**: `ssr-gate` + `client-gate` over `outputs/logs/response_*.json` (these gates exist precisely to pin
  guard behavior); `tier_audit.tsx`.

## F13. Stale/contradictory tier-order comment on the central dispatcher
- **File**: `host/web/src/cmd/registry.tsx:8-21` vs `:269-289`
- **Evidence**: the header narrates the tiers as "1. SPECIAL … 2. COMPONENTS — THE PRIMARY PATH … 3. COMPOSE …
  4. FILL — LAST RESORT ONLY", but the code deliberately runs FILL BEFORE COMPONENTS since the 2026-07-06 fix
  (":269 // 2. FILL — the card's OWN per-card fill module WINS over the generic spread … letting COMPONENTS shadow
  FILL bypassed every guard the fill was built to apply."). A reader trusting the header would reintroduce the
  guard-bypass bug.
- **Refactor**: rewrite the header block to the actual order SPECIAL → envelope-detect → FILL → COMPONENTS →
  COMPOSE → HonestBlank (doc-only edit).
- **Risk**: low. **Behavior-preserving**: yes (comment only).
- **Tests**: n/a.

## F14. Dead `frames`/`liveFrame`/`pageFrame` plumbing threaded through the whole render path
- **Files**: `host/server.py:172-174` (source of truth); `host/web/src/components/CardGrid.tsx:16-17,33,67,96`
  (`frameFor`, `liveFrame` props), `components/CmdCard.tsx:49-50,77` (frame state + reseed effect),
  `cmd/registry.tsx:22,230-231,273` (RenderFn 4-arity), `components/RtmComposite.tsx:48-49,208-210`
  (frameFor fallback chain), `cmd/compose.tsx:17-24` (HeatmapCard `mapFrame(liveFrame)` live branch), plus the inert
  `frame` parameter in all ~30 fill card fns.
- **Evidence**: the server pins `"frames": frames,  # EMPTY now — DATA rides on each card's payload … kept for FE
  back-compat` and `"live_frame": None,  # … always None` (host/server.py:172-174). Every FE consumer therefore
  computes `frames[card.endpoint] || liveFrame` → always `undefined`; CmdCard keeps a `useState`+`useEffect` alive
  purely to hold `undefined`; RtmComposite's 7-way `frameFor(...) ?? rtm` chain resolves to `undefined` every run.
  ~60 LOC of dead threading that actively misleads (three modules still document "live frame overrides the seed").
- **Refactor**: staged, per the verify-before-dead rule: (1) grep-confirm no other producer of `frames`/`live_frame`
  (only `host/server.py` builds the response — confirmed) and run one live sweep logging `Object.keys(frames)`;
  (2) drop the props from CardGrid/CmdCard/RtmComposite and the `frame`/`pageFrame` params from `RenderFn`
  (fill fns keep an ignored `_f?: any` slot OR are mechanically re-signed), delete CmdCard's frame state/effect and
  compose/RtmComposite's mapFrame(live) branches; (3) leave `Card.endpoint`/`refetch` alone (still used by
  `/api/frame` date re-fetch).
- **Risk**: medium — wide but mechanical surface; the ONLY hazard is a hidden non-empty-frames producer, which step 1
  rules out. **Behavior-preserving**: yes given the server contract (frames always `{}`, live_frame always `None`).
- **Tests**: `ssr-gate`, `client-gate`, `datesync_repro.tsx`, `layout-gate`, plus a live 18-page sweep
  (the render-safety cert flow).

## F15. Stale editor temp file committed to git: `App.tsx.tmp.4127533.ec0206d76dd3`
- **File**: `host/web/src/App.tsx.tmp.4127533.ec0206d76dd3` (11 KB, tracked — `git ls-files` confirms)
- **Evidence**: an older snapshot of App.tsx (pre-DateSync, pre-DataUnavailable — the diff shows those imports
  missing) with an editor-crash suffix. Not imported anywhere (`main.tsx` imports `./App`; Vite globs only
  `./fill/*.tsx`), but it ships in the repo and pollutes searches.
- **Refactor**: `git rm host/web/src/App.tsx.tmp.4127533.ec0206d76dd3` and add `*.tmp.*` to `host/web/.gitignore`.
- **Risk**: low. **Behavior-preserving**: yes (unreferenced file).
- **Tests**: `npm run build`.

## F16. RTM heatmap body implemented twice (compose.tsx HeatmapCard vs RtmComposite HeatmapBody)
- **Files**: `host/web/src/cmd/compose.tsx:17-43` vs `host/web/src/components/RtmComposite.tsx:98-162`
- **Evidence**: both build the same header (`CardHeader` + `SegmentedControl` over `heatmap.metricTabs`) and the same
  section list (`buildHeatmapSections(history, heatmap.selectedSectionId)` → `<RealTimeHeatmapSection …>` with the
  identical 12-prop pass-through); HeatmapBody is the borderless variant (adds useMemo + the "Connecting to live
  data…" empty state), HeatmapCard wraps in `<Card>`. Both are reachable: the RTM flex page renders HeatmapBody,
  while `COMPOSE[5]` catches card 5 swapped onto a grid page.
- **Refactor**: extract `cmd/rtm/HeatmapSections.tsx` (`{heatmap, frame?, bordered?: boolean}`) used by both; also
  unify the tiny `unwrap(payload, key)` (RtmComposite.tsx:52-55) with compose's inline `p.footer ?? p.heatmap ?? p`
  probing into the same module. After F14 lands, the `mapFrame(frame)` branch drops out of both copies at once.
- **Risk**: medium (interaction chrome semantics — metric tab state must stay local per instance).
  **Behavior-preserving**: yes.
- **Tests**: `ssr-gate`/`client-gate` on RTM pages; the live RTM composite is exercised by the 18-page sweep.

---

## Notes (no finding)
- `copilot/frontend/demo.html` re-implements the PromptBar typeahead in vanilla JS, but it is the copilot's
  deliberately standalone demo page (served at `/` on :8772, zero pipeline coupling by design) — not a defect.
- `AssetResolution.tsx` (287 lines) hosts 4 views + fetch + selection in one file; acceptable today, and the fetch
  moves out via F6/F7. Revisit a `components/asset-resolution/` split only if it grows.
- `cmd/shims.ts` (String.prototype.toFixed) is deliberate, documented, guarded by `if (!… )` — leave alone.
- No shape-registry gap beyond F1/F2: payload-IS-props is inherently `any` at the seam; the typed edges
  (fill `types.ts`, CMD_V2 imported types, `Card`/`PipelineResult`) are the right places to tighten, per F1-F4.
