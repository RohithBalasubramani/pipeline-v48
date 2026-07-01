import type { PipelineResult, DateWindow } from "./types";

export async function runPipeline(prompt: string, assetId?: number | string | null, dateWindow?: DateWindow | null): Promise<PipelineResult> {
  const res = await fetch("/api/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, asset_id: assetId ?? null, date_window: dateWindow ?? null }),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body?.error || `HTTP ${res.status}`);
  return body as PipelineResult;
}

/** PER-CARD date re-fetch: a card's own date control changed → re-fetch JUST its ems_backend frame for the new window.
 *  `consumer` = the card's data_instructions.consumer (carries mfm_id + endpoint + is_history). Returns the new frame. */
export async function fetchCardFrame(consumer: unknown, dateWindow: DateWindow): Promise<any> {
  const res = await fetch("/api/frame", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ consumer, date_window: dateWindow }),
  });
  const body = await res.json();
  if (!res.ok || !body?.ok) throw new Error(body?.error || body?.why || `HTTP ${res.status}`);
  return body.frame;
}
