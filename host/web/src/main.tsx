import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { ErrorBoundary } from "./components/ErrorBoundary";
import "@cmd-v2/index.css";   // CMD_V2 Tailwind v4 + design tokens — styles the imported CMD_V2 cards
import "./styles.css";      // host chrome (loaded after, re-asserts the dark shell)

// /admin → the internal admin console (src/admin/), lazy so the product bundle never pays for it.
const AdminApp = React.lazy(() => import("./admin/AdminApp").then(m => ({ default: m.AdminApp })));
const isAdmin = window.location.pathname.startsWith("/admin");

// APP-ROOT ERROR BOUNDARY [FR-2] — the outermost safety net. Even with per-card try/catch + per-card boundaries, a throw
// in the shell (layout, header, a hook) would otherwise white-screen the whole app. This boundary catches it and shows a
// recoverable error panel instead of a blank page, so the render-guarantee ("never a white screen") holds app-wide.
function AppErrorPanel({ err, onRetry }: { err: string; onRetry: () => void }) {
  return (
    <div style={{ padding: 24, fontFamily: "ui-monospace, monospace", color: "#d4351c",
                  background: "#faf8f3", minHeight: "100vh", whiteSpace: "pre-wrap" }}>
      <h2 style={{ marginTop: 0 }}>⚠ Application error</h2>
      <p style={{ color: "#555" }}>The dashboard shell hit an unrecoverable render error. Your last prompt was not lost —
        reload to try again.</p>
      <button onClick={onRetry}
        style={{ margin: "8px 0", padding: "6px 14px", cursor: "pointer" }}>Retry render</button>
      <pre style={{ fontSize: 12, color: "#a00", overflow: "auto" }}>{err}</pre>
    </div>
  );
}

const rootBoundary = React.createRef<ErrorBoundary>();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary
      ref={rootBoundary}
      errorText={(e) => String(e?.stack ?? e?.message ?? e)}
      onCatch={(e, info) => console.error("[app-root] uncaught render error", e, info)}
      fallback={(err) => <AppErrorPanel err={err} onRetry={() => rootBoundary.current?.reset()} />}
    >
      {isAdmin
        ? <React.Suspense fallback={<div style={{ padding: 24, fontFamily: "monospace" }}>loading admin console…</div>}>
            <AdminApp />
          </React.Suspense>
        : <App />}
    </ErrorBoundary>
  </React.StrictMode>
);
