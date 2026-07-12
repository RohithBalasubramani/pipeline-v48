/** pages/ValidationPage.tsx — validation log: each run's pre-L2 page verdict + column pass/warn/fail summary +
 *  per-card validation mix, and the external harness sessions (outputs/validation/sessions). */
import { useEffect, useState } from "react";
import { fetchValidation } from "../api";
import { Chip, JsonBlock } from "../bits";
import { FilterBar, Loading, RunLink, type Window, winQs } from "../widgets";

const V_TONE: Record<string, string> = { pass: "ok", warn: "warn", pass_with_gaps: "warn", fail: "err", asset_pending: "skip" };

export function ValidationPage() {
  const [win, setWin] = useState<Window>({ from: "", to: "" });
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    setData(null);
    fetchValidation(winQs(win) ? `?${winQs(win)}` : "").then(setData).catch((e) => setErr(e.message));
  }, [tick]);   // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      <FilterBar win={win} setWin={setWin} onApply={() => setTick(tick + 1)} />
      {!data ? <Loading err={err} /> : (
        <>
          <div className="px-panel">
            <h3>per-run validation ({(data.runs || []).length})</h3>
            <div className="px-tablewrap" style={{ border: "none" }}>
              <table className="px-table">
                <thead><tr><th>when</th><th>run</th><th>prompt</th><th>page</th><th>verdict</th>
                  <th className="px-num">cols ✓/△/✗</th><th className="px-num">gap frac</th><th>cards</th></tr></thead>
                <tbody>
                  {(data.runs || []).map((r: any) => {
                    const d = r.data_summary || {};
                    return (
                      <tr key={r.run_id}>
                        <td className="px-muted">{r.ts?.slice(5, 16).replace("T", " ")}</td>
                        <td><RunLink rid={r.run_id} /></td>
                        <td className="px-prompt-cell" title={r.prompt || ""}>{r.prompt || "—"}</td>
                        <td className="px-prompt-cell">{r.page_key || "—"}</td>
                        <td><Chip tone={V_TONE[r.verdict] ?? ""}>{r.verdict}</Chip>
                            {r.validation_blocked ? <Chip tone="err">blocked</Chip> : null}</td>
                        <td className="px-num">{d.n_columns != null ? `${d.n_pass}/${d.n_warn}/${d.n_fail}` : "—"}</td>
                        <td className="px-num">{r.expected_gap_frac ?? "—"}</td>
                        <td>{Object.entries(r.card_verdicts || {}).map(([k, v]) =>
                          <Chip key={k} tone={V_TONE[k] ?? ""}>{k} {String(v)}</Chip>)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
          <div className="px-panel" style={{ marginTop: 12 }}>
            <h3>harness sessions ({(data.sessions || []).length})</h3>
            {!(data.sessions || []).length && <div className="px-empty">no harness sessions recorded (outputs/validation/sessions)</div>}
            {(data.sessions || []).map((s: any) => (
              <div key={s.session} className="px-sec">
                <h4>{s.session} — {s.manifest?.passed ?? "?"} passed / {s.manifest?.failed ?? "?"} failed
                  {s.manifest?.finished_at ? ` · ${s.manifest.finished_at}` : ""}</h4>
                <div className="px-tablewrap">
                  <table className="px-table">
                    <thead><tr><th>case</th><th>prompt</th><th>run</th><th>outcome</th><th>judgment</th><th>why</th></tr></thead>
                    <tbody>
                      {(s.cases || []).map((c: any) => (
                        <tr key={c.case_id}>
                          <td>{c.case_id}</td>
                          <td className="px-prompt-cell" title={c.prompt || ""}>{c.prompt}</td>
                          <td>{c.run_id ? <RunLink rid={c.run_id} /> : "—"}</td>
                          <td>{c.outcome}</td>
                          <td><Chip tone={c.pass ? (c.degraded ? "warn" : "ok") : "err"}>
                            {c.pass ? (c.degraded ? "degraded pass" : "pass") : `fail @ ${c.stage || "?"}`}</Chip></td>
                          <td className="px-prompt-cell" title={c.why || ""}>{c.why || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
          {data.runs?.length ? null : <JsonBlock value={null} />}
        </>
      )}
    </>
  );
}
