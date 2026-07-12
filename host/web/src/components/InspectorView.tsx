import { useEffect, useMemo, useState } from "react";
import {
  fetchInspectorTrace,
  fetchInspectorTraces,
  type InspectorDecision,
  type InspectorTraceDetail,
  type InspectorTraceSummary,
} from "../api";

// AI DECISION INSPECTOR — every AI decision of one pipeline execution, fully disclosed: prompt, model, sampling
// params, the materialized candidate set, what was selected vs rejected, the model's reasoning + confidence,
// latency, token usage and the raw final output. Read-only over GET /api/inspector/* (obs trace store).
// Three panes: executions rail → decision timeline → decision detail. Neuract cream chrome (cc-insp-*).

const STAGE_LABEL: Record<string, string> = {
  route: "1a · page routing",
  stories: "1a · card stories",
  asset_resolve: "1b · asset resolution",
  basket: "1b · column basket",
  l2_emit: "L2 · card emit",
  knowledge_ems: "knowledge gate",
  insight_narrator: "exec · AI summary",
};

function fmtTs(ts: string | number | null | undefined): string {
  if (ts == null) return "—";
  try {
    const d = typeof ts === "number" ? new Date(ts * 1000) : new Date(ts);
    return isNaN(d.getTime()) ? String(ts) : d.toLocaleString(undefined, { hour12: false });
  } catch { return String(ts); }
}

function fmtMs(ms: number | null | undefined): string {
  if (ms == null) return "—";
  return ms >= 10000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
}

function fmtConfidence(c: number | boolean | null | undefined): string | null {
  if (c == null) return null;
  if (typeof c === "boolean") return c ? "confident" : "not confident";
  return c.toFixed(2);
}

function prettyJson(v: unknown): string {
  try { return JSON.stringify(v, null, 2) ?? "—"; } catch { return String(v); }
}

/** The raw model reply, pretty-printed when it parses as JSON (mirrors the pipeline's own {...} extraction). */
function prettyResponse(text: string | null | undefined): string {
  if (!text) return "—";
  const m = /\{[\s\S]*\}/.exec(text.replace(/<think>[\s\S]*?<\/think>/g, ""));
  if (m) { try { return JSON.stringify(JSON.parse(m[0]), null, 2); } catch { /* raw below */ } }
  return text;
}

function StatusDot({ status }: { status?: string | null }) {
  const color = status === "error" ? "var(--coral-500)" : status === "degraded" ? "var(--mustard-400)" : "var(--sage-400)";
  return <span className="cc-insp-dot" style={{ background: color }} title={status ?? "ok"} />;
}

// ── executions rail ─────────────────────────────────────────────────────────────────────────────────────────────

function TraceRail({ traces, selected, onPick, loading, error }: {
  traces: InspectorTraceSummary[]; selected: string | null; onPick: (id: string) => void;
  loading: boolean; error: string | null;
}) {
  return (
    <aside className="cc-insp-rail">
      <div className="cc-insp-rail-head">EXECUTIONS</div>
      {loading && <div className="cc-insp-quiet">loading…</div>}
      {error && <div className="cc-insp-error">{error}</div>}
      {!loading && !error && traces.length === 0 && <div className="cc-insp-quiet">no traces recorded yet</div>}
      {traces.map((t) => (
        <button key={t.trace_id} onClick={() => onPick(t.trace_id)}
                className={"cc-insp-tracebtn" + (t.trace_id === selected ? " is-selected" : "")}>
          <div className="cc-insp-tracebtn-top">
            <StatusDot status={t.status} />
            <span className="cc-insp-mono">{fmtTs(t.started_at)}</span>
            <span className="cc-insp-mono cc-insp-dim">{fmtMs(t.latency_ms)}</span>
          </div>
          <div className="cc-insp-tracebtn-prompt">{t.prompt || t.kind || t.trace_id}</div>
          <div className="cc-insp-mono cc-insp-dim cc-insp-tracebtn-meta">
            {t.n_llm_calls != null ? `${t.n_llm_calls} AI calls` : ""}
            {t.tokens_prompt != null ? ` · ${t.tokens_prompt}+${t.tokens_completion ?? 0} tok` : ""}
            {t.page_key ? ` · ${t.page_key}` : ""}
          </div>
        </button>
      ))}
    </aside>
  );
}

