# React frontend audit — pipeline_v48/host/web (lens: react)

Date: 2026-07-12. Scope: `/home/rohith/desktop/BFI/backend/layer2/pipeline_v48/host/web` (no `host/src` exists).
All file:line references were read directly during this audit.

## Overall assessment

The FE is small (~40 first-party files + 84 fill files), well-commented, and unusually disciplined about the
per-leaf-degradation and zero-fabrication contracts: three nested error-boundary layers (`main.tsx` AppBoundary,
`CmdCard` Boundary + try/catch around `renderCmd`, `RtmComposite` PieceBoundary), a deliberate 5-tier render dispatch,
and real render-cert harnesses (`scripts/ssr_gate.mjs`, `client_repro.tsx`, `tier_audit.tsx`, `datesync_repro.tsx` —
the date-sync contract is actually gated). Hooks usage is largely correct: fill "render functions" properly wrap
components (`card-73.tsx:23`, `card-18.tsx:34`) so hooks never run in plain calls; PromptBar has AbortController +
sequence-guard + client cache; polling effects all carry cleanup.

The real problems are: (1) the one data-honesty hole — a failed page-wide date re-fetch is silently swallowed and the
card keeps showing the old window's numbers; (2) enterprise deployability — the build depends on the literal path
`/home/rohith/CMD_V2` and that repo's `node_modules`, ships as ONE eager 2.47 MB chunk with three.js inside, and the
production runtime is the Vite dev server; (3) a large, admittedly heuristic defensive surface (guards/shims/unwrap)
whose enum mirrors and key-shape regexes will drift silently against the read-only CMD_V2 tree; and (4) dead
`frames`/`liveFrame` plumbing threaded through every render signature.

---

## Findings (ranked)

### F1 — HIGH · correctness/data-honesty: failed date re-fetch is silently swallowed; card shows the OLD window's data under the NEW date selection
- `src/components/CmdCard.tsx:63-68`:
  ```ts
  React.useEffect(() => {
    if (!sharedWindow || !(card as any).is_history) return;
    let live = true;
    fetchCardFrame(card, sharedWindow).then((p) => { if (live && p) setPayloadOverride(p); }).catch(() => {});
    return () => { live = false; };
  }, [sharedWindow, card]);
  ```
- `.catch(() => {})`: when `/api/frame` fails (the :5433 neuract tunnel historically flaps; the executor re-runs real
  queries per card so failures are expected), the card silently keeps its previous payload. Meanwhile the card's own
  date control (local state in the fill component, e.g. `card-18.tsx:51` selection state) already displays the NEW
  range. Result: numbers from window A labeled as window B — precisely the "mislabeled data" class the whole pipeline
  is engineered to prevent server-side.
- Also: no loading affordance during the re-fetch (which runs a real per-card executor round-trip), and no
  `AbortController` — only the state update is guarded, in-flight requests keep running server work.
- Fix (safe, additive): per-card refetch state (`loading | error`), surface error through the existing reason-ⓘ
  channel (`CmdCard.tsx:106-109`) or a small stale-window badge; pass an AbortSignal into `fetchCardFrame`
  (`src/api.ts:21-35` accepts none today).

### F2 — HIGH · deployability: the FE cannot be built anywhere but this machine — hardcoded CMD_V2 path + undeclared dependencies
- `vite.config.ts:8` — `const CMD_V2 = "/home/rohith/CMD_V2";` (also `fs.allow` line 23, watch-ignore line 28).
- `tsconfig.json:16` — `"@cmd-v2/*": ["/home/rohith/CMD_V2/src/*"]`.
- `package.json:14-17` — dependencies are ONLY `react` + `react-dom`. Everything the ~50 imported CMD_V2 components
  need (three.js, @react-three/fiber, d3-sankey, tailwind tokens…) resolves implicitly out of
  `/home/rohith/CMD_V2/node_modules` — confirmed present in the built bundle (`dist/assets/index-CICbP_yT.js` contains
  `WebGLRenderer`, `@react-three`).
- Consequences at enterprise scale: no CI build, no second deploy target, no container image, and — because CMD_V2 is
  version-unpinned — `guards.ts`' mirrored enums (see F7) drift against whatever happens to be checked out there.
- Fix (safe): `const CMD_V2 = process.env.V48_CMD_V2_PATH ?? …` (same pattern as `V48_HOST_API` on line 6); pin CMD_V2
  (git submodule/commit or a packed tarball dependency); declare the actual runtime deps in package.json.

