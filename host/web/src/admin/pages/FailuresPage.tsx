/** pages/FailuresPage.tsx — failure report: aggregates by reason/stage/day + the filtered recent list. The failures
 *  sink is comprehensive (stage-hook mirror + classified LLM failures), so this page is also the error explorer.
 *  Real failures are the primary view; honest-blank reason telemetry (stage=="reason", mirrored into the sink by
 *  design) arrives pre-bucketed as `blank_reasons` and renders as a collapsed secondary section. */
import { useEffect, useState } from "react";
import { fetchFailures } from "../api";
import { Bars, FilterBar, Loading, RunLink, Spark, type Window, winQs } from "../widgets";

export function FailuresPage() {
  const [win, setWin] = useState<Window>({ from: "", to: "" });
  const [q, setQ] = useState("");
  const [reason, setReason] = useState("");
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    setData(null);
    const parts = [winQs(win), q ? `q=${encodeURIComponent(q)}` : "", reason ? `reason=${encodeURIComponent(reason)}` : "", "limit=200"]
      .filter(Boolean).join("&");
    fetchFailures(parts ? `?${parts}` : "").then(setData).catch((e) => setErr(e.message));
  }, [tick]);   // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      <FilterBar win={win} setWin={setWin} q={q} setQ={setQ} qLabel="reason / detail / stage"
                 extra={
                   <div className="px-field"><label>reason</label>
                     <input value={reason} placeholder="e.g. timeout" onChange={(e) => setReason(e.target.value)} /></div>
                 }
                 onApply={() => setTick(tick + 1)} />
      {!data ? <Loading err={err} /> : (
        <>
          <div className="px-grid2">
            <div className="px-panel"><h3>by reason ({data.total.toLocaleString()} real failures)</h3>
              <Bars err rows={(data.by_reason || []).slice(0, 14).map((r: any) => ({ label: r.reason || "—", value: r.count }))} /></div>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <Spark caption="failures by day" points={(data.by_day || []).map((d: any) => ({ day: d.day, value: d.count }))} />
              <div className="px-panel"><h3>by stage</h3>
                <Bars err rows={(data.by_stage || []).slice(0, 8).map((r: any) => ({ label: r.stage || "—", value: r.count }))} /></div>
            </div>
          </div>
          <div className="px-panel" style={{ marginTop: 12 }}>
            <h3>recent ({(data.recent || []).length} shown)</h3>
            <div className="px-tablewrap" style={{ border: "none" }}>
              <table className="px-table">
                <thead><tr><th>when</th><th>run</th><th>stage</th><th>card</th><th>reason</th><th>detail</th></tr></thead>
                <tbody>
                  {(data.recent || []).map((f: any, i: number) => (
                    <tr key={i}>
                      <td className="px-muted">{f.ts?.slice(5, 19).replace("T", " ") || "—"}</td>
                      <td><RunLink rid={f.run_id} /></td>
                      <td>{f.stage || "—"}</td>
                      <td className="px-num">{f.card_id ?? "—"}</td>
                      <td style={{ color: "var(--coral-700)", fontWeight: 700 }}>{f.reason}</td>
                      <td className="px-prompt-cell" style={{ maxWidth: 520 }} title={f.detail || ""}>{f.detail}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          {data.honest_gaps ? <HonestGapsPanel hg={data.honest_gaps} /> : null}
          {data.blank_reasons ? <BlankReasonsPanel br={data.blank_reasons} /> : null}
          {data.quarantined || data.dedup ? (
            <div className="px-muted" style={{ marginTop: 8, fontSize: 12 }}>
              excluded from the failure aggregates: {(data.quarantined?.total ?? 0).toLocaleString()} quarantined
              pre-2026-07-12 pytest artifacts · {((data.dedup?.layer_exception_twins ?? 0) +
              (data.dedup?.fill_gap_mirrors ?? 0)).toLocaleString()} historical write-twin/mirror rows
              ({data.dedup?.layer_exception_twins ?? 0} exception twins, {data.dedup?.fill_gap_mirrors ?? 0} gap mirrors)
            </div>
          ) : null}
        </>
      )}
    </>
  );
}

/** Collapsed secondary section: PER-CARD answerability gaps (reason=="fill_gap", stage=="L2.card") — a card the
 *  AI honestly declared unanswerable on this asset (valid terminal per the reflect contract), with the AI's own
 *  note as detail. Telemetry, not failures. */
function HonestGapsPanel({ hg }: { hg: any }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="px-panel" style={{ marginTop: 12 }}>
      <h3 style={{ cursor: "pointer", userSelect: "none" }} onClick={() => setOpen(!open)}>
        <span className="px-muted" style={{ display: "inline-block", width: 14 }}>{open ? "▼" : "▶"}</span>{" "}
        Honest answerability gaps (per-card, valid terminals) — {(hg.total ?? 0).toLocaleString()}
      </h3>
      {open && (
        <>
          <Spark caption="gaps by day" points={(hg.by_day || []).map((d: any) => ({ day: d.day, value: d.count }))} />
          <h3 style={{ marginTop: 12 }}>recent ({(hg.recent || []).length} shown)</h3>
          <div className="px-tablewrap" style={{ border: "none" }}>
            <table className="px-table">
              <thead><tr><th>when</th><th>run</th><th>card</th><th>note</th></tr></thead>
              <tbody>
                {(hg.recent || []).map((f: any, i: number) => (
                  <tr key={i}>
                    <td className="px-muted">{f.ts?.slice(5, 19).replace("T", " ") || "—"}</td>
                    <td><RunLink rid={f.run_id} /></td>
                    <td className="px-num">{f.card_id ?? "—"}</td>
                    <td className="px-prompt-cell" style={{ maxWidth: 640 }} title={f.detail || ""}>{f.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

/** Collapsed secondary section: per-leaf honest-blank REASON telemetry (stage=="reason") — deliberately mirrored
 *  into the failures sink, NOT failures. Teal bars (non-error hue) + the same recent-table layout. */
function BlankReasonsPanel({ br }: { br: any }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="px-panel" style={{ marginTop: 12 }}>
      <h3 style={{ cursor: "pointer", userSelect: "none" }} onClick={() => setOpen(!open)}>
        <span className="px-muted" style={{ display: "inline-block", width: 14 }}>{open ? "▼" : "▶"}</span>{" "}
        Honest-blank reasons (telemetry, not failures) — {(br.total ?? 0).toLocaleString()}
      </h3>
      {open && (
        <>
          <Bars rows={(br.by_reason || []).slice(0, 14).map((r: any) => ({ label: r.reason || "—", value: r.count }))} />
          <h3 style={{ marginTop: 12 }}>recent ({(br.recent || []).length} shown)</h3>
          <div className="px-tablewrap" style={{ border: "none" }}>
            <table className="px-table">
              <thead><tr><th>when</th><th>run</th><th>card</th><th>reason</th><th>detail</th></tr></thead>
              <tbody>
                {(br.recent || []).map((f: any, i: number) => (
                  <tr key={i}>
                    <td className="px-muted">{f.ts?.slice(5, 19).replace("T", " ") || "—"}</td>
                    <td><RunLink rid={f.run_id} /></td>
                    <td className="px-num">{f.card_id ?? "—"}</td>
                    <td>{f.reason}</td>
                    <td className="px-prompt-cell" style={{ maxWidth: 520 }} title={f.detail || ""}>{f.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
