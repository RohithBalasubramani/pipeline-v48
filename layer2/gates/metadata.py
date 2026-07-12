"""layer2/gates/metadata.py — the exact_metadata BYTE-IDENTITY gate + ENFORCE + the no-default scrub. The
byte-identity gate is LOAD-BEARING [META-02]: `enforce_exact_metadata` REVERTS any leaf the AI changed without
declaring it in `morphed` (or that leaked chrome) back to its byte-identical default, so the resting render is
GUARANTEED byte-identical to the harvested ground truth. [PROMPTS §L2 gates 2/3]"""
import copy
from layer2.emit.metadata.split import split, DATA_SLOT
from config.app_config import cfg


# Tunable vocab of design-system "chrome" markers — a morphed value containing any of these is rejected as leaked
# chrome. DB-editable as gates.chrome_markers (json). Read lazily per call (NOT at import) so app_config.reload()
# and a late-arriving DB both take effect — the import-time read pinned the code default for the process life.
_CHROME_DEFAULT = ["=>", "function(", "function (", "React.", "onClick", "px solid", "rgba("]


def _chrome_markers():
    return cfg("gates.chrome_markers", _CHROME_DEFAULT)


def _is_chrome(v):
    return isinstance(v, str) and any(t in v for t in _chrome_markers())


def gate_exact_metadata(exact_metadata, default_payload, morphed=None):
    """Every metadata leaf present + byte-identical to the default (unless declared in `morphed`); no data leaf, no chrome."""
    morphed = set(morphed or [])
    skeleton, _data_paths = split(default_payload)
    issues = []

    def walk(skel, got, path):
        if skel == DATA_SLOT:                                   # a DATA leaf must NOT be authored as metadata
            if got is not None:
                issues.append(f"{path}: DATA leaf authored in exact_metadata (belongs to data_instructions)")
            return
        if isinstance(skel, dict):
            if not isinstance(got, dict):
                issues.append(f"{path}: missing metadata object"); return
            for k, v in skel.items():
                walk(v, got.get(k), f"{path}.{k}" if path else k)
            for k in got:
                if k not in skel:
                    issues.append(f"{path}.{k}: invented metadata key (not in default shape)")
            return
        if isinstance(skel, list):
            if not isinstance(got, list) or len(got) != len(skel):
                issues.append(f"{path}: metadata array shape changed"); return
            for i, v in enumerate(skel):
                walk(v, got[i], f"{path}[{i}]")
            return
        # leaf — a byte-identical default is GROUND TRUTH (OK even if it is a default rgba()/hex colour the harvested
        # payload legitimately ships, e.g. a radar polygonFill or a legend colour). Only a CHANGED value is policed: an
        # undeclared change is a byte-identity violation; a declared morph must not INTRODUCE chrome.
        if got == skel:
            return
        if path not in morphed:
            issues.append(f"{path}: byte-identical-default violation (got {got!r}, default {skel!r})")
        elif _is_chrome(got):
            issues.append(f"{path}: design-system chrome leaked into a morphed value ({got!r})")

    walk(skeleton, exact_metadata, "")
    return (not issues), issues


def enforce_exact_metadata(exact_metadata, default_payload, morphed=None):
    """LOAD-BEARING byte-identity enforcement [META-02]. Walk the default SKELETON and REBUILD a payload where every
    leaf is the byte-identical default UNLESS it was legitimately morphed (declared in `morphed` AND chrome-free). Any
    undeclared change, invented key, shape drift, or chrome-leaking morph is DROPPED (reverted to default). The result
    is guaranteed to pass gate_exact_metadata. Returns (safe_exact_metadata, reverted_paths[]).

    This never fabricates: it only ever restores the harvested ground-truth default; a genuinely story-driven, chrome-
    free, declared morph survives verbatim."""
    morphed = set(morphed or [])
    skeleton, _data_paths = split(default_payload)
    reverted = []

    def rebuild(skel, got, path):
        if skel == DATA_SLOT:
            return None                                         # DATA leaf stays elided (filled live on the frontend)
        if isinstance(skel, dict):
            g = got if isinstance(got, dict) else {}
            return {k: rebuild(v, g.get(k), f"{path}.{k}" if path else k) for k, v in skel.items()}
        if isinstance(skel, list):
            if not isinstance(got, list) or len(got) != len(skel):
                if isinstance(got, list) and got != skel:
                    reverted.append(path)                       # array shape drift → revert whole array to default
                return copy.deepcopy(skel)
            return [rebuild(v, got[i], f"{path}[{i}]") for i, v in enumerate(skel)]
        # leaf
        if got == skel:
            return skel                                         # byte-identical (ground truth) — keep
        if path in morphed and not _is_chrome(got):
            return got                                          # legitimate declared, chrome-free morph — keep
        reverted.append(path)                                   # undeclared change / chrome leak → revert to default
        return skel

    safe = rebuild(skeleton, exact_metadata, "")
    return safe, reverted


def enforce_free_metadata(ai_exact_metadata):
    """NO-DEFAULT enforce [folded scrub]. A card with NO harvested card_payloads row (no stored payload_stripped) has
    the AI author exact_metadata off the seed-bearing contract payload_schema_json — so its data leaves ('540.9 kW')
    and clock labels ('13:14:10') would ship verbatim. There is NO stored seedless skeleton to revert against, so
    gate_exact_metadata/enforce_exact_metadata (which need a default ref) cannot cover this case. This is the ONE
    check that path needs: data leaves → typed placeholders (leaf_classify) + narrative/clock/provenance scrubbed.
    It REUSES the canonical strip worker (grounding.default_assemble._strip_and_scrub) — the SAME transform the build
    script persists — so there is no second strip implementation and no runtime strip_to_placeholders caller. Chrome
    (labels/booleans/colors) is untouched; never raises."""
    if not isinstance(ai_exact_metadata, (dict, list)):
        return ai_exact_metadata
    try:
        from grounding.default_assemble import _strip_and_scrub   # shared worker (build script owns strip_to_placeholders)
        return _strip_and_scrub(ai_exact_metadata)
    except Exception:
        return ai_exact_metadata