### F3 — HIGH · observability: per-card render errors are invisible to operators — three catch layers, zero telemetry
- `src/components/CmdCard.tsx:75-80` — try/catch around `renderCmd` stores `renderErr` for the tile UI only; nothing
  is logged or reported.
- `src/components/CmdCard.tsx:13-27` — class `Boundary` has `getDerivedStateFromError` but NO `componentDidCatch`/log.
- `src/components/RtmComposite.tsx:32-40` — `PieceBoundary` likewise renders "piece unavailable" silently.
- Only the app-root boundary logs (`src/main.tsx:13`).
- The entire guards.ts surface exists because CMD_V2 components crash on blank leaves ("family H"). When CMD_V2
  changes and a new crash class appears in production, the FE will mask it as an honest-blank tile and nobody will
  know — the exact failure mode the render-verdict telemetry was built to avoid, re-introduced at the last hop.
- Fix (safe): `console.error` + a fire-and-forget POST (e.g. to the host's existing run-log seam) in all three catch
  points, keyed by card_id/run_id.

### F4 — MEDIUM · performance: one date pick = every card re-renders and every payload is deep-cloned twice; no memoization anywhere on the card render path
- `src/cmd/registry.tsx:244` `forceBlank(card.payload, …)` → `structuredClone` (line 113) on EVERY render of every
  card; then `registry.tsx:267` `guardPayload(p0)` → a SECOND `structuredClone` + full recursive `walk`
  (`src/cmd/guards.ts:528-541`).
- `src/components/DateSync.tsx:17` — context value `{ window, setWindow }` is a fresh object each provider render;
  every `CmdCard` consumes it unconditionally (`CmdCard.tsx:57`), so one `setSharedWindow` re-renders ALL cards
  (history or not), then each history card's fetch resolves → another re-render each.
- `renderCmd` output is never memoized (`CmdCard.tsx:77` re-invokes it every render), and
  `src/cmd/date-adapter.ts:52-57` builds a new `onRangeChange` closure per render while `unwrap`
  (`registry.tsx:56-98`) builds new prop objects — so even a `React.memo`'d CMD_V2 component could never bail out.
- With ≤14 cards this survives, but payloads carry full time-series; a single pick does O(2·N) deep clones + N guard
  walks + K executor refetches. This is the re-render storm hot path for live interaction.
- Fix (safe): in `CmdCard`, `useMemo(() => renderCmd(rc, …), [rc.payload, rc.render, sharedWindow])`; memoize the
  context value; hoist `dateControlProps` per card. (Keep the clones — they are the no-mutation contract — just stop
  re-running them per render.)

### F5 — MEDIUM · production runtime is the Vite DEV server; the committed dist build is stale and unused
- `vite.config.ts:20-33` — only a `server` block (`host: true`, port 5188, proxies). No `build` config; nothing in
  `host/server.py` serves static files; the documented runtime is Vite :5188.
- `dist/assets/index-CICbP_yT.js` mtime Jul 6 vs `src/` files edited Jul 9 (`App.tsx`, `scripts/datesync_repro.tsx`)
  — whatever `dist` was for, it is not part of the serve path and is now stale in-tree.
- Dev server in production = dev-mode React (slower, larger), unminified source served to every client, HMR websocket
  exposed on all interfaces, no caching headers, and a single Node process nobody supervises as a service.
- Fix: `vite build` + serve `dist/` (from the host API process or nginx) for the production port; keep :5188 for dev.
  Behavior-preserving for users (risky only in that it changes the serving topology).

### F6 — MEDIUM · bundle: single eager 2.47 MB chunk (709 KB gzip) with three.js inside; zero code-splitting
- `dist/assets/index-CICbP_yT.js` = 2,472,931 bytes (gzip 709,539). One chunk.
- Causes: `src/cmd/components.ts:3-54` statically imports ~40 CMD_V2 components; `src/cmd/registry.tsx:25`
  `import.meta.glob("./fill/*.tsx", { eager: true })` loads all 12 fill barrels (84 files) eagerly;
  `src/cmd/special.tsx:20` statically imports `CentralAssetViewer` — which drags the whole three.js +
  @react-three/fiber stack (confirmed in the bundle) into first paint for every user, though it renders only for
  asset_3d cards with a bound GLB.
- `grep React.lazy|Suspense` over `src/` → zero hits.
- Fix (safe): `React.lazy(() => import(...CentralAssetViewer))` + `<Suspense>` inside `Asset3dEnvelope`
  (`special.tsx:49-73` already has the SSR guard seam to hang it on); optionally `build.rollupOptions.manualChunks`
  to split cmd-v2 vendor code. GLB/draco payloads are runtime-fetched by URL, so they are already out of the bundle.

### F7 — MEDIUM · drift risk: guards.ts hand-mirrors CMD_V2's tone enums and key-shape contracts; a NEW legitimate CMD_V2 tone gets silently rewritten to 'info'
- `src/cmd/guards.ts:167-177` — `KNOWN_TONES` is a hand-copied union "mirrored per-map from the READ-ONLY CMD_V2
  sources"; `fixBadge` (guards.ts:185-194) rewrites any tone outside it to `"info"`. If CMD_V2 adds a tone (say
  `caution`), served payloads carrying it are silently re-toned — wrong chrome, no crash, no signal.
