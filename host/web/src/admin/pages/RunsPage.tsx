/** pages/RunsPage.tsx — recent pipeline runs: date window + text query over prompt/run_id/page/asset, newest first,
 *  every row linking into the trace viewer. */
import { useEffect, useState } from "react";
import { fetchRuns, type RunSummary } from "../api";
import { tok, ms } from "../bits";
import { FilterBar, Loading, RunLink, Stat, VerdictMix, type Window } from "../widgets";
import { navigate, traceHref } from "../router";

export function RunsPage() {
  const [win, setWin] = useState<Window>({ from: "", to: "" });
  const [q, setQ] = useState("");
  const [data, setData] = useState<{ total: number; runs: RunSummary[] } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    setData(null);
    fetchRuns({ from: win.from, to: win.to, q, limit: "100" })
      .then(setData)
      .catch((e) => setErr(e.message));
  }, [tick]);   // eslint-disable-line react-hooks/exhaustive-deps — fetch on Apply, not per keystroke

  const runs = data?.runs ?? [];
  const totTok = runs.reduce((s, r) => s + (r.prompt_tokens || 0) + (r.completion_tokens || 0), 0);
  return (
    <>
      <FilterBar win={win} setWin={setWin} q={q} setQ={setQ} qLabel="prompt / run / page / asset"
                 onApply={() => setTick(tick + 1)} />
      {!data ? <Loading err={err} /> : (
        <>
          <div className="px-statgrid">
            <Stat k="runs in window" v={data.total} />
            <Stat k="ai tokens (listed)" v={tok(totTok)} />
            <Stat k="failure rows" v={runs.reduce((s, r) => s + (r.n_failures || 0), 0).toLocaleString()} />
            <Stat k="sql reads" v={runs.reduce((s, r) => s + (r.n_sql || 0), 0).toLocaleString()} />
          </div>
          <div className="px-tablewrap">
            <table className="px-table">
              <thead><tr>
                <th>when</th><th>run</th><th>prompt</th><th>page</th><th>asset</th>
                <th className="px-num">cards</th><th>verdicts</th><th className="px-num">elapsed</th>
                <th className="px-num">execs</th><th className="px-num">fails</th>
                <th className="px-num">ai</th><th className="px-num">tokens</th><th className="px-num">sql</th>
              </tr></thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.run_id} className="click" onClick={() => navigate(traceHref(r.run_id))}>
                    <td className="px-muted">{r.ts?.slice(5, 16).replace("T", " ") || "—"}</td>
                    <td onClick={(e) => e.stopPropagation()}><RunLink rid={r.run_id} /></td>
                    <td className="px-prompt-cell" title={r.prompt || ""}>{r.prompt || <span className="px-muted">—</span>}</td>
                    <td>{r.page_key || (r.kind === "knowledge" ? "knowledge" : "—")}</td>
                    <td>{r.asset || "—"}{r.asset_how ? <span className="px-muted"> · {r.asset_how}</span> : null}</td>
                    <td className="px-num">{r.cards ?? "—"}</td>
                    <td><VerdictMix render={r.rendered} partial={r.partial} blank={r.blank} /></td>
                    <td className="px-num">{ms(r.elapsed_ms)}</td>
                    <td className="px-num">{r.executions}</td>
                    <td className="px-num" style={r.n_failures ? { color: "var(--coral-500)" } : undefined}>{r.n_failures || 0}</td>
                    <td className="px-num">{r.n_ai_calls}</td>
                    <td className="px-num">{tok(r.prompt_tokens + r.completion_tokens)}</td>
                    <td className="px-num">{r.n_sql}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!runs.length && <div className="px-empty">no runs match</div>}
          </div>
        </>
      )}
    </>
  );
}
