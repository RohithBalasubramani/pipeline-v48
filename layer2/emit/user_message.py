"""layer2/emit/user_message.py — build the Layer-2 per-card USER message (the assembled Layer2CardInput). [PROMPTS §L2(b)]
Shows the metadata SHAPE + byte-identical STATIC-CONFIG DEFAULTS: the STORED stripped skeleton
(card_payloads.payload_stripped, built by scripts/build_stripped_payloads.py — data leaves → typed placeholders,
narrative/clock scrubbed), read DIRECTLY. Runtime stripping is retired: a NULL payload_stripped fails loudly (run the
builder), never a silent on-the-fly strip."""
import json

from config.app_config import cfg
from layer2.emit.asset_facts import nameplate_line, data_window_line
from layer2.emit.panel_members_block import panel_members_block

# equipment-registry facts [stream C] — additive lines beside NAMEPLATE/DATA WINDOW; a broken/absent module must
# never take the user message down (facts degrade to none, prompt byte-identical to pre-wiring).
try:
    from layer2.emit.equipment_facts import equipment_fact_lines
except Exception:                                              # pragma: no cover — import-time armor
    def equipment_fact_lines(asset):
        return ()
from layer2.emit.slot_catalog import build_slot_catalog, render_slot_catalog
from layer2.emit.instructions.consumer_binding import domain_endpoints
# OVERSIZED-PROMPT compaction HOME = emit/prompt_compact.py (monoliths F9, 2026-07-12); re-exported byte-compatibly.
from layer2.emit.prompt_compact import (                                                   # noqa: F401
    _compact_arrays, _compact_catalog, maybe_compact as _maybe_compact)


def _fields_optional_classes():
    """Handling classes whose cards carry NO data_instructions.fields (pure chrome / run_special widget builders /
    panel_aggregate consumers). ONE accessor (config.gates_vocab) shared with layer2/build.py + validate/build.py,
    so the prompt and the gates can never disagree — the old local default here was 4-of-5 (missing panel_aggregate),
    putting prompt and gate on opposite sides on a DB outage [A6a]."""
    from config.gates_vocab import fields_optional_classes
    return fields_optional_classes()


def _basket_lines(basket, cap=400):   # show the FULL DB schema (neuract meters ~40 cols; lt_panels ~190) — uncapped in practice
    from layer2.quantity_class import column_class
    out = []
    cols = basket.get("columns") or []
    hidden = max(0, len(cols) - cap)
    for c in cols[:cap]:
        hint = c.get("kind") or "raw"          # NAME-PATTERN guess from spelling (describe.py) — NOT an instruction
        has = c.get("has_data")
        # qty = the column's PHYSICAL QUANTITY class (from its self-describing name + describe unit, layer2/
        # quantity_class vocab) — the emit's hard wall: a column only ever binds a slot of the SAME quantity.
        qty = column_class(c) or "?"
        # TOKEN BUNDLE [C1]: empty metric/rank fields are DROPPED (they were empty on 4540/4540 sweep lines — pure
        # separator noise), and the ★/✗ markers are short TOKENS defined ONCE in the DB SCHEMA header above (the
        # per-line prose repeated the same two sentences ~130K chars per sweep).
        bits = [f"  {c.get('column')}"]
        if c.get("metric"):
            bits.append(str(c["metric"]))
        bits += [f"name_hint={hint}", c.get("unit") or "", f"qty={qty}", f"data={'Y' if has else 'N'}"]
        if c.get("rank") is not None:
            bits.append(f"rank={c.get('rank')}")
        line = " | ".join(bits)
        # the pre-L2 validation verdict folded into the basket (validate/build): a FAILED column is UNBINDABLE (the
        # gate rejects it) — token defined in the header: substitute or honest-blank.
        if c.get("verdict") == "fail":
            line += "  ✗ FAILED-VALIDATION"
        elif has and hint == "derived":
            # THE TRAP: describe.py's name-regex tags real logged columns (_spread/_unbalance/_pct/current_min|max/_loss)
            # 'derived' purely from spelling. They ARE logged (data=Y) — reading them is kind:raw, NOT an fn. The token's
            # meaning (never wrap a live column in an invented recovery fn) is defined ONCE in the header. [emit R1]
            line += "  ★ REAL-LOGGED (kind:raw)"
        out.append(line)
    if hidden:
        out.append(f"  … (+{hidden} lower-ranked columns not shown — prompt budget; bind ONLY from the lines above)")
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
        # WHY-PROSE CAP [C1]: an exact match (conf 1.0) explains itself — its `why` sentence is pure repetition
        # ("this column IS the asked-for quantity" × every row). Keep the prose ONLY where it carries information:
        # a substitute / low-confidence row (conf<1.0), where WHY this stand-in was picked matters to the bind.
        try:
            conf = float(p.get("confidence"))
        except (TypeError, ValueError):
            conf = None
        why = f"  ({p.get('why') or ''})" if (conf is None or conf < 1.0) and p.get("why") else ""
        out.append(f"  {p.get('column')} | conf={p.get('confidence')} | {p.get('label') or ''}"
                   f"{('  ⟵ stands in for: ' + sub) if sub else ''}{why}")
    return "\n".join(out)


