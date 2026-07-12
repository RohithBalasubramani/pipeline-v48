"""ems_exec/renderers/ — the SPECIAL-CARD RENDERERS (the cards that render OUTSIDE the per-card column-fill executor).

The per-card executor (ems_exec/executor/fill.py) fills one asset's own gic_* columns onto one CMD_V2 payload. It has
NO fan-out, NO GLB resolution, and NO LLM. A handful of cards need one of those three things, so each lives here as its
own atomic renderer with the uniform signature:

    render(asset, card, ctx) -> payload

where ctx carries {asset_table, mfm_id, db_link, window, page_key}. Every renderer:
  · reads DATA from NEURACT ONLY (ems_exec.data.neuract + data.lt_panels.panel_members + registries.neuract) — never a
    premier_energies simulator;
  · HONEST-DEGRADES a missing number / model / member to the frontend's own empty/placeholder state — never fabricated;
  · reads its knobs from a DB-driven config/* accessor with a code-default fallback.

Concerns (one file each):
    asset_3d     — the 3D-viewer cards (60 Engine Callout + the ~23 asset_3d cards): the 4-tier GLB resolver + merged
                   viewer look, object=null (the FE's own ComingSoon) when nothing binds — never a fabricated GLB.
    fuel_anatomy — card 63 (Fuel Tank Anatomy): a 3D card whose backend supplies only the 3 tank telemetry numbers
                   (all null today — the DG fuel domain gap), NOT a GLB. Routed here specially even though its
                   card_handling class is asset_3d.
    panel_aggregate — the RECIPE-LESS panel_aggregate cards (e.g. 1/4/84/94/95): the members→neuract→rollup fan-out
                   feeding the per-card executor (ctx['_agg_row']) for KPI/scalar leaves + member-rolled bucketed trend
                   series. Recipe cards (5/7/9/10/11/12/13/…) are served by the generic roster interpreter first.
    narrative_ai — the AI-summary cards (8/19/25/28): a PRE-JUDGED story from real neuract facts, the LLM narrates ONE
                   line (or the deterministic fallback template over the same real numbers). Story builders in _story/.
    _insight     — the Django-free stdlib port of backend2/panels/insight.py (the vLLM narrator + cache + fallback).

DISPATCH (run_special) — the host asks for a card's ``handling_class`` (a cmd_catalog.card_handling row). This module maps
that class → the right renderer's ``render()``. The single wrinkle: a few cards carry ``handling_class = 'asset_3d'`` in
the DB but are NOT GLB cards (they mount a 3D component fed by a plain telemetry SNAPSHOT payload — the Fuel Tank Anatomy
tank). Those are routed to ``fuel_anatomy.render`` by the SHAPE OF THEIR OWN SKELETON (a top-level ``snapshot`` object —
``_is_telemetry_3d``), NEVER a hardcoded card id, BEFORE the generic asset_3d GLB path. An unknown class → None, so the
host cleanly falls back to the generic per-card executor. [atomic; one concern per file]

ROSTER-INTERPRETER (generalization package §3/§4 — cutover DONE 2026-07-03): the member-scope classes (topology_sld /
panel_aggregate) are served by ONE generic recipe interpreter (ems_exec/executor/roster.py) driven by
cmd_catalog.card_fill_recipe rows. run_special routes a roster kind through the interpreter FIRST; only a card with no
roster recipe falls through to its legacy builder — for panel_aggregate that is the recipe-less agg-row + bucketed-series
render (cards 1/4/84/94/95); topology_sld has NO legacy builder anymore (file deleted), so a recipe-less/DB-outage
topology_sld card honest-degrades to the L2 skeleton in the host. (The off/shadow cutover valve + the shadow-mode differ
are removed — the interpreter is unconditional now.)
"""
from __future__ import annotations

from ems_exec.renderers import asset_3d, fuel_anatomy, panel_aggregate, narrative_ai

# handling_class → the renderer module whose render(asset, card, ctx) builds that class's payload — DISCOVERED from the
# package itself: every non-underscore sibling module that declares HANDLING_CLASSES = ("<class>", …) self-registers.
# Adding a special renderer = dropping ONE new module in this folder with that declaration (+ its cmd_catalog.
# card_handling rows) — no dict edit here, no host edit (host/exec_cards derives its special set from special_kinds()
# below). Deterministic: modules scan in sorted name order, first claim of a class wins; a module that fails to import
# is skipped (one broken renderer must never take down the registry — the shipped four are still hard-imported above,
# so a defect in THOSE fails loudly exactly as before). Only the classes that render OUTSIDE the per-card column-fill
# executor (need fan-out / GLB / LLM) belong here; every other class (single_asset_*, nav_index) is NOT special →
# run_special returns None and the host uses the generic executor. panel_aggregate DOES fan out (a panel → its members)
# so it renders here, then REUSES the per-card executor for its KPI/scalar leaves.
def _discover_by_kind():
    import importlib
    import pkgutil
    by_kind = {}
    for name in sorted(m.name for m in pkgutil.iter_modules(__path__) if not m.name.startswith("_")):
        try:
            mod = importlib.import_module(f"{__name__}.{name}")
        except Exception:
            continue
        for k in (getattr(mod, "HANDLING_CLASSES", ()) or ()):
            k = str(k).strip()
            if k:
                by_kind.setdefault(k, mod)
    return by_kind


