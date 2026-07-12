/** pages/CoveragePage.tsx — per-leaf coverage report: how much of what was served carried REAL data (leaf_stats),
 *  verdict mixes by page and by day, honest-blank cards with their reasons. */
import { useEffect, useState } from "react";
import { fetchCoverage } from "../api";
import { Bars, FilterBar, Loading, RunLink, Spark, Stat, VerdictMix, type Window, winQs } from "../widgets";

export function CoveragePage() {
  const [win, setWin] = useState<Window>({ from: "", to: "" });
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    setData(null);
    fetchCoverage(winQs(win) ? `?${winQs(win)}` : "").then(setData).catch((e) => setErr(e.message));
  }, [tick]);   // eslint-disable-line react-hooks/exhaustive-deps

  if (err) return <Loading err={err} />;
  const t = data?.totals;
  return (
    <>
      <FilterBar win={win} setWin={setWin} onApply={() => setTick(tick + 1)} />
      {!data ? <Loading /> : (
        <>
          <div className="px-statgrid">
            <Stat k="runs with cards" v={t.runs} />
            <Stat k="cards served" v={t.cards} />
            <Stat k="real leaf coverage" v={t.real_pct != null ? `${t.real_pct}%` : "—"}
                  sub={`${t.real.toLocaleString()} real / ${t.data.toLocaleString()} data leaves`} />
            <div className="px-stat">
              <div className="k">verdict mix</div>
              <div className="v"><VerdictMix render={t.render} partial={t.partial} blank={t.honest_blank} /></div>
              <div className="sub">render · partial · honest_blank</div>
            </div>
          </div>
          <div className="px-grid2">
            <Spark caption="real-leaf % by day"
                   points={(data.by_day || []).map((d: any) => ({ day: d.day, value: d.real_pct ?? 0 }))}
                   fmt={(n) => `${n}%`} />
            <div className="px-panel">
              <h3>top blank reasons</h3>
              <Bars rows={(data.top_blank_reasons || []).map((r: any) => ({ label: r.reason, value: r.count }))} />
            </div>
          </div>
          <div className="px-panel" style={{ marginTop: 12 }}>
            <h3>by page</h3>
            <div className="px-tablewrap" style={{ border: "none" }}>
              <table className="px-table">
                <thead><tr><th>page</th><th className="px-num">runs</th><th className="px-num">cards</th>
                  <th className="px-num">real %</th><th>verdicts</th></tr></thead>
                <tbody>
                  {(data.by_page || []).map((p: any) => (
                    <tr key={p.page_key}>
                      <td className="px-prompt-cell">{p.page_key}</td>
                      <td className="px-num">{p.runs}</td>
                      <td className="px-num">{p.cards}</td>
                      <td className="px-num">{p.real_pct != null ? `${p.real_pct}%` : "—"}</td>
                      <td><VerdictMix render={p.render} partial={p.partial} blank={p.honest_blank} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          {(data.honest_blanks || []).length > 0 && (
            <div className="px-panel" style={{ marginTop: 12 }}>
              <h3>honest-blank cards ({data.honest_blanks.length})</h3>
              <div className="px-tablewrap" style={{ border: "none" }}>
                <table className="px-table">
                  <thead><tr><th>run</th><th>card</th><th>title</th><th>page</th><th>reason</th></tr></thead>
                  <tbody>
                    {data.honest_blanks.map((b: any, i: number) => (
                      <tr key={i}>
                        <td><RunLink rid={b.run_id} /></td>
                        <td className="px-num">{b.card_id}</td>
                        <td className="px-prompt-cell">{b.title || "—"}</td>
                        <td className="px-prompt-cell">{b.page_key || "—"}</td>
                        <td className="px-prompt-cell" title={b.reason || ""}>{b.reason || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </>
  );
}
