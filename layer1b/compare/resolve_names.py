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

from run.parallel import run_parallel
from layer1b.resolve.asset_resolve import resolve_asset
from layer1b.compare.discriminators import _discriminators, _norm
from layer1b.compare.detect import named_full_rows

# a confident single resolution: an asset was pinned by NAME (or named-but-empty no_data) with NO open picker list.
# collision_gate_fullname = the deterministic full-name pin (user spelled one colliding row out in full) — also a
# confident single resolution (a pin with no picker), so a compare sub-prompt that full-name-pins keeps its pin.
_CONFIDENT_HOW = {"AI", "user-choice", "no_data", "collision_gate_fullname"}


def _span_regex(name):
    """A tolerant regex matching THIS asset's name / GIC-node prefix in the ORIGINAL (un-normalized) prompt, so the
    OTHER names can be stripped out to isolate one asset per sub-prompt. Built from the same discriminators used to
    detect the full-name mention: the whole registry name and the 'GIC-01-N3' node prefix. Punctuation/space/case
    insensitive (each gap → `[-_ ]*`). None when the name yields no usable discriminator."""
    pats = []
    for src in (name, _gic_prefix(name)):
        if not src:
            continue
        toks = [t for t in re.split(r"[^a-z0-9]+", str(src).lower()) if t]
        if toks:
            pats.append(r"[-_ ]*".join(re.escape(t) for t in toks))
    if not pats:
        return None
    return re.compile("(" + "|".join(sorted(pats, key=len, reverse=True)) + ")", re.IGNORECASE)


def _gic_prefix(name):
    m = re.match(r"\s*(gic[-_ ]?\d+[-_ ]?n\d+)", str(name or "").lower())
    return m.group(1) if m else None


def _sub_prompt(prompt, keep_row, other_rows):
    """The original prompt with the OTHER assets' names removed, keeping only `keep_row`'s asset name — so resolve_asset
    sees ONE specific asset (the AI's confident-pin then fires on that single name). The compare conjunctions left
    behind ('and', 'vs') are harmless to the resolver; the kept name stays verbatim so the model resolves it cleanly."""
    out = prompt
    for r in other_rows:
        rx = _span_regex(r[1])
        if rx:
            out = rx.sub(" ", out)
    out = re.sub(r"\s+", " ", out).strip()
    return out or prompt


def resolve_compare(prompt, cands=None):
    """Resolve every fully-named asset in a natural-compare prompt through resolve_asset, concurrently. Returns
    {confident, ambiguous, resolutions}: `confident` = mfm_ids that resolved to exactly one meter (dedup, order kept);
    `ambiguous` = names that stayed a picker on their own sub-prompt. The caller routes to the multi-asset compare only
    when len(confident) >= 2 (and no name went ambiguous — every named asset must pin, or the picker is the honest answer)."""
    rows = named_full_rows(prompt, cands)
    if len(rows) < 2:
        return {"confident": [], "ambiguous": [], "resolutions": []}

    thunks = {}
    for i, r in enumerate(rows):
        others = [o for o in rows if o[0] != r[0]]
        sub = _sub_prompt(prompt, r, others)
        thunks[i] = (lambda p=sub: resolve_asset(p))

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
        if how in _CONFIDENT_HOW and mfm_id is not None and not has_picker:
            if mfm_id not in seen:
                seen.add(mfm_id)
                confident.append(mfm_id)
        else:
            ambiguous.append(r[1])
        resolutions.append({"name": r[1], "how": how, "mfm_id": mfm_id, "picker": has_picker})
    return {"confident": confident, "ambiguous": ambiguous, "resolutions": resolutions}
