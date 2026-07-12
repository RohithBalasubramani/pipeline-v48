/** pages/AssetsPage.tsx — asset-resolution log: how 1b resolved each execution (confident pin / ambiguous picker /
 *  user-choice / empty), candidate counts, class priors, gate decisions. */
import { useEffect, useState } from "react";
import { fetchAssetsLogQs } from "../api";
import { Chip } from "../bits";
import { Bars, FilterBar, Loading, RunLink, type Window, winQs } from "../widgets";

const HOW_TONE: Record<string, string> = { AI: "ok", confident: "ok", "user-choice": "", pinned: "", ambiguous: "warn", empty: "err" };

export function AssetsPage() {
  const [win, setWin] = useState<Window>({ from: "", to: "" });
  const [q, setQ] = useState("");
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    setData(null);
    const parts = [winQs(win), q ? `q=${encodeURIComponent(q)}` : ""].filter(Boolean).join("&");
    fetchAssetsLogQs(parts ? `?${parts}` : "").then(setData).catch((e) => setErr(e.message));
  }, [tick]);   // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      <FilterBar win={win} setWin={setWin} q={q} setQ={setQ} qLabel="asset / prompt"
                 onApply={() => setTick(tick + 1)} />
      {!data ? <Loading err={err} /> : (
        <>
          <div className="px-grid2">
            <div className="px-panel"><h3>resolution outcome</h3>
              <Bars rows={(data.by_how || []).map((h: any) => ({ label: h.how, value: h.count }))} /></div>
            <div className="px-panel"><h3>most-resolved assets</h3>
              <Bars rows={(data.by_asset || []).slice(0, 12).map((a: any) => ({ label: a.asset, value: a.count }))} /></div>
          </div>
          <div className="px-panel" style={{ marginTop: 12 }}>
            <h3>events ({(data.events || []).length} shown)</h3>
            <div className="px-tablewrap" style={{ border: "none" }}>
              <table className="px-table">
                <thead><tr><th>when</th><th>run</th><th>prompt</th><th>asset</th><th>how</th>
                  <th className="px-num">candidates</th><th className="px-num">basket cols</th><th>gate</th></tr></thead>
                <tbody>
                  {(data.events || []).map((e: any, i: number) => (
                    <tr key={i}>
                      <td className="px-muted">{e.ts?.slice(5, 16).replace("T", " ") || "—"}</td>
                      <td><RunLink rid={e.run_id} /></td>
                      <td className="px-prompt-cell" title={e.prompt || ""}>{e.prompt || "—"}</td>
                      <td>{e.asset || "—"}{e.class_mismatch ? <Chip tone="warn">class mismatch</Chip> : null}</td>
                      <td><Chip tone={HOW_TONE[e.how] ?? ""}>{e.how || "—"}</Chip></td>
                      <td className="px-num">{e.candidates ?? "—"}</td>
                      <td className="px-num">{e.basket_cols ?? "—"}</td>
                      <td className="px-prompt-cell" title={e.gate_decision || ""}>
                        {e.no_data ? <Chip tone="err">no data</Chip> : null} {e.gate_decision || "—"}
                      </td>
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