_BY_KIND = _discover_by_kind()

# TELEMETRY-SNAPSHOT DISCRIMINATOR [card-63 hardcode removal]: a handful of cards carry handling_class='asset_3d' in the
# DB but are NOT GLB cards — they mount a 3D component fed by a plain telemetry SNAPSHOT payload (e.g. the Fuel Tank
# Anatomy tank), not a resolved GLB. The GENERIC tell, verified across every asset_3d row: a true GLB card has NO
# harvested card_payloads skeleton (it renders a GLB envelope, object=null when nothing binds), whereas a telemetry-3D
# card carries a harvested skeleton whose top level is a `snapshot` object. So we route by the SHAPE OF THE CARD'S OWN
# SKELETON, never a hardcoded card id. The snapshot-carrying key(s) are a DB-driven set (app_config renderers.
# telemetry_snapshot_keys) with a code-default so a new telemetry-3D card lights up with an editable row, no code change.
_DEFAULT_TELEMETRY_SNAPSHOT_KEYS = ("snapshot",)


def _telemetry_snapshot_keys():
    """The top-level payload keys whose presence marks an asset_3d card as a TELEMETRY-snapshot card (→ fuel_anatomy),
    not a GLB card. Editable app_config renderers.telemetry_snapshot_keys row; code-default {'snapshot'}. Never raises."""
    try:
        from config.app_config import cfg
        v = cfg("renderers.telemetry_snapshot_keys", None)
        if isinstance(v, (list, tuple)) and v:
            return tuple(str(k) for k in v)
    except Exception:
        pass
    return _DEFAULT_TELEMETRY_SNAPSHOT_KEYS


def _is_telemetry_3d(card):
    """True iff the card's OWN harvested skeleton (exact_metadata / payload / _default_payload) carries a telemetry
    snapshot key → it renders via fuel_anatomy (a plain snapshot payload), not the GLB asset_3d resolver. Pure shape
    check over the card's own payload — no card id, no class-name special-case. Never raises."""
    if not isinstance(card, dict):
        return False
    keys = _telemetry_snapshot_keys()
    for src in ("exact_metadata", "payload", "skeleton", "_default_payload"):
        sk = card.get(src)
        if isinstance(sk, dict) and any(isinstance(sk.get(k), dict) for k in keys):
            return True
    return False

# the member-scope classes served by the GENERIC ROSTER INTERPRETER (ems_exec.executor.roster) FIRST — a card with a
# card_fill_recipe row renders through the interpreter; a recipe-less card falls through to its legacy builder (_BY_KIND)
# if it has one (panel_aggregate → the recipe-less agg-row render; topology_sld → no builder → None → host skeleton).
# DB-DRIVEN: the live set is the app_config row renderers.roster_kinds (json list) so a NEW member-scope class is a row
# edit, no code change; the code default below is the shipped pair.
_ROSTER_KINDS_DEFAULT = ("topology_sld", "panel_aggregate")


def _roster_kinds():
    """The handling classes the roster interpreter serves first. Editable app_config renderers.roster_kinds row;
    code-default _ROSTER_KINDS_DEFAULT. Never raises."""
    try:
        from config.app_config import cfg
        v = cfg("renderers.roster_kinds", None)
        if isinstance(v, (list, tuple)) and v:
            return tuple(str(k) for k in v)
    except Exception:
        pass
    return _ROSTER_KINDS_DEFAULT


def special_kinds():
    """EVERY handling_class that renders via run_special (the discovered registry classes ∪ the roster-interpreter
    classes) — the ONE source the host's special-vs-generic split derives from (host/exec_cards). A new renderer module
    or a new roster_kinds row extends this automatically; no host edit."""
    return tuple(sorted(set(_BY_KIND) | set(_roster_kinds())))


