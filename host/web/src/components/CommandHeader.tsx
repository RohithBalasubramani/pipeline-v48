import { useEffect, useState } from "react";
import { PromptBar, type Seed } from "./PromptBar";

// Neuract mark — the engineer's monogram, teal ink. Quiet brand chrome (README: brand lives in
// typography/layout, not a hero color); the logo is the one figural element.
function NeuractMark() {
  return (
    <svg width="30" height="29" viewBox="0 0 184 180" fill="none" xmlns="http://www.w3.org/2000/svg" aria-label="Neuract">
      <path fillRule="evenodd" clipRule="evenodd" d="M0.0200043 50.75L0.0390015 101.5L3.59801 97.255C6.36001 93.962 8.413 92.645 12.757 91.382C19.554 89.406 28.376 89.972 33.757 92.729C37.362 94.575 44.419 102.813 52.837 115C57.335 121.513 80.973 153.995 92.316 169.25L100.308 180H120.777C140.116 180 141.171 179.904 139.899 178.25C139.159 177.288 136.946 174.475 134.981 172C133.017 169.525 130.575 166.15 129.555 164.5C128.535 162.85 125.745 159.025 123.355 156C120.965 152.975 114.256 143.975 108.447 136C102.639 128.025 94.649 117.098 90.693 111.717C80.692 98.114 68.94 82.016 59.5 68.987C55.1 62.915 49.364 55.146 46.753 51.723C44.143 48.3 40.135 42.8 37.848 39.5C33.431 33.128 27.9 25.552 16.125 9.75L8.86 0H4.42999H0L0.0200043 50.75ZM47.328 5.75C59.719 22.222 66.854 31.858 70.04 36.425C71.987 39.216 76.037 44.713 79.04 48.641C82.043 52.568 88.325 61.06 93 67.511C105.491 84.749 125.541 112.249 139.312 131.031C144.365 137.924 151.65 147.96 155.5 153.335C159.35 158.709 165.377 166.908 168.893 171.553C175.193 179.878 175.348 180 179.643 180H184V129.333V78.667L180.25 82.465C172.33 90.488 161.825 92.262 151.929 87.25C145.323 83.904 139.048 76.119 106.992 31.5C102.645 25.45 95.68 15.887 91.513 10.25L83.937 0H63.469H43.002L47.328 5.75ZM140.086 3.11501C122.181 12.062 118.749 35.802 133.263 50.316C147.464 64.517 171.795 60.381 180.661 42.26C186.429 30.47 183.424 15.944 173.388 7.11099C167.768 2.16299 161.559 0 152.982 0C147.525 0 145.191 0.564005 140.086 3.11501ZM18.192 124.144C-0.205999 131.212 -5.254 156.841 8.953 171.048C23.75 185.845 48.553 181.448 57.172 162.5C60.421 155.356 60.37 145.28 57.05 138.526C53.682 131.675 47.399 125.665 41.504 123.656C34.865 121.394 24.801 121.604 18.192 124.144Z" fill="currentColor" />
    </svg>
  );
}

type SiteStatus = { site: string; live: boolean };

export function CommandHeader({
  onRun,
  loading,
  seed,
  showStatus = true,
}: {
  onRun: (prompt: string) => void;
  loading: boolean;
  seed?: Seed;
  showStatus?: boolean;
}) {
  // Site identity + LIVE dot come from the backend (GET /api/site): `site` is the DB-tunable app_config value; `live`
  // is a REAL probe of the live-data DB connection. Poll every 15s so the dot tracks the actual connection.
  const [status, setStatus] = useState<SiteStatus>({ site: "PEGEPL · SEETARAMPUR", live: true });

  useEffect(() => {
    let alive = true;
    const load = () =>
      fetch("/api/site")
        .then((r) => r.json())
        .then((d) => { if (alive && d.ok) setStatus({ site: d.site || "PEGEPL · SEETARAMPUR", live: !!d.live }); })
        .catch(() => { if (alive) setStatus((s) => ({ ...s, live: false })); });
    load();
    const t = window.setInterval(load, 15000);
    return () => { alive = false; window.clearInterval(t); };
  }, []);

  const { site, live } = status;

  return (
    <header className="cc-header">
      <div className="cc-logo"><NeuractMark /></div>
      <div className="cc-title">COMMAND CENTER</div>

      <div className="cc-barwrap">
        <PromptBar onRun={onRun} loading={loading} seed={seed} />
      </div>

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
