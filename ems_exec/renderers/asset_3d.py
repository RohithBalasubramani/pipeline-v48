"""ems_exec/renderers/asset_3d.py — the 3D-VIEWER renderer (cards 60 Engine Callout + 82 Transformer 3D).

Renders OUTSIDE the per-card column-fill executor (which has no GLB resolution): it resolves WHICH GLB an asset shows +
the viewer look, and emits the ViewerResolveResponse envelope the frontend viewer consumes:

    { equipment: {id, key, kind, type, pageType},
      object:    {slug, label, url, rating}  OR  null,     ← the resolved 3D model (null = honest ComingSoon)
      viewer:    {camera, lighting, environment, bloom, toneMap, pills, …} }   ← the merged look

Ports backend2 core/resolver.py:58-144 resolve_viewer onto V48's NEURACT-only stack:
  · object    — layer2/emit/metadata/asset_3d.emit_asset_3d(asset, page_key): the 4-tier most-specific-first resolver
                over lt_asset_3d (override → rating-variant → type-default → global-default), already carrying the
                ABSOLUTE GLB url via config.asset3d_media.glb_url. REALITY today: the neuract asset_3d tables are EMPTY
                and every *_asset_3d_id FK is NULL (registries.neuract.assets3d.model_for → None), so the resolver binds
                NOTHING → object=null → the FE shows its own ComingSoon3D / placeholder. NEVER a fabricated model.
  · viewer    — deep_merge (services.dict_merge.deep_merge) of the global viewer_defaults baseline (a DB-driven
                config/viewer_policy knob) with the asset's own preset. backend2 _merge, per-leaf override.

DATA = NEURACT ONLY. HONEST-DEGRADE: a missing model / DB outage → object=null (never a guessed GLB), viewer={} baseline.
DB-DRIVEN: page_type, the GLB media base, the global-default key, and the viewer_defaults baseline are all editable
cmd_catalog rows (config.viewer_policy + config.asset3d_media) with code-default fallbacks. [atomic; one concern]
"""
from __future__ import annotations

import json

from layer2.emit.metadata.asset_3d import emit_asset_3d as _emit_asset_3d
from services.dict_merge import deep_merge as _deep_merge

# viewer_defaults is an OPTIONAL JSON baseline stored as the editable viewer_policy __knob__ row
# 'viewer.viewer_defaults' (backend2 AppKV[viewer_defaults]). Read fail-open; absent → {} (empty baseline, honest).
_VIEWER_DEFAULTS_KNOB = "viewer.viewer_defaults"


