# host/web — V48 frontend (React 19 + Vite + TS)

The prompt → cards preview UI. Renders each selected card with its **real CMD_V2 component**
(payload = props). What it talks to and what you see: see `../README.md` (host overview).

## Bootstrap on a fresh clone / new machine

Prereqs: **Node 22** (developed and gate-verified against v22; `package.json` declares no `engines`
floor), npm, and a **read-only checkout of the CMD_V2 repo** somewhere on disk (the historical
default location is `/home/rohith/CMD_V2`).

```bash
cd host/web
npm install

# 1. Point the ONE machine-specific fact — where CMD_V2 lives — at your checkout [audit R3]:
CMD_V2_ROOT=/path/to/CMD_V2 bash scripts/link-cmd-v2.sh

# 2. Typecheck must be clean before anything else:
npx tsc -b --noEmit

# 3. Dev server (proxies /api → :8770, /copilot → :8772, /admin/api → :8790):
npm run dev            # http://localhost:5188
```

### What link-cmd-v2.sh does (and why you cannot skip it)

`scripts/link-cmd-v2.sh` writes **both** consumers of the CMD_V2 location:

- `cmd-v2-src` — a symlink to `$CMD_V2_ROOT/src`. This is vite's `@cmd-v2` alias fallback
  (`vite.config.ts` realpaths it). It is **gitignored** (pipeline_v48/.gitignore), so a fresh clone
  does not have it until you run the script.
- `tsconfig.cmdv2.json` — the tsc `paths` mapping for `@cmd-v2/*`. **GENERATED — do not hand-edit.**
  The script deliberately writes the *real absolute path* here, not the symlink: mapping tsc through
  the symlink makes it resolve CMD_V2's imports against `host/web/node_modules` (≈390 type errors).
  The tracked copy carries the historical default path (`/home/rohith/CMD_V2/src`); on any machine
  where CMD_V2 lives elsewhere, re-running the script rewrites it (and dirties the tracked file —
  don't commit your machine-specific path).

`tsconfig.json` `extends: "./tsconfig.cmdv2.json"`, so if that file is missing `tsc -b` dies with
TS5083 before reporting a single source error.

### Caveat: the `CMD_V2_ROOT` env var steers **vite only**

At dev/build time `vite.config.ts` resolves `@cmd-v2` as: env `CMD_V2_ROOT` → `cmd-v2-src` symlink
→ historical default. **tsc never reads the env** — it always uses the generated
`tsconfig.cmdv2.json` path. Setting `CMD_V2_ROOT` without re-running `link-cmd-v2.sh` makes
typecheck and bundle resolve `@cmd-v2` from two different trees. To move CMD_V2, run the script;
use the bare env var only for a throwaway vite run where the type mismatch is understood.

## The three standing gates

All three run offline (no backend needed) via `vite-node`:

- `npm run ssr-gate -- '<glob-or-file>'` — renders EVERY card of the given served-response JSONs
  through the real `renderCmd` path with `react-dom/server`. FAIL on any card that throws, or that
  falls to the NULL fallback while carrying a payload. (Quote the glob so the script expands it.)
- `npm run client-gate` — mounts served cards with `react-dom/client` inside jsdom, flushing
  effects (the phase SSR skips). Defaults to `<repo>/outputs/logs/response_*.json`; FAIL on any
  throw during mount/effects or NaN-SVG-attribute errors on payload-bearing cards.
  `npm run client-gate -- '<glob-or-file>'` to target specific responses.
- `npm run layout-gate` — verifies the grid-placement plan (`src/layout/gridPlan.ts`) seats every
  case's cards collision-free into one viewport-bounded grid.

## Build

`npm run build` = `tsc -b && vite build`. Note the dev server is what's deployed today (`npm run
dev` on :5188); `vite preview` serves the built bundle.
