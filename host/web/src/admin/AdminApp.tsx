/** admin/AdminApp.tsx — the /admin shell: header + section nav + the routed page. Self-contained console over the
 *  admin API (:8790 via the /admin/api proxy); the product app (App.tsx prompt shell) is untouched by design. */
import "./admin.css";
import "./widgets.css";
import { navigate, useRoute } from "./router";
import { RunsPage } from "./pages/RunsPage";
import { ExplorerPage } from "./pages/ExplorerPage";
import { TracePage } from "./pages/TracePage";
import { CoveragePage } from "./pages/CoveragePage";
import { LatencyPage } from "./pages/LatencyPage";
import { FailuresPage } from "./pages/FailuresPage";
import { AiUsagePage } from "./pages/AiUsagePage";
import { SqlPage } from "./pages/SqlPage";
import { AssetsPage } from "./pages/AssetsPage";
import { ValidationPage } from "./pages/ValidationPage";
import { SearchPage } from "./pages/SearchPage";
import { ReplayPage } from "./pages/ReplayPage";

const SECTIONS: { key: string; label: string }[] = [
  { key: "runs", label: "Runs" },
  { key: "explorer", label: "Explorer" },
  { key: "coverage", label: "Coverage" },
  { key: "latency", label: "Latency" },
  { key: "failures", label: "Failures" },
  { key: "ai", label: "AI Usage" },
  { key: "sql", label: "SQL" },
  { key: "assets", label: "Assets" },
  { key: "validation", label: "Validation" },
  { key: "search", label: "Search" },
  { key: "replay", label: "Replay" },
];

export function AdminApp() {
  const route = useRoute();
  const section = route.section === "trace" ? "runs" : route.section;
  return (
    <div className="px-shell">
      <header className="px-header">
        <div className="px-title">V48 ADMIN <small>· pipeline console</small></div>
        <nav className="px-nav">
          {SECTIONS.map((s) => (
            <button key={s.key} className={section === s.key ? "on" : ""} onClick={() => navigate(s.key)}>
              {s.label}
            </button>
          ))}
        </nav>
        <a className="px-backlink" href="/">← command center</a>
      </header>
      <main className="px-work">
        <div className="px-work-inner">
          {route.section === "trace" ? <TracePage rid={route.rest[0] || ""} />
            : route.section === "explorer" ? <ExplorerPage />
            : route.section === "coverage" ? <CoveragePage />
            : route.section === "latency" ? <LatencyPage />
            : route.section === "failures" ? <FailuresPage />
            : route.section === "ai" ? <AiUsagePage />
            : route.section === "sql" ? <SqlPage />
            : route.section === "assets" ? <AssetsPage />
            : route.section === "validation" ? <ValidationPage />
            : route.section === "search" ? <SearchPage />
            : route.section === "replay" ? <ReplayPage />
            : <RunsPage />}
        </div>
      </main>
    </div>
  );
}
