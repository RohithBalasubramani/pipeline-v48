"""layer2/emit/user_message.py — build the Layer-2 per-card USER message (the assembled Layer2CardInput). [PROMPTS §L2(b)]
Shows the metadata SHAPE + byte-identical STATIC-CONFIG DEFAULTS (from the harvested default payload, DATA elided)."""
import json

from layer2.emit.metadata.split import split
from layer2.emit.data.consumer_binding import domain_endpoints, RETIRED_ENDPOINTS
from layer2.emit.data.endpoint_registry import LIVE_ENDPOINTS


def _basket_lines(basket, cap=400):   # show the FULL DB schema (neuract meters ~40 cols; lt_panels ~190) — uncapped in practice
    out = []
    for c in (basket.get("columns") or [])[:cap]:
        out.append(f"  {c.get('column')} | {c.get('metric') or ''} | {c.get('kind') or 'raw'} | "
                   f"{c.get('unit') or ''} | {'Y' if c.get('has_data') else 'N'} | {c.get('rank') if c.get('rank') is not None else ''}")
    return "\n".join(out)


def _recipe_fields(fields):
    return json.dumps([{k: f.get(k) for k in ("kind", "role", "label", "metric", "unit")} for f in (fields or [])])


def _probable_lines(basket):
    """1b's RANKED relevant columns with relevance confidence + substitute_for (the asked-for concept a low-confidence
    column stands in for). Layer 2 best-effort: bind exact (conf~1.0); if exact is absent, use the highest-confidence
    SUBSTITUTE here and NOTE it. Empty -> the basket exact-matched everything (no substitution needed)."""
    out = []
    for p in (basket.get("probable") or []):
        sub = p.get("substitute_for")
        out.append(f"  {p.get('column')} | conf={p.get('confidence')} | {p.get('label') or ''}"
                   f"{('  ⟵ stands in for: ' + sub) if sub else ''}  ({p.get('why') or ''})")
    return "\n".join(out)


