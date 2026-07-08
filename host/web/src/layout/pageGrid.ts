import { isCssTrackList } from "./tracks";
import { resolveVocab, type LayoutVocab } from "./vocab";

// Resolve the page's REAL grid template from 1a's layout (cmd_catalog page_specs). One concern: the page grid.
export interface PageLayout {
  layout_primitive?: string | null;
  grid_template_columns?: string | null;
  grid_template_rows?: string | null;
  layout_gap?: string | null;
  layout_padding?: string | null;
  fe_vocab?: Partial<LayoutVocab> | null;   // OPTIONAL DB-tunable layout vocab overrides threaded by the server
}
export interface PageGrid { primitive: string; cols: string; rows?: string; gap: string; padding: string; vocab: LayoutVocab; }

export function pageGrid(layout?: PageLayout | null): PageGrid {
  const vocab = resolveVocab(layout?.fe_vocab);
  // layout_primitive decides the placement strategy: the flex primitive → region columns (RTM); else → real CSS grid.
  const prim = (layout?.layout_primitive || vocab.default_primitive).trim().toLowerCase();
  return {
    primitive: prim,
    // grid_template_columns/rows are honored ONLY when they are a real CSS track list (tracks.isCssTrackList rejects
    // prose / "none" / empty) — else derive from the fallback / equal viewport rows so a prose value never overflows.
    cols: isCssTrackList(layout?.grid_template_columns) ? layout!.grid_template_columns! : vocab.fallback_cols,
    rows: isCssTrackList(layout?.grid_template_rows) ? layout!.grid_template_rows! : undefined,
    gap: layout?.layout_gap || vocab.fallback_gap,
    padding: layout?.layout_padding || vocab.fallback_padding,
    vocab,
  };
}
