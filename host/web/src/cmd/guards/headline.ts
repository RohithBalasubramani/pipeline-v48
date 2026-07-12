// guards/headline.ts — g6 backend-headline threading (split F12, 2026-07-12).
import { isDict } from "./_shared";

// ── g6: thread the card's REAL generated summary into the CMD_V2 backend-paragraph seam. Two touch points:
//   • `backendHeadline` on every presentation dict that carries a template 'vocab' (the V&C AiSummaryCard reads
//     pres.backendHeadline; extra keys on other vocab-dicts are inert), and
//   • a top-level 'backendAiSummary' prop (the HPQ PqAiSummaryCard takes it as a prop) — added by unwrap (registry).
export function aiHeadlineOf(payload: any): string | null {
  const t = payload?.ai_summary?.text ?? payload?.widgets?.ai_summary?.text;
  return typeof t === "string" && t.trim() ? t : null;
}
export function threadHeadline(node: any, text: string): void {
  if (Array.isArray(node)) {
    for (const el of node) if (el != null && typeof el === "object") threadHeadline(el, text);
    return;
  }
  if (!isDict(node)) return;
  if (isDict(node.vocab) && node.backendHeadline == null) node.backendHeadline = text;
  for (const v of Object.values(node)) if (v != null && typeof v === "object") threadHeadline(v, text);
}
