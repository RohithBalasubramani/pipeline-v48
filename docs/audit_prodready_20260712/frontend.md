# Production-Readiness Audit — Frontend lens (host/web)

Date: 2026-07-12 (differential re-audit after same-day refactor campaign)
Auditor: frontend lens agent
Scope: host/web (React 19 + Vite + TS), types.ts vs host/enrich.py + server.py contract,
CMD_V2 anchor relocatability, F14 frames plumbing, registry/fill discovery, api.ts.

Status: COMPLETE. Net result: today's FE claims (F14 wire prune, R10 union, Batch-6 consolidation, R3 anchor)
are substantively TRUE and verified live; the residue is one medium fresh-clone/bootstrap gap (OBS-1) and six
low doc-drift / partial-claim items (OBS-2..7).

## Findings

### OBS-1 — MEDIUM · fresh-clone bootstrap of the CMD_V2 anchor is UNDOCUMENTED and half-committed
- The R3 "relocatable anchor" fix is real on THIS machine: `vite.config.ts:12-20` (env `CMD_V2_ROOT` → `cmd-v2-src`
  symlink realpath → historical default), `scripts/link-cmd-v2.sh` writes both the symlink and the generated
  `tsconfig.cmdv2.json`.
- BUT: `tsconfig.json` (git-TRACKED, modified today) `extends: "./tsconfig.cmdv2.json"` — and `tsconfig.cmdv2.json`
  + `scripts/link-cmd-v2.sh` are both UNTRACKED (`git status --porcelain` = `??`), while `cmd-v2-src` is gitignored
  (`.gitignore:43`). A fresh clone either (a) misses tsconfig.cmdv2.json entirely → `tsc -b` dies with TS5083 before
  a single source error, or (b) if the pending mega-commit `git add -A`s it, ships `/home/rohith/CMD_V2/src/*`
  (machine-specific, "GENERATED — do not hand-edit").
- `grep -rn "link-cmd-v2\|CMD_V2_ROOT\|cmd-v2-src" **/*.md` → ZERO hits: no README/ops doc tells a new machine to run
  `CMD_V2_ROOT=... bash scripts/link-cmd-v2.sh`. host/README.md doesn't mention it.
- Fix (safe): commit link-cmd-v2.sh; commit a default tsconfig.cmdv2.json (historical default path) or generate-if-
  missing in the build script; add the one-liner bootstrap to host/README.md + ops/SERVICES.md.

### OBS-2 — LOW · vite.config.ts comment claims tsc "can never disagree" with vite — but `CMD_V2_ROOT` env only steers vite
- `vite.config.ts:10-13` comment: "tsconfig paths resolve through the SAME symlink so tsc and vite can never
  disagree". False on both halves: link-cmd-v2.sh:5-6 explicitly writes the REAL path into tsconfig.cmdv2.json
  because mapping through the symlink breaks tsc (390 type errors); and env `CMD_V2_ROOT` overrides vite at process
  start while tsc keeps the generated path — set the env without re-running the script and typecheck vs bundle
  resolve @cmd-v2 from two different trees.
- Fix (safe): correct the comment; optionally have `npm run build`/typecheck fail when
  `CMD_V2_ROOT` is set and disagrees with the generated tsconfig path.

### OBS-3 — LOW · `render.suppress_default_leaves` is typed + honored in the FE but produced by NOTHING server-side
- `types.ts:35` declares it; `registry.tsx:236` `forceBlank(card.payload, rv.suppress_default_leaves)` force-blanks
  those paths per render. Grep across all .py: zero producers — the field came from the RETIRED Layer-3
  render-guarantee contract (host/enrich.py `render` dict has no such key). forceBlank early-returns on the empty
  list (registry.tsx:113) so no perf cost, but the NO-SEED-LEAK "FE re-assert" is dead wire contract that new
  authors will assume works.
- Fix (safe): either delete the field + forceBlank call, or keep and document it as a server-side seam that is
  currently never exercised (tier_audit.tsx also preprocesses with it).

