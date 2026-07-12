/** pages/SearchPage.tsx — search: prompts (→ matching runs) and errors (→ failure rows), both windowed, both
 *  landing on the trace viewer. */
import { useState } from "react";
import { searchErrors, searchPrompts, type RunSummary } from "../api";
import { ms, tok } from "../bits";
import { FilterBar, Loading, RunLink, VerdictMix, type Window, winQs } from "../widgets";
import { navigate, traceHref } from "../router";

export function SearchPage() {
  const [mode, setMode] = useState<"prompts" | "errors">("prompts");
  const [win, setWin] = useState<Window>({ from: "", to: "" });
  const [q, setQ] = useState("");
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [hits, setHits] = useState<any[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const go = async (m = mode, query = q) => {
    setBusy(true); setErr(null);
    try {
      const parts = [`q=${encodeURIComponent(query)}`, winQs(win)].filter(Boolean).join("&");
      if (m === "prompts") setRuns((await searchPrompts(`?${parts}`)).runs);
      else setHits((await searchErrors(`?${parts}&limit=200`)).hits);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div className="px-tabs">
        <button className={mode === "prompts" ? "on" : ""} onClick={() => setMode("prompts")}>Prompt search</button>
        <button className={mode === "errors" ? "on" : ""} onClick={() => setMode("errors")}>Error search</button>
      </div>
      <FilterBar win={win} setWin={setWin} q={q} setQ={setQ}
                 qLabel={mode === "prompts" ? "prompt text" : "error reason / detail"}
                 onApply={() => go()} />
      {busy && <Loading />}
      {err && <Loading err={err} />}
      {mode === "prompts" && runs && !busy && (
        <div className="px-tablewrap">
          <table className="px-table">
            <thead><tr><th>when</th><th>run</th><th>prompt</th><th>page</th><th>asset</th>
              <th className="px-num">cards</th><th>verdicts</th><th className="px-num">elapsed</th><th className="px-num">tokens</th></tr></thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.run_id} className="click" onClick={() => navigate(traceHref(r.run_id))}>
                  <td className="px-muted">{r.ts?.slice(5, 16).replace("T", " ")}</td>
                  <td onClick={(e) => e.stopPropagation()}><RunLink rid={r.run_id} /></td>
                  <td className="px-prompt-cell" title={r.prompt || ""}>{r.prompt}</td>
                  <td className="px-prompt-cell">{r.page_key || "—"}</td>
                  <td>{r.asset || "—"}</td>
                  <td className="px-num">{r.cards ?? "—"}</td>
                  <td><VerdictMix render={r.rendered} partial={r.partial} blank={r.blank} /></td>
                  <td className="px-num">{ms(r.elapsed_ms)}</td>
                  <td className="px-num">{tok(r.prompt_tokens + r.completion_tokens)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!runs.length && <div className="px-empty">no prompts match</div>}
        </div>
      )}
      {mode === "errors" && hits && !busy && (
        <div className="px-tablewrap">
          <table className="px-table">
            <thead><tr><th>when</th><th>run</th><th>stage</th><th>card</th><th>reason</th><th>detail</th></tr></thead>
            <tbody>
              {hits.map((f: any, i: number) => (
                <tr key={i}>
                  <td className="px-muted">{f.ts?.slice(5, 19).replace("T", " ")}</td>
                  <td><RunLink rid={f.run_id} /></td>
                  <td>{f.stage || "—"}</td>
                  <td className="px-num">{f.card_id ?? "—"}</td>
                  <td style={{ color: "var(--coral-700)", fontWeight: 700 }}>{f.reason}</td>
                  <td className="px-prompt-cell" style={{ maxWidth: 520 }} title={f.detail || ""}>{f.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!hits.length && <div className="px-empty">no errors match</div>}
        </div>
      )}
    </>
  );
}
