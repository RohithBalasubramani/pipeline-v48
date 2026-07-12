// guards/_shared.ts — the tiny helpers every rule file uses (split F12, 2026-07-12).
export const DASH = "—";
export const blank = (v: any) => v == null || v === "";
export function isDict(v: any): v is Record<string, any> {
  return v != null && typeof v === "object" && !Array.isArray(v);
}
export const finite = (v: any) => typeof v === "number" && Number.isFinite(v);
