import { useState } from "react";
import type { Card } from "../types";
import { CmdCard } from "./CmdCard";

function bodyHeight(c: Card): number {
  const h = c.size?.height_px ?? null;
  if (!h) return 240;
  return Math.max(130, Math.min(560, Math.round(h * 0.62)));
}

function vdotClass(c: Card): string {
  const v = c.validation?.verdict;
  return v === "pass" || v === "warn" || v === "fail" ? v : "none";
}

export function CardFrame({ card, liveFrame }: { card: Card; liveFrame?: any }) {
  const [showInspect, setShowInspect] = useState(false);
  const [showStory, setShowStory] = useState(true);
  const h = bodyHeight(card);

  return (
    <div className="card">
      <div className="chead">
        <span className={`vdot ${vdotClass(card)}`} title={`validation: ${card.validation?.verdict ?? "n/a"}`} />
        <span className="ctitle" title={card.title}>{card.title}</span>
        {card.role && <span className="crole">· {card.role}</span>}
        <span className="cid">#{card.card_id}</span>
      </div>

      <div className="cbody" style={{ minHeight: h }}>
        {card.payload ? (
          <CmdCard card={card} h={h} liveFrame={liveFrame} />
        ) : (
          <div className="placeholder" style={{ height: h }}>
            <div className="big">▦</div>
            <div>no CMD_V2 payload</div>
            <div className="k">
              {card.payload_error
                ? "payload lookup error"
                : `control / nav card${card.slot?.tab ? ` · tab ${card.slot.tab}` : ""}`}
            </div>
          </div>
        )}
      </div>

      <div className="cfoot">
        <div className="togglerow">
          {card.story && (
            <button onClick={() => setShowStory((s) => !s)}>{showStory ? "hide story" : "story"}</button>
          )}
          <button onClick={() => setShowInspect((s) => !s)}>
            {showInspect ? "hide payload" : "payload + meta"}
          </button>
        </div>
        {showStory && card.story && <div className="story">{card.story}</div>}
        {showInspect && (
          <div className="inspector">
            <div className="kv" style={{ marginBottom: 8 }}>
              story_id <code>{card.story_id ?? "—"}</code>
              {card.variant ? <> · variant <code>{card.variant}</code></> : null}
              {card.subcards.length > 0 ? <> · {card.subcards.length} subcard(s)</> : null}
              <br />
              slot <code>{card.slot?.region ?? "—"} #{card.slot?.slot_order ?? "—"}</code>
              {" · "}size <code>{card.size?.width_px ?? "?"}×{card.size?.height_px ?? "?"}</code>
              {" "}<code>({card.size?.size_source})</code>
            </div>
            {card.payload_error && (
              <div className="kv" style={{ color: "var(--fail)", marginBottom: 8 }}>{card.payload_error}</div>
            )}
            <h5>payload {card.has_payload ? "(default — Layer-2 morph pending)" : "(none)"}</h5>
            <pre>{JSON.stringify(card.payload ?? null, null, 2)}</pre>
            {card.key_roles != null && (
              <>
                <h5>key_roles (per-leaf morph map)</h5>
                <pre>{JSON.stringify(card.key_roles, null, 2)}</pre>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
