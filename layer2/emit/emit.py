"""layer2/emit/emit.py — the ONE Layer-2 per-card AI call. Composes the 3 atomic prompt parts (swap + metadata +
data_instructions) into the system prompt, builds the user message, calls Qwen, returns the raw Layer2CardOutput. [PROMPTS §L2(a)(d)]

HARDENED [2026-07-03 emit findings]:
  · RECOVERY LIBRARY is GENERATED from the live derivation registry (ems_exec.derivations.registry.catalog()) into the
    {{RECOVERY_LIBRARY}} placeholder in data_instructions.md — the AI-visible fn list can never drift from the code
    LIBRARY again (the static list was missing kpiKwLoadPctOfRated + the whole energy today/week/month family);
  · ONE bounded transport retry (app_config llm.transport_retry, default 1) when call_qwen fails — a 120s-graze under
    sweep load no longer silently ships a default-skeleton card;
  · `feedback` kwarg — the gate-failure re-prompt seam (layer2/build.py appends the EXACT gate issues; with pinned
    seed/temp the appended text is what makes the retry non-identical);
  · call is stage-tagged ('l2_emit') so its timeout is the DB row llm.timeout.l2_emit and failures are classified,
    returning {"_llm_error": kind} instead of a silent {} (build.py degrades honestly on it)."""
import os
import re

from llm.client import call_qwen
from layer2.emit.user_message import build_user

_P = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts")

_LIB_PLACEHOLDER = "{{RECOVERY_LIBRARY}}"
_ROSTER_BEGIN, _ROSTER_END = "<!--ROSTER:BEGIN-->", "<!--ROSTER:END-->"

# A '<word>:' pseudo-prefix marks a NON-FRAME base (nameplate:rated_kva, breaker:rating_a — resolved from a config /
# equipment-schema table, never a meter column), so the plain-basket filter must skip it. Generalized from the old
# literal 'nameplate:' split; '<asset name>' and real columns don't match, keeping their classification byte-identical.
_PSEUDO_BASE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*:")


def _nameplate_rated(card_in):
    """True/False = the resolved asset's nameplate rating is populated; None = unknown (no asset / DB outage) —
    unknown NEVER hides a fn (never over-filter on missing info; the executor's fill-time guard still protects)."""
    table = ((card_in or {}).get("asset") or {}).get("table")
    if not table:
        return None
    try:
        from config.nameplates import rated_kva
        return rated_kva(table) is not None
    except Exception:
        return None


def _breaker_rated(card_in):
    """True/False = the resolved asset's breaker rating_a is populated; None = unknown (no asset / DB outage) —
    unknown NEVER hides a fn (mirrors _nameplate_rated exactly). False covers every DETERMINISTIC no-fill state
    (no breaker row / NULL or non-positive rating / dup-table meter), where offering the fn is pure temptation.
    Reached only while equipment.derivations.enabled is on — at knobs-off the breaker fns are absent at the source
    (registry.catalog), so this probe never runs on a certified emission."""
    table = ((card_in or {}).get("asset") or {}).get("table")
    if not table:
        return None
    try:
        from data.equipment.ratings import breaker_state
        return breaker_state(table)
    except Exception:
        return None