- Same class: `NULL_DASH_EXCLUDE` suffix regex (guards.ts:126), `PANEL_MEASURE` (guards.ts:332),
  `REF_LINE_TONES` (guards.ts:435) — all shape/name heuristics against code this repo does not control; and
  `src/cmd/shims.ts:49-50` mutates CMD_V2's exported `STATUS_PILL_TONE` map at module load.
- Counter-example done right: `guards.ts:102` imports CMD_V2's own `resolveEventFilter` instead of re-encoding it.
- Fix (safe): where CMD_V2 exports the maps (the comment at guards.ts:20-27 names them: `STATUS_PILL_TONES`,
  `PALETTE`, `KPI_STATUS_DOT_PRESETS`, `TONE_PRESETS`…), derive the key-sets by import; where not exported, add a
  standing assertion to `tier_audit`/`ssr_gate` that `KNOWN_TONES ⊇ Object.keys(map)` so drift fails the gate instead
  of shipping.

### F8 — MEDIUM · type-safety: the payload=props contract is fully untyped and shape-heuristic-routed
- 336 `any` annotations across `src/` (grep count). `src/cmd/components.ts:57`
  `COMPONENTS: Record<number, React.ComponentType<any>>`; `Card.payload: unknown` (types.ts:65) is immediately
  `any`-cast everywhere; every fill `CARDS` value takes `payload: any`.
- Routing itself is heuristic: `registry.tsx:259-261` detects envelopes BY KEY SHAPE before the FILL/COMPONENTS
  registries (`isTopologyEnvelope` fires on any payload with an `sld` key, `isAsset3dEnvelope` on `object`/`viewer` —
  special.tsx:89-97), and `unwrap` (registry.tsx:56-98) guesses the prop name by aliasing the single inner object to
  `data`/`vm`/`view` simultaneously. A payload key rename in L2/card_payloads, or a CMD_V2 prop rename, produces a
  silently-blank or mis-routed card that only the runtime harnesses can catch.
- This is a deliberate design ("payload IS the props") — the finding is that NOTHING checks it at compile time while
  two other layers (L2 emit + card_payloads seeds) can each change the shape independently.
- Fix (safe, incremental): type the `COMPONENTS` map entries against the components' actual prop types
  (`typeof Cmp50` props), generate per-card payload interfaces from the card_payloads seeds, and narrow
  `renderCmd`'s card parameter to `Card` from types.ts instead of the ad-hoc inline type (registry.tsx:227-228).

### F9 — MEDIUM · dead plumbing: frames/liveFrame/pageFrame are always empty but still threaded through the entire render stack
- Server: `host/server.py:126` `frames, frame_status = {}, {}`; `:172-174` served empty/None "for FE back-compat".
- FE keeps full plumbing alive: `src/types.ts:119-121` (`frames`, `frame_status`, `live_frame`);
  `src/App.tsx:129-130` passes them; `src/components/CardGrid.tsx:16-17` `frameFor` (always → null), `:67`, `:96`;
  `src/components/CmdCard.tsx:48-50` (a `frame` useState + reseed effect that only ever stores null), `:77`;
  `src/cmd/registry.tsx:22` RenderFn signature `(payload, frame?, onDateChange?, pageFrame?)`;
  `src/components/RtmComposite.tsx:48-49, 208-210, 221-234` (frame resolution cascade over always-undefined values);
  `src/cmd/compose.tsx:107` `(payload, liveFrame?)`; every fill barrel signature (`fill/*.tsx` `frame?: any`).
