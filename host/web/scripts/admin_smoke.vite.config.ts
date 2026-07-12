// scripts/admin_smoke.vite.config.ts — minimal config for the admin smoke: the admin section imports no CMD_V2 and
// no Tailwind, so the main config's plugins (whose full-reloads abort vite-node mid-run) are deliberately absent.
import { defineConfig } from "vite";

export default defineConfig({
  esbuild: { jsx: "automatic" },
  // a SIBLING session edits src/ live — without this, any edit restarts vite-node's server mid-smoke (ERR_CLOSED_SERVER)
  server: { watch: null },
});