def _interpreter_payload(asset, card, ctx):
    """The GENERIC roster-interpreter payload for a member-scope card — the exact run_card path the cutover will serve
    (executor fill + roster seams). None when the card has no roster instruction/recipe (so 'on' falls back to legacy)
    or on any failure (honest-degrade; never raises).

    Recipe keying: card_fill_recipe is looked up by the RENDER identity (`render_card_id`, the swap target when Layer 2
    swapped this slot) — the payload is already the target's shape, so the original slot id's recipe must never run
    against it. Unswapped cards: render_card_id == card_id."""
    try:
        from ems_exec.executor import recipe as _recipe
        from ems_exec.serve import run as _run
        card = card or {}
        ctx = ctx or {}
        em = next((card[k] for k in ("exact_metadata", "payload", "skeleton") if isinstance(card.get(k), dict)), None)
        di = card.get("data_instructions") or {}
        rid = card.get("render_card_id") if isinstance(card, dict) else None
        rid = rid if rid is not None else _card_id(card)
        if em is None or not _recipe.roster_for(di, rid):
            return None                        # no skeleton / no roster instruction+recipe → nothing generic to run
        return _run.run_card(em, di, ctx.get("asset_table"), db_link=ctx.get("db_link"), window=ctx.get("window"),
                             default_payload=card.get("_default_payload"),
                             shape_ref=card.get("shape_ref"),   # RAW default → fab_guards raw-vs-stripped wall (no over-blank)
                             mfm_id=ctx.get("mfm_id"), asset_name=(asset or {}).get("name"), card_id=rid)
    except Exception:
        return None


def run_special(kind, asset, card, ctx):
    """Render a SPECIAL card (one that renders outside the per-card column-fill executor) → its structured payload.

    ``kind``  — the card's ``handling_class`` (cmd_catalog.card_handling): 'asset_3d' | 'topology_sld' |
                'panel_aggregate' | 'narrative_ai'.
    ``asset`` — 1b's resolved asset dict ({mfm_id, table, name, key, kind, type, …}).
    ``card``  — the card def row ({id/card_id, payload/exact_metadata, …}).
    ``ctx``   — {asset_table, mfm_id, db_link, window, page_key}.

    Returns the renderer's structured JSON payload, or **None** for a kind we do not special-case (so the host falls
    back to the generic per-card executor). Never raises — a renderer that throws honest-degrades to None here too, so a
    single broken special card can never take down the run; the host then renders it via the generic path / empty state.

    Wrinkle: a telemetry-3D card (Fuel Tank Anatomy) has ``kind == 'asset_3d'`` in the DB but is a fuel-telemetry card,
    not a GLB card, so it is routed to ``fuel_anatomy.render`` by the shape of its own skeleton (a top-level ``snapshot``
    object — ``_is_telemetry_3d``) before the generic asset_3d module is selected.
    """
    # ── ROSTER-INTERPRETER first (member-scope panel classes) ────────────────────────────────────────────────────────
    # A roster kind (topology_sld / panel_aggregate) renders through the ONE generic interpreter when it has a
    # card_fill_recipe row. A recipe-less card returns None here and falls through to its legacy builder below.
    if kind in _roster_kinds():
        out = _interpreter_payload(asset, card, ctx)
        if out is not None:
            return out                   # the generic recipe path IS the render
    module = _resolve(kind, card)
    if module is None:
        return None                      # not a special kind / recipe-less topology_sld → host uses the generic executor
    try:
        return module.render(asset, card, ctx)
    except Exception:
        # a renderer that throws is treated as "no special payload" → the host falls back to the generic path / the FE's
        # own empty state. We NEVER fabricate a payload here and NEVER let one card crash the whole run.
        return None


def _resolve(kind, card):
    """The legacy renderer module for (kind, card), or None. An asset_3d card whose OWN skeleton carries a telemetry
    snapshot (shape-based discriminator, no hardcoded card id) is a telemetry-3D card → fuel_anatomy; every other asset_3d
    card is a GLB card → the asset_3d resolver. topology_sld has no legacy module (recipe-only) → None (host skeleton)."""
    if kind == "asset_3d" and _is_telemetry_3d(card):
        return fuel_anatomy
    return _BY_KIND.get(kind)


def _card_id(card):
    """The int card id from the card row (keys id/card_id/cid), or None. Tolerates card being a bare id too."""
    if isinstance(card, dict):
        for k in ("id", "card_id", "cid"):
            v = card.get(k)
            try:
                return int(v)
            except (TypeError, ValueError):
                continue
        return None
    try:
        return int(card)
    except (TypeError, ValueError):
        return None


__all__ = ["run_special", "special_kinds", "asset_3d", "fuel_anatomy", "panel_aggregate", "narrative_ai"]
