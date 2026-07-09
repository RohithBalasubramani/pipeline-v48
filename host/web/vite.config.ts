import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

const API = process.env.V48_HOST_API || "http://localhost:8770";
const COPILOT = process.env.V48_COPILOT_API || "http://localhost:8772";  // standalone EMS Query Copilot
const CMD_V2 = "/home/rohith/CMD_V2";   // read-only — we import its REAL card components, never edit them

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    dedupe: ["react", "react-dom"],     // ONE React across host/web + CMD_V2/node_modules
    alias: {
      "@cmd-v2": path.resolve(CMD_V2, "src"),
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
    },
  },
});
