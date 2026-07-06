"""config/asset3d_media.py — the absolute base URL the layer2 asset_3d emit prepends to a stored GLB ``file`` path.

The ems_backend serves uploaded GLBs at ``<http_base>/media/<file>`` (settings.MEDIA_URL='/media/'). The Django-side
resolver (lt_panels/asset3d/resolve.py) uses ``request.build_absolute_uri`` for this; the layer2 emit runs in a
SEPARATE process with no request, so it needs the base as CONFIG. This is a NEW concern → its OWN single-purpose file
(atomic-structure rule), mirroring quality_policy's num()/txt() accessor style over an editable cmd_catalog row.

DB-DRIVEN: the base is the editable ``viewer_policy`` __knob__ row ``viewer.glb_media_base`` (rides the same table the
rest of the asset_3d viewer knobs use); the code default is the ems_backend HTTP origin from config.ems_backend +
MEDIA_URL. fail-open: DB down / row absent → the code default, so the emit builds the same url either way. NEVER
fabricates a url for a missing file — the caller only calls glb_url() when it has a real ``file`` path. [#1 asset_3d]
"""
import os

from config.ems_backend import EMS_WS_HOST, EMS_WS_PORT

# ── code defaults (the fail-open fallback) ──────────────────────────────────────────────────────────────────────────
# The ems_backend HTTP origin (NOT the WS scheme) + MEDIA_URL. Env-overridable; the DB knob wins when set.
_HTTP_SCHEME = os.environ.get("EMS_HTTP_SCHEME", "http")
_MEDIA_URL = os.environ.get("EMS_MEDIA_URL", "/media/")            # ems_backend settings.MEDIA_URL
_GLB_MEDIA_BASE_DEFAULT = f"{_HTTP_SCHEME}://{EMS_WS_HOST}:{EMS_WS_PORT}{_MEDIA_URL}".rstrip("/") + "/"


def glb_media_base():
    """The absolute base URL a stored GLB ``file`` path hangs off — editable row viewer.glb_media_base (rides
    cmd_catalog.viewer_policy), else the ems_backend HTTP origin + MEDIA_URL code default. Always ends in '/'. Never
    raises (fail-open) — the emit builds an identical url with the DB down."""
    try:
        from config import viewer_policy as _vp
        base = _vp._txt("viewer.glb_media_base", None)            # rides the same viewer_policy __knob__ surface
    except Exception:
        base = None
    base = (base or _GLB_MEDIA_BASE_DEFAULT).strip()
    return base if base.endswith("/") else base + "/"


def glb_url(file_path):
    """The absolute GLB url for a stored ``file`` path (the DB's ``lt_asset_3d.file`` value, e.g. '3d/glb/pcc1a.glb').
    None for an empty/missing path (HONEST-DEGRADE — never a guessed url). Mirrors backend2 CatAsset.model_url +
    assets/serializers.get_url, but assembled from CONFIG (no Django request in the layer2 process)."""
    if not file_path:
        return None
    rel = str(file_path).lstrip("/")
    # A path already carrying MEDIA_URL (e.g. '/media/3d/glb/x.glb') is joined without double-prefixing the media seg.
    media_seg = _MEDIA_URL.strip("/")
    if media_seg and rel.startswith(media_seg + "/"):
        rel = rel[len(media_seg) + 1:]
    return glb_media_base() + rel
