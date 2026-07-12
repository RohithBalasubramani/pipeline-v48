/** pages/ReplayPage.tsx — replay launcher: re-fire a prompt at the live host (:8770). The deterministic run id means
 *  the launched replay links to its trace immediately; a page run is LLM-bound (minutes) so the table polls while
 *  anything is queued/running. Concurrency is capped server-side (vLLM contention). */
import { useEffect, useRef, useState } from "react";
import { fetchReplays, postReplay } from "../api";
import { Chip, ms } from "../bits";
import { Loading, RunLink } from "../widgets";

const S_TONE: Record<string, string> = { done: "ok", running: "warn", queued: "warn", error: "err" };

export function ReplayPage() {
  const [prompt, setPrompt] = useState("");
  const [assetId, setAssetId] = useState("");
  const [rows, setRows] = useState<any[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = () =>
    fetchReplays().then((r) => setRows(r.replays)).catch((e) => setErr(e.message));

  useEffect(() => {
    refresh();
    timer.current = setInterval(() => {
      // poll only while something is in flight
      setRows((cur) => {
        if (cur?.some((x) => x.status === "queued" || x.status === "running")) refresh();
        return cur;
      });
    }, 4000);
    return () => { if (timer.current) clearInterval(timer.current); };
  }, []);

  const launch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    setBusy(true); setErr(null);
    try {
      await postReplay({ prompt: prompt.trim(), asset_id: assetId.trim() ? Number(assetId) || assetId.trim() : null });
      setPrompt("");
      await refresh();
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : String(ex));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <form className="px-replay-form" onSubmit={launch}>
        <div className="px-field" style={{ flex: 1, minWidth: 320 }}>
          <label>prompt</label>
          <input className="wide" style={{ width: "100%" }} value={prompt} placeholder="e.g. voltage and current for UPS-02"
                 onChange={(e) => setPrompt(e.target.value)} />
        </div>
        <div className="px-field"><label>asset id (pin, optional)</label>
          <input value={assetId} placeholder="mfm_id" onChange={(e) => setAssetId(e.target.value)} /></div>
        <button className="px-btn" disabled={busy || !prompt.trim()} type="submit">
          {busy ? "launching…" : "↻ Launch replay"}
        </button>
        <p className="px-note" style={{ width: "100%" }}>
          Runs the LIVE pipeline via host :8770 (up to ~5 min per page run; max 2 in flight — vLLM contention).
          The trace link is active immediately; artifacts append as the run progresses.
        </p>
      </form>
      {err && <div className="px-error-banner">{err}</div>}
      {!rows ? <Loading /> : (
        <div className="px-tablewrap">
          <table className="px-table">
            <thead><tr><th>started</th><th>status</th><th>prompt</th><th>trace</th>
              <th className="px-num">cards</th><th className="px-num">elapsed</th><th>result</th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.replay_id}>
                  <td className="px-muted">{r.started?.slice(5, 19).replace("T", " ")}</td>
                  <td><Chip tone={S_TONE[r.status] ?? ""}>{r.status}</Chip></td>
                  <td className="px-prompt-cell" title={r.prompt}>{r.prompt}</td>
                  <td><RunLink rid={r.response_run_id || r.run_id} /></td>
                  <td className="px-num">{r.cards ?? "—"}</td>
                  <td className="px-num">{ms(r.elapsed_ms)}</td>
                  <td>
                    {r.status === "done" ? (r.ok ? <Chip tone="ok">ok</Chip> : <Chip tone="warn">ok:false</Chip>) : null}
                    {r.asset_pending ? <Chip tone="warn">picker</Chip> : null}
                    {r.error ? <span style={{ color: "var(--coral-500)" }}>{r.error}</span> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!rows.length && <div className="px-empty">no replays launched yet this server session</div>}
        </div>
      )}
    </>
  );
}