def build_user(card_in):
    s, cr, asset = card_in["story"], card_in["catalog_row"], card_in.get("asset") or {}
    rec, con, ctl, feas = cr["recipe"], cr["contract"], cr["controls"], cr["feasibility"]
    dp = cr.get("default_payload")

    # metadata shape + byte-identical defaults: the harvested default payload with DATA leaves elided
    if dp:
        skeleton, data_paths = split(dp["payload"])
        meta_block = json.dumps(skeleton, indent=1)
        shape_note = f"(real harvested default; DATA leaves shown as \"$DATA\" are filled by data_instructions: {data_paths})"
    else:
        skeleton, data_paths = (con.get("payload_schema_json") or {}), []
        meta_block = json.dumps(skeleton, indent=1)
        shape_note = "(contract payload_schema_json — no harvested default available)"

    caps = ", ".join(f"{c['metric']}:{str(c['supported']).lower()}" for c in con.get("capabilities", []))
    de = domain_endpoints(cr.get("backend_strategy"))                 # this card's VALID endpoints (live + its history variants)
    _valid = ([de["live"]] if de["live"] else []) + de["history"]
    # build() uses the AI's endpoint AS-IS (no code snap), so the prompt carries the WHOLE truth (derived from
    # ems_backend): the closed set of endpoints that EXIST + the retired names that don't.
    _closed = f"  ONLY these endpoints EXIST (emit EXACTLY one): {sorted(LIVE_ENDPOINTS)}."
    _retired = (f"  ★ RETIRED — DO NOT EXIST, NEVER emit: {sorted(RETIRED_ENDPOINTS)}. "
                f"ALL Harmonics/PQ data is the SINGLE live socket `power-quality-summary` (no PQ history variant).")
    _ep_hint = (f"your card's NATURAL endpoints (prefer one): {_valid}  — `{de['live']}` is the LIVE/now screen; "
                f"{de['history'] or 'none'} are its DATE-CAPABLE history variants for a trend/profile card."
                + _closed + _retired
                if de["live"] else "this card has NO ems_backend screen (non-data card) — omit the ems_backend block.")
    cands = "\n".join(
        f"  - cand {c['card_id']} \"{c['title']}\" {c['width_px']}x{c['height_px']} | role:{c.get('analytical_role')} "
        f"| purpose:{c.get('card_purpose')} | viz:{c.get('visualization')}" for c in card_in.get("swap_candidates", []))

    parts = [
        f"RUN: {card_in['run_id']}   CARD: {card_in['card_id']}   PAGE: {card_in['page_key']}",
        f"GROUP CARD: {str(card_in['is_group_card']).lower()}   GROUP: {card_in.get('group_id') or 'none'}",
        "",
        f"PAGE STORY (Layer 1a): {s.get('page_story')}",
        f"THIS CARD'S STORY ANGLE (Layer 1a): {s.get('analytical_story')}   [your morph + a swap target MUST serve this angle]",
        f"METRIC: {s.get('metric')}   INTENT: {s.get('intent')}",
        f"TEMPLATE CARD SET (1a's chosen ids — NEVER swap to one of these): {s.get('template_card_ids')}",
        "",
        f"ASSET (Layer 1b): {asset.get('name')} (class={asset.get('class')}, table={asset.get('table')}, "
        f"panel_id={asset.get('panel_id')}, nameplate_scope=default)",
        "DB SCHEMA — the asset's REAL columns (bind EVERY data field to one of these; never invent a column):",
        "  (column | metric | kind | unit | has_data | rank)",
        _basket_lines(card_in["column_basket"]),
        "",
        "RELEVANT COLUMNS (Layer 1b, ranked; conf=1.0 exact, 0.6–0.8 = closest real STAND-IN when the exact quantity "
        "isn't measured). BEST-EFFORT: bind the exact column when present; if the asked-for quantity is absent, bind the "
        "highest-confidence substitute below and report it in data_note. Do NOT fabricate a column.",
        _probable_lines(card_in["column_basket"]) or "  (every concept exact-matched — no substitution needed)",
        "",
        "THIS CARD (cmd_catalog row):",
        f"  title: {cr.get('title')}",
        f"  handling_class: {cr.get('handling_class')}   resolver_scope: {cr.get('resolver_scope')}   "
        f"payload_family: {cr.get('payload_family')} [REF-ONLY: DATA-fill dialect]",
        f"  contract: component={con.get('component')} host_cmd_component={con.get('host_cmd_component')} shape={con.get('canonical_shape')}",
        f"  ems_backend ENDPOINT — {_ep_hint}",
        f"    Choose by the card's ANALYTICAL INTENT (orientation={rec.get('intent') or rec.get('orientation')}), NOT keyword overlap:"
        f" a now/snapshot card → the LIVE screen; a trend/profile/history card → a history variant. STRONG preference for the"
        f" list above; a RELATED screen is fine if THIS card's story needs it (e.g. a PQ card plotting a current trend → current-history)."
        f" Only an UNRELATED page's screen (e.g. real-time-monitoring on a power-quality card) is wrong.",
        f"  recipe (UNRESOLVED — resolve into data_instructions.fields): shape={rec.get('payload_shape')} "
        f"orientation={rec.get('orientation')} entity_dim={rec.get('entity_dim')} selection_dim={rec.get('selection_dim')} "
        f"selection_role={rec.get('selection_role')}",
        f"    fields={_recipe_fields(rec.get('fields'))}",
        "    (for a kind=derived slot: NAME a `fn` from the RECOVERY LIBRARY block in data_instructions.md whose "
        "base_columns are ALL in the DB SCHEMA above, set target_column to the frame column, scope=row; honest-degrade "
        "the FOUR WALLS — emit no derived field. CONFIG chrome stays a literal in exact_metadata, never an fn.)",
        f"  controls: time_mode={ctl.get('time_mode')} sampling_options={ctl.get('sampling_options')} "
        f"segmented_tabs={ctl.get('segmented_tabs')} defaults={ctl.get('defaults')}",
        f"  capabilities (metric:supported): {caps}",
        f"  feasibility: verdict={feas.get('verdict')} required_topology={feas.get('required_topology')} reason={feas.get('reason')}",
        "",
        f"METADATA SHAPE + STATIC-CONFIG DEFAULTS — author EVERY non-$DATA key as exact_metadata, BYTE-IDENTICAL "
        f"unless the story justifies a morph {shape_note}:",
        meta_block,
        "",
        f"SWAP CANDIDATES (±15% size, render_real, off-page, not in template) — closest {len(card_in.get('swap_candidates', []))}:",
        cands or "  (none)",
    ]
    if card_in["is_group_card"] and card_in.get("shared_ctx_ref"):
        ref = card_in["shared_ctx_ref"]
        parts += ["", "SHARED CONTEXT REF (read-only; built once in Move 1; data_instructions.fields[].source points HERE):",
                  f"  $id: {ref.get('$id')}   buffer_keys: {ref.get('buffer_keys')}   interaction_seeds: {ref.get('interaction_seeds')}",
                  "  Your atom holds NO data — fields[].source points at the shared buffer; you STILL author full exact_metadata."]
    parts += ["", "Decide keep/swap (rules 1-3 + interdependency + confidence>=0.9 + named criterion), then MORPH-EMIT:",
              "author exact_metadata (byte-identical default, morph per story) + data_instructions (resolved recipe, real basket columns). JSON:"]
    return "\n".join(parts)
