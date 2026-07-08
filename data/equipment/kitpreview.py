"""data/equipment/kitpreview.py — stream D: the 3D-model resolver over the LOCAL `equipment` kitpreview_* tables.

The neuract lt_asset_3d catalog is EMPTY today (every 3D card ships object=null); the cmd_equipment kit-preview
catalog (mirrored locally into cmd_catalog schema `equipment`, :5432 ONLY) carries 55 real models (39 with an
uploaded glb_file, 25 with a KPI-overlay template) bound by 49 viewer rules. This module resolves WHICH model an
identity-VERIFIED equipment node shows, exactly like backend2 core/resolver.py:63-108 `resolve_binding`,
most-specific-first:

    1. for_key  = the node's equipment key                     (e.g. 'pcc-1a')
    2. for_type + rating                                       (a rating VARIANT of the type, e.g. lt_panel/630A)
    3. for_type with rating='' (the wildcard)                  (the class default, e.g. 'chiller')
    4. kitpreview_app_kv['default_panel_model']                ('individual' page family, PANEL-typed nodes only)

Empty-string for_key / rating on a rule are WILDCARDS; rules are page_type-scoped (a rule with page_type='' matches
any). `for_type` matches the node's panel_type code XOR asset_type code (equipment carries exactly one, DB CHECK).

HONEST SOURCES ONLY: the cat_asset `url` column is NEVER read (33 dead-host + 21 empty rows — the stale-url lesson);
`glb_file` is the ONLY file source, and it is METADATA — whether the file actually exists locally is the CALLER's
default-deny gate (layer2/emit/metadata/asset_3d._tier_kitpreview), never claimed here. Fail-open by contract: any
DB error / missing row -> None/{} (never raises, never cached — the next call retries via db.eq_q).
"""
import json

from data.equipment import db as _db

# kitpreview_viewer_rule ⋈ kitpreview_cat_asset columns, in SELECT order (zip target for the row dicts).
_RULE_COLS = ("for_type", "for_key", "rating", "page_type", "preset",
              "slug", "label", "glb_file", "default_overrides", "template")


def resolve_model(equipment_key, panel_type_code, asset_type_code, rating, page_type):
    """The kit-preview model for an identity-verified equipment node, most-specific-first (see module docstring).

    Returns ``{slug, label, glb_file, default_overrides: dict, template: dict|None, rule_preset: dict|None}`` —
    glb_file is registry METADATA (the caller owns the local-existence gate); ``rule_preset`` is the winning rule's
    own preset, kept SEPARATE from the model's default_overrides so the caller merges rule-over-defaults (backend2
    _merge). None on no matching rule / rule without a model row / DB error. Never raises."""
    try:
        rows = _rules()
        pt = (page_type or "").strip()
        key = (equipment_key or "").strip()
        type_code = ((panel_type_code or asset_type_code) or "").strip()
        rt = (rating or "").strip()
        cand = [r for r in rows if r["page_type"] in (pt, "")]

        pick = None
        if key:                                                     # tier 1 — the node's own key
            pick = next((r for r in cand if r["for_key"] == key), None)
        if pick is None and type_code and rt:                       # tier 2 — a rating variant of the type
            pick = next((r for r in cand if r["for_type"] == type_code and r["rating"] == rt), None)
        if pick is None and type_code:                              # tier 3 — the type default (rating wildcard)
            pick = next((r for r in cand if r["for_type"] == type_code and r["rating"] == ""), None)
        if pick is not None:
            if not pick["slug"]:                                    # a rule with no model row binds NOTHING (honest)
                return None
            return _model_dict(pick, rule_preset=_json(pick["preset"]))

        # tier 4 — the global default panel model: 'individual' page family + a PANEL-typed node ONLY
        # (backend2 resolver.py: AppKV['default_panel_model'], individual page_type only).
        if pt == "individual" and (panel_type_code or "").strip():
            slug = _app_kv("default_panel_model")
            if isinstance(slug, str) and slug.strip():
                row = _cat_asset_by_slug(slug.strip())
                if row is not None:
                    return _model_dict(row, rule_preset=None)
        return None
    except Exception:                                               # noqa: BLE001 — fail-open by contract
        return None