def _recovery_library_block(card_in=None):
    """The RECOVERY LIBRARY lines, generated from the ONE code LIBRARY (registry.catalog()) so prompt and executor can
    never disagree. A derivation_binding row annotated scope='topology' is marked not-single-meter-bindable (its base
    columns are synthetic topology-pair keys, e.g. hv_input_kw). Never raises — on any failure the block honestly says
    the library is unavailable (the AI then emits NO derived fields = honest-degrade, never an invented fn).

    PER-CARD BASKET FILTER [C2 token/temptation cut — TAIL-only variance, the shared prompt prefix stays byte-identical
    so vLLM prefix caching is preserved]: with a card_in, a fn whose non-nameplate base_columns are NOT all in this
    card's column basket is HIDDEN (it could never be legally bound here — showing it was pure temptation: DG fuel fns
    on panel voltage cards), and a fn with a `nameplate:<rating>` base is hidden when THIS asset's rating is known-empty
    (the empty-denominator rule). A `breaker:<rating>` base gets the same empty-denominator treatment via the tri-state
    _breaker_rated probe (known-empty hides; unknown never does), probed LAZILY on the first breaker-based entry so a
    knobs-off emission — where registry.catalog() omits the breaker fns at the source — performs zero equipment reads.
    A trailer always says how many fns were hidden and why, so a legal recovery is never silently invisible. No card_in
    (or an unknown basket) → the FULL library, unchanged."""
    try:
        from ems_exec.derivations.registry import catalog
        scopes = {}
        try:
            from config.derivation_binding import all_bindings
            scopes = {b["metric"]: b.get("scope") for b in all_bindings()}
        except Exception:
            scopes = {}
        basket_cols = None
        rated = None
        if card_in is not None:
            basket_cols = {c.get("column") for c in ((card_in.get("column_basket") or {}).get("columns") or [])
                           if c.get("column")}
            rated = _nameplate_rated(card_in)
        lines, hidden = [], 0
        brated = "unprobed"                                    # lazy tri-state: probed once, only if a breaker fn shows
        for e in catalog():
            base = e.get("base_columns") or []
            if basket_cols is not None:
                plain = [b for b in base if not _PSEUDO_BASE.match(str(b))]
                nplate = [b for b in base if str(b).startswith("nameplate:")]
                brk = [b for b in base if str(b).startswith("breaker:")]
                if plain and not all(b in basket_cols for b in plain):
                    hidden += 1
                    continue                                   # base columns not on this meter — never legally bindable
                if nplate and rated is False:
                    hidden += 1
                    continue                                   # empty nameplate denominator — the fn must not be offered
                if brk:
                    if brated == "unprobed":
                        brated = _breaker_rated(card_in)
                    if brated is False:
                        hidden += 1
                        continue                               # empty breaker denominator — same rule, tri-state probed
            mark = "  ★ topology-pair only — NOT single-meter bindable (never pick for a fields[] fn)" \
                if scopes.get(e["fn"]) == "topology" else ""
            q = e.get("quantity") or "unclassified"
            note = f" | note={e['note']}" if e.get("note") else ""
            lines.append(f"{e['fn']} | quantity={q} | base_columns=[{','.join(e['base_columns'])}] "
                         f"| fidelity={e['fidelity']}{note}{mark}")
        if hidden:
            lines.append(f"({hidden} fns hidden — their base columns are not on this meter / the nameplate rating is "
                         f"empty, so they CANNOT be legally bound here; do NOT name a fn that is not listed above)")
        return "\n".join(lines)
    except Exception:
        return "(recovery library unavailable — emit NO derived fields; honest-degrade)"


def _wants_roster_section(card_in):
    """The ROSTER section ships ONLY to a member-scope card (roster_spec present, or a panel_aggregate/topology_sld
    handling class) — 28 of 85 calls need it; everyone else got 20 lines of temptation. Unknown card → keep (safe)."""
    if card_in is None:
        return True
    cr = card_in.get("catalog_row") or {}
    if (cr.get("recipe") or {}).get("roster_spec"):
        return True
    return cr.get("handling_class") in ("panel_aggregate", "topology_sld")


def _endpoint_sets():
    """(live, retired) endpoint name lists for the system-prompt placeholders — run-constant (same substitution every
    call, so the shared prefix stays cacheable). Sourced from the SAME registries the user-message hint uses."""
    try:
        from layer2.emit.instructions.consumer_binding import RETIRED_ENDPOINTS
        from layer2.emit.instructions.endpoint_registry import LIVE_ENDPOINTS
        return sorted(LIVE_ENDPOINTS), sorted(RETIRED_ENDPOINTS)
    except Exception:
        return [], []


_MORPHMAP_PROMPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "morphmap", "prompt.md")