def _skeleton_paths(node, prefix=""):
    """Every dict path (containers AND leaves) in the skeleton — the DUAL-OWNED suffix matcher's search space."""
    if isinstance(node, dict):
        for k, v in node.items():
            p = f"{prefix}.{k}" if prefix else str(k)
            yield p
            yield from _skeleton_paths(v, p)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _skeleton_paths(v, f"{prefix}[{i}]")


def _dual_owned_line(skeleton):
    """★ DUAL-OWNED flag for THIS card [C4 fixture relocation]: the 'AI-default, data-overridable' metadata key paths
    (the worker MAY overwrite them from a live frame — RTM sectionContracts, HPQ signature spokes/selectedName). The
    GENERIC rule lives in metadata.md (DUAL-OWNED SLOTS); the per-card examples moved OUT of the shared system prompt
    into exactly the cards that carry them: vocabulary = the DB row emit.dual_owned_keys (path suffixes), matched
    against THIS card's own skeleton paths — no card ids, no RTM/HPQ fixtures in the shared prefix. '' when none."""
    keys = [str(k).strip() for k in (cfg("emit.dual_owned_keys",
            ["sectionContracts", "pres.spokes", "pres.selectedName"]) or []) if str(k).strip()]
    if not keys or not isinstance(skeleton, dict):
        return ""
    hits = []
    for p in _skeleton_paths(skeleton):
        if any(p == k or p.endswith("." + k) for k in keys) and p not in hits:
            hits.append(p)
    if not hits:
        return ""
    return ("★ DUAL-OWNED metadata keys of THIS card (AI-default, data-overridable — the DUAL-OWNED SLOTS rule): "
            "author your normal byte-identical default for each; the DATA worker MAY overwrite it from the live "
            f"frame at fill time: {', '.join(hits)}")


def build_user(card_in):
    """The per-card user message — rebuilt COMPACTED when it exceeds the DB-config char budget (oversized prompts
    were a deterministic l2_emit timeout: the c24 23.4K-tok family). The budget decision + engine live in
    emit/prompt_compact.py (monoliths F9); compaction is honesty-preserving and self-announcing in ai_ logs."""
    return _maybe_compact(_build, card_in)

