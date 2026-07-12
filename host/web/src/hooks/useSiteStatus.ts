import { useEffect, useState } from "react";
import { fetchSite } from "../api";

// The ONE /api/site poll loop — CommandHeader (15 s LIVE dot) and DataUnavailable (12 s outage probe) each hand-rolled
// the same fetch/interval/alive-guard idiom with different intervals; two independent pollers could even disagree
// about liveness on the same screen. Interval stays a per-caller parameter (the two cadences are intentional).
export function useSiteStatus(intervalMs = 15000, opts?: { initialLive?: boolean; initialSite?: string }) {
  const [status, setStatus] = useState<{ site: string; live: boolean; checkedAt: string }>({
    site: opts?.initialSite ?? "",
    live: opts?.initialLive ?? false,
    checkedAt: "",
  });

  useEffect(() => {
    let alive = true;
    const probe = () =>
      fetchSite()
        .then((d) => {
          if (!alive) return;
          setStatus((s) => ({
            site: (d.ok && d.site) ? d.site : s.site,
            live: !!d.live,
            checkedAt: new Date().toLocaleTimeString(),
          }));
        })
        .catch(() => {
          if (!alive) return;
          setStatus((s) => ({ ...s, live: false, checkedAt: new Date().toLocaleTimeString() }));
        });
    probe();
    const t = window.setInterval(probe, intervalMs);
    return () => { alive = false; window.clearInterval(t); };
  }, [intervalMs]);

  return status;
}
