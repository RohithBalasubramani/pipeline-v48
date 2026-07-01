import React from "react";
import type { Card } from "../types";
import { CmdCard } from "./CmdCard";
import { pageGrid, type PageLayout } from "../layout/pageGrid";
import { cellPos } from "../layout/cellPos";
import { isBand } from "../layout/regions";
import { RtmComposite } from "./RtmComposite";

const cardH = (c: Card): number | undefined => c.size?.height_px ?? undefined;            // card_grid_size footprint height
const bySlot = (a: Card, b: Card) => (a.slot?.slot_order ?? 0) - (b.slot?.slot_order ?? 0);

// Lays cards out in the page's REAL template (cmd_catalog page_specs, carried by 1a) — edge-to-edge, no debug frame.
// page_specs.layout_primitive decides the strategy:  flex → region columns (RTM);  grid → CSS grid + cell placement.
// Mirrors pipeline_v47 V47Grid. [placement = page_specs grid ⊕ page_layout_cards region/cell/slot ⊕ card_grid_size]
// frame for a card = frames[card.endpoint] (Option A: that card's CMD V2 mapper consumes it), else the page frame.
const frameFor = (c: Card, frames?: Record<string, any>, liveFrame?: any) =>
  (c.endpoint && frames && frames[c.endpoint]) || liveFrame;

export function CardGrid({ cards, layout, frames, liveFrame }: { cards: Card[]; layout?: PageLayout | null; frames?: Record<string, any>; liveFrame?: any }) {
  if (!cards.length) return null;
  const G = pageGrid(layout);
  const band = cards.filter((c) => isBand(c.slot?.region)).sort(bySlot);          // page header / control strip → top band
  const body = cards.filter((c) => !isBand(c.slot?.region));
  const shell: React.CSSProperties = {
    display: "flex", flexDirection: "column", gap: G.gap, padding: G.padding,
    height: "100%", minHeight: 0, background: "#faf8f3",
  };

  return (
    <div style={shell}>
      {band.map((c) => <CmdCard key={c.card_id} card={c} h={cardH(c)} liveFrame={frameFor(c, frames, liveFrame)} pageFrame={liveFrame} />)}
      {G.primitive === "flex" ? <RtmFlex G={G} cards={body} frames={frames} />
                              : <RealGrid G={G} cards={body} frames={frames} liveFrame={liveFrame} />}
    </div>
  );
}

// GRID primitive: one CSS grid with the real template; each card seated by cellPos (sorted by slot_order so the
// unparseable ones auto-flow into the right sequence). The cell fills its track (CmdCard h=undefined → 100%).
function RealGrid({ G, cards, frames, liveFrame }: { G: ReturnType<typeof pageGrid>; cards: Card[]; frames?: Record<string, any>; liveFrame?: any }) {
  const style: React.CSSProperties = {
    display: "grid", gridTemplateColumns: G.cols, gridTemplateRows: G.rows, gap: G.gap, flex: 1, minHeight: 0,
  };
  return (
    <div style={style}>
      {[...cards].sort(bySlot).map((c) => (
        <div key={c.card_id} style={{ ...cellPos(c.slot), minHeight: 0, overflow: "hidden" }}>
          <CmdCard card={c} liveFrame={frameFor(c, frames, liveFrame)} pageFrame={liveFrame} />
        </div>
      ))}
    </div>
  );
}

// FLEX primitive (RTM panel-overview / real-time-monitoring): the EMS page is NOT 8 floating boxes — it is TWO
// composite Cards (RealTimeMonitoringLayout). Lay them out in the page's REAL 2-column template (G.cols, e.g.
// "minmax(0,1fr) 300px") and let RtmComposite render the LEFT heatmap Card (col 1) + RIGHT rail Card (col 2),
// each merging its 4 cards borderless. Backend untouched — RtmComposite still renders each card by its own
// identity (renderCmd / the fill fns) from the card's own payload + frame. Only the GRID path uses RealGrid.
function RtmFlex({ G, cards, frames }: { G: ReturnType<typeof pageGrid>; cards: Card[]; frames?: Record<string, any> }) {
  const style: React.CSSProperties = {
    display: "grid", gridTemplateColumns: G.cols, gridTemplateRows: G.rows, gap: G.gap, flex: 1, minHeight: 0,
  };
  return (
    <div style={style}>
      <RtmComposite cards={cards} frames={frames} />
    </div>
  );
}