### OBS-4 — LOW · stale "frames={} EMPTY for back-compat" comments contradict the executed F14 retirement (~28 files)
- The F14 prune is REAL in code (verified: server.py/multi_asset.py emit no page-level frames/frame_status/
  live_frame; App/CardGrid/CmdCard/registry/RtmComposite threading gone; renderCmd is 2-arg). But the header of
  `host/server.py:17` still says "`frames` is emitted EMPTY for back-compat", `registry.tsx:12,21` say "frames is
  EMPTY", and ~25 fill modules carry "the host emits frames={} EMPTY" (e.g. fill/dg-operations-runtime.tsx:12,
  fill/panel-overview-harmonics-pq.tsx:9). The host now emits NO frames field at all.
- Also `server.py:89` still logs `frames=[]` into the obs RESPONSE stage — a permanently-empty telemetry field.
- Fix (safe): sweep the comment wording ("frames are retired" not "emitted empty"); drop the obs `frames=[]` kwarg.

### OBS-5 — LOW · R10 claim "api.ts checks res.ok before res.json()" is only true for 4 of 8 fetchers
- Checked: `runPipeline` (api.ts:137), `fetchCardFrame` (:157), `fetchInspectorTraces` (:116), `fetchInspectorTrace`
  (:123) — all guard with the shared `httpError`. NOT guarded: `fetchSite` (:18), `fetchAssets` (:24),
  `copilotSuggest` (:32), `copilotStarters` (:44) — a proxy HTML 502 there still surfaces as a SyntaxError from
  `res.json()`. Callers tolerate it (PromptBar catches suggest errors; fetchAssets/copilotStarters coerce to []),
  so impact is cosmetic console noise / a missed LIVE dot — but the AUDIT_REPORT item-17 claim overstates.
- Fix (safe): add the same `if (!res.ok) throw await httpError(res)` line to the four.

### OBS-6 — LOW · refactor ledger still lists F14 as an OPEN follow-up although it was executed (and verified here)
- `docs/findings/refactor_20260712/EXECUTED_AND_FOLLOWUPS.md` follow-up #9 (line ~136): "F14 (dead frames/liveFrame
  plumbing — grep-confirmed server always serves frames:{} / live_frame:null; wide but mechanical)" — but
  `APPLY_LOG_unused_dupes_audit.md` executed it end-to-end later the same day, and this audit re-verified it in code
  AND on a live archived response (`outputs/logs/response_r_490b1393b9.json` has no page-level
  frames/frame_status/live_frame keys). Two same-day docs now disagree about the state of the tree.
- Fix (safe): strike/annotate follow-up #9's F14 clause in the ledger.

### OBS-7 — LOW · ErrorBoundary consolidation shipped an `onCatch` telemetry seam but only the app root uses it — per-card render errors are still silent (react F3 remains, now a one-liner)
- `components/ErrorBoundary.tsx:24-26` — the ONE shared class now has `componentDidCatch → props.onCatch`.
  `main.tsx:36` passes onCatch (console.error). But `CmdCard.tsx:91` (per-card boundary) and `RtmComposite.tsx`
  Piece (~line 31) pass only `fallback`, and the `renderCmd` try/catch (`CmdCard.tsx:58-63`) stores `renderErr`
  without logging. A CMD_V2 crash in production still degrades to an honest-blank tile with zero operator signal.
- Not claimed fixed anywhere — recorded because the refactor made the fix trivial: pass
  `onCatch={(e) => console.error("[card", card.card_id, "]", e)}` at both call sites + a console.error beside
  `renderErr =`.

---

## Verified OK (positive verification of today's claims)

- **`tsc -b --noEmit` exits 0** right now on host/web (React 19 + TS 5.5, admin console included; node_modules
  present, node v22).
- **F14 wire prune is REAL end-to-end**: `host/server.py` build_response (lines 95-133) and `host/multi_asset.py`
  emit no page-level `frames`/`frame_status`/`live_frame`; a LIVE archived response
  (`outputs/logs/response_r_490b1393b9.json`) confirms the keys are absent on the wire; FE chain pruned —
  CardGrid has no frameFor, CmdCard has no frame state/reseed effect, `renderCmd(card, onDateChange)` is 2-arg
  (registry.tsx:221-224), RtmComposite's liveFrame cascade is gone. Per-card `frame_status` (ER-6) correctly KEPT
  (enrich.py:246, types.ts:66, CmdCard.tsx:68).
