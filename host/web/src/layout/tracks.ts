// tracks.ts — ONE concern: decide whether a page_specs grid-template string is a REAL CSS track list, and if so how
// many tracks it declares. page_specs.grid_template_columns / grid_template_rows are hand-authored and sometimes carry
// PROSE instead of CSS ("three flex layers: tiles shrink-0 / chart flex-[3] / table flex-[2]", "none (single auto
// row…)", "left panel internal grid-rows-2 (…)"). Handing that prose to the browser as gridTemplateRows makes it drop
// the value and auto-size — a silent overflow. So the placement layer asks THIS module first: prose → not a track list
// → the caller derives equal viewport rows instead. GENERIC — keys off token SHAPE, never a page name.

// A single top-level token is "track-ish" iff it is a CSS track keyword / function / <track-size>. Anything alphabetic
// that isn't one of those (a prose word like "three", "tiles", "layers:", "flex-[3]") disqualifies the whole string.
const TRACKISH =
  /^(?:auto|min-content|max-content|(?:repeat|minmax|fit-content|calc)\([^]*\)|\[[-\w\s]+\]|[-+]?\d*\.?\d+(?:fr|px|%|r?em|v[hw]|vmin|vmax|ch|ex|cm|mm|in|pt|pc|q)?)$/i;

// Split on top-level whitespace only (never inside minmax()/repeat()/(…)). Depth-tracked so "minmax(0, 1fr)" is ONE
// token and "(two equal HoverExpandCards)" is ONE token.
function topLevelTokens(s: string): string[] {
  const out: string[] = []; let cur = "", depth = 0;
  for (const ch of s) {
    if (ch === "(" || ch === "[") depth++;
    else if (ch === ")" || ch === "]") depth = Math.max(0, depth - 1);
    if (/\s/.test(ch) && depth === 0) { if (cur) { out.push(cur); cur = ""; } }
    else cur += ch;
  }
  if (cur) out.push(cur);
  return out;
}

// TRUE iff `s` is a usable CSS grid track list (safe to hand to gridTemplateColumns/Rows). Empty, an explicit
// non-grid marker ("none…", "non-grid…"), or any prose token → FALSE.
export function isCssTrackList(s?: string | null): boolean {
  const t = (s || "").trim();
  if (!t) return false;
  if (/^(?:none|non-grid)\b/i.test(t)) return false;
  const toks = topLevelTokens(t);
  return toks.length > 0 && toks.every((tok) => TRACKISH.test(tok));
}

// How many row/column tracks `s` declares — 0 when it is NOT a real CSS track list (prose/none/empty) so the caller
// falls back to derived equal rows. "repeat(2, …)" → 2; "minmax(..) minmax(..)" → 2; "1fr 1fr" → 2.
export function countTracks(s?: string | null): number {
  if (!isCssTrackList(s)) return 0;
  const t = (s as string).trim();
  const rep = /^repeat\(\s*(\d+)/i.exec(t);      // a leading repeat() drives the count (common single-repeat case)
  if (rep) return Number(rep[1]);
  return topLevelTokens(t).length;
}
