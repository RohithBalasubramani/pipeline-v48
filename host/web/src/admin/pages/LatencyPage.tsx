/** pages/LatencyPage.tsx — latency report: per-stage spacing stats (stage lines are end-markers), end-to-end
 *  elapsed trend by day, and the slowest runs linking into their traces. */
import { useEffect, useState } from "react";
import { fetchLatency } from "../api";
import { ms } from "../bits";
import { FilterBar, Loading, RunLink, Spark, type Window, winQs } from "../widgets";

export function LatencyPage() {
  const [win, setWin] = useState<Window>({ from: "", to: "" });
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    setData(null);
    fetchLatency(winQs(win) ? `?${winQs(win)}` : "").then(setData).catch((e) => setErr(e.message));
  }, [tick]);   // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      <FilterBar win={win} setWin={setWin} onApply={() => setTick(tick + 1)} />
      {!data ? <Loading err={err} /> : (
        <>
          <div className="px-grid2">
            <Spark caption="avg end-to-end by day (ms)"
                   points={(data.by_day || []).map((d: any) => ({ day: d.day, value: d.avg_ms }))}
                   fmt={(n) => ms(n)} />
            <Spark caption="p90 end-to-end by day (ms)"
                   points={(data.by_day || []).map((d: any) => ({ day: d.day, value: d.p90_ms }))}
                   fmt={(n) => ms(n)} />
          </div>
          <div className="px-grid2" style={{ marginTop: 12 }}>
            <div className="px-panel">
              <h3>per-stage spacing (since previous event)</h3>
              <div className="px-tablewrap" style={{ border: "none" }}>
                <table className="px-table">
                  <thead><tr><th>stage</th><th className="px-num">n</th><th className="px-num">avg</th>
                    <th className="px-num">p50</th><th className="px-num">p90</th><th className="px-num">max</th></tr></thead>
                  <tbody>
                    {(data.stages || []).map((s: any) => (
                      <tr key={s.stage}>
                        <td>{s.stage}</td>
                        <td className="px-num">{s.count}</td>
                        <td className="px-num">{ms(s.avg_ms)}</td>
                        <td className="px-num">{ms(s.p50_ms)}</td>
                        <td className="px-num">{ms(s.p90_ms)}</td>
                        <td className="px-num">{ms(s.max_ms)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="px-note">1a∥1b and per-card fan-outs overlap in wall time — read these as event spacing;
                end-to-end elapsed is the honest figure.</p>
            </div>
            <div className="px-panel">
              <h3>slowest runs</h3>
              <div className="px-tablewrap" style={{ border: "none" }}>
                <table className="px-table">
                  <thead><tr><th>run</th><th>when</th><th>prompt</th><th className="px-num">cards</th><th className="px-num">elapsed</th></tr></thead>
                  <tbody>
                    {(data.slowest || []).map((r: any) => (
                      <tr key={r.run_id}>
                        <td><RunLink rid={r.run_id} /></td>
                        <td className="px-muted">{r.ts?.slice(5, 16).replace("T", " ")}</td>
                        <td className="px-prompt-cell" title={r.prompt || ""}>{r.prompt}</td>
                        <td className="px-num">{r.cards ?? "—"}</td>
                        <td className="px-num">{ms(r.elapsed_ms)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
}