- Cost: every new fill/card author must thread and reason about inert parameters; `CmdCard`'s dead `frame` state
  invites future misuse; `RtmComposite`'s `liveRailVM`/`mapFrame` branches (:59-70, 101-105) are unreachable code
  carrying real complexity.
- Fix (safe mechanically, wide diff): delete the response fields server-side and the whole FE thread in one sweep;
  the datesync/ssr gates cover the regression surface.

### F10 — MEDIUM · global String.prototype.toFixed/toPrecision monkey-patch: honest-dash fix that also silently un-formats numeric strings app-wide
- `src/cmd/shims.ts:22-41` — adds `toFixed`/`toPrecision` to `String.prototype` returning the string unchanged,
  imported first from guards.ts:101 so it applies to the entire app (host chrome, CMD_V2, third-party libs).
- Intended for `'—'.toFixed(1) === '—'`, but it applies to EVERY string: a numeric-string leaf (`"12.3456"`) that
  reaches an unguarded `x.toFixed(1)` now renders full-precision instead of throwing — the throw would have exposed a
  serialization bug (executor emitting strings where numbers belong); the shim converts that bug class into silently
  wrong display precision. It also changes feature-detection semantics for any library probing `toFixed` to
  distinguish numbers.
- Fix (safe, keeps the dash behavior): inside the shim, if `String(this) !== "—"` (and not blank), log a one-time
  telemetry warning with the value — dash rides through as today, real numeric strings become visible defects.

### F11 — LOW/MEDIUM · App.tsx parses the persisted dashboard from sessionStorage on EVERY render
- `src/App.tsx:47` — `const saved = _loadSaved();` runs in the component body (not a lazy `useState` initializer):
  every App re-render (run lifecycle, thread/seed/resolving updates) re-reads sessionStorage and `JSON.parse`s the
  entire saved `PipelineResult` (line 38) — potentially hundreds of KB of card payloads — then throws the result away
  (it only feeds `useState` initial values, lines 48/51).
- Companion cost: `_save` (App.tsx:42-44) `JSON.stringify`s the full result on every completed run; >5 MB dashboards
  silently lose persistence (quota catch) — acceptable, but worth knowing.
- Fix (safe, 2 lines): `useState(() => _loadSaved())` once and derive both initial values from it.

### F12 — LOW · side effect inside a setState updater (StrictMode double-refetch of the whole page in dev)
- `src/cmd/fill/panel-overview-harmonics-pq/card-23.tsx:50-63` — `updateSelection` calls
  `onDateChange?.(selectionToWindow(next))` INSIDE the `setFilterSelection` updater function. Updaters must be pure;
  React StrictMode (enabled — `main.tsx:33`) double-invokes them in dev, so one preset click publishes the shared
  window twice → every history card on the page re-fetches twice. Production fires once, but it is a rules violation
  and a dev-signal falsifier.
- The sibling card does it correctly: `fill/panel-overview-voltage-current/card-18.tsx:53-56` calls `onDateChange`
  sequentially after `setSelection`.
- Fix (safe): compute `next` outside and call `setFilterSelection(next)` + `onDateChange(...)` sequentially.

### F13 — LOW · 36 card ids registered in BOTH FILL and COMPONENTS with order-dependent precedence — a documented past bug's trap still armed
- `src/cmd/registry.tsx:269-283` — FILL is checked before COMPONENTS; the comment records that the reverse order
  "bypassed every guard the fill was built to apply" (a real 2026-07-06 incident, card 41). The COMPONENTS entries for
  ids 18–27, 36–49, 66–69, 74–81 (36 ids, verified by intersecting `components.ts:57-118` with the fill `CARDS` maps)
  are permanently shadowed dead mappings, kept only implicitly.
- The duplicate-warning at registry.tsx:32 only covers FILL-vs-FILL collisions.
- Fix (safe): either delete the shadowed COMPONENTS entries (tier_audit.tsx exists precisely to compare tiers — keep
  them there instead), or add a startup assertion that logs the intended shadowing so a future re-order fails loudly.

### F14 — LOW · external Google Fonts CDN in index.html — hostile to on-prem/air-gapped plant deployments
- `index.html:7-9` — `fonts.googleapis.com` / `fonts.gstatic.com` links for Space Mono + Inter. The product's data
  plane is deliberately local (SSH-tunneled Postgres, LAN Vite/host); a site without internet gets font fallback at
  best, a render-blocking stall at worst. Aeromono is already self-hosted (`public/fonts/`) — do the same for these
  two. Fix: safe.