def _system(card_in=None):
    # PROMPT COMPOSITION — the base is the rules-first data_instructions_v2.md, the SINGLE Layer-2 contract (it subsumes
    # the retired swap.md + metadata.md + data_instructions.md trio; the llm.prompt_v2 selector + those files are gone).
    # ONE remaining DEFAULT-OFF flag, emit.morphmap_mode:
    #  · morph-map is the morphs-only metadata contract, appended as an explicit PART 2 OVERRIDE section for a card that
    #    HAS a stored skeleton to overlay (use_morphmap_metadata = flag on AND catalog_row.default_payload.payload_stripped
    #    non-null — the SAME fact build._finalize routes the morphs on). A NO-DEFAULT-PAYLOAD card (no card_payloads row —
    #    e.g. the AI-Summary / Heatmap time-axis narrative cards) keeps v2's FULL-author exact_metadata contract even with
    #    the flag on, so it authors exact_metadata, hits build.py's no-dp branch, and never trips "no default payload +
    #    empty exact_metadata". When the override is composed the output envelope is rewritten to "morphs":{} below — the
    #    empirically dominant lever (the model follows the concrete JSON template). build.py routes a {"morphs":…} return
    #    through morphmap.producer.apply; a full exact_metadata return still routes the full path (shape-keyed, fail-safe).
    from layer2.emit.morphmap.mode import use_morphmap_metadata as _use_mm
    _mm = _use_mm(card_in)
    parts = []
    with open(os.path.join(_P, "data_instructions_v2.md"), errors="replace") as f:
        parts.append(f.read().strip())
    if _mm:
        with open(_MORPHMAP_PROMPT, errors="replace") as f:
            parts.append(
                "════ PART 2 OVERRIDE — MORPH-MAP (supersedes R12's `_morphed` mechanism and PART 2's "
                "exact_metadata retype for THIS card; every OTHER rule R1-R14 stands unchanged) ════\n"
                + f.read().strip())
    out = "\n\n".join(parts)
    live, retired = _endpoint_sets()
    out = out.replace("{{LIVE_ENDPOINTS}}", str(live)).replace("{{RETIRED_ENDPOINTS}}", str(retired))
    # conditional ROSTER section (marker-wrapped, sits at the TAIL right before the RECOVERY LIBRARY — cutting it
    # never touches the shared prefix): shown only to member-scope cards, markers stripped either way.
    b, e = out.find(_ROSTER_BEGIN), out.find(_ROSTER_END)
    if b != -1 and e != -1:
        if _wants_roster_section(card_in):
            out = out.replace(_ROSTER_BEGIN + "\n", "").replace(_ROSTER_END + "\n", "")
        else:
            out = out[:b] + out[e + len(_ROSTER_END) + 1:]
    if _LIB_PLACEHOLDER in out:
        out = out.replace(_LIB_PLACEHOLDER, _recovery_library_block(card_in))
    # MORPH-MAP OUTPUT-ENVELOPE ACTIVATION [live-activation of the morphs path]: the metadata contract is morphs-only,
    # but the base prompt's final 'Emit exactly {…}' envelope in data_instructions_v2.md still shows
    # "exact_metadata":{"_morphed":[]} — a contradiction the model resolves toward the concrete JSON template, so it
    # emitted exact_metadata and build.py's shape-router sent it down the FULL path (morph-map never actually
    # activated). When the morph-map PART 2 override is composed for a skeleton card,
    # rewrite that ONE envelope key to the morphs shape so the single output contract the model sees is morphs
    # (build._mm_raw then routes {"morphs":…} through morphmap.producer.apply). Off / no-dp cards keep exact_metadata
    # verbatim — the substring is unique to the envelope line.
    if _mm:
        out = out.replace('"exact_metadata":{"_morphed":[]}', '"morphs":{}')
    return out


def emit(card_in, feedback=None):
    """One per-card emit. `feedback` = gate issue strings from a REJECTED previous attempt (appended verbatim so the
    deterministic model sees a different input and can correct exactly those defects). Returns the parsed dict; on
    LLM failure (after one bounded transport retry) the dict carries `_llm_error` so build.py can degrade honestly —
    NEVER a silent {} that reads as an intentional empty emission."""
    from config.app_config import cfg
    user = build_user(card_in)
    if feedback:
        user += ("\n\nPREVIOUS ATTEMPT REJECTED — the deterministic gate found EXACTLY these defects. "
                 "Fix ONLY these (everything else was fine) and re-emit the FULL JSON object:\n"
                 + "\n".join(f"  - {i}" for i in feedback))
    sysmsg = _system(card_in)
    # Transient-only bounded retry — the ONE shared policy (llm/transient_retry): a deterministic
    # 'timeout'/'truncated' fails fast (retrying doubles the wall-clock hang — the card-5 32K-tok heatmap
    # 2x-timeout page-hang); a transport/5xx blip is re-sent within llm.transport_retry.
    from llm.transient_retry import retry_transient
    # DECISION INSPECTOR: the slot's swap pool IS the selection set of PART 1 (keep-vs-swap) — declared per attempt
    # (call_qwen clears the context on return) so the llm event's `decision` names the pool this card chose from.
    # Fan-out threads each carry their own contextvar copy (run/parallel), so per-card contexts never cross.
    from obs import llm_tap
    _swap_pool = [{"card_id": c.get("card_id"), "title": c.get("title")}
                  for c in (card_in.get("swap_candidates") or [])]

    def _call():
        llm_tap.set_decision(kind="selection", candidate_kind="swap_target", candidates=_swap_pool,
                             card_id=card_in.get("card_id"), gate_feedback_retry=bool(feedback))
        return call_qwen(sysmsg, user, stage="l2_emit", on_error="marker")

    # legacy fetch-block key (replay tapes / old cached emissions) normalized ONCE here — every downstream reader
    # (build, window_backfill, recipe, gates) sees only data_instructions.fetch. [rename 2026-07-12]
    from domain.fetch_spec import normalize
    return normalize(retry_transient(_call))
