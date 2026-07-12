"""config/asset3d_media.py — the base URL the layer2 asset_3d emit prepends to a stored GLB ``file`` path.

ROOT-RELATIVE since 2026-07-12 [legacy-EMS retirement]: the v48 web origin ITSELF serves the GLBs — Vite serves
``host/web/public/`` natively (dev and build), so ``/media/3d/glb/<name>.glb`` resolves against whatever origin the
page was loaded from (localhost or a LAN IP alike — the old ``http://localhost:8890`` legacy-EMS default broke every
off-box browser). No Django media server, no extra port, no CORS.

DB-DRIVEN: the base is the editable ``viewer_policy`` __knob__ row ``viewer.glb_media_base`` (rides the same table the
rest of the asset_3d viewer knobs use); the code default below mirrors it. fail-open: DB down / row absent → the code
default, so the emit builds the same url either way. NEVER fabricates a url for a missing file — the caller only calls
glb_url() when it has a real ``file`` path. [#1 asset_3d]
"""
import os

# ── code default (the fail-open fallback) ───────────────────────────────────────────────────────────────────────────
# Root-relative: the web origin serves host/web/public/media/. Env-overridable (an absolute base is still honored for
# an external media host); the DB knob wins when set.
_GLB_MEDIA_BASE_DEFAULT = os.environ.get("V48_GLB_MEDIA_BASE", "/media/")


def glb_media_base():
    """The base URL a stored GLB ``file`` path hangs off (root-relative ``/media/`` default, or an absolute base via
    the editable row viewer.glb_media_base / env). Always ends in '/'. Never raises (fail-open) — the emit builds an
    identical url with the DB down."""
    try:
        from config import viewer_policy as _vp
        base = _vp._txt("viewer.glb_media_base", None)            # rides the same viewer_policy __knob__ surface
    except Exception:
        base = None
    base = (base or _GLB_MEDIA_BASE_DEFAULT).strip()
    return base if base.endswith("/") else base + "/"


def glb_url(file_path):
    """The GLB url for a stored ``file`` path (the DB's ``lt_asset_3d.file`` value, e.g. '3d/glb/pcc1a.glb').
    None for an empty/missing path (HONEST-DEGRADE — never a guessed url). Mirrors backend2 CatAsset.model_url +
    assets/serializers.get_url, but assembled from CONFIG (no Django request in the layer2 process)."""
    if not file_path:
        return None
    rel = str(file_path).lstrip("/")
    # A path already carrying the media segment (e.g. '/media/3d/glb/x.glb') is joined without double-prefixing it.
    if rel.startswith("media/"):
        rel = rel[len("media/"):]
    return glb_media_base() + rel
