"""layer1a/db_reads/page_layout.py — page-level layout (grid template) from page_specs. [contract 2 layout, #15]"""
from data.db_client import q


def read_page_layout(page_key, db="cmd_catalog"):
    rows = q(
        db,
        "SELECT coalesce(layout_primitive,''), coalesce(grid_template_columns,''), coalesce(grid_template_rows,''), "
        "coalesce(layout_gap,''), coalesce(layout_padding,''), coalesce(layout_shape,''), "
        "coalesce(render_shell,''), coalesce(module,'') "
        f"FROM page_specs WHERE page_key=$k${page_key}$k$ AND status='live'",
    )
    if not rows:
        return {}
    r = rows[0]
    n = lambda v: v or None
    return {"layout_primitive": n(r[0]), "grid_template_columns": n(r[1]), "grid_template_rows": n(r[2]),
            "layout_gap": n(r[3]), "layout_padding": n(r[4]), "layout_shape": n(r[5]),
            "render_shell": n(r[6]), "module": n(r[7])}
