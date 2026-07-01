// Resolve the page's REAL grid template from 1a's layout (cmd_catalog page_specs). One concern: the page grid.
export interface PageLayout {
  layout_primitive?: string | null;
  grid_template_columns?: string | null;
  grid_template_rows?: string | null;
  layout_gap?: string | null;
  layout_padding?: string | null;
}
export interface PageGrid { primitive: string; cols: string; rows?: string; gap: string; padding: string; }

const isTracks = (s?: string | null) => !!s && !/^\s*(none|non-grid)\b/i.test(s);

export function pageGrid(layout?: PageLayout | null): PageGrid {
  // layout_primitive decides the placement strategy: "flex" → region columns (RTM); anything else → real CSS grid.
  const prim = (layout?.layout_primitive || "grid").trim().toLowerCase();
  return {
    primitive: prim,
    cols: isTracks(layout?.grid_template_columns) ? layout!.grid_template_columns! : "minmax(0,1fr) 300px",
    rows: isTracks(layout?.grid_template_rows) ? layout!.grid_template_rows! : undefined,
    gap: layout?.layout_gap || "0.75rem",
    padding: layout?.layout_padding || "1rem",
  };
}
