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

from llm.client import call_qwen
from layer2.emit.user_message import build_user

_P = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts")

_LIB_PLACEHOLDER = "{{RECOVERY_LIBRARY}}"
_ROSTER_BEGIN, _ROSTER_END = "<!--ROSTER:BEGIN-->", "<!--ROSTER:END-->"


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


def _recovery_library_block(card_in=None):
    """The RECOVERY LIBRARY lines, generated from the ONE code LIBRARY (registry.catalog()) so prompt and executor can
    never disagree. A derivation_binding row annotated scope='topology' is marked not-single-meter-bindable (its base
    columns are synthetic topology-pair keys, e.g. hv_input_kw). Never raises — on any failure the block honestly says
    the library is unavailable (the AI then emits NO derived fields = honest-degrade, never an invented fn).

    PER-CARD BASKET FILTER [C2 token/temptation cut — TAIL-only variance, the shared prompt prefix stays byte-identical
    so vLLM prefix caching is preserved]: with a card_in, a fn whose non-nameplate base_columns are NOT all in this
    card's column basket is HIDDEN (it could never be legally bound here — showing it was pure temptation: DG fuel fns
    on panel voltage cards), and a fn with a `nameplate:<rating>` base is hidden when THIS asset's rating is known-empty
    (the empty-denominator rule). A trailer always says how many fns were hidden and why, so a legal recovery is never
    silently invisible. No card_in (or an unknown basket) → the FULL library, unchanged."""
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
        for e in catalog():
            base = e.get("base_columns") or []
            if basket_cols is not None:
                plain = [b for b in base if not str(b).startswith("nameplate:")]
                nplate = [b for b in base if str(b).startswith("nameplate:")]
                if plain and not all(b in basket_cols for b in plain):
                    hidden += 1
                    continue                                   # base columns not on this meter — never legally bindable
                if nplate and rated is False:
                    hidden += 1
                    continue                                   # empty nameplate denominator — the fn must not be offered
            mark = "  ★ topology-pair only — NOT single-meter bindable (never pick for a fields[] fn)" \
                if scopes.get(e["fn"]) == "topology" else ""
            q = e.get("quantity") or "unclassified"
            lines.append(f"{e['fn']} | quantity={q} | base_columns=[{','.join(e['base_columns'])}] "
                         f"| fidelity={e['fidelity']}{mark}")
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
        from layer2.emit.data.consumer_binding import RETIRED_ENDPOINTS
        from layer2.emit.data.endpoint_registry import LIVE_ENDPOINTS
        return sorted(LIVE_ENDPOINTS), sorted(RETIRED_ENDPOINTS)
    except Exception:
        return [], []


_MORPHMAP_PROMPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "morphmap", "prompt.md")


def _system(card_in=None):
    # PROMPT SELECTION (two DEFAULT-OFF flags; default path is the byte-identical 3-file concat):
    #  · llm.prompt_v2 → the rules-first rewrite data_instructions_v2.md which SUBSUMES swap+metadata+data into ONE file
    #    (still the full-author exact_metadata contract). Held default-off pending a larger A/B (the 8-card A/B showed a
    #    coverage regression). Takes precedence: v2 carries its own metadata contract, so morph-map does not compose in.
    #  · emit.morphmap_mode → swap ONLY the metadata slice (metadata.md → morphmap/prompt.md, the morphs-only Part-2
    #    variant); swap.md + data_instructions.md unchanged. build.py routes the {"morphs":…} return through
    #    morphmap.producer.apply. The two flags are mutually exclusive; prompt_v2 wins if both are somehow set.
    #    ★ DP-GATED: the morph-map metadata slice is composed ONLY for a card that HAS a stored skeleton to overlay
    #    (use_morphmap_metadata = flag on AND catalog_row.default_payload.payload_stripped non-null — the SAME fact
    #    build._finalize routes the morphs on). A NO-DEFAULT-PAYLOAD card (no card_payloads row — e.g. the AI-Summary /
    #    Heatmap time-axis narrative cards) keeps the FULL-author metadata.md even with the flag on, so it authors
    #    exact_metadata, hits build.py's no-dp else-branch, and never trips "no default payload + empty exact_metadata".
    from config.app_config import cfg as _cfg
    from layer2.emit.morphmap.mode import use_morphmap_metadata as _use_mm
    prompt_v2 = str(_cfg("llm.prompt_v2", "false")).strip().lower() in ("1", "true", "yes", "on")
    parts = []
    if prompt_v2:
        with open(os.path.join(_P, "data_instructions_v2.md"), errors="replace") as f:
            parts.append(f.read().strip())
    else:
        _mm = _use_mm(card_in)
        for name in ("swap.md", "metadata.md", "data_instructions.md"):
            path = _MORPHMAP_PROMPT if (name == "metadata.md" and _mm) else os.path.join(_P, name)
            with open(path, errors="replace") as f:
                parts.append(f.read().strip())
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
    # MORPH-MAP OUTPUT-ENVELOPE ACTIVATION [live-activation of the morphs path]: the metadata slice is morphmap/prompt.md
    # (morphs-only), but data_instructions.md's final 'Emit exactly {…}' envelope still shows
    # "exact_metadata":{"_morphed":[]} — a contradiction the model resolves toward the concrete JSON template, so it
    # emitted exact_metadata and build.py's shape-router sent it down the FULL path (morph-map never actually activated).
    # When the morph-map metadata slice is composed, rewrite that ONE envelope key to the morphs shape so the single
    # output contract the model sees is morphs (build._mm_raw then routes {"morphs":…} through morphmap.producer.apply).
    # Off / prompt_v2 / no-dp cards keep exact_metadata verbatim — the substring is unique to the envelope line.
    if not prompt_v2 and _use_mm(card_in):
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
    raw = call_qwen(sysmsg, user, stage="l2_emit", on_error="marker")
    retries = max(0, int(cfg("llm.transport_retry", 1)))
    # A 'timeout'/'truncated' error is DETERMINISTIC for this prompt (the same large emit will time out / overrun
    # again), so retrying only DOUBLES the wall-clock hang (the card-5 32K-tok heatmap 2x-timeout page-hang). Retry
    # ONLY transient failures (transport/5xx); a deterministic failure honest-fails fast → build.py degrades honestly.
    no_retry = {k.strip() for k in (cfg("llm.no_retry_kinds", "timeout,truncated") or "").split(",") if k.strip()}
    while isinstance(raw, dict) and raw.get("_llm_error") and raw.get("_llm_error") not in no_retry and retries > 0:
        retries -= 1
        raw = call_qwen(sysmsg, user, stage="l2_emit", on_error="marker")
    return raw or {}
