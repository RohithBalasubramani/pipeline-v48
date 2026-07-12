import { PromptBar, type Seed } from "./PromptBar";
import { useSiteStatus } from "../hooks/useSiteStatus";

export function CommandHeader({
  onRun,
  loading,
  seed,
  showStatus = true,
  onOpenInspector,
}: {
  onRun: (prompt: string) => void;
  loading: boolean;
  seed?: Seed;
  showStatus?: boolean;
  onOpenInspector?: () => void;   // AI Decision Inspector entry (optional — every existing call site keeps compiling)
}) {
  // Site identity + LIVE dot come from the backend (GET /api/site): `site` is the DB-tunable app_config value; `live`
  // is a REAL probe of the live-data DB connection. Poll every 15s so the dot tracks the actual connection.
  const { site, live } = useSiteStatus(15000, { initialLive: true, initialSite: "PEGEPL · SEETARAMPUR" });

  return (
    <header className="cc-header">
      <div className="cc-title">AI COMMAND CENTER</div>

      <div className="cc-barwrap">
        <PromptBar onRun={onRun} loading={loading} seed={seed} />
      </div>

      {onOpenInspector && (
        <button className="cc-nav-btn" onClick={onOpenInspector} title="AI Decision Inspector — every AI decision of a run">
          INSPECTOR
        </button>
      )}

      {showStatus && (
        <div className="cc-status">
          <div className="cc-status-col">
            <div className="cc-status-live">
              <span
                className="cc-status-dot"
                style={{
                  background: live ? "var(--sage-400)" : "var(--slate-soft)",
                  boxShadow: live ? "0 0 0 3px rgba(163,193,136,0.22)" : "none",
                }}
                title={live ? "live-data DB connected" : "live-data DB unreachable"}
              />
              <span className="cc-status-livelabel" style={{ color: live ? "var(--sage-700)" : "var(--slate-500)" }}>
                {live ? "LIVE" : "OFFLINE"}
              </span>
            </div>
            <span className="cc-status-site">{site}</span>
          </div>
        </div>
      )}
    </header>
  );
}
