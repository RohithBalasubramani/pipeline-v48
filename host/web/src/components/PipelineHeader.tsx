import type { PipelineResult } from "../types";

function assetLabel(a: PipelineResult["asset"]): { txt: string; cls: string } {
  if (a.asset?.name) return { txt: `${a.asset.name}${a.asset.class ? ` · ${a.asset.class}` : ""}`, cls: "" };
  if (a.how === "ambiguous") return { txt: `ambiguous (${a.candidates.length})`, cls: "v-warn" };
  if (a.how === "empty") return { txt: "no asset (metric-only)", cls: "" };
  return { txt: "unresolved", cls: "v-asset_pending" };
}

export function PipelineHeader({
  r,
  onPick,
}: {
  r: PipelineResult;
  onPick: (id: number) => void;
}) {
  const v = r.validation.verdict;
  const asset = assetLabel(r.asset);
  const errKeys = Object.keys(r.errors || {});

  return (
    <div className="header">
      <div className="top">
        <h2>{r.page.page_title || r.page.page_key || "—"}</h2>
        <span className="pk">{r.page.page_key}</span>
        <div className="badges">
          {r.page.metric && <span className="badge metric">metric · <b>{r.page.metric}</b></span>}
          {r.page.intent && <span className="badge intent">intent · <b>{r.page.intent}</b></span>}
          <span className={`badge ${asset.cls}`}>asset · <b>{asset.txt}</b></span>
          {r.asset.n_columns != null && <span className="badge">basket · <b>{r.asset.n_columns} cols</b></span>}
          <span className={`badge v-${v ?? "null"}`}>validation · <b>{v ?? "n/a"}</b></span>
        </div>
      </div>

      <div className="meta">
        <span>shell <code>{r.page.shell || "—"}</code></span>
        <span>{r.cards.length} cards</span>
        <span>{r.cards.filter((c) => c.has_payload).length}/{r.cards.length} with Layer-2 payload</span>
        {r.page.groups?.length > 0 && (
          <span>
            {r.page.groups.length} interdependency group(s) · coupling{" "}
            <code>{r.page.groups[0].coupling?.join(", ")}</code>
          </span>
        )}
        <span>run <code>{r.run_id}</code></span>
        <span>{r.elapsed_ms} ms</span>
      </div>

      {errKeys.length > 0 && (
        <div className="errbar">
          {errKeys.map((k) => (
            <div key={k}>
              <code>{k}</code> failed — {r.errors[k]}
            </div>
          ))}
        </div>
      )}

    </div>
  );
}
