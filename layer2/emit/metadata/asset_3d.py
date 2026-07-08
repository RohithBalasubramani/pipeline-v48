"""layer2/emit/metadata/asset_3d.py — exact_metadata for a 3D-viewer card: the resolved GLB object + viewer context.

Fills the 23 asset_3d + 2 topology_sld dead-end cards with an HONEST 3D object (scene coords stay FE — this authors the
focus labels + which GLB to load). Ports backend2 core/resolver.py's 4-tier most-specific-first binding onto V48's flat
lt_asset_3d catalog, but as a SQL read (the layer2 pipeline runs in a SEPARATE process from Django — it reaches the same
target_version1.neuract registry the topology layer reads, never the Django ORM):

    1. mfm.asset_3d_override_id            — the per-MFM override           (lt_mfm.asset_3d_override_id)
    2. type + rating variant              — a rating variant of the type   (lt_asset_3d.rating = the MFM's nameplate)
    3. mfm_type.default_asset_3d_id       — the type default               (lt_mfm_type.default_asset_3d_id)
    4. viewer.default_asset_3d_key        — the honest global-default GLB   (individual/overview page-types only)
    5. equipment kit-preview fallback     — the LOCAL cmd_catalog kit-preview catalog (data/equipment/kitpreview),
       keyed on the identity-VERIFIED equipment node (stream A bridge.identity_node — never a raw equipment_id hop),
       behind cfg('equipment.kitpreview.enabled','off') + a DEFAULT-DENY local-file existence gate. lt_asset_3d
       (tiers 1-4) WINS whenever it binds; the 5th tier only fills the today-always-null gap. [stream D]

Returns ``{"object": {slug,label,url,rating}, "viewer": {pageType}}`` — or ``{"reason": <human sentence>}`` (from
config.reason_templates, cause ``no_asset_3d``; plus an additive ``cause`` key when tier 5 names a more specific
per-leaf gap, e.g. ``glb_not_in_media_root``) when NOTHING binds. NEVER a wrong/guessed GLB: a card with no bound
model + no configured default honest-degrades to a reason, the FE shows "—". The absolute GLB url is built from
config.asset3d_media (mirrors backend2 CatAsset.model_url / assets/serializers.get_url).

DB-DRIVEN: page_type (render path), the rating vocab, the global-default key and the GLB media base are all editable
cmd_catalog rows (config.viewer_policy + config.asset3d_media); the reason sentence is an editable reason_template row.
fail-open everywhere — a DB outage yields None / a reason, never a crash or a fabricated model."""
import os

from config import viewer_policy as _vp
from config import asset3d_media as _media
from config import reason_templates as _reasons
from config.databases import DATA_DB, DATA_SCHEMA
from data.db_client import q


def emit_asset_3d(asset, page_key, page_type=None):
    """exact_metadata overlay for a 3D-viewer card. ``asset`` = 1b's resolved asset dict ({mfm_id, table, panel_id, …});
    ``page_key`` = the card's page (→ its viewer render path). Returns ``{object, viewer}`` on a resolved GLB, else
    ``{reason}`` (honest-degrade, cause=no_asset_3d) — NEVER a wrong GLB. ``page_type`` may be passed to skip the lookup.

    A non-data / bad input (no mfm_id) also honest-degrades to a reason: this emit binds a REAL model to a REAL meter,
    it never invents one."""
    pt = (page_type or _page_type_of(page_key) or "individual")
    mfm_id = (asset or {}).get("mfm_id")
    obj, gap_cause = _resolve_object(mfm_id, pt, (asset or {}).get("table")) if mfm_id else (None, None)
    if obj is None:
        # HONEST-DEGRADE: no per-MFM model, no type default, no configured global default → a reason, never a guess.
        label = (asset or {}).get("name") or (f"MFM {mfm_id}" if mfm_id else "this card")
        out = {"reason": _reasons.reason("no_asset_3d", asset=label)}
        if gap_cause:                       # a kit-preview model RESOLVED but its GLB failed the local-file gate —
            out["cause"] = gap_cause        # the specific per-leaf cause ('glb_not_in_media_root') rides along.
        return out
    return {"object": obj, "viewer": {"pageType": pt}}