def _build(card_in, *, oversize=False):
    s, cr, asset = card_in["story"], card_in["catalog_row"], card_in.get("asset") or {}
    rec, con, ctl, feas = cr["recipe"], cr["contract"], cr["controls"], cr["feasibility"]
    dp = cr.get("default_payload")

    # metadata shape + byte-identical defaults: the STORED stripped skeleton (payload_stripped — data leaves reset to
    # typed placeholders 0/[], narrative/clock scrubbed), read DIRECTLY. Runtime stripping is retired: a NULL here means
    # the builder was never run for this card (scripts/build_stripped_payloads.py) — fail loudly rather than silently
    # strip on the fly (which would hide the missing row and could drift from the certified seedless column).
    from config.app_config import cfg as _cfg2
    if dp:
        skeleton = dp.get("payload_stripped")
        if skeleton is None:
            raise ValueError(
                f"card {card_in['card_id']}: card_payloads.payload_stripped is NULL — the stored seedless skeleton is "
                "missing. Runtime stripping is retired; run scripts/build_stripped_payloads.py.")
        data_paths = dp.get("data_paths") or []
        shape_note = (f"(real harvested default, pre-stripped: DATA leaves reset to typed placeholders (0/[]) and "
                      f"filled by data_instructions: {data_paths})")
        # DATA-TIER SHAPE COLLAPSE [emit diet Stage 2, flag emit.diet.morph_shape — Mechanism-A root fix]: a
        # morph-map card's shown skeleton carried its zero-filled DATA grids verbatim (card 24's periods×panels
        # harmonic matrix), and the model copied+expanded them into 14K-token fabricated-data morphs the producer
        # rejects anyway (obs row 4485). Collapse every data_paths subtree to ONE live-fill marker so the temptation
        # never reaches the prompt. Morph-map cards only — full-author cards must keep typed placeholders to copy.
        if data_paths:
            from layer2.emit.diet import morph_shape as _diet_shape
            if _diet_shape():
                from layer2.emit.morphmap.mode import use_morphmap_metadata as _use_mm
                if _use_mm(card_in):
                    from layer2.emit.morphmap.shape_collapse import collapse_data_tier
                    skeleton = collapse_data_tier(skeleton, data_paths)
                    shape_note += (" ★ DATA-tier subtrees are shown COLLAPSED to <<DATA: N element(s)…>> markers — "
                                   "the executor fills them LIVE; never author, morph, or re-type them")
    else:
        skeleton, data_paths = (con.get("payload_schema_json") or {}), []
        shape_note = "(contract payload_schema_json — no harvested default available)"
    if oversize:                                              # OVERSIZED-PROMPT CONTEXT CAP — skeleton exemplars
        skeleton_shown = _compact_arrays(skeleton, int(_cfg2("emit.oversize_array_exemplars", 2)))
        meta_block = json.dumps(skeleton_shown, indent=1)
        shape_note += (" ★ COMPACTED for prompt budget: long arrays show only their first elements — author the "
                       "visible exemplars; every omitted element ships as its byte-identical default automatically")
    else:
        meta_block = json.dumps(skeleton, indent=1)

    caps = ", ".join(f"{c['metric']}:{str(c['supported']).lower()}" for c in con.get("capabilities", []))
    de = domain_endpoints(cr.get("backend_strategy"))                 # this card's VALID endpoints (live + its history variants)
    _valid = ([de["live"]] if de["live"] else []) + de["history"]
    # ENDPOINT TEXT LIVES IN THE SYSTEM PROMPT [C1]: the run-constant CLOSED SET + RETIRED blocklist + choose-by rules
    # are substituted ONCE into data_instructions.md ({{LIVE_ENDPOINTS}}/{{RETIRED_ENDPOINTS}} — the cacheable shared
    # prefix); repeating them here cost ~95K chars per sweep. The user message carries ONLY the per-card facts.
    _ep_hint = (f"your card's NATURAL endpoints (prefer one): {_valid}  — `{de['live']}` is the LIVE/now screen; "
                f"{de['history'] or 'none'} are its DATE-CAPABLE history variants for a trend/profile card. "
                f"(The closed set / retired blocklist / choose-by rules are in the system prompt.)"
                if de["live"] else "this card has NO live endpoint (non-data card) — omit the fetch block.")
    cands = "\n".join(
        f"  - cand {c['card_id']} \"{c['title']}\" {c['width_px']}x{c['height_px']} | role:{c.get('analytical_role')} "
        f"| purpose:{c.get('card_purpose')} | viz:{c.get('visualization')}" for c in card_in.get("swap_candidates", []))

    # SLOT CATALOG — the EXACT fillable leaf paths in THIS card's default payload + the best real basket column per leaf.
    # This is the slot VOCABULARY: field.slot MUST be one of these paths (the executor resolves ONLY a real leaf path,
    # never an invented token). Empty on a $ctx group atom's non-data card / a card with no data leaves.
    slot_catalog = build_slot_catalog(dp["payload"], card_in["column_basket"]) if dp else []
    slot_summaries = []
    basket_cap = 400
    if oversize:                                              # OVERSIZED-PROMPT CONTEXT CAP — sibling slots + basket lines
        slot_catalog, slot_summaries = _compact_catalog(slot_catalog, int(_cfg2("emit.oversize_sibling_exemplars", 3)))
        basket_cap = int(_cfg2("emit.oversize_basket_cap", 40))

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
        ]
    # NAMEPLATE + DATA WINDOW verbatim facts [C3]: the real rating row (a '—' rating ⇒ any fn/const needing it is
    # UNBINDABLE — the faith-based I_RATED=131 / ratedKw=600 consts had no fact to check against) and the table's real
    # first/last logged ts (28/38 window emits chose wall-clock 'today' over a lagging dataset — 255 no_reading blanks).
    for _fact in (nameplate_line(asset), data_window_line(asset, card_in.get("column_basket")),
                  *equipment_fact_lines(asset)):              # equipment-registry facts [stream C]; () on miss/off
        if _fact:
            parts.append(_fact)
    parts += [
        "DB SCHEMA — the asset's REAL columns (bind EVERY data field to one of these; never invent a column).",
        "  ★ name_hint is a NAME-PATTERN guess from the column's spelling, NOT an instruction. A column with data=Y is a "
        "REAL LOGGED VALUE: bind it kind:raw by its EXACT name even if name_hint says 'derived' (current_max_spread, "
        "current_unbalance_pct are logged columns — READ them raw, NEVER wrap them in an fn). Reserve kind=derived for a "
        "quantity that has NO column of its own. A line marked `★ REAL-LOGGED (kind:raw)` is EXACTLY that case; a line "
        "marked `✗ FAILED-VALIDATION` is mostly-null on this meter — do NOT bind it (substitute same-quantity or "
        "honest-blank with a data_note).",
        "  ★ qty = the column's PHYSICAL QUANTITY (temperature/power/energy/current/voltage/frequency/…). This is a "
        "HARD WALL: a column binds ONLY a slot of the SAME quantity — power is NOT temperature/aging/readiness/count; "
        "a deviation/spread column is NEVER crest-factor/flicker; thd_current_* is NEVER a voltage-harmonic (h5/h7) "
        "value. If NO column carries the slot's quantity, the slot is HONEST-BLANK (omit the field, say why in "
        "data_note) — the gate blanks any cross-quantity bind, so a proxy never ships.",
        "  (column | metric? | name_hint | unit | qty | data | rank? — empty metric/rank fields are omitted)",
        _basket_lines(card_in["column_basket"], cap=basket_cap),
        "",
        "RELEVANT COLUMNS (Layer 1b, ranked; conf=1.0 exact, 0.6–0.8 = closest real STAND-IN when the exact quantity "
        "isn't measured). BEST-EFFORT: bind the exact column when present; if the asked-for quantity is absent, bind the "
        "highest-confidence substitute below — ONLY within the slot's SAME physical-quantity family (THE CANONICAL "
        "SAME-QUANTITY-FAMILY PROXY RULE in PART 2: declare it in data_note + morph the describing leaves; a "
        "DIFFERENT-quantity column is NEVER a substitute, omit the field instead). Do NOT fabricate a column.",
        _probable_lines(card_in["column_basket"]) or "  (every concept exact-matched — no substitution needed)",
        ]
    _pm = panel_members_block(asset)                        # verbatim panel topology facts (panels only; '' otherwise)
    if _pm:
        parts += ["", _pm]
    # ★ SECTION-COMPARE DIRECTIVE [sections overlay]: 1b DETERMINISTICALLY detected that the prompt compares 2+ bus
    # sections of THIS panel (compare_sections stamp). The overlay contract itself lives in the system prompt's ROSTER
    # section (★ BUS-SECTION COMPARE OVERLAY); a rule buried in a 63K-char system prompt is not salient enough on its
    # own (verified live: rule present, facts present, zero splits emitted) — this per-run trigger makes it BINDING.
    _cmp_secs = (asset or {}).get("compare_sections") if isinstance(asset, dict) else None
    if _pm and _cmp_secs:
        try:
            from data.equipment.sections import token as _sec_token
            _sec_toks = [_sec_token(asset.get("name"), s) for s in _cmp_secs]
        except Exception:
            _sec_toks = []
        _sec_toks = [t for t in _sec_toks if t] or [f"1{s}" for s in _cmp_secs]
        parts += ["",
                  f"★ BUS-SECTION COMPARE — REQUIRED FOR THIS RUN: the prompt compares bus sections "
                  f"{' vs '.join(_cmp_secs)} of THIS panel. Apply the BUS-SECTION COMPARE OVERLAY rule (ROSTER section "
                  f"of the system prompt) to THIS card — this is an instruction, not an option:",
                  f"  · every roster SERIES slot: re-emit as mode \"series_split\" with one series PER SECTION, match "
                  f"{{\"sections\": [\"<token>\"]}} using the tokens VERBATIM from the PANEL MEMBERS `section=` facts "
                  f"above (e.g. {_sec_toks}); key = \"<origkey>_{_cmp_secs[0].lower()}\"/\"<origkey>_"
                  f"{_cmp_secs[-1].lower()}\".",
                  "  · PAIR every split with its pres morphs in exact_metadata: duplicate the matching stackSeries/"
                  "lineSeries entry per section (suffixed key, label \"<orig> — Sec A/B\", DISTINCT color per section), "
                  "extend stackOrder/lineOrder, list every changed path in _morphed. A split without these morphs "
                  "renders NOTHING.",
                  "  · every roster ELEMENT slot: keep the recipe and ADD \"section\": {\"a\":\"section\",\"b\":\"attr\"} "
                  "so each row/spoke declares its section; morph pres columns with {\"id\":\"section\",\"header\":\"Sec\"} "
                  "when the card's columns are payload-driven.",
                  f"  · NAME THE COMPARISON IN THE TITLE: morph the card's title heading (pres.titlePrefix, or the "
                  f"title/cardTitle leaf this card uses) so the header itself reads as a {' vs '.join(_cmp_secs)} "
                  f"comparison — e.g. \"{_cmp_secs[0]} vs {_cmp_secs[-1]} — <the card's own name>\". The host does NOT "
                  f"add any comparison suffix; the title is entirely yours. List the changed path in _morphed.",
                  "  · non-roster leaves stay unchanged; a section with no members in the facts is never invented."]
    parts += [
        "",
        "THIS CARD (cmd_catalog row):",
        f"  title: {cr.get('title')}",
        f"  handling_class: {cr.get('handling_class')}   resolver_scope: {cr.get('resolver_scope')}   "
        f"payload_family: {cr.get('payload_family')} [REF-ONLY: DATA-fill dialect]",
        f"  contract: component={con.get('component')} host_cmd_component={con.get('host_cmd_component')} shape={con.get('canonical_shape')}",
        f"  fetch ENDPOINT — {_ep_hint}",
        f"  recipe (UNRESOLVED — resolve into data_instructions.fields): shape={rec.get('payload_shape')} "
        f"orientation={rec.get('orientation')} entity_dim={rec.get('entity_dim')} selection_dim={rec.get('selection_dim')} "
        f"selection_role={rec.get('selection_role')}",
        f"    fields={_recipe_fields(rec.get('fields'))}",
        ]
    # ROSTER recipe [package §2c]: the card's card_fill_recipe.roster_spec row VERBATIM — the AI's data_instructions
    # .roster MUST conform to it (its ONLY decision surface is the COLUMN inside col/delta/phase_mean/prefer_abs
    # bindings, chosen from the DB SCHEMA block). Absent on non-roster cards (block omitted).
    if rec.get("roster_spec"):
        parts += ["    roster_spec (VERBATIM card recipe — data_instructions.roster MUST conform; "
                  "you may only choose the COLUMN inside col/delta/phase_mean/prefer_abs bindings, "
                  "from the DB SCHEMA above): "
                  + json.dumps(rec["roster_spec"], separators=(",", ":"))]
    parts += [
        "    (for a kind=derived slot: NAME a `fn` from the RECOVERY LIBRARY block at the bottom of the system prompt "
        "whose base_columns are ALL in the DB SCHEMA above, set target_column to the frame column, scope=row; "
        "honest-degrade the FIVE PHYSICAL WALLS — emit no derived field. CONFIG chrome stays a literal in "
        "exact_metadata, never an fn.)",
        f"  controls: time_mode={ctl.get('time_mode')} sampling_options={ctl.get('sampling_options')} "
        f"segmented_tabs={ctl.get('segmented_tabs')} defaults={ctl.get('defaults')}",
        f"  capabilities (metric:supported): {caps}",
        f"  feasibility: verdict={feas.get('verdict')} required_topology={feas.get('required_topology')} reason={feas.get('reason')}",
        ]
    if cr.get("handling_class") in _fields_optional_classes():
        # THREE no-fields stories, one branch each [A5]: a member-scope card WITH a roster_spec is a ROSTER CARD (its
        # DATA rides data_instructions.roster — the old two-way split dropped it into the NO-FIELDS/OMIT-fetch
        # chrome text while the roster_spec block above said 'roster MUST conform': 12-of-23 emitted the fetch block,
        # 11 omitted, card 18 dropped the roster entirely). A panel_aggregate with NO roster_spec rides its consumer's
        # panel fan-out. Everything else is chrome/special-renderer. All three are LEGITIMATE fields: [] emissions.
        if rec.get("roster_spec"):
            # Written against the gate's REAL acceptance (gates.gate_data_instructions + gate_roster): fields: []
            # beside a non-empty roster CONFORMS; gate_roster folds clean column choices in and backfills omitted
            # recipe slots verbatim; the fetch block feeds the consumer's window/range knobs (consumer_build
            # ai_spec) — it is NOT omitted on a roster card.
            from layer2.emit.diet import roster_diff as _diet_roster
            if _diet_roster():
                # ROSTER-DIFF CONTRACT [emit diet Stage 1, forensics 2026-07-15]: the full-retype form spent ~55% of
                # every completion re-typing recipe truth gate_roster folds back verbatim anyway (a 110-entry roster
                # = 6K of a 7.3K-token emit). Same decision surface, diff-shaped output; the gate's omitted-slot
                # backfill (roster.py:163) reconstructs the identical normalized roster.
                parts += [
                    "  ★ ROSTER CARD (member-scope, roster_spec above): this card's DATA rides data_instructions"
                    ".roster — emit `roster` as a DIFF against the recipe: ONLY the entries you CHANGE (a COLUMN "
                    "choice inside col/delta/phase_mean/prefer_abs bindings, from the DB SCHEMA above, or a "
                    "BUS-SECTION series_split), slot copied VERBATIM on each emitted entry. OMIT every slot and "
                    "element key you keep — each omitted part ships the recipe VERBATIM automatically, and "
                    "`roster: []` is CORRECT when the recipe already binds everything. Also emit "
                    "data_instructions.fields: [] (an EMPTY list — LEGITIMATE beside a roster, passes the gate). "
                    "KEEP the fetch block (endpoint per the hint above — it drives the member fan-out's window/range "
                    "knobs); do NOT invent per-member fields or values. Author the FULL exact_metadata per the shape "
                    "below. answerability = MEMBER COVERAGE: \"full\" when every member reports (has_data=Y in the "
                    "PANEL MEMBERS block), \"partial\" when some members are dark (they honest-blank per-leaf — name "
                    "them in data_note).",
                ]
            else:
                parts += [
                    "  ★ ROSTER CARD (member-scope, roster_spec above): this card's DATA rides data_instructions.roster — "
                    "emit `roster` (one entry per recipe slot, slot copied VERBATIM; your ONLY decision is the COLUMN "
                    "inside col/delta/phase_mean/prefer_abs bindings, from the DB SCHEMA above) AND "
                    "data_instructions.fields: [] (an EMPTY list — LEGITIMATE beside a roster, passes the gate). KEEP the "
                    "fetch block (endpoint per the hint above — it drives the member fan-out's window/range knobs); "
                    "do NOT invent per-member fields or values. Author the FULL exact_metadata per the shape below. "
                    "answerability = MEMBER COVERAGE: \"full\" when every member reports (has_data=Y in the PANEL MEMBERS "
                    "block), \"partial\" when some members are dark (they honest-blank per-leaf — name them in data_note).",
                ]
        elif cr.get("handling_class") == "panel_aggregate":
            parts += [
                "  ★ PANEL-AGGREGATE CARD (handling_class=panel_aggregate, no roster_spec): this card renders ONE "
                "element PER PANEL MEMBER (feeders/meters), but its per-member DATA is filled by its backend_strategy "
                "consumer's panel fan-out at render time — NOT from fields[] and NOT from a roster (this card has NO "
                "roster_spec, so do NOT emit data_instructions.roster — a roster here is rejected). Emit "
                "data_instructions.fields: [] (an EMPTY list — LEGITIMATE here, passes the gate); do NOT invent "
                "per-member fields or values (that fabricates). Author the FULL exact_metadata per the shape below. "
                "answerability=\"full\" when the panel resolves; a member with no data honest-blanks per-leaf.",
            ]
        else:
            parts += [
                f"  ★ NO-FIELDS CARD (handling_class={cr.get('handling_class')}): this card's DATA is NOT filled from "
                "fields[] — it is pure UI chrome or a special renderer (narrative/topology/3D widgets built server-side). "
                "Emit data_instructions.fields: [] (an EMPTY list — this is LEGITIMATE here and passes the gate), OMIT the "
                "fetch block, and author the FULL exact_metadata per the shape below (that IS the render). "
                "answerability=\"full\" (the card renders completely from its metadata). Do NOT invent data fields. "
                "TIME-CURSOR chrome (history tick labels / currentLabel / a scrubber's step state) CANNOT be known when you "
                "author: emit history as an EMPTY list ([]) and currentLabel as \"\" with canStepBack/canStepForward false — "
                "NEVER fabricated placeholder samples ([{\"label\":\"\"}, …]) or a pretend step state; the page composite "
                "derives the real cursor from the sibling heatmap's live history at render time.",
            ]
    # MORPH-MAP MODE [emit.morphmap_mode]: the system prompt (morphmap/prompt.md) asks for a {"morphs":{path:value}}
    # map instead of a full exact_metadata retype — every default ships byte-identical by construction. Keep the SHAPE
    # block verbatim (the AI still needs to see the leaf paths + defaults to choose the few morphs), but flip the
    # instruction wording so the user message agrees with the system prompt.
    # ★ DP-GATED (SAME decision as emit._system): the morphs-only header is shown ONLY for a card that HAS a stored
    # skeleton (default_payload.payload_stripped non-null — `dp` truthy here means the shape block above is the STORED
    # skeleton, not the contract example). A NO-DEFAULT-PAYLOAD card keeps the full-author header even with the flag on,
    # so the user message and the system prompt AGREE and the card authors exact_metadata (build.py's no-dp path).
    from layer2.emit.morphmap.mode import use_morphmap_metadata as _use_mm
    _mm = _use_mm(card_in)
    _meta_header = (
        f"METADATA SHAPE + STATIC-CONFIG DEFAULTS — these ship BYTE-IDENTICAL automatically. Return `morphs`: a flat "
        f"map of ONLY the few story-driven leaf paths you change (dotted+[i], copied verbatim from the shape; `{{}}` is "
        f"the common case). DATA leaves (typed 0/[] placeholders) are NEVER morphs {shape_note}:"
        if _mm else
        f"METADATA SHAPE + STATIC-CONFIG DEFAULTS — author EVERY metadata key as exact_metadata, BYTE-IDENTICAL "
        f"unless the story justifies a morph; DATA leaves already show their typed placeholder (0/[]) — copy them "
        f"as-is, NEVER refill them with a value {shape_note}:")
    parts += ["", _meta_header, meta_block]
    _dual = _dual_owned_line(skeleton)          # per-card DUAL-OWNED flag [C4] — '' on every card without those keys
    if _dual:
        parts.append(_dual)
    parts += [
        "",
        "★ FILLABLE DATA-LEAF SLOTS — the EXACT payload leaf paths the executor fills, each with its VERBATIM payload "
        "context. Every data field's `slot` MUST be COPIED VERBATIM from the left column below "
        "(an invented token like tile_r / series_r / sourceInputKw does NOT resolve — the executor only reaches a real "
        "leaf path). For a kind=raw/bucketed/derived leaf, bind a `column`/`fn` from the DB SCHEMA above whose quantity "
        "matches the leaf's own label/unit/section context (the R-phase leaf → the *_r column). A slot marked "
        "`| expected_qty=X` takes ONLY a qty=X column/fn — the gate BLANKS any cross-quantity bind (power is never "
        "temperature/aging/readiness/count; deviation/spread is never crest-factor/flicker); a suffix `(weak)` marks a "
        "dimension-only class (percent/ratio) — match the label's own SEMANTIC, never a different quantity that merely "
        "shares the unit. When NO schema column "
        "measures a leaf's quantity, emit NO field for that leaf AT ALL (omit it — the leaf honest-blanks; say why in "
        "data_note, answerability=partial); NEVER emit a raw/bucketed field with column=null — kind=\"time\" is the "
        "ONLY column-less field (a TIME AXIS line below). Never fabricate:",
        "\n".join([render_slot_catalog(slot_catalog)] + slot_summaries),
        "",
        f"SWAP CANDIDATES (±15% size, render_real, off-page, not in template) — closest {len(card_in.get('swap_candidates', []))}:",
        cands or "  (none)",
    ]
    if card_in["is_group_card"] and card_in.get("shared_ctx_ref"):
        ref = card_in["shared_ctx_ref"]
        parts += ["", "SHARED CONTEXT REF (read-only; built once in Move 1; data_instructions.fields[].source points HERE):",
                  f"  $id: {ref.get('$id')}   buffer_keys: {ref.get('buffer_keys')}   interaction_seeds: {ref.get('interaction_seeds')}",
                  "  Your atom holds NO data — fields[].source points at the shared buffer; you STILL author full exact_metadata."]
    _closing = (
        "return morphs (flat {path:value} of the story-driven few; {} = all defaults) + data_instructions (resolved "
        "recipe, real basket columns). JSON:"
        if _mm else
        "author exact_metadata (byte-identical default, morph per story) + data_instructions (resolved recipe, real "
        "basket columns). JSON:")
    _swap_directive = "Decide keep/swap (rules 1-3 + interdependency + confidence>=0.9 + named criterion), then MORPH-EMIT:"
    # T1-12 DATALESS AI-NOMINATION clause — appended ONLY when the DB knob swap.dataless_nomination is on; off = the
    # directive bytes are IDENTICAL to the legacy prompt (the shared cacheable prefix is untouched).
    try:
        from config import feasibility as _feas_cfg
        if _feas_cfg.DATALESS_NOMINATION:
            _swap_directive += (" If THIS card is WHOLLY unfillable for this asset (answerability=\"none\"), you MAY "
                                "name a SWAP CANDIDATE above (its exact card_id) as swap_to_id — a fillable, same-size "
                                "card that best serves this story angle — and the render-gate will honor your "
                                "nomination instead of the closest-size default.")
    except Exception:
        pass
    parts += ["", _swap_directive, _closing]
    return "\n".join(parts)
