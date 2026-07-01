import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import "@cmd-v2/index.css";   // CMD_V2 Tailwind v4 + design tokens — styles the imported CMD_V2 cards
import "./styles.css";      // host chrome (loaded after, re-asserts the dark shell)

// APP-ROOT ERROR BOUNDARY [FR-2] — the outermost safety net. Even with per-card try/catch + per-card boundaries, a throw
// in the shell (layout, header, a hook) would otherwise white-screen the whole app. This boundary catches it and shows a
// recoverable error panel instead of a blank page, so the render-guarantee ("never a white screen") holds app-wide.
class AppBoundary extends React.Component<{ children: React.ReactNode }, { err: string | null }> {
  state = { err: null as string | null };
  static getDerivedStateFromError(e: any) { return { err: String(e?.stack ?? e?.message ?? e) }; }
  componentDidCatch(e: any, info: any) { console.error("[app-root] uncaught render error", e, info); }
  render() {
    if (this.state.err) {
      return (
        <div style={{ padding: 24, fontFamily: "ui-monospace, monospace", color: "#d4351c",
                      background: "#faf8f3", minHeight: "100vh", whiteSpace: "pre-wrap" }}>
          <h2 style={{ marginTop: 0 }}>⚠ Application error</h2>
          <p style={{ color: "#555" }}>The dashboard shell hit an unrecoverable render error. Your last prompt was not lost —
            reload to try again.</p>
          <button onClick={() => this.setState({ err: null })}
            style={{ margin: "8px 0", padding: "6px 14px", cursor: "pointer" }}>Retry render</button>
          <pre style={{ fontSize: 12, color: "#a00", overflow: "auto" }}>{this.state.err}</pre>
        </div>
      );
    }
    return this.props.children;
  }
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AppBoundary>
      <App />
    </AppBoundary>
  </React.StrictMode>
);
