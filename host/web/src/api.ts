import type { PipelineResult, DateWindow } from "./types";

export async function runPipeline(prompt: string, assetId?: number | string | Array<number | string> | null, dateWindow?: DateWindow | null, history?: Array<{ prompt: string; answer: string }> | null): Promise<PipelineResult> {
  // MULTI-ASSET: an ARRAY of ids → compare them in one run (asset_ids[]); a single id/none stays on asset_id.
  const ids = Array.isArray(assetId) ? assetId : null;
  const res = await fetch("/api/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    // `history` = prior knowledge turns (oldest-first) so the one AI layer resolves follow-up questions in context.
    body: JSON.stringify({ prompt, asset_id: ids ? null : (assetId ?? null), asset_ids: ids, date_window: dateWindow ?? null, history: history ?? null }),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body?.error || `HTTP ${res.status}`);
  return body as PipelineResult;
}

/** PER-CARD date re-fetch: a card's own CMD_V2 date control changed → re-COMPLETE JUST this card's payload for the new
 *  window via the same per-card NEURACT executor the page uses. Post the card's OWN payload as the metadata skeleton +
 *  its data_instructions + the server-served `refetch` bundle (asset_table / asset_name / member_scope / default) so the
 *  server can dispatch the right renderer (panel_aggregate member fan-out included). Returns the re-filled `payload`. */
export async function fetchCardFrame(card: any, dateWindow: DateWindow): Promise<any> {
  const res = await fetch("/api/frame", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      exact_metadata: card?.payload,
      data_instructions: card?.data_instructions,
      refetch: card?.refetch,
      date_window: dateWindow,
    }),
  });
  const body = await res.json();
  if (!res.ok || !body?.ok) throw new Error(body?.error || body?.why || `HTTP ${res.status}`);
  return body.payload;
}