# ── the 5-tier resolve (SQL, most-specific-first) ───────────────────────────────────────────────────────────────────
def _resolve_object(mfm_id, page_type, asset_table=None):
    """``(object, gap_cause)`` for the MFM's bound GLB, resolved MOST-SPECIFIC-FIRST over the flat lt_asset_3d catalog,
    then the equipment kit-preview fallback (tier 5, knob-gated). ``(None, None)`` when nothing binds (the honest-
    degrade signal); ``(None, 'glb_not_in_media_root')`` when a kit-preview model resolved but its GLB is not in the
    verified local media root. fail-open: any read error → (None, None) (a reason follows)."""
    rating = _mfm_rating(mfm_id)
    row = (_tier_override(mfm_id)
           or _tier_rating_variant(mfm_id, rating, page_type)
           or _tier_type_default(mfm_id)
           or _tier_global_default(page_type))
    if not row:
        # tier 5 — the LOCAL equipment kit-preview catalog (lt_asset_3d stays authoritative: it WON above if it bound).
        return _tier_kitpreview(asset_table, page_type)
    key, name, file_path = row[0], row[1], (row[2] if len(row) > 2 else None)
    return {
        "slug": key or None,
        "label": name or None,
        "url": _media.glb_url(file_path),                 # None when the file is unset (honest-degrade, never guessed)
        "rating": (rating or None),
    }, None


def _tier_override(mfm_id):
    """Tier 1 — the per-MFM override (lt_mfm.asset_3d_override_id → its lt_asset_3d row). None when unset."""
    return _one(
        f"SELECT a.key, a.name, a.file FROM {DATA_SCHEMA}.lt_asset_3d a "
        f"JOIN {DATA_SCHEMA}.lt_mfm m ON m.asset_3d_override_id = a.id "
        f"WHERE m.id = {int(mfm_id)}")


def _tier_rating_variant(mfm_id, rating, page_type):
    """Tier 2 — a rating VARIANT: an lt_asset_3d whose category matches the MFM type's default bucket AND whose rating
    matches this MFM's nameplate rating. Requires the NEW nullable columns (rating/page_type); a pre-migration DB simply
    returns nothing (the read errors → None → the tier is skipped). None when no variant exists."""
    if not rating:
        return None
    return _one(
        f"SELECT a.key, a.name, a.file FROM {DATA_SCHEMA}.lt_asset_3d a "
        f"WHERE a.category = ("
        f"  SELECT d.category FROM {DATA_SCHEMA}.lt_asset_3d d "
        f"  JOIN {DATA_SCHEMA}.lt_mfm_type t ON t.default_asset_3d_id = d.id "
        f"  JOIN {DATA_SCHEMA}.lt_mfm m ON m.mfm_type_id = t.id WHERE m.id = {int(mfm_id)}) "
        f"AND a.rating = '{_esc(rating)}' "
        f"AND (a.page_type = '{_esc(page_type)}' OR a.page_type IS NULL OR a.page_type = '') "
        f"ORDER BY a.key LIMIT 1")


def _tier_type_default(mfm_id):
    """Tier 3 — the MFM type's default model (lt_mfm_type.default_asset_3d_id). None when the type has no default."""
    return _one(
        f"SELECT a.key, a.name, a.file FROM {DATA_SCHEMA}.lt_asset_3d a "
        f"JOIN {DATA_SCHEMA}.lt_mfm_type t ON t.default_asset_3d_id = a.id "
        f"JOIN {DATA_SCHEMA}.lt_mfm m ON m.mfm_type_id = t.id "
        f"WHERE m.id = {int(mfm_id)}")


def _tier_global_default(page_type):
    """Tier 4 — the honest global-default GLB (the lt_asset_3d keyed by viewer.default_asset_3d_key()). individual /
    overview page-types ONLY — a 'variant' tab never falls through to the catch-all. None when the key isn't in the
    catalog (still honest — no per-panel guess, just the one configured default or nothing)."""
    if page_type not in ("individual", "overview"):
        return None
    key = _vp.default_asset_3d_key()
    if not key:
        return None
    return _one(
        f"SELECT a.key, a.name, a.file FROM {DATA_SCHEMA}.lt_asset_3d a "
        f"WHERE a.key = '{_esc(key)}' LIMIT 1")


