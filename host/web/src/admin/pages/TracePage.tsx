/** pages/TracePage.tsx — the trace viewer: ONE run's full story. Execution picker (same prompt appends to the same
 *  trace files), the nine-stage accordion (stageMap folds stage records + AI calls + SQL + failures into the fixed
 *  pipeline story), served cards with verdicts + leaf coverage, reflect notes, raw response, one-click replay. */
import { useEffect, useMemo, useState } from "react";
import { fetchTrace, postReplay, type Trace } from "../api";
import { Chip, Dot, JsonBlock, Kv, ms, tok } from "../bits";
import { AiCallRow } from "../AiCallRow";
import { buildStages, failureSeverity, type StageBundle } from "../stageMap";
import { Loading, RunLink, VerdictMix } from "../widgets";
import { navigate } from "../router";

export function TracePage({ rid }: { rid: string }) {
  const [trace, setTrace] = useState<Trace | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [execIdx, setExecIdx] = useState<number | null>(null);   // null = latest
  const [replayMsg, setReplayMsg] = useState<string | null>(null);

  useEffect(() => {
    setTrace(null); setErr(null); setExecIdx(null);
    fetchTrace(rid).then((r) => setTrace(r.trace)).catch((e) => setErr(e.message));
  }, [rid]);

  const lastIdx = (trace?.timeline.length ?? 1) - 1;
  const sel = execIdx ?? lastIdx;
  const stages = useMemo<StageBundle[]>(() => {
    if (!trace) return [];
    const exec = trace.timeline[sel] ?? null;
    // artifacts stamped with this execution; null-execution strays ride with the LAST execution
    const mine = <T extends { execution?: number | null }>(xs: T[]) =>
      xs.filter((x) => x.execution === sel || (x.execution == null && sel === lastIdx));
    return buildStages(exec, mine(trace.ai_calls), mine(trace.sql), mine(trace.failures));
  }, [trace, sel, lastIdx]);

  if (!trace) return <Loading err={err} />;
  const s = trace.summary;
  const resp = trace.response;

  const replay = async () => {
    if (!s.prompt) return;
    setReplayMsg("launching…");
    try {
      await postReplay({ prompt: s.prompt });
      setReplayMsg(null);
      navigate("replay");
    } catch (e) {
      setReplayMsg(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <>
      <div className="px-tracehead">
        <div className="prompt">{s.prompt || <span className="px-muted">(no prompt recorded)</span>}</div>
        <div className="px-kvrow">
          <Kv k="run id" v={s.run_id} />
          <Kv k="last activity" v={s.ts} />
          <Kv k="page" v={s.page_key} />
          <Kv k="asset" v={s.asset ? `${s.asset} (${s.asset_how || "?"})` : null} />
          <Kv k="elapsed" v={ms(s.elapsed_ms)} />
          <Kv k="cards" v={s.cards} />
          <div className="px-kv"><span className="k">verdicts</span>
            <span className="v"><VerdictMix render={s.rendered} partial={s.partial} blank={s.blank} /></span></div>
          <Kv k="tokens" v={`${tok(s.prompt_tokens)}→${tok(s.completion_tokens)}`} />
          <div className="px-kv"><span className="k">actions</span>
            <span className="v" style={{ display: "flex", gap: 6 }}>
              <button className="px-btn ghost" style={{ height: 24, fontSize: 11 }} onClick={replay}
                      disabled={!s.prompt}>↻ replay</button>
              <a className="px-backlink" href={`/admin/api/run/${rid}/response`} target="_blank" rel="noreferrer">raw response ↗</a>
            </span></div>
        </div>
        {replayMsg && <p className="px-note" style={{ color: "var(--coral-500)" }}>{replayMsg}</p>}
      </div>

      {trace.timeline.length > 1 && (
        <div className="px-tabs">
          {trace.timeline.map((e, i) => (
            <button key={i} className={sel === i ? "on" : ""} onClick={() => setExecIdx(i)}
                    title={`started ${e.started || "?"} · wall ${ms(e.wall_ms)}`}>
              #{i + 1}{i === lastIdx ? " (latest)" : ""}
            </button>
          ))}
        </div>
      )}

      {stages.map((b, i) => <StagePanel key={b.key} idx={i + 1} b={b} rid={rid} />)}

      {resp?.cards?.length ? (
        <div className="px-panel" style={{ marginTop: 12 }}>
          <h3>served cards ({resp.cards.length})</h3>
          <div className="px-tablewrap" style={{ border: "none" }}>
            <table className="px-table">
              <thead><tr><th>card</th><th>title</th><th>verdict</th><th>leaves real/data</th><th>note / reason</th></tr></thead>
              <tbody>
                {resp.cards.map((c: any, i: number) => (
                  <tr key={i}>
                    <td>{c.card_id}{c.render_card_id && c.render_card_id !== c.card_id ? `→${c.render_card_id}` : ""}</td>
                    <td className="px-prompt-cell">{c.title || "—"}{c.asset?.name ? <span className="px-muted"> · {c.asset.name}</span> : null}</td>
                    <td><Chip tone={c.verdict === "render" ? "ok" : c.verdict === "partial" ? "warn" : c.verdict ? "skip" : ""}>{c.verdict || "—"}</Chip>
                        {c.payload_error ? <Chip tone="err">payload_error</Chip> : null}</td>
                    <td className="px-num">{c.leaf_stats ? `${c.leaf_stats.real ?? 0}/${c.leaf_stats.data ?? 0}` : "—"}</td>
                    <td className="px-prompt-cell" title={c.data_note || c.reason || ""}>{c.data_note || c.reason || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {trace.notes ? (
        <div className="px-panel" style={{ marginTop: 12 }}>
          <h3>reflect notes</h3>
          <JsonBlock value={trace.notes} />
        </div>
      ) : null}
    </>
  );
}

function StagePanel({ idx, b, rid }: { idx: number; b: StageBundle; rid: string }) {
  const [open, setOpen] = useState(b.status === "error");
  return (
    <div className={`px-stage${open ? " open" : ""}`}>
      <div className="px-stage-head" onClick={() => setOpen(!open)}>
        <span className="idx">{idx}</span>
        <Dot status={b.status} />
        <span className="name">{b.title}</span>
        <span className="blurb">{b.blurb}</span>
        <span className="metrics">
          {b.latency_ms !== null && <Chip>{ms(b.latency_ms)}</Chip>}
          {b.tokens && <Chip>{tok(b.tokens.prompt)}→{tok(b.tokens.completion)} tok</Chip>}
          {b.aiCalls.length > 0 && <Chip>{b.aiCalls.length} ai</Chip>}
          {b.sql.length > 0 && <Chip>{b.sql.length} sql</Chip>}
          {b.errors.length > 0 && <Chip tone="err">{b.errors.length} err</Chip>}
          {b.warnings.length > 0 && <Chip tone="warn">{b.warnings.length} warn</Chip>}
        </span>
        <span className="chev">▶</span>
      </div>
      {open && (
        <div className="px-stage-body">
          {b.records.length > 0 && (
            <div className="px-sec"><h4>stage records</h4>
              {b.records.map((r, i) => (
                <div className="px-fail" key={i}>
                  <span className="px-muted">{r.ts?.slice(11, 19)}</span>{" "}
                  <b>{r.stage}</b>{" "}
                  {r.dur_ms !== null && <span className="px-muted">+{ms(r.dur_ms)} </span>}
                  <span style={{ wordBreak: "break-word" }}>
                    {Object.entries(r.fields).map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : v}`).join("  ")}
                  </span>
                </div>
              ))}
            </div>
          )}
          {b.aiCalls.length > 0 && (
            <div className="px-sec"><h4>ai calls ({b.aiCalls.length})</h4>
              {b.aiCalls.map((c) => <AiCallRow key={c.idx} rid={rid} call={c} />)}
            </div>
          )}
          {b.sql.length > 0 && (
            <div className="px-sec"><h4>sql reads ({b.sql.length})</h4>
              <div className="px-tablewrap">
                <table className="px-table">
                  <thead><tr><th>t</th><th>db</th><th>sql</th><th className="px-num">rows</th><th className="px-num">ms</th></tr></thead>
                  <tbody>
                    {b.sql.map((q) => (
                      <tr key={q.idx}>
                        <td className="px-muted">{q.ts?.slice(11, 19) || "—"}</td>
                        <td>{q.db}</td>
                        <td style={{ maxWidth: 560, wordBreak: "break-word", fontFamily: "var(--font-mono)" }}
                            title={q.params ? `params: ${q.params}` : undefined}>
                          {q.sql}{q.err ? <span style={{ color: "var(--coral-500)" }}> — {q.err}</span> : null}
                        </td>
                        <td className="px-num">{q.rows ?? "—"}</td>
                        <td className="px-num">{q.ms ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          {(b.errors.length > 0 || b.warnings.length > 0) && (
            <div className="px-sec"><h4>failures</h4>
              {[...b.errors, ...b.warnings].map((f, i) => (
                <div className={`px-fail ${failureSeverity(f)}`} key={i}>
                  <span className="px-muted">{f.ts?.slice(11, 19)}</span>{" "}
                  <span className="reason">{f.reason}</span>
                  {f.card_id !== null ? <span className="px-muted"> card {f.card_id}</span> : null}{" "}
                  <span>{f.detail}</span>
                </div>
              ))}
            </div>
          )}
          {!b.records.length && !b.aiCalls.length && !b.sql.length && !b.errors.length && !b.warnings.length && (
            <div className="px-empty">nothing recorded at this stage</div>
          )}
        </div>
      )}
    </div>
  );
}