- **R10 discriminated union is REAL**: types.ts:136-151 `DashboardResult | KnowledgeResult` on `kind`; App.tsx:85/88/115
  gates on `kind === "knowledge"`. Known documented residual unchanged: server stamps `kind` only on the knowledge
  branch (server.py:345); `DashboardResult.kind` stays optional exactly as types.ts:134-135 flags.
- **types.ts ⇄ enrich.py field-by-field**: every declared Card field is served — `data_note`/`l2_answerability`
  attached by `host/notes.py:28-30` (server.py:86), `card.asset` tag on multi-asset only (multi_asset.py:106),
  `refetch` only for is_history cards (enrich.py:218-222), `render.gaps`/`leaf_stats`/watermark as declared;
  `trace_id` stamped by `obs/middleware.py:69` (`resp.setdefault`). Server extras not in types
  (swap/conforms/fill_source/fill_ok/fill_why, render.slots/leaf_stats) are additive and unread — harmless.
- **registry tier order matches its header** (SPECIAL/envelope → FILL → COMPONENTS → COMPOSE → HonestBlank;
  registry.tsx:15-23 vs 249-290); FILL-before-COMPONENTS (the 2026-07-06 incident guard) intact.
- **fill/ glob discovery consistent**: 12 top-level barrels ↔ 12 card folders 1:1; barrels re-export `CARDS`; the
  non-recursive `./fill/*.tsx` glob is documented in each barrel (e.g. dg-engine-cooling.tsx:5-6).
- **Shared-component consolidation fully adopted**: ErrorBoundary (app root/CmdCard/RtmComposite), HonestBlankTile
  (registry + CmdCard only homes), icons.tsx (App/AssetResolution/PromptBar; admin's `Spark` in widgets.tsx:65 is a
  different sparkline widget, not a drift copy), hooks/useSiteStatus (CommandHeader + DataUnavailable).
- **SSR gate re-run during this audit** (offline, vite-node): PASS — 8/8 cards rendered, 0 throws, 0
  payload-bearing null fallbacks over `response_r_490b1393b9.json` + `response_r_318a2ce062.json`. (Two other
  recent responses are knowledge envelopes → 0 cards, vacuous pass.)
- **F15 fixed**: `App.tsx.tmp.*` gone from tree and index; pipeline_v48/.gitignore now covers `host/web/dist/`,
  `*.tsbuildinfo`, `host/web/cmd-v2-src` (git check-ignore verified).
- **Batch-6 "pre-existing build break card-47" fix** holds (tsc green implies `loadImpactWatch` satisfied).
- **Anchor works on THIS machine**: vite.config.ts env→symlink→default chain with realpath; `fs.allow` + watch-ignore
  derive from the same root; tsconfig extends the generated tsconfig.cmdv2.json whose path matches the symlink target.
- **api.ts is the one endpoint home** with typed responses for all 8 fetchers + sessionStorage restore logic works
  as documented (reload → clean slate via Navigation Timing, save only completed dashboards, quota fail-open).

## Known-open items re-checked and UNCHANGED (not re-reported; see docs/audit_2026-07-12/react.md)

- F1 silent date-refetch failure — `CmdCard.tsx:49` still `.catch(() => {})`, no AbortSignal.
- F2 hardcoded-machine build deps — package.json still declares only react/react-dom; CMD_V2 node_modules implicit.
- F4 re-render hotspots — DateSync.tsx:17 fresh context object per render; guardPayload clone per card render
  (forceBlank now always early-returns since nothing serves suppress_default_leaves — see OBS-3).
- F5 Vite dev server as prod runtime; stale dist/ (now gitignored).
- F6 eager three.js in the one bundle — CentralAssetViewer still statically imported (special.tsx:20); ONE
  React.lazy now exists (admin console, main.tsx:9) proving the pattern works here.
- F10 String.prototype toFixed/toPrecision monkeypatch — shims.ts:22-41 byte-identical.
- F11 `_loadSaved()` still runs in App component body every render (App.tsx:49).
- F13 36 dual-registered card ids, FILL shadowing COMPONENTS, warn only covers FILL-vs-FILL.
- react-F14 Google Fonts CDN — index.html:7-9 unchanged.
- F16 date-vocab duplication — partially improved (fill/shared/sampling-window.ts collapsed the byte-identical
  feeder/DG pair; the host-token vocabulary is still re-encoded per page).

