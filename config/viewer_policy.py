"""config/viewer_policy.py — thin reader over cmd_catalog.viewer_policy (the page-family → viewer knobs the phase-2
asset_3d resolver reads).

Answers, for a page_key: is this an INDIVIDUAL (single-feeder detail) page, an OVERVIEW (panel bootstrap + 3D/SLD) page,
or a VARIANT (a same-page tab flavour)? Plus the rating vocab the resolver ranks candidates by, and the default
asset_3d key when a page/panel has no configured GLB yet. NO hardcoded page-family map or asset-key literal in the
resolver — every mapping is an EDITABLE ROW here (mirrors config.endpoint_policy's dedicated-table style).

Ports the intent behind CMD/backend2 lt_panels/views.py:429 _OVERVIEW_PAGES (slug → 3D-asset-key). V48 keeps the
resolver PURE-config: it reads page_type_for() to decide the render path, rating_vocab() to rank/label the candidate,
and default_asset_3d_key() as the honest fallback GLB (never fabricating a per-panel model that doesn't exist).

fail-open: a missing row OR a DB outage → the built-in code default (this module never raises, never blocks import), so
lookups behave identically until an editable row exists. [#1 asset_3d resolver: DB-driven config]
"""
from data.db_client import q

# ── page-family code defaults (the fallback when the DB row / table is absent) ───────────────────────────────────────
#    The V48 page_key is 'shell/tab' (config.available_pages). The SHELL segment decides the family:
#    individual-feeder-meter-shell → an individual single-feeder detail; panel-overview-shell → a panel overview.
_SHELL_PAGE_TYPE = {
    "individual-feeder-meter-shell": "individual",
    "panel-overview-shell": "overview",
}
# Explicit per-page_key overrides (a tab that is a same-page variant flavour rather than its shell's default family).
_PAGE_TYPE_OVERRIDE = {}

# The three page-type buckets the asset_3d resolver branches on (the closed vocab).
_PAGE_TYPES = ("individual", "overview", "variant")

# Rating vocab — the ordered rating tokens the resolver ranks/labels a candidate asset by (best → worst). Editable CSV
# row viewer.rating_vocab; the resolver uses the ORDER as the rank and the tokens as the display labels.
_RATING_VOCAB_DEFAULT = "exact,strong,plausible,weak,none"

# Default asset_3d key — the honest fallback GLB when a page/panel has no configured model yet (backend2 views.py:430
# 'pcc1a-v1' is the one uploaded GLB). Editable row viewer.default_asset_3d_key.
_DEFAULT_ASSET_3D_KEY = "pcc1a-v1"


def _shell_of(page_key):
    """The shell (first '/'-segment) of a V48 page_key ('individual-feeder-meter-shell/energy-power' → the shell)."""
    if not page_key:
        return None
    return str(page_key).split("/", 1)[0].strip()


def page_type_for(page_key):
    """The viewer family for a page_key → 'individual' | 'overview' | 'variant'. Prefers the editable DB row
    (viewer_policy.page_type by page_key, then by shell), falls back to the code map on a missing row / DB outage.
    An unknown page_key with no shell match → None (the resolver honest-degrades, never guesses a render path)."""
    shell = _shell_of(page_key)
    try:
        rows = q("cmd_catalog",
                 "SELECT page_type FROM viewer_policy "
                 f"WHERE page_key='{_esc(page_key)}' OR page_key='{_esc(shell)}' "
                 "ORDER BY (page_key='" + _esc(page_key) + "') DESC")
        if rows and rows[0][0] not in (None, "", "NULL"):
            pt = str(rows[0][0]).strip().lower()
            if pt in _PAGE_TYPES:
                return pt
    except Exception:
        pass   # DB down / table absent → fall through to the code map (fail-open)
    if page_key in _PAGE_TYPE_OVERRIDE:
        return _PAGE_TYPE_OVERRIDE[page_key]
    return _SHELL_PAGE_TYPE.get(shell)


def rating_vocab():
    """The ordered rating tokens the asset_3d resolver ranks/labels a candidate by (best→worst). Editable CSV row
    viewer.rating_vocab. A malformed / absent row falls back to the code default so the resolver never breaks."""
    raw = _txt("viewer.rating_vocab", _RATING_VOCAB_DEFAULT)
    toks = tuple(s.strip().lower() for s in (raw or "").split(",") if s.strip())
    return toks or tuple(s.strip() for s in _RATING_VOCAB_DEFAULT.split(","))


def default_asset_3d_key():
    """The honest fallback 3D-asset key when a page/panel has no configured GLB (never fabricates a per-panel model).
    Editable row viewer.default_asset_3d_key; code default = the one uploaded GLB (backend2 views.py:430)."""
    return _txt("viewer.default_asset_3d_key", _DEFAULT_ASSET_3D_KEY)


def all_page_types():
    """{page_key: page_type} for every configured row (DB rows preferred, else the built-in shell/override map) — for a
    build-time audit / bulk resolve."""
    try:
        rows = q("cmd_catalog", "SELECT page_key, page_type FROM viewer_policy ORDER BY page_key")
        if rows:
            return {r[0]: (str(r[1]).strip().lower() if r[1] not in (None, "", "NULL") else None) for r in rows}
    except Exception:
        pass
    out = dict(_SHELL_PAGE_TYPE)
    out.update(_PAGE_TYPE_OVERRIDE)
    return out


def _txt(key, default=None):
    """A single text knob from cmd_catalog.viewer_policy.txt_value (key/value rows, key='__knob__:<key>'). Never raises;
    returns `default` with the DB down or the row absent (fail-open, mirrors quality_policy.txt)."""
    try:
        rows = q("cmd_catalog",
                 f"SELECT txt_value FROM viewer_policy WHERE page_key='__knob__:{_esc(key)}'")
    except Exception:
        return default
    if not rows or rows[0][0] in (None, "", "NULL"):
        return default
    return rows[0][0]


def _esc(s):
    return "" if s is None else str(s).replace("'", "''")
