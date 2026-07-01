"""layer1b/resolve/asset_resolve.py — PURE-AI asset resolution: confident pin / ambiguous candidates / empty / pinned.
The AI resolves by NAME, never by registry id: the lt_mfm id is off-by-one from the unit number in the name
('Transformer 6' = id 7), so a model that emits an id reliably mis-pins to an adjacent sibling (and crosses class,
e.g. DG-08 -> RTCC Panel). We hide the id column from the model and map its VERBATIM name back to the registry row
deterministically (exact, then space/punctuation/case-insensitive), so the readable name is authoritative and the id
is looked up, never guessed. [spec section 2 L1b, #14; batch root-cause: asset_name_mismatch (11/66)]"""
import os
import re

from llm.client import call_qwen
from layer1b.resolve.asset_candidates import asset_candidates, as_asset
from layer1b.resolve.no_data_gate import no_data_outcome
from layer1b.resolve.pinned_skip import pinned_skip
from layer1b.resolve.class_from_subject import class_from_subject, candidates_of_class
from layer1b.resolve.confident_pin import confident_pin
from layer1b.resolve.ambiguous_candidates import ambiguous_candidates

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_prompt(name):
    with open(os.path.join(_HERE, "prompts", name)) as f:
        return f.read()


def _norm(s):
    """space/punctuation/case-insensitive match key: 'PCC Panel 2 A' == 'pcc panel 2a' == 'PCC-Panel-2A'."""
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


def resolve_asset(prompt, asset_id_override=None):
    cands = asset_candidates()
    by_id = {str(c[0]): c for c in cands}

    # PIPELINE_ASSET_ID round-trip: the user already picked -> skip resolution (delegated to pinned_skip: honors the
    # exact pin, no de-dup, but still runs the no_data gate so an empty pick surfaces NO-DATA not a blank card). [#14]
    pinned = pinned_skip(asset_id_override, by_id)
    if pinned is not None:
        return pinned

    # CLASS PRIOR: infer the equipment class from the prompt subject/metric and narrow the listing shown to the AI, so
    # a bare/implied class with no unit number is resolved within the right class instead of across all 310 rows. The
    # prior only NARROWS (fail-open to the full list) — it never drops the real answer. [RN-06 class-from-concept]
    prior = class_from_subject(prompt)
    listed = candidates_of_class(cands, prior)

    # NAME -> registry row (deterministic). by_norm carries ALL rows for a normalized key, so a name that collides
    # across rows surfaces as ambiguous rather than an arbitrary pick. Resolution maps against the FULL registry (not
    # just the class-narrowed listing) so a verbatim name the AI copies always maps back even if the prior mis-narrowed.
    by_name = {c[1]: c for c in cands}
    by_norm = {}
    for c in cands:
        by_norm.setdefault(_norm(c[1]), []).append(c)

    def resolve_name(name):
        if name in by_name:                                            # exact verbatim copy
            return by_name[name]
        rows = by_norm.get(_norm(name))                                # space/punct/case-insensitive
        return rows[0] if rows and len(rows) == 1 else None            # unique-or-None (collisions -> ambiguous)

    # listing has NO id column: the model must reason over name/class/load_group only, never registry ids. The
    # NO-DATA flag marks empty/never-wired meters: the model should PREFER data-bearing assets and only resolve to a
    # NO-DATA one when the prompt explicitly names it (we then return the no_data outcome).
    listing = "\n".join(
        f"{c[1]}\t{c[5]}\t{c[4]}\t{'NO-DATA' if not c[6] else ''}" for c in listed
    )
    system = _load_prompt("asset_system.md")
    user = (f"CANDIDATES (name<TAB>class<TAB>load_group<TAB>flag):\n{listing}\n\n"
            f"PROMPT: {prompt!r}\nASSET MENTION: {prompt!r}\nJSON:")
    res = call_qwen(system, user, timeout=60) or {}

    confident = res.get("confident", True)
    picks = [r for r in (resolve_name(n) for n in res.get("names", [])) if r]
    cand_rows = [r for r in (resolve_name(n) for n in res.get("candidates", [])) if r]

    if confident and picks:                                          # asked asset resolved...
        # confident_pin applies prefer-populated device de-dup: DG-01 pinned to the empty gic_28_*_jk twin re-points to
        # the populated dg_1_mfm sibling of the SAME physical device (keyed by name identity, resolved by table). [DS-09]
        asset = confident_pin(picks[0], cands)
        return no_data_outcome(asset) or {"asset": asset, "how": "AI", "candidates": []}   # ...has data? render. else NO-DATA outcome.
    if confident and not picks and not cand_rows:
        return {"asset": None, "how": "empty", "candidates": []}      # pure metric prompt, no asset
    crows = cand_rows or picks
    if not crows:
        crows = [c for c in cands if c[6]] or cands                   # AI gave nothing -> surface DATA-bearing meters
    # ambiguous_candidates de-dups by registry id AND by physical-device identity (prefer-populated), so the picker
    # never offers both DG-01 twins — only the populated one. [RN-06, DS-09]
    return ambiguous_candidates(crows, cands)
