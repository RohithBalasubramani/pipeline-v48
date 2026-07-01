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
    proxy: {
      "/api": { target: API, changeOrigin: true },
      "/copilot": { target: COPILOT, changeOrigin: true },
    },
  },
});