def render(asset, card, ctx):
    """The ViewerResolveResponse envelope for a 3D-viewer card (60 Engine Callout / 82 Transformer 3D).

    ``asset`` = 1b's resolved asset dict ({mfm_id, table, name, key, kind, type, …}); ``card`` = the card def row
    ({id, …}); ``ctx`` = {asset_table, mfm_id, db_link, window, page_key}. Returns the structured envelope — with
    object=null (+ the FE's own placeholder) when nothing binds, NEVER a fabricated GLB.
    """
    asset = asset or {}
    ctx = ctx or {}
    page_key = ctx.get("page_key")

    # ── object: the resolved GLB (4-tier most-specific-first) OR null (honest-degrade) ──────────────────────────────
    # emit_asset_3d returns {object, viewer:{pageType}} on a bound model, or {reason:…} when NOTHING binds. We take the
    # object verbatim (its url is already the ABSOLUTE config.asset3d_media url) and derive page_type from it when set.
    emitted = _emit_asset_3d(_asset_for_emit(asset, ctx), page_key)
    obj = emitted.get("object") if isinstance(emitted, dict) else None
    page_type = ((emitted.get("viewer") or {}).get("pageType") if isinstance(emitted, dict) else None) \
        or _page_type(page_key)

    # ── viewer: global baseline ⊕ this asset's preset (deep merge, preset wins per leaf) ────────────────────────────
    viewer = _deep_merge(_viewer_defaults(), _asset_preset(obj))

    out = {
        "equipment": {
            "id": asset.get("mfm_id") if asset.get("mfm_id") is not None else asset.get("id"),
            "key": asset.get("key") or asset.get("slug"),
            "kind": asset.get("kind") or "asset",
            "type": asset.get("type") or asset.get("mfm_type") or asset.get("asset_type"),
            "pageType": page_type,
        },
        "object": obj,          # {slug,label,url,rating} OR None — NEVER a fabricated model
        "viewer": viewer,       # merged look (empty {} baseline when nothing configured — honest)
    }
    # ADDITIVE optional key [stream D]: a kit-preview-resolved object may carry a backend-driven KPI-overlay
    # `template` JSON (25/55 catalog slugs). Pass it through top-level when present; absent (every lt_asset_3d
    # object today) → the key is OMITTED and the envelope is byte-identical — per-leaf honest-blank downstream.
    if isinstance(obj, dict) and obj.get("template") is not None:
        out["template"] = obj["template"]
    # HONEST-GAP REASON [c60 wrong-template family]: an UNBOUND model must carry the 3D-appropriate reason (the
    # editable reason_template 'no_3d_model'/'no_asset_3d' rows — never the metric sentence 'these metrics not logged
    # by this meter', which describes a column card, not a model binding). The resolver's own reason (emit_asset_3d's
    # 4-tier miss note) ships verbatim when present. Rides the SAME per-leaf channel every card uses (fill.GAPS_KEY —
    # the host pops it into render.gaps/reason; telemetry, never a render gate).
    if obj is None:
        try:
            resolver_reason = (emitted or {}).get("reason") if isinstance(emitted, dict) else None
            if not resolver_reason:
                from config.reason_templates import reason as _reason
                name = asset.get("name") or asset.get("label") or ctx.get("asset_table") or "this asset"
                resolver_reason = _reason("no_asset_3d", asset=name)
        except Exception:
            resolver_reason = "No 3D model registered for this asset."
        try:
            from ems_exec.executor.fill import GAPS_KEY
            # the resolver may name a MORE SPECIFIC cause (e.g. 'glb_not_in_media_root' — a kit-preview model
            # resolved but its GLB failed the default-deny local-file gate [stream D]); generic 'no_3d_model' else.
            cause = (emitted.get("cause") if isinstance(emitted, dict) else None) or "no_3d_model"
            out[GAPS_KEY] = [{"slot": "object", "cause": cause, "metric": "3D model",
                              "column": None, "fn": None, "reason": resolver_reason}]
        except Exception:
            pass
    return out


# ── helpers ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _asset_for_emit(asset, ctx):
    """The dict emit_asset_3d needs — it keys on ``mfm_id`` (and uses ``name`` only for the reason sentence). Prefer the
    resolved asset's own mfm_id, else the ctx's (they agree; ctx is the authoritative binding)."""
    mfm_id = ctx.get("mfm_id")
    if mfm_id is None:
        mfm_id = asset.get("mfm_id")
    return {"mfm_id": mfm_id, "name": asset.get("name") or asset.get("label"), "table": ctx.get("asset_table")}


def _page_type(page_key):
    """The viewer render-path family for a page_key ('individual'|'overview'|'variant'|None) — the editable
    viewer_policy row (fail-open code default). None → the FE keeps its own default framing."""
    try:
        from config import viewer_policy as _vp
        return _vp.page_type_for(page_key)
    except Exception:
        return None


def _viewer_defaults():
    """The GLOBAL viewer-look baseline (camera/lighting/environment/bloom/toneMap/pills/…): the editable JSON knob
    viewer.viewer_defaults on cmd_catalog.viewer_policy (backend2 AppKV[viewer_defaults]). fail-open → {} (an empty
    baseline is honest — the FE viewer supplies its own defaults; we never fabricate a look)."""
    try:
        from config import viewer_policy as _vp
        raw = _vp._txt(_VIEWER_DEFAULTS_KNOB, None)
    except Exception:
        raw = None
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        val = json.loads(raw)
        return val if isinstance(val, dict) else {}
    except (ValueError, TypeError):
        return {}


def _asset_preset(obj):
    """The resolved asset's OWN viewer preset (backend2 CatAsset.default_overrides ⊕ ViewerRule.preset). The V48 4-tier
    emit returns only {slug,label,url,rating} today (no preset column), so a per-asset preset carried on the object is
    honoured when present, else {} (the baseline stands alone). Never fabricates a look."""
    if isinstance(obj, dict):
        preset = obj.get("viewer") or obj.get("preset") or obj.get("default_overrides")
        if isinstance(preset, dict):
            return preset
    return {}