def _tier_kitpreview(asset_table, page_type):
    """Tier 5 — the LOCAL equipment kit-preview fallback (stream D). ``(object, gap_cause)``:

      · gated by cfg('equipment.kitpreview.enabled','off') — OFF (the shipped default) → (None, None), byte-identical
        to the certified 4-tier behaviour;
      · keyed on the IDENTITY-VERIFIED equipment node ONLY (stream A bridge.identity_node: name-similarity-gated —
        a bay meter whose equipment pointer is its HOSTING PANEL never loads the panel's GLB as its own; unverified
        → (None, None), object stays null);
      · DEFAULT-DENY existence gate: the model's glb_file is registry METADATA — the object ships ONLY when the
        LOCAL directory knob equipment.kitpreview.media_base is a readable dir actually containing the file
        (an unset / remote / unreadable root NEVER ships a url — the stale-url lesson). The SERVED url is built by
        config.asset3d_media.glb_url (the ems_backend /media/ route), never the checked filesystem path;
      · rule.preset is deep-merged OVER the model's default_overrides into obj['preset'] (backend2 _merge; the
        renderer's _asset_preset chain viewer→preset→default_overrides honours it); obj['template'] = the KPI-overlay
        JSON (None → per-leaf honest-blank downstream).

    Everything is imported lazily under a BROAD guard: a missing/half-built stream-A bridge, a DB blip, anything —
    → (None, None), never a raise (wave-1 parallel build + the never-raise facts rule)."""
    try:
        from config.app_config import cfg
        if str(cfg("equipment.kitpreview.enabled", "off")).strip().lower() not in ("on", "true", "1", "yes"):
            return None, None
        if not asset_table:
            return None, None
        from data.equipment.bridge import identity_node                        # stream A; lazy — may not exist yet
        node = identity_node(asset_table)
        if not node:
            return None, None                                                  # identity unverified → honest null
        from data.equipment import kitpreview as _kp
        rating = _kp.config_rating(node.get("node_id"))                        # 1/120 populated; fail-open None
        model = _kp.resolve_model(node.get("key"), node.get("panel_type_code"),
                                  node.get("asset_type_code"), rating or "", page_type)
        if not model or not model.get("glb_file"):
            return None, None                                                  # no rule / no uploaded GLB → null
        if _kitpreview_local_glb(model["glb_file"]) is None:
            return None, "glb_not_in_media_root"                               # DEFAULT-DENY: unverifiable → no url
        from services.dict_merge import deep_merge as _deep_merge
        return {
            "slug": model.get("slug") or None,
            "label": model.get("label") or None,
            "url": _media.glb_url(model["glb_file"]),                          # the SERVED url, never the FS path
            "rating": (rating or None),
            "preset": _deep_merge(model.get("default_overrides"), model.get("rule_preset")),
            "default_overrides": model.get("default_overrides") or {},
            "template": model.get("template"),                                 # 25/55 slugs; None = honest blank
        }, None
    except Exception:                                                          # noqa: BLE001 — never raise, never guess
        return None, None


def _kitpreview_local_glb(glb_file):
    """The verified LOCAL path for a kit-preview glb_file, or None (DEFAULT-DENY). The root MUST be the editable
    knob equipment.kitpreview.media_base — BY CONTRACT a LOCAL filesystem directory (the same dir the ems_backend
    serves as /media/). Unset / a URL / unreadable / file absent → None; a traversal outside the root → None."""
    try:
        from config.app_config import cfg
        root = str(cfg("equipment.kitpreview.media_base", "") or "").strip()
        if not root or not os.path.isdir(root):
            return None                                    # empty / remote-looking / unreadable root → DENY
        real_root = os.path.realpath(root)
        path = os.path.realpath(os.path.join(real_root, str(glb_file).lstrip("/")))
        if not path.startswith(real_root + os.sep):
            return None                                    # path traversal → DENY
        return path if os.path.isfile(path) else None
    except Exception:                                      # noqa: BLE001
        return None


# ── helpers ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _mfm_rating(mfm_id):
    """The MFM's nameplate rating token used to pick a rating variant (backend2 _equipment_rating). Read from
    lt_mfm.rated_capacity_kva → a compact token; '' when the meter has none (NEVER fabricated). fail-open to '' if the
    column is absent (pre-reseed) / the read errors."""
    row = _one(f"SELECT rated_capacity_kva FROM {DATA_SCHEMA}.lt_mfm WHERE id = {int(mfm_id)}")
    if not row or row[0] in (None, "", "0"):
        return ""
    try:
        f = float(row[0])
        return str(int(f)) if f.is_integer() else str(f)
    except (TypeError, ValueError):
        return str(row[0]).strip()


def _page_type_of(page_key):
    """The viewer render-path family for a page_key (individual|overview|variant|None) — the editable viewer_policy row
    (fail-open code default)."""
    try:
        return _vp.page_type_for(page_key)
    except Exception:
        return None


def _one(sql):
    """The first row of a fail-open SQL read (None on empty / any error) — so a missing column / DB outage degrades to
    the next tier (and ultimately a reason), never a crash. The layer2 topology layer uses the same fail-open pattern."""
    try:
        rows = q(DATA_DB, sql)
    except Exception:
        return None
    return rows[0] if rows else None


def _esc(s):
    return "" if s is None else str(s).replace("'", "''")
