/** admin/AiCallRow.tsx — one LLM call: slim header row (stage · tokens · finish) expanding to prompt/reply heads,
 *  parsed reply JSON when it fits, and an on-demand "load full call" fetch of the complete request/response bodies
 *  (admin/api/run/<rid>/ai/<idx> — the multi-MB records are never loaded in bulk). Confidence/reasoning fields the
 *  models emit (1b `confident`, basket `confidence`/`why`, L2 `swap_decision.confidence/criterion/reason`) live in
 *  the reply JSON shown here. */
import { useState } from "react";
import { fetchAiCall, type AiCall } from "./api";
import { Chip, JsonBlock, tok } from "./bits";

function parsedReply(head: string): any | null {
  try {
    const j = JSON.parse(head);
    return typeof j === "object" ? j : null;
  } catch {
    return null;
  }
}

export function AiCallRow({ rid, call }: { rid: string; call: AiCall }) {
  const [open, setOpen] = useState(false);
  const [full, setFull] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const reply = parsedReply(call.resp_head);

  const loadFull = async () => {
    setBusy(true);
    setErr(null);
    try {
      const r = await fetchAiCall(rid, call.idx);
      setFull(r.call ?? r);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const fullMsgs: any[] = full?.request?.messages ?? [];
  const fullReply = full?.response?.choices?.[0]?.message?.content;
  const usage = full?.response?.usage;

  return (
    <div className="px-ai">
      <div className="px-ai-head" onClick={() => setOpen(!open)}>
        <span style={{ color: "var(--slate-soft)" }}>#{call.idx}</span>
        <Chip>{call.stage}</Chip>
        <span className="px-muted">{call.ts?.slice(11, 19) || "—"}</span>
        <span>{tok(call.ptok)}→{tok(call.ctok)} tok</span>
        {call.finish && call.finish !== "stop" ? <Chip tone="err">{call.finish}</Chip> : null}
        {call.guided_json ? <span className="px-muted">guided</span> : null}
        <span className="px-muted" style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {call.resp_head?.slice(0, 110)}
        </span>
      </div>
      {open && (
        <div className="px-ai-body">
          <div className="px-sec"><h4>system (head)</h4><pre className="px-json">{call.sys_head || "—"}</pre></div>
          <div className="px-sec"><h4>user (head)</h4><pre className="px-json">{call.user_head || "—"}</pre></div>
          <div className="px-sec">
            <h4>reply {reply ? "(parsed)" : "(head)"}</h4>
            {reply ? <JsonBlock value={reply} /> : <pre className="px-json">{call.resp_head || "—"}</pre>}
          </div>
          {!full ? (
            <button className="px-btn ghost" onClick={loadFull} disabled={busy} style={{ height: 26 }}>
              {busy ? "loading…" : `load full call (${Math.round(call.req_chars / 1024)} KB prompt)`}
            </button>
          ) : (
            <>
              {usage && (
                <p className="px-note">
                  usage: prompt {tok(usage.prompt_tokens)} · completion {tok(usage.completion_tokens)} · total {tok(usage.total_tokens)}
                  {full?.request?.model ? ` · ${full.request.model}` : ""}
                </p>
              )}
              {fullMsgs.map((m: any, i: number) => (
                <div className="px-sec" key={i}>
                  <h4>{m.role} (full)</h4>
                  <JsonBlock value={m.content} fold={4000} label={`${m.role} message`} />
                </div>
              ))}
              <div className="px-sec">
                <h4>reply (full)</h4>
                <JsonBlock value={fullReply ?? full?.response} fold={4000} label="reply" />
              </div>
            </>
          )}
          {err && <p className="px-note" style={{ color: "var(--coral-500)" }}>{err}</p>}
        </div>
      )}
    </div>
  );
}
