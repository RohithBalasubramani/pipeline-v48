import React from "react";
import type { Card } from "../types";
import { CmdCard } from "./CmdCard";
import { pageGrid, type PageLayout } from "../layout/pageGrid";
import { planGrid } from "../layout/gridPlan";
import { isBand } from "../layout/regions";
import { RtmComposite } from "./RtmComposite";

const cardH = (c: Card): number | undefined => c.size?.height_px ?? undefined;            // card_grid_size footprint height
const bySlot = (a: Card, b: Card) => (a.slot?.slot_order ?? 0) - (b.slot?.slot_order ?? 0);

// Lays cards out in the page's REAL template (cmd_catalog page_specs, carried by 1a) — edge-to-edge, no debug frame.
// page_specs.layout_primitive decides the strategy:  flex → region columns (RTM);  grid → CSS grid + cell placement.
// Mirrors pipeline_v47 V47Grid. [placement = page_specs grid ⊕ page_layout_cards region/cell/slot ⊕ card_grid_size]
// MULTI-ASSET compare: cards carry `card.asset` (id/name/class). When 2+ distinct assets are present, stack one full
// page-grid per asset under an asset header (each group reuses the SAME shared template — 1a ran once). A single asset
// (or an untagged single-asset run) falls straight through to the normal grid below. [author-once-per-class]
function AssetHeader({ name, cls }: { name?: string | null; cls?: string | null }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 16px", background: "#f3efe6",
                  borderBottom: "1px solid #e6e0d4", fontFamily: "var(--font-mono, ui-monospace, monospace)" }}>
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--sage-400, #7a9e6e)" }} />
      <span style={{ fontWeight: 600, color: "var(--teal-900, #1f3d3a)", fontSize: 14 }}>{name || "Asset"}</span>
      {cls && <span style={{ color: "var(--slate-500, #6b7280)", fontSize: 12, letterSpacing: 0.3 }}>{cls}</span>}
    </div>
  );
}

export function CardGrid({ cards, layout }: { cards: Card[]; layout?: PageLayout | null }) {
  if (!cards.length) return null;

  // grouped compare view — one stacked, scrollable full-height page per asset
  const assetIds = Array.from(new Set(cards.map((c) => c.asset?.id).filter((x) => x != null)));
  if (assetIds.length > 1) {
    return (
      <div style={{ display: "flex", flexDirection: "column", height: "100%", overflowY: "auto", background: "#faf8f3" }}>
        {assetIds.map((aid) => {
          const group = cards.filter((c) => c.asset?.id === aid);
          const a0 = group[0]?.asset;
          return (
            <section key={String(aid)} style={{ flex: "none", height: "90vh", minHeight: 520, display: "flex", flexDirection: "column", borderBottom: "1px solid #e6e0d4" }}>
              <AssetHeader name={a0?.name} cls={a0?.class} />
              <div style={{ flex: 1, minHeight: 0 }}>
                <CardGrid cards={group} layout={layout} />
              </div>
            </section>
          );
        })}
      </div>
    );
  }

  const G = pageGrid(layout);                                                      // page template + resolved layout vocab
  const band = cards.filter((c) => isBand(c.slot?.region, G.vocab)).sort(bySlot);  // strip/header/banner → full-width top band
  const body = cards.filter((c) => !isBand(c.slot?.region, G.vocab));
  const shell: React.CSSProperties = {
    display: "flex", flexDirection: "column", gap: G.gap, padding: G.padding,
    height: "100%", minHeight: 0, background: "#faf8f3",
  };

  return (
    <div style={shell}>
      {band.map((c) => <CmdCard key={c.card_id} card={c} h={cardH(c)} />)}
      {G.primitive === G.vocab.flex_primitive ? <RtmFlex G={G} cards={body} />
                              : <RealGrid G={G} cards={body} />}
    </div>
  );
}

// GRID primitive — EMS single-viewport placement. One CSS grid with the page's real column tracks; each card seated by
// its TEMPLATE CELL (page_layout_cards.cell). GENERIC (no per-page CSS): we resolve every card to a concrete (col,row),
// then size the grid rows to EXACTLY the rows used so the whole page fits the leftover viewport with no scroll:
//   • parse the cell → {col,row,span} (parseCell);  band header already lifted out (CardGrid) → REBASE the row prose
//     that counts the header as r1 (harmonics r2/r3 → grid rows 1/2);
//   • a card with no row auto-stacks WITHIN its column (a per-column running counter) so column-mates never collide in
//     row 1 (power-quality: side card 47 = col1; the two right cards 48/49 stack col2 row1 / col2 row2);
//   • a card that is ALONE in its column spans every row (full-height side rail — power-quality card 47);
//   • gridTemplateRows = the template's rows if it already declares enough tracks, else repeat(N,minmax(0,1fr)) for the
//     N rows actually used → equal fractions of the viewport, no implicit auto rows that would overflow.
function RealGrid({ G, cards }: { G: ReturnType<typeof pageGrid>; cards: Card[] }) {
  const plan = planGrid(cards, G.rows, G.vocab);               // PURE placement: cells → concrete (col,row) + row tracks
  const byId = new Map(cards.map((c) => [c.card_id, c]));
  const style: React.CSSProperties = {
    display: "grid", gridTemplateColumns: G.cols, gridTemplateRows: plan.rows, gap: G.gap, flex: 1, minHeight: 0,
  };
  return (
    <div style={style}>
      {plan.seats.map((s) => {
        const c = byId.get(s.card_id)!;
        return (
          <div key={c.card_id} style={{ ...s.style, minHeight: 0, overflow: "hidden" }}>
            <CmdCard card={c} />
          </div>
        );
      })}
    </div>
  );
}

// FLEX primitive (RTM panel-overview / real-time-monitoring): the EMS page is NOT 8 floating boxes — it is TWO
// composite Cards (RealTimeMonitoringLayout). Lay them out in the page's REAL 2-column template (G.cols, e.g.
// "minmax(0,1fr) 300px") and let RtmComposite render the LEFT heatmap Card (col 1) + RIGHT rail Card (col 2),
// each merging its 4 cards borderless. Backend untouched — RtmComposite still renders each card by its own
// identity (renderCmd / the fill fns) from the card's own payload. Only the GRID path uses RealGrid.
function RtmFlex({ G, cards }: { G: ReturnType<typeof pageGrid>; cards: Card[] }) {
  const style: React.CSSProperties = {
    display: "grid", gridTemplateColumns: G.cols, gridTemplateRows: G.rows, gap: G.gap, flex: 1, minHeight: 0,
  };
  return (
    <div style={style}>
      <RtmComposite cards={cards} />
    </div>
  );
}
