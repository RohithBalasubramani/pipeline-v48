"""layer2/emit/metadata/asset_3d.py — exact_metadata for a 3D-viewer card: the resolved GLB object + viewer context.

Fills the 23 asset_3d + 2 topology_sld dead-end cards with an HONEST 3D object (scene coords stay FE — this authors the
focus labels + which GLB to load). Ports backend2 core/resolver.py's 4-tier most-specific-first binding onto V48's flat
lt_asset_3d catalog, but as a SQL read (the layer2 pipeline runs in a SEPARATE process from Django — it reaches the same
target_version1.neuract registry the topology layer reads, never the Django ORM):

    1. mfm.asset_3d_override_id            — the per-MFM override           (lt_mfm.asset_3d_override_id)
    2. type + rating variant              — a rating variant of the type   (lt_asset_3d.rating = the MFM's nameplate)
    3. mfm_type.default_asset_3d_id       — the type default               (lt_mfm_type.default_asset_3d_id)
    4. viewer.default_asset_3d_key        — the honest global-default GLB   (individual/overview page-types only)

Returns ``{"object": {slug,label,url,rating}, "viewer": {pageType}}`` — or ``{"reason": <human sentence>}`` (from
config.reason_templates, cause ``no_asset_3d``) when NOTHING binds. NEVER a wrong/guessed GLB: a card with no bound
model + no configured default honest-degrades to a reason, the FE shows "—". The absolute GLB url is built from
config.asset3d_media (mirrors backend2 CatAsset.model_url / assets/serializers.get_url).

DB-DRIVEN: page_type (render path), the rating vocab, the global-default key and the GLB media base are all editable
cmd_catalog rows (config.viewer_policy + config.asset3d_media); the reason sentence is an editable reason_template row.
fail-open everywhere — a DB outage yields None / a reason, never a crash or a fabricated model."""
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
    obj = _resolve_object(mfm_id, pt) if mfm_id else None
    if obj is None:
        # HONEST-DEGRADE: no per-MFM model, no type default, no configured global default → a reason, never a guess.
        label = (asset or {}).get("name") or (f"MFM {mfm_id}" if mfm_id else "this card")
        return {"reason": _reasons.reason("no_asset_3d", asset=label)}
    return {"object": obj, "viewer": {"pageType": pt}}


# ── the 4-tier resolve (SQL, most-specific-first) ───────────────────────────────────────────────────────────────────
def _resolve_object(mfm_id, page_type):
    """``{slug,label,url,rating}`` for the MFM's bound GLB, resolved MOST-SPECIFIC-FIRST over the flat lt_asset_3d
    catalog. None when nothing binds (the honest-degrade signal). fail-open: any read error → None (a reason follows)."""
    rating = _mfm_rating(mfm_id)
    row = (_tier_override(mfm_id)
           or _tier_rating_variant(mfm_id, rating, page_type)
           or _tier_type_default(mfm_id)
           or _tier_global_default(page_type))
    if not row:
        return None
    key, name, file_path = row[0], row[1], (row[2] if len(row) > 2 else None)
    return {
        "slug": key or None,
        "label": name or None,
        "url": _media.glb_url(file_path),                 # None when the file is unset (honest-degrade, never guessed)
        "rating": (rating or None),
    }


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