def viewer_defaults():
    """kitpreview_app_kv['viewer_defaults'] JSON (the global viewer-look baseline); {} on miss/error. Never raises."""
    try:
        val = _app_kv("viewer_defaults")
        return val if isinstance(val, dict) else {}
    except Exception:                                               # noqa: BLE001
        return {}


def config_rating(equipment_node_id):
    """The equipment_config ``rating`` text for an equipment node id (1/120 populated today — e.g. 'bpdb-01' →
    '660A'; NEVER depended on, read fail-open). Used to pick a rating VARIANT rule. None on miss/error/bad id.

    Lives HERE (not in the layer2 tier) because the single-door rule pins all `equipment`-schema SQL to
    data/equipment/*.py — the pinned resolve_model API takes the rating as a plain argument."""
    try:
        node_id = int(equipment_node_id)
    except (TypeError, ValueError):
        return None
    try:
        rows = _db.eq_q("SELECT rating FROM equipment.equipment_config "
                        f"WHERE equipment_id = {node_id} ORDER BY id")
    except Exception:                                               # noqa: BLE001
        return None
    for r in rows:
        if r and r[0] and str(r[0]).strip():
            return str(r[0]).strip()
    return None


# ── internals ───────────────────────────────────────────────────────────────────────────────────────────────────────
def _rules():
    """Every viewer rule joined to its model, in rule-id order (first hit within a tier wins — the DB's own
    deterministic order). csv-null ('') preserved so wildcard matching stays exact. Raises like eq_q — the ONE
    public caller (resolve_model) wraps fail-open."""
    rows = _db.eq_q(
        "SELECT r.for_type, r.for_key, r.rating, r.page_type, r.preset, "
        "       a.slug, a.label, a.glb_file, a.default_overrides, a.template "
        "FROM equipment.kitpreview_viewer_rule r "
        "LEFT JOIN equipment.kitpreview_cat_asset a ON a.id = r.model_id "
        "ORDER BY r.id")
    return [dict(zip(_RULE_COLS, r)) for r in rows]


def _cat_asset_by_slug(slug):
    """The cat_asset row for a slug (slug is UNIQUE), shaped like a _RULE_COLS dict (rule fields blank). None on miss."""
    rows = _db.eq_q(
        "SELECT '', '', '', '', NULL, a.slug, a.label, a.glb_file, a.default_overrides, a.template "
        f"FROM equipment.kitpreview_cat_asset a WHERE a.slug = '{_esc(slug)}'")
    if not rows:
        return None
    return dict(zip(_RULE_COLS, rows[0]))


def _app_kv(key):
    """kitpreview_app_kv[key] parsed from its jsonb text (a JSON string / object / …). None on miss."""
    rows = _db.eq_q(f"SELECT value FROM equipment.kitpreview_app_kv WHERE key = '{_esc(key)}'")
    if not rows or not rows[0] or rows[0][0] in (None, ""):
        return None
    return _json(rows[0][0])


def _model_dict(row, rule_preset):
    """The pinned resolve_model return shape from a joined row-dict. glb_file stays METADATA (may be None)."""
    return {
        "slug": row["slug"] or None,
        "label": row["label"] or None,
        "glb_file": (row["glb_file"] or None),
        "default_overrides": _json(row["default_overrides"]) or {},
        "template": _json(row["template"]),
        "rule_preset": rule_preset if isinstance(rule_preset, dict) else None,
    }


def _json(txt):
    """A jsonb column's csv text -> the parsed value; None on empty/unparseable (honest miss, never raises)."""
    if txt in (None, ""):
        return None
    if isinstance(txt, (dict, list)):
        return txt
    try:
        return json.loads(txt)
    except (ValueError, TypeError):
        return None


def _esc(s):
    return "" if s is None else str(s).replace("'", "''")
