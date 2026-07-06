import React from "react";
// SPECIAL renderers — the cards whose COMPLETED payload is a WIDGET-ENVELOPE, not the CMD V2 component's props.
// The generic COMPONENTS path spreads props from the payload; these three handling-classes instead carry a
// `{widgets:{…}}` (or `{object,viewer,…}`) envelope that the CMD V2 tab renders through a specific primitive. This
// module maps each envelope → the exact CMD V2 component the real tab uses, reading straight out of the envelope.
//
//   narrative_ai  — payload = {widgets:{ai_summary:{badge,text}}} (also mirrored on data.ai_summary / top-level). The
//                   CMD V2 tabs render the one-sentence insight through the <AiSummary text/> primitive. Cards 8 & 28
//                   have NO Storybook payload (no props to spread) so they ONLY carry this envelope → they render here.
//                   (Cards 19 & 25 DO carry rich AiSummaryCard/PqAiSummaryCard props → they render via COMPONENTS.)
//   asset_3d      — payload = the ViewerResolveResponse envelope {object:{slug,label,url,rating}|null, viewer, …}. With
//                   no bound GLB (object=null) — the honest V48 state — the CMD V2 tab shows its own <ComingSoon3D/>.
//   topology_sld  — payload = {widgets:{sld:{incoming,outgoing,bus,…}}}. The panel-overview SLD tab renders it through
//                   <EnergySingleLineDiagram panelData/>; a null/absent sld → the component's own empty schematic.
//
// HONEST-DEGRADE: every branch tolerates a null/empty envelope and renders the component's own empty state — never a
// crash, never a fabricated value.
import { AiSummary } from "@cmd-v2/components/charts/primitives/AiSummary";
import { ComingSoon3D } from "@cmd-v2/components/ComingSoon3D";
import { CentralAssetViewer } from "@cmd-v2/components/three-viewer-kit/viewers/components/CentralAssetViewer.component";
import { EnergySingleLineDiagram } from "@cmd-v2/pages/electrical/lt-pcc/test-tabs/energy-distribution/EnergySingleLineDiagram";

// Pull the ai_summary widget from wherever the emitter placed it (widgets / data / top-level). [narrative_ai.py _emit]
function aiSummaryOf(payload: any): { text?: string } | null {
  if (!payload || typeof payload !== "object") return null;
  return (
    payload.widgets?.ai_summary ??
    payload.data?.ai_summary ??
    payload.ai_summary ??
    null
  );
}

/** narrative_ai envelope-only cards (8, 28): one-sentence AI insight via the CMD V2 <AiSummary/> primitive.
 *  Honest-blank: no text → the primitive renders an empty line (never a crash). */
function NarrativeEnvelope({ payload }: { payload: any }): React.ReactNode {
  const w = aiSummaryOf(payload);
  return (
    <div className="h-full min-h-0 w-full overflow-auto p-3">
      <AiSummary text={w?.text ?? ""} />
    </div>
  );
}

/** asset_3d viewer envelope (60 + the asset 3D cards): the RESOLVED GLB rendered through CMD V2's own
 *  <CentralAssetViewer/> (the exact viewer TransformerOverviewTab mounts) when the backend bound a model
 *  (object.url), else the honest <ComingSoon3D/> placeholder — never a fabricated model. [c60: the DB-bound
 *  dg_final_v2.glb used to be discarded and ComingSoon drawn unconditionally.] */
function Asset3dEnvelope({ payload }: { payload: any }): React.ReactNode {
  const label =
    (payload && typeof payload === "object" &&
      (payload.object?.label || payload.title || payload.label)) || "3D view";
  const url = payload?.object?.url;
  if (typeof url === "string" && url.trim()) {
    // SSR GUARD [family H]: CentralAssetViewer mounts a three.js Canvas (@react-three/fiber) which needs a DOM/WebGL
    // host — server-side rendering (the ssr_gate/ssr_repro harness / any future SSR) crashes inside fiber's hooks.
    // Render an empty shell server-side; the browser always takes the real 3D path (typeof window is defined there).
    // Same class-level guard as the fill/dg-fuel-efficiency 3D card — the whole asset_3d envelope class, no card ids.
    if (typeof window === "undefined") {
      return <div style={{ height: "100%", minHeight: 0 }} aria-label="3D viewer (client-only)" />;
    }
    return (
      <div className="h-full min-h-0 w-full min-w-0">
        <CentralAssetViewer assetUrl={url} title={String(label)} height="100%" />
      </div>
    );
  }
  return (
    <div className="h-full min-h-0 w-full min-w-0">
      <ComingSoon3D label={String(label)} />
    </div>
  );
}

/** topology_sld envelope: the panel schematic via CMD V2's own <EnergySingleLineDiagram/>. `widgets.sld` is passed as
 *  panelData; the component has its own defaults + optional panelData, so a null/absent sld draws its empty schematic. */
function TopologySldEnvelope({ payload }: { payload: any }): React.ReactNode {
  const sld = payload?.widgets?.sld ?? payload?.sld ?? undefined;
  return (
    <div className="h-full min-h-0 w-full min-w-0">
      <EnergySingleLineDiagram panelData={sld} />
    </div>
  );
}

// A completed payload is an ENVELOPE (not props) when it carries one of these keys AND no story props to spread. We key
// SPECIAL by handling-class-derived card_id below, but also expose these detectors so the registry can route a card
// whose payload turned out to be an envelope even if its id was not pre-listed (defensive; a swapped-in card).
export function isNarrativeEnvelope(payload: any): boolean {
  return !!aiSummaryOf(payload) && !hasStoryProps(payload);
}
export function isAsset3dEnvelope(payload: any): boolean {
  return !!payload && typeof payload === "object" && ("object" in payload || "viewer" in payload) && ("viewer" in payload || payload.object === null || typeof payload.object === "object");
}
export function isTopologyEnvelope(payload: any): boolean {
  return !!payload?.widgets?.sld || !!payload?.sld;
}
// A payload has real component props when it carries any non-envelope, non-variant key (so we render it via COMPONENTS
// rather than as a bare envelope). ai_summary / widgets / object / viewer / sld are envelope keys, not props.
const ENVELOPE_KEYS = new Set(["variant", "widgets", "ai_summary", "object", "viewer", "template", "sld"]);
function hasStoryProps(payload: any): boolean {
  if (!payload || typeof payload !== "object") return false;
  return Object.keys(payload).some((k) => !ENVELOPE_KEYS.has(k));
}

// card_id → SPECIAL renderer. Only the ENVELOPE-ONLY cards live here (they have no spreadable props). Cards whose
// completed payload carries real component props (19, 25 AiSummary; 74–81 asset cards) render via COMPONENTS.
//   8, 28  → narrative_ai envelope (no Storybook payload → widgets.ai_summary only)
//   60     → asset_3d viewer envelope (bound GLB → CentralAssetViewer; unbound → honest ComingSoon)
export const SPECIAL: Record<number, (payload: any) => React.ReactNode> = {
  8: (p) => <NarrativeEnvelope payload={p} />,
  28: (p) => <NarrativeEnvelope payload={p} />,
  60: (p) => <Asset3dEnvelope payload={p} />,
};

// Envelope-kind renderers exposed so the registry can route by DETECTED envelope shape (defensive, for swapped-in cards
// or the out-of-range topology_sld/asset_3d ids not pre-listed above).
export const ENVELOPE_RENDERERS = {
  narrative_ai: (p: any) => <NarrativeEnvelope payload={p} />,
  asset_3d: (p: any) => <Asset3dEnvelope payload={p} />,
  topology_sld: (p: any) => <TopologySldEnvelope payload={p} />,
};
