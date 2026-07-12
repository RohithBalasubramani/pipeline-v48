# Fixes — frontend group (audit_prodready_20260712)

Date: 2026-07-12 ~08:12 IST. Files owned: host/web/src/api.ts, host/web/src/components/CmdCard.tsx,
host/web/README.md (new), pipeline_v48/.gitignore, host/web/.gitignore.

## Pre-edit freshness check
- api.ts mtime 06:56, CmdCard.tsx 06:48, .gitignore 07:42 — none within 3 min of edit time; current
  content read in full before editing.

## Changes

### 1. host/web/src/api.ts — [frontend OBS-5]
- Added `if (!res.ok) throw await httpError(res);` (same line + same trailing comment as the four
  already-guarded fetchers) to the four unguarded ones: `fetchSite`, `fetchAssets`,
  `copilotSuggest`, `copilotStarters`. +4 lines, nothing else touched.
- Caller safety verified BEFORE editing — all four call sites already `.catch()`/try-catch:
  `hooks/useSiteStatus.ts:17` (.catch → live:false), `components/AssetResolution.tsx:55`
  (.catch → leave empty), `components/PromptBar.tsx:73` (try/catch, non-abort errors swallowed),
  `components/SuggestedCommands.tsx:22` (.catch → keep FALLBACK). Healthy path (res.ok)
  byte-identical; a non-2xx now surfaces as a clean `httpError` message through the existing catch
  path instead of a `SyntaxError` from `res.json()` on a proxy HTML 502.

### 2. host/web/src/components/CmdCard.tsx — [frontend OBS-7]
- Per-card ErrorBoundary usage now passes the existing `onCatch` seam
  (`onCatch={(e) => console.error("[card", card.card_id, "]", e)}`) — a CMD_V2 component throw
  caught by the boundary is no longer operator-invisible. Dependency-free, no network.
- Added `console.error("[card", card.card_id, "] render error:", e)` in the SAFE-RENDER catch
  beside `renderErr =` (the audit noted renderErr was stored without logging).
- NOT touched: `RtmComposite.tsx` Piece boundary (same gap, file not in my ownership list) → see
  Skipped.
- Behavior: healthy render path unchanged; error paths gain a console.error only (fallback JSX and
  degradation contract untouched).

### 3. host/web/README.md — NEW — [frontend OBS-1, MEDIUM]
- Fresh-clone bootstrap doc: Node 22, `npm install`, `CMD_V2_ROOT=... bash scripts/link-cmd-v2.sh`
  (writes BOTH the gitignored `cmd-v2-src` symlink for vite and the generated
  `tsconfig.cmdv2.json` for tsc), `npx tsc -b --noEmit`, `npm run dev` (:5188, proxy map), the
  three gates (`ssr-gate` / `client-gate` / `layout-gate` — descriptions taken from each script's
  own header), and the OBS-2 caveat verbatim in spirit: env `CMD_V2_ROOT` steers vite ONLY, tsc
  always uses the generated tsconfig path, so env-without-script = typecheck and bundle resolving
  @cmd-v2 from two different trees.
- Every claim verified against the CURRENT tree before writing: package.json scripts (build =
  `tsc -b && vite build`; the three gate scripts exist), vite.config.ts:14-19 (env → symlink →
  default chain), scripts/link-cmd-v2.sh (writes real path into tsconfig.cmdv2.json because the
  symlink mapping breaks tsc), tsconfig.json extends ./tsconfig.cmdv2.json, node v22.22.0 on this
  machine, no `engines` field in package.json.
- STATE CHANGE since the audit doc was written: `tsconfig.cmdv2.json` + `scripts/link-cmd-v2.sh`
  are now git-TRACKED (commit 6db166f) — the audit's "(a) fresh clone misses tsconfig.cmdv2.json"
  branch no longer applies; its "(b) ships the machine-specific path" branch DID happen. README
  documents exactly that: the tracked copy carries the historical default path and re-running the
  script per machine rewrites (dirties) it — don't commit a machine-specific path.

### 4. .gitignore(s) — [security OBS-7] — NO EDIT NEEDED (verified already covered)
- `pipeline_v48/.gitignore:36` already has `.env*.local` (and `:35` `.env`); `git ls-files | grep
  -i '\.env'` in pipeline_v48 = ZERO tracked env files; `git check-ignore -v
  host/web/.env.development.local` → matched by `.gitignore:36`.
- The tracked file the security lens flagged, `frontend/.env.production.local`, lives in the OUTER
  BFI repo (`/home/rohith/desktop/BFI` is a separate git repo from pipeline_v48). That repo's
  `.gitignore:27` ALREADY contains `.env*.local` — future adds are blocked there too. The file
  itself stays tracked because gitignore never untracks (untracking = `git rm --cached`, forbidden
  by the brief; content verified non-secret by the security lens: public NEXT_PUBLIC_* URLs).
- Did NOT create host/web/.gitignore — it would duplicate a pattern the repo-root .gitignore
  already applies to that subtree (patterns without slashes match in all subdirectories).

## Gates
- `cd host/web && npx tsc -b --noEmit` → exit 0.
- `npx tsc -b --noEmit --force` (full non-incremental re-check, to rule out stale tsbuildinfo
  skipping the edited files) → exit 0.
- No .py files edited → `py_compile` N/A; no pytest files named for this group.
- Diff scope confirmed: api.ts +4/-0, CmdCard.tsx +2/-1 (one line gained onCatch), README.md new;
  no other file touched.

## Skipped
- **RtmComposite.tsx Piece boundary (frontend OBS-7, second call site)** — same silent-error gap,
  but the file is not in this group's ownership list. One-liner for the owner:
  pass `onCatch={(e) => console.error("[piece]", e)}` (with the piece's card id if in scope) at the
  `<ErrorBoundary fallback=...>` around each Piece (~line 31).

