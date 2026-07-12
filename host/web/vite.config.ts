import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";
import fs from "fs";

const API = process.env.V48_HOST_API || "http://localhost:8770";
const COPILOT = process.env.V48_COPILOT_API || "http://localhost:8772";  // standalone EMS Query Copilot
const ADMIN = process.env.V48_ADMIN_API || "http://localhost:8790";      // admin console API (admin/server.py)
// CMD_V2 location — read-only (we import its REAL card components, never edit them). ONE relocatable anchor instead
// of a hard-coded absolute path [audit R3]: env CMD_V2_ROOT wins (CI / another machine), else the ./cmd-v2-src
// symlink (scripts/link-cmd-v2.sh maintains it; tsconfig paths resolve through the SAME symlink so tsc and vite can
// never disagree), else the historical default.
const CMD_V2_SRC = process.env.CMD_V2_ROOT
  ? path.join(process.env.CMD_V2_ROOT, "src")
  : fs.existsSync(path.resolve("cmd-v2-src"))
    ? fs.realpathSync(path.resolve("cmd-v2-src"))
    : "/home/rohith/CMD_V2/src";
const CMD_V2 = path.dirname(CMD_V2_SRC);

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    dedupe: ["react", "react-dom"],     // ONE React across host/web + CMD_V2/node_modules
    alias: {
      "@cmd-v2": CMD_V2_SRC,
      react: path.resolve("node_modules/react"),
      "react-dom": path.resolve("node_modules/react-dom"),
    },
  },
  server: {
    host: true,
    port: 5188,
    fs: { allow: [path.resolve("."), CMD_V2] },
    // CMD_V2 is READ-ONLY here (we import its cards, never edit them). Do NOT full-page-reload :5188 when a SEPARATE
    // dev/session edits CMD_V2 source — that churn (source-twin / bms / *.test.ts saved every ~20-40s) reloaded the
    // host faster than it could render, leaving a blank, constantly-refreshing page. The host renders a stable CMD_V2
    // snapshot; a manual refresh picks up an intentional CMD_V2 change. Only host/web/src edits still HMR.
    watch: { ignored: [`${CMD_V2}/**`] },
    proxy: {
      "/api": { target: API, changeOrigin: true },
      "/copilot": { target: COPILOT, changeOrigin: true },
      "/admin/api": { target: ADMIN, changeOrigin: true },
    },
  },
});
