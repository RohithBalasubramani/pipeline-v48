/** pages/SqlPage.tsx — SQL execution report (obs/sql_trace records): what ran where, how slow, what failed;
 *  searchable by SQL text, filterable by source db / floor latency / run id. */
import { useEffect, useState } from "react";
import { fetchSql } from "../api";
import { FilterBar, Loading, RunLink, Stat, type Window, winQs } from "../widgets";

export function SqlPage() {
  const [win, setWin] = useState<Window>({ from: "", to: "" });
  const [q, setQ] = useState("");
  const [source, setSource] = useState("");
  const [slowMs, setSlowMs] = useState("");
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    setData(null);
    const parts = [winQs(win), q ? `q=${encodeURIComponent(q)}` : "", source ? `source=${encodeURIComponent(source)}` : "",
                   slowMs ? `slow_ms=${encodeURIComponent(slowMs)}` : "", "limit=150"].filter(Boolean).join("&");
    fetchSql(parts ? `?${parts}` : "").then(setData).catch((e) => setErr(e.message));
  }, [tick]);   // eslint-disable-line react-hooks/exhaustive-deps

  const sqlTable = (rows: any[], caption: string) => (
    <div className="px-panel" style={{ marginTop: 12 }}>
      <h3>{caption}</h3>
      <div className="px-tablewrap" style={{ border: "none" }}>
        <table className="px-table">
          <thead><tr><th>when</th><th>run</th><th>db</th><th>sql</th><th className="px-num">rows</th><th className="px-num">ms</th></tr></thead>
          <tbody>
            {rows.map((r: any, i: number) => (
              <tr key={i}>
                <td className="px-muted">{r.ts?.slice(5, 19).replace("T", " ") || "—"}</td>
                <td><RunLink rid={r.run_id} /></td>
                <td>{r.db}</td>
                <td style={{ maxWidth: 620, wordBreak: "break-word" }} title={r.params ? `params: ${r.params}` : undefined}>
                  {r.sql}{r.err ? <span style={{ color: "var(--coral-500)" }}> — {r.err}</span> : null}
                </td>
                <td className="px-num">{r.rows ?? "—"}</td>
                <td className="px-num" style={(r.ms || 0) > 1000 ? { color: "var(--coral-700)", fontWeight: 700 } : undefined}>{r.ms ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && <div className="px-empty">nothing matches</div>}
      </div>
    </div>
  );

  return (
    <>
      <FilterBar win={win} setWin={setWin} q={q} setQ={setQ} qLabel="sql text"
                 extra={<>
                   <div className="px-field"><label>source db</label>
                     <input value={source} placeholder="neuract / cmd_catalog" onChange={(e) => setSource(e.target.value)} /></div>
                   <div className="px-field"><label>min ms</label>
                     <input value={slowMs} placeholder="e.g. 500" onChange={(e) => setSlowMs(e.target.value)} /></div>
                 </>}
                 onApply={() => setTick(tick + 1)} />
      {!data ? <Loading err={err} /> : (
        <>
          <div className="px-statgrid">
            <Stat k="executions" v={data.total.toLocaleString()} />
            <Stat k="errors" v={data.errors} />
            {(data.by_source || []).map((s: any) => (
              <Stat key={s.source} k={s.source} v={s.count.toLocaleString()}
                    sub={`avg ${s.avg_ms ?? "—"}ms · ${s.rows.toLocaleString()} rows${s.errors ? ` · ${s.errors} err` : ""}`} />
            ))}
          </div>
          {sqlTable(data.slowest || [], "slowest")}
          {sqlTable(data.recent || [], "recent")}
        </>
      )}
    </>
  );
}