### F15 — LOW · committed editor temp file (tracked) and stale build artifacts in the tree
- `src/App.tsx.tmp.4127533.ec0206d76dd3` is git-tracked (verified via `git ls-files`) — an 11 KB stale copy of
  App.tsx that ships to every clone and confuses grep/refactors.
- `tsconfig.tsbuildinfo` and the stale `dist/` (see F5) also live in-tree.
- Fix (safe): `git rm`, add `*.tmp.*`, `dist/`, `*.tsbuildinfo` to .gitignore.

### F16 — LOW · the host date-window vocabulary is re-encoded in ~10 files
- `src/cmd/date-adapter.ts:14-26` (`RANGE_MAP`) plus 9 per-page `date-wiring.ts`/`date-window.ts` files (497 lines
  total — wc verified) each map a different CMD_V2 picker vocabulary onto the same host tokens
  (`today|yesterday|last-7-days|this-month|custom-range` × `hourly|2hour|shift|day|week`). The per-page halves are
  legitimately different (different CMD_V2 pickers — consistent with the atomic-structure rule); the HOST-token half
  is the same literal set 10 times. Adding a host range token (e.g. `last-quarter`) is a 10-file edit with silent
  partial-miss failure (unknown tokens pass through verbatim, date-adapter.ts:38).
- Fix (safe): one `host-window-vocab.ts` exporting the token constants/types; per-page files keep their own
  picker-side mapping but consume the shared target vocab.

---

## Explicitly checked and CLEAN (no finding)

- **Hooks in fill renderers**: all fill `CARDS` functions return elements wrapping proper components; hooks live
  inside components (`card-73.tsx:23-43`, `card-18.tsx:34-81`, `compose.tsx:17-105`). No rules-of-hooks violation on
  the registry's conditional-tier dispatch.
- **Race safety of the date-sync fetch**: per-effect `live` flag (CmdCard.tsx:65-67) prevents stale overwrites on
  rapid picks (cancellation of the network request itself is F1's residual).
- **PromptBar** (`components/PromptBar.tsx`): AbortController + monotonic `seq` guard + submit-time invalidation +
  bounded client cache (lines 87-158) — the best-engineered fetch path in the app. (Nit: `blurT` timeout is not
  cleared on unmount, line 113 — harmless.)
- **Error boundaries exist at three scopes** (app root / card / RTM piece) and honest-blank rather than white-screen —
  the SSR-crash history is genuinely addressed at render time; F3 is about their silence, not their absence.
- **Key usage**: `CardGrid.tsx:67,95` keys by `card_id` (unique per grid), multi-asset sections by asset id (:45);
  `KnowledgeAnswer.tsx:34` / `SuggestedCommands.tsx:37` index keys are on append-only/replace-whole lists —
  acceptable.
- **Layout engine** (`layout/*.ts`): pure, DB-vocab-driven, no per-page CSS, occupancy-grid de-collision
  (gridPlan.ts:57-75) — clean and consistent with the DB-driven-config principle.
- **sessionStorage restore semantics** (App.tsx:22-44): reload-detection via Navigation Timing with legacy fallback,
  fail-open — deliberate and documented.
- **Render harnesses**: `scripts/ssr_gate.mjs` (fail on throw or null-with-payload), `datesync_repro.tsx` (asserts
  exactly the history cards refetch), `tier_audit.tsx` — real, runnable contracts, not aspirational docs.

## Notes on the design principles themselves (critique)

- *Per-leaf degradation* is honored, but its FE implementation is FOUR compensating layers for the same crash family
  (display_dash server-side, guards.ts g1–g16, shims.ts prototype patch, error boundaries). Each layer is individually
  defensible; together they mean the true rendering contract of a card lives in no single place. The durable fix is
  upstream (typed payload contracts per card — F8), which would let g-rules retire instead of accreting (g16 was added
  2026-07-07).
- *AI-first minimal code* stops at the FE boundary: guards.ts's 541 lines ARE per-shape business rules in code —
  justified only because CMD_V2 is read-only. Worth stating that explicitly in the rule doc so the exception doesn't
  become a precedent.
- *Atomic structure* is followed well in `cmd/fill/*` (one card per file, thin barrels), at the cost of the
  vocabulary duplication in F16 — atomic files still deserve shared constants.
