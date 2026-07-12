"""layer1b/compare/resolve_names.py — resolve EACH named asset of a natural compare through the SAME 1b resolver.

Given a prompt that names 2+ specific assets ('compare energy and power of GIC-01-N3-UPS-01 and GIC-02-N5-UPS-04'),
build ONE per-name sub-prompt for each named row (the shared metric words + THAT ONE asset name, the OTHER names
stripped) and run layer1b.resolve.resolve_asset on each CONCURRENTLY (run/parallel — the same primitive 1a‖1b use).

Why per-name sub-prompts and not one multi-name call: the AI asset resolver is single-asset by contract (one confident
pin OR one ambiguous list). Feeding it one asset at a time lets the EXISTING confident-pin / collision / no_data logic
decide EACH name on its own merits — reusing the resolver verbatim, no new resolution rule. A name that is a genuine
homonym in isolation (bare 'UPS-01') stays AMBIGUOUS on its own sub-prompt, so it is NOT auto-pinned; only names that
resolve to exactly ONE meter (how AI/user-choice/no_data, a pinned asset, no candidate list) count as confident.

Returns {confident:[mfm_id,…], ambiguous:[name,…], resolutions:[…]}. The caller compares when len(confident) >= 2.
Never raises: a per-name resolve failure is isolated (that name simply isn't confident).
"""
import re

from lib.parallel import run_parallel   # primitive's home (run/parallel is its facade; cycle-kill 2026-07-12)
from layer1b.resolve.asset_resolve import resolve_asset
from layer1b.compare.discriminators import _norm
from layer1b.compare.detect import named_full_rows

# a confident single resolution: an asset was pinned by NAME (or named-but-empty no_data) with NO open picker list.
# collision_gate_fullname = the deterministic full-name pin (user spelled one colliding row out in full) — also a
# confident single resolution (a pin with no picker), so a compare sub-prompt that full-name-pins keeps its pin.
from layer1b.how import RESOLVED_ANY as _CONFIDENT_HOW


# token separator inside a typed asset name: ANY short run of non-alphanumerics — names carry '(', ')', '[', ']',
# ':', '+', '.' ('GIC-15-N3-PCC-01 (Transformer-01) [Secure Elite300]', '300A + 750KVAR (APFCR-01)'); the old [-_ ]*
# class stopped at the first paren, leaving dangling name fragments in the sub-prompts (silent single-path degrade).
# Bounded {0,4} + anchored literal tokens => a separator can never bridge across a real word like ' and '.
_SEP = r"[^a-zA-Z0-9]{0,4}"


def _toks(src):
    return [t for t in re.split(r"[^a-z0-9]+", str(src or "").lower()) if t]


def _span_regex(name):
    """A tolerant regex matching THIS asset's name in the ORIGINAL (un-normalized) prompt — every SPELLING the user
    could have typed — so the OTHER names can be stripped out to isolate one asset per sub-prompt. Patterns
    (longest-first alternation; each token gap → _SEP, a bounded non-alphanumeric run):
      · the whole registry name ('gic 01 n3 ups 01 cl 600kva');
      · the GIC-node prefix WITH AN OPTIONAL NAME TAIL — mandatory 'gic-01-n3' then each following name token as a
        NESTED OPTIONAL (gic·01·n3(?:·ups(?:·01(?:…)?)?)?, · = _SEP). The user types 'GIC-01-N3-UPS-01'
        without the 'CL:600KVA' rating tail; a prefix-only strip left a DANGLING bare '-UPS-01' in the sub-prompt — a
        5-way homonym the resolver now (correctly) refuses to pin, silently killing the compare. The optional tail
        consumes exactly as much of the real name as the prompt carries — anchored on literal tokens, so surrounding
        words ('and', the other asset) are never swallowed;
      · every pcc_panel_alias spelling of a PCC panel ('pcc-2a' / 'panel-2a' / 'pcc-2' …) — the registry name
        'PCC-Panel-2' never appears in 'compare PCC-1A and PCC-2A', so name-token stripping alone left BOTH names in
        BOTH sub-prompts (the AI pinned the same panel twice → 1 confident → the compare silently degraded to single).
    None when the name yields no usable discriminator."""
    pats = []
    name_toks = _toks(name)
    if name_toks:
        pats.append(_SEP.join(re.escape(t) for t in name_toks))
    gp = _gic_prefix(name)
    if gp:
        ptoks = _toks(gp)
        tail = name_toks[len(ptoks):]                      # the name tokens after the GIC prefix (ups, 01, cl, …)
        chain = ""
        for t in reversed(tail):                           # nested optionals: consume as much tail as is present
            chain = r"(?:" + _SEP + re.escape(t) + chain + r")?"
        pats.append(_SEP.join(re.escape(t) for t in ptoks) + chain)
    try:                                                   # PCC panel alias spellings (raw; fail-open to none)
        from layer1b.compare.detect import _panel_alias_index
        for alias in _panel_alias_index().get(_norm(name), []):
            atoks = _toks(alias)
            if atoks:
                pats.append(_SEP.join(re.escape(t) for t in atoks))
    except Exception:
        pass
    if not pats:
        return None
    return re.compile("(" + "|".join(sorted(set(pats), key=len, reverse=True)) + ")", re.IGNORECASE)