// ── decision timeline ───────────────────────────────────────────────────────────────────────────────────────────

function DecisionList({ detail, selected, onPick }: {
  detail: InspectorTraceDetail; selected: number; onPick: (i: number) => void;
}) {
  const t = detail.trace;
  return (
    <section className="cc-insp-list">
      <div className="cc-insp-trace-head">
        <div className="cc-insp-trace-prompt">{(t?.prompt as string) || "(no prompt)"}</div>
        <div className="cc-insp-mono cc-insp-dim">
          <StatusDot status={t?.status as string} /> {t?.status ?? "ok"} · {fmtMs(t?.latency_ms as number)} ·{" "}
          {detail.decisions.length} AI decision{detail.decisions.length === 1 ? "" : "s"} · {String(t?.trace_id ?? "")}
        </div>
      </div>
      {detail.stages.length > 0 && (
        <details className="cc-insp-stages">
          <summary>stage timeline ({detail.stages.length})</summary>
          {detail.stages.map((s, i) => (
            <div key={i} className="cc-insp-stagerow cc-insp-mono">
              <StatusDot status={s.status} />
              <span className="cc-insp-stagerow-name">{s.stage}{s.card_id != null ? ` · card ${s.card_id}` : ""}</span>
              <span className="cc-insp-dim">{fmtMs(s.latency_ms)}</span>
              {s.n_llm_calls ? <span className="cc-insp-dim">llm×{s.n_llm_calls}</span> : null}
            </div>
          ))}
        </details>
      )}
      <div className="cc-insp-rail-head">AI DECISIONS</div>
      {detail.decisions.length === 0 && <div className="cc-insp-quiet">no LLM calls recorded on this trace</div>}
      {detail.decisions.map((d) => {
        const conf = fmtConfidence(d.decision?.confidence);
        return (
          <button key={d.i} onClick={() => onPick(d.i)}
                  className={"cc-insp-decbtn" + (d.i === selected ? " is-selected" : "")}>
            <div className="cc-insp-decbtn-top">
              <span className="cc-insp-stagechip">{STAGE_LABEL[d.stage ?? ""] ?? d.stage ?? "?"}</span>
              {d.card_id != null && <span className="cc-insp-chip">card {d.card_id}</span>}
              {(d.attempt ?? 0) > 0 && <span className="cc-insp-chip cc-insp-chip--warn">retry #{d.attempt}</span>}
              {d.error_kind && <span className="cc-insp-chip cc-insp-chip--err">{d.error_kind}</span>}
            </div>
            <div className="cc-insp-mono cc-insp-dim cc-insp-decbtn-meta">
              {fmtMs(d.latency_ms)}
              {d.tokens_prompt != null ? ` · ${d.tokens_prompt}+${d.tokens_completion ?? 0} tok` : ""}
              {conf ? ` · conf ${conf}` : ""}
            </div>
          </button>
        );
      })}
    </section>
  );
}

// ── decision detail ─────────────────────────────────────────────────────────────────────────────────────────────

function MetaChip({ label, value }: { label: string; value: string | number | null | undefined }) {
  if (value == null || value === "") return null;
  return (
    <div className="cc-insp-meta">
      <div className="cc-insp-meta-label">{label}</div>
      <div className="cc-insp-meta-value cc-insp-mono">{String(value)}</div>
    </div>
  );
}

function candidateKey(c: unknown): string {
  if (c == null) return "";
  if (typeof c !== "object") return String(c);
  const o = c as Record<string, unknown>;
  return String(o.page_key ?? o.name ?? o.column ?? o.card_id ?? o.kind ?? JSON.stringify(o));
}

function candidateLabel(c: unknown): string {
  if (c == null) return "";
  if (typeof c !== "object") return String(c);
  const o = c as Record<string, unknown>;
  const id = candidateKey(c);
  const extras = Object.entries(o)
    .filter(([k, v]) => v != null && String(v) !== id && k !== "page_key" && k !== "name" && k !== "column" && k !== "card_id")
    .map(([k, v]) => `${k}=${String(v)}`).join("  ");
  return extras ? `${id}   ${extras}` : id;
}

function DecisionDetail({ d }: { d: InspectorDecision }) {
  const dv = d.decision ?? {};
  const rejected = new Set((dv.rejected ?? []).map((r) => String(r)));
  const selectedJson = dv.selected != null ? prettyJson(dv.selected) : null;
  const conf = fmtConfidence(dv.confidence);
  const p = d.params ?? {};
  const totalTok = d.tokens_prompt != null || d.tokens_completion != null
    ? (d.tokens_prompt ?? 0) + (d.tokens_completion ?? 0) : null;
  return (
    <section className="cc-insp-detail">
      <div className="cc-insp-detail-head">
        <span className="cc-insp-stagechip">{STAGE_LABEL[d.stage ?? ""] ?? d.stage ?? "?"}</span>
        {d.card_id != null && <span className="cc-insp-chip">card {d.card_id}</span>}
        <span className="cc-insp-mono cc-insp-dim">{fmtTs(d.ts)} · attempt {d.attempt ?? 0}
          {d.finish_reason ? ` · finish=${d.finish_reason}` : ""}</span>
        {d.error_kind && <span className="cc-insp-chip cc-insp-chip--err">{d.error_kind}</span>}
      </div>

      <div className="cc-insp-metagrid">
        <MetaChip label="MODEL" value={d.model} />
        <MetaChip label="TEMPERATURE" value={p.temperature != null ? String(p.temperature) : null} />
        <MetaChip label="SEED" value={p.seed != null ? String(p.seed) : null} />
        <MetaChip label="FORMAT" value={p.response_format} />
        <MetaChip label="LATENCY" value={fmtMs(d.latency_ms)} />
        <MetaChip label="TOKENS IN" value={d.tokens_prompt ?? null} />
        <MetaChip label="TOKENS OUT" value={d.tokens_completion ?? null} />
        <MetaChip label="TOKENS TOTAL" value={totalTok} />
        <MetaChip label="TIMEOUT" value={p.timeout_s != null ? `${p.timeout_s}s` : null} />
        <MetaChip label="ENDPOINT" value={p.url} />
      </div>

      {(dv.kind || dv.candidate_kind) && (
        <div className="cc-insp-block">
          <div className="cc-insp-block-title">DECISION · {dv.kind ?? "unknown"}
            {dv.candidate_kind ? ` over ${dv.candidate_kind}` : ""}</div>

          {selectedJson && (
            <div className="cc-insp-selected">
              <div className="cc-insp-block-sub">SELECTED</div>
              <pre className="cc-insp-pre cc-insp-pre--selected">{selectedJson}</pre>
            </div>
          )}
          {conf && <div className="cc-insp-confline">confidence: <b>{conf}</b></div>}
          {dv.reasoning && (
            <div>
              <div className="cc-insp-block-sub">REASONING</div>
              <div className="cc-insp-reasoning">{dv.reasoning}</div>
            </div>
          )}

          {(dv.candidates?.length ?? 0) > 0 && (
            <div>
              <div className="cc-insp-block-sub">
                CANDIDATES ({dv.candidates_total ?? dv.candidates!.length})
                {" · "}{rejected.size} rejected
              </div>
              <div className="cc-insp-cands">
                {dv.candidates!.map((c, i) => {
                  const key = candidateKey(c);
                  const isRejected = rejected.has(key);
                  return (
                    <div key={i} className={"cc-insp-cand cc-insp-mono" + (isRejected ? " is-rejected" : " is-selected")}>
                      <span className="cc-insp-cand-mark">{isRejected ? "✗" : "✓"}</span> {candidateLabel(c)}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
          {(dv.candidates?.length ?? 0) === 0 && (dv.rejected?.length ?? 0) > 0 && (
            <div>
              <div className="cc-insp-block-sub">REJECTED ({dv.rejected!.length})</div>
              <div className="cc-insp-cands">
                {dv.rejected!.map((r, i) => (
                  <div key={i} className="cc-insp-cand cc-insp-mono is-rejected">
                    <span className="cc-insp-cand-mark">✗</span> {String(r)}
                  </div>
                ))}
              </div>
            </div>
          )}
          {dv.error && <div className="cc-insp-error">decision view: {dv.error}</div>}
        </div>
      )}

      <div className="cc-insp-block">
        <div className="cc-insp-block-title">PROMPT</div>
        <details className="cc-insp-fold">
          <summary>system ({(d.prompt_system ?? "").length.toLocaleString()} chars)</summary>
          <pre className="cc-insp-pre">{d.prompt_system || "—"}</pre>
        </details>
        <details className="cc-insp-fold" open>
          <summary>user ({(d.prompt_user ?? "").length.toLocaleString()} chars)</summary>
          <pre className="cc-insp-pre">{d.prompt_user || "—"}</pre>
        </details>
      </div>

      <div className="cc-insp-block">
        <div className="cc-insp-block-title">FINAL OUTPUT</div>
        <pre className="cc-insp-pre">{prettyResponse(d.response)}</pre>
      </div>
    </section>
  );
}

// ── the view ────────────────────────────────────────────────────────────────────────────────────────────────────

export function InspectorView({ initialTraceId, onBack }: { initialTraceId?: string | null; onBack: () => void }) {
  const [traces, setTraces] = useState<InspectorTraceSummary[]>([]);
  const [tracesLoading, setTracesLoading] = useState(true);
  const [tracesError, setTracesError] = useState<string | null>(null);
  const [traceId, setTraceId] = useState<string | null>(initialTraceId ?? null);
  const [detail, setDetail] = useState<InspectorTraceDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [decisionIdx, setDecisionIdx] = useState(0);

  useEffect(() => {
    let dead = false;
    setTracesLoading(true);
    fetchInspectorTraces(60)
      .then((rows) => { if (dead) return; setTraces(rows); setTracesError(null);
                        if (!initialTraceId && rows.length) setTraceId((cur) => cur ?? rows[0].trace_id); })
      .catch((e) => !dead && setTracesError(e instanceof Error ? e.message : String(e)))
      .finally(() => !dead && setTracesLoading(false));
    return () => { dead = true; };
  }, [initialTraceId]);

  useEffect(() => {
    if (!traceId) return;
    let dead = false;
    setDetailLoading(true);
    setDetailError(null);
    fetchInspectorTrace(traceId)
      .then((d) => { if (dead) return; setDetail(d); setDecisionIdx(0); })
      .catch((e) => !dead && setDetailError(e instanceof Error ? e.message : String(e)))
      .finally(() => !dead && setDetailLoading(false));
    return () => { dead = true; };
  }, [traceId]);

  const decision = useMemo(
    () => detail?.decisions?.find((d) => d.i === decisionIdx) ?? detail?.decisions?.[0] ?? null,
    [detail, decisionIdx],
  );

  return (
    <div className="cc-insp-root">
      <div className="cc-insp-topbar">
        <button className="cc-insp-back" onClick={onBack}>← COMMAND CENTER</button>
        <span className="cc-insp-title">AI DECISION INSPECTOR</span>
        <span className="cc-insp-dim cc-insp-mono">every AI decision · prompt · candidates · selection · reasoning · cost</span>
      </div>
      <div className="cc-insp-body">
        <TraceRail traces={traces} selected={traceId} onPick={setTraceId}
                   loading={tracesLoading} error={tracesError} />
        {detailLoading ? (
          <div className="cc-insp-quiet cc-insp-fill">loading trace…</div>
        ) : detailError ? (
          <div className="cc-insp-error cc-insp-fill">{detailError}</div>
        ) : detail ? (
          <>
            <DecisionList detail={detail} selected={decision?.i ?? 0} onPick={setDecisionIdx} />
            {decision ? <DecisionDetail d={decision} />
                      : <div className="cc-insp-quiet cc-insp-fill">no AI decisions on this trace</div>}
          </>
        ) : (
          <div className="cc-insp-quiet cc-insp-fill">pick an execution on the left</div>
        )}
      </div>
    </div>
  );
}
