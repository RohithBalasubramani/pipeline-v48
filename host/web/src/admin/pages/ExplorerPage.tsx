/** pages/ExplorerPage.tsx — pipeline explorer, fleet view: each raw stage's health across the window (runs touched,
 *  events, failures), plus page and asset drill-downs whose sample runs jump into the trace viewer. */
import { useEffect, useState } from "react";
import { fetchExplorer } from "../api";
import { ms } from "../bits";
import { FilterBar, Loading, RunLink, type Window, winQs } from "../widgets";

export function ExplorerPage() {
  const [win, setWin] = useState<Window>({ from: "", to: "" });
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    setData(null);
    fetchExplorer(winQs(win) ? `?${winQs(win)}` : "").then(setData).catch((e) => setErr(e.message));
  }, [tick]);   // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      <FilterBar win={win} setWin={setWin} onApply={() => setTick(tick + 1)} />
      {!data ? <Loading err={err} /> : (
        <>
          <div className="px-statgrid">
            {(data.stages || []).map((s: any) => (
              <div className="px-stat" key={s.stage}>
                <div className="k">{s.stage}</div>
                <div className="v">{s.runs} <span style={{ fontSize: 11, fontWeight: 400 }}>runs</span></div>
                <div className="sub">
                  {s.events.toLocaleString()} events
                  {s.failures ? <span style={{ color: "var(--coral-500)" }}> · {s.failures} fails</span> : ""}
                </div>
              </div>
            ))}
          </div>
          <div className="px-grid2">
            <div className="px-panel">
              <h3>pages ({(data.pages || []).length})</h3>
              <div className="px-tablewrap" style={{ border: "none" }}>
                <table className="px-table">
                  <thead><tr><th>page</th><th className="px-num">runs</th><th className="px-num">cards</th>
                    <th className="px-num">avg elapsed</th><th>sample runs</th></tr></thead>
                  <tbody>
                    {(data.pages || []).map((p: any) => (
                      <tr key={p.page_key}>
                        <td className="px-prompt-cell">{p.page_key}</td>
                        <td className="px-num">{p.runs}</td>
                        <td className="px-num">{p.cards}</td>
                        <td className="px-num">{ms(p.avg_elapsed_ms)}</td>
                        <td>{(p.run_ids || []).slice(0, 3).map((r: string) => <span key={r}><RunLink rid={r} />{" "}</span>)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="px-panel">
              <h3>assets ({(data.assets || []).length})</h3>
              <div className="px-tablewrap" style={{ border: "none" }}>
                <table className="px-table">
                  <thead><tr><th>asset</th><th>class</th><th className="px-num">runs</th><th>sample runs</th></tr></thead>
                  <tbody>
                    {(data.assets || []).map((a: any) => (
                      <tr key={a.asset}>
                        <td className="px-prompt-cell">{a.asset}</td>
                        <td>{a.asset_class || "—"}</td>
                        <td className="px-num">{a.runs}</td>
                        <td>{(a.run_ids || []).slice(0, 3).map((r: string) => <span key={r}><RunLink rid={r} />{" "}</span>)}</td>
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