def _gic_prefix(name):
    m = re.match(r"\s*(gic[-_ ]?\d+[-_ ]?n\d+)", str(name or "").lower())
    return m.group(1) if m else None


def _sub_prompt(prompt, keep_row, other_rows):
    """The original prompt with the OTHER assets' names removed, keeping only `keep_row`'s asset name — so resolve_asset
    sees ONE specific asset (the AI's confident-pin then fires on that single name). The compare conjunctions left
    behind ('and', 'vs') are harmless to the resolver; the kept name stays verbatim so the model resolves it cleanly.

    KEPT-NAME MASK [phantom-alias fix]: an OTHER row's pattern can match INSIDE the kept name — PCC-Panel-2's alias
    'panel-2' is an infix of the kept 'Chiller Panel-2 Main INC', so stripping the others mutilated the kept name
    ('Chiller Main Inc') or erased it outright, and the sub-prompt resolved empty (the live 5-chiller compare pinned
    single). Mask the kept row's FIRST span with a sentinel before stripping, restore after — the kept name is
    untouchable by construction."""
    out = prompt
    sentinel = "\x00KEEP\x00"
    kept_text = None
    krx = _span_regex(keep_row[1])
    if krx:
        m = krx.search(out)
        if m:
            kept_text = m.group(0)
            out = out[: m.start()] + sentinel + out[m.end():]
    for r in other_rows:
        rx = _span_regex(r[1])
        if rx:
            out = rx.sub(" ", out)
    if kept_text is not None:
        out = out.replace(sentinel, kept_text, 1)
    out = re.sub(r"\s+", " ", out).strip()
    return out or prompt


def resolve_compare(prompt, cands=None):
    """Resolve every fully-named asset in a natural-compare prompt through resolve_asset, concurrently. Returns
    {confident, ambiguous, resolutions}: `confident` = mfm_ids that resolved to exactly one meter (dedup, order kept);
    `ambiguous` = names that stayed a picker on their own sub-prompt. The caller routes to the multi-asset compare only
    when len(confident) >= 2 (and no name went ambiguous — every named asset must pin, or the picker is the honest answer)."""
    from layer1b.resolve.asset_candidates import asset_candidates
    cands = cands if cands is not None else asset_candidates()   # ONE probe, shared by detection AND every sub-resolve
    rows = named_full_rows(prompt, cands)
    if len(rows) < 2:
        return {"confident": [], "ambiguous": [], "resolutions": []}

    thunks = {}
    for i, r in enumerate(rows):
        others = [o for o in rows if o[0] != r[0]]
        sub = _sub_prompt(prompt, r, others)
        # share the SAME candidate list: N concurrent sub-resolves re-probing has_data over the tunnel (3-5 parallel
        # 250-table sweeps) contended and flap-errored -> ambiguous -> silent single-path [compare-share fix]
        thunks[i] = (lambda p=sub: resolve_asset(p, cands=cands))

    results = run_parallel(thunks)

    confident, ambiguous, resolutions, seen = [], [], [], set()
    for i, r in enumerate(rows):
        res = results.get(i)
        if isinstance(res, Exception) or not isinstance(res, dict):
            ambiguous.append(r[1])
            resolutions.append({"name": r[1], "how": "error", "mfm_id": None})
            continue
        asset = res.get("asset") or {}
        how = res.get("how")
        has_picker = bool(res.get("candidates"))
        mfm_id = asset.get("mfm_id")
        # CONFIDENT only when the sub-prompt pinned exactly ONE meter (a real asset, no open picker). A bare-token name
        # that stayed ambiguous on its own → NOT confident → falls through to the single-asset picker (no wrong auto-pin).
        # EXCEPT how='no_data' [dark-member fix, validation r5 telemetry]: a named-but-DARK meter resolved to EXACTLY
        # the named row — the alternatives list it carries is the SINGLE-path picker affordance, not resolution doubt.
        # In a compare the user's pick is already explicit: the dark member JOINS the compare and its lane renders
        # honest-blank (per-leaf degradation) instead of the whole compare silently single-pinning the first name.
        if how in _CONFIDENT_HOW and mfm_id is not None and (not has_picker or how == "no_data"):
            if mfm_id not in seen:
                seen.add(mfm_id)
                confident.append(mfm_id)
        else:
            ambiguous.append(r[1])
        resolutions.append({"name": r[1], "how": how, "mfm_id": mfm_id, "picker": has_picker})
    return {"confident": confident, "ambiguous": ambiguous, "resolutions": resolutions}
