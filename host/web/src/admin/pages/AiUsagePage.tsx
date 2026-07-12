/** pages/AiUsagePage.tsx — AI usage: call/token totals, spend by day / stage / model, heaviest calls → traces. */
import { useEffect, useState } from "react";
import { fetchUsage } from "../api";
import { tok } from "../bits";
import { Bars, FilterBar, Loading, RunLink, Spark, Stat, type Window, winQs } from "../widgets";

export function AiUsagePage() {
  const [win, setWin] = useState<Window>({ from: "", to: "" });
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    setData(null);
    fetchUsage(winQs(win) ? `?${winQs(win)}` : "").then(setData).catch((e) => setErr(e.message));
  }, [tick]);   // eslint-disable-line react-hooks/exhaustive-deps

  const t = data?.totals;
  return (
    <>
      <FilterBar win={win} setWin={setWin} onApply={() => setTick(tick + 1)} />
      {!data ? <Loading err={err} /> : (
        <>
          <div className="px-statgrid">
            <Stat k="llm calls" v={t.calls.toLocaleString()} sub={`${t.runs} runs`} />
            <Stat k="prompt tokens" v={tok(t.prompt_tokens)} />
            <Stat k="completion tokens" v={tok(t.completion_tokens)} />
            <Stat k="total tokens" v={tok(t.total_tokens)} />
          </div>
          <div className="px-grid2">
            <Spark caption="total tokens by day"
                   points={(data.by_day || []).map((d: any) => ({ day: d.day, value: (d.prompt_tokens || 0) + (d.completion_tokens || 0) }))}
                   fmt={(n) => tok(n)} />
            <div className="px-panel"><h3>calls by stage</h3>
              <Bars rows={(data.by_stage || []).map((s: any) => ({
                label: s.stage, value: s.calls,
                hint: `${s.stage}: ${s.calls} calls · ${tok(s.prompt_tokens)}→${tok(s.completion_tokens)} tok` }))} /></div>
          </div>
          <div className="px-grid2" style={{ marginTop: 12 }}>
            <div className="px-panel"><h3>by model</h3>
              <div className="px-tablewrap" style={{ border: "none" }}>
                <table className="px-table">
                  <thead><tr><th>model</th><th className="px-num">calls</th><th className="px-num">prompt tok</th><th className="px-num">completion tok</th></tr></thead>
                  <tbody>
                    {(data.by_model || []).map((m: any) => (
                      <tr key={m.model}><td>{m.model}</td><td className="px-num">{m.calls.toLocaleString()}</td>
                        <td className="px-num">{tok(m.prompt_tokens)}</td><td className="px-num">{tok(m.completion_tokens)}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="px-panel"><h3>token spend by stage</h3>
              <Bars rows={(data.by_stage || []).map((s: any) => ({
                label: s.stage, value: (s.prompt_tokens || 0) + (s.completion_tokens || 0) }))} /></div>
          </div>
          <div className="px-panel" style={{ marginTop: 12 }}>
            <h3>heaviest calls</h3>
            <div className="px-tablewrap" style={{ border: "none" }}>
              <table className="px-table">
                <thead><tr><th>run</th><th>when</th><th>stage</th><th className="px-num">prompt</th>
                  <th className="px-num">completion</th><th className="px-num">total</th><th>finish</th><th>system head</th></tr></thead>
                <tbody>
                  {(data.heaviest || []).map((h: any, i: number) => (
                    <tr key={i}>
                      <td><RunLink rid={h.run_id} /></td>
                      <td className="px-muted">{h.ts?.slice(5, 16).replace("T", " ")}</td>
                      <td>{h.stage}</td>
                      <td className="px-num">{tok(h.ptok)}</td>
                      <td className="px-num">{tok(h.ctok)}</td>
                      <td className="px-num" style={{ fontWeight: 700 }}>{tok(h.ttok)}</td>
                      <td>{h.finish === "stop" ? <span className="px-muted">stop</span> : <b style={{ color: "var(--coral-500)" }}>{h.finish || "—"}</b>}</td>
                      <td className="px-prompt-cell" style={{ maxWidth: 340 }}>{h.sys_head}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </>
  );
}
