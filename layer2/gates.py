"""layer2/gates.py — DETERMINISTIC Layer-2 emit gates. exact_metadata = byte-identical defaults + no chrome (vs the
harvested ground truth); data_instructions = every field a real basket column / const / $ctx. [PROMPTS §L2 gates 2/3]

The byte-identity gate is LOAD-BEARING [META-02]: `enforce_exact_metadata` REVERTS any leaf the AI changed without
declaring it in `morphed` (or that leaked chrome) back to its byte-identical default, so the resting render is
GUARANTEED byte-identical to the harvested ground truth — a non-conforming payload never ships, it self-heals to the
default. [contract POST: ENFORCING byte-identity gate (revert non-conforming to default)]"""
import copy
from layer2.emit.metadata.split import split, DATA_SLOT
from config.app_config import cfg

# Tunable vocab of design-system "chrome" markers — a morphed value containing any of these is rejected as leaked
# chrome. DB-editable as gates.chrome_markers (json) so the deny-list can be tuned without a code change.
_CHROME = cfg("gates.chrome_markers",
              ["=>", "function(", "function (", "React.", "onClick", "px solid", "rgba("])


def _is_chrome(v):
    return isinstance(v, str) and any(t in v for t in _CHROME)


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


def gate_data_instructions(data_instructions, basket, *, is_group_card=False):
    real = {c.get("column") for c in (basket.get("columns") or []) if c.get("column")}
    issues = []
    fields = data_instructions.get("fields") or []
    if not fields:
        issues.append("data_instructions.fields is empty")
    for i, f in enumerate(fields):
        kind, src, col = f.get("kind"), f.get("source"), f.get("column")
        # LITERAL / CHROME fields — a const value or a text label. The literal lives in exact_metadata, NOT a data
        # column; demanding a column here wrongly rejected every "Live Health" status text (source=='const' too).
        # source=='frame' = a fan-out / list-structure field the FRONTEND fills from the live frame (column_override
        # dropped its hallucinated column) — no column to bind here either.
        if kind in ("const", "text") or src in ("const", "frame"):
            if kind == "const" and f.get("value") is None:
                issues.append(f"fields[{i}] kind=const without a value")
            continue
        if src == "$ctx":
            if not is_group_card:
                issues.append(f"fields[{i}] source=$ctx on a non-group card")
            continue
        # DERIVED — computed by a fn (the derivation LIBRARY) over base_columns; it has NO single resolved column.
        # Validate it carries the fn + its base inputs instead of demanding a column.
        if kind == "derived":
            if not f.get("fn"):
                issues.append(f"fields[{i}] kind=derived without fn")
            if not f.get("base_columns"):
                issues.append(f"fields[{i}] kind=derived without base_columns")
            continue
        # DIRECT live/test-db column fields.
        if src not in ("live", "test-db"):
            issues.append(f"fields[{i}] bad source {src!r} (want live|test-db|const|$ctx)")
        if col and col not in real:
            issues.append(f"fields[{i}] column {col!r} not in basket (hallucinated)")
        if not col:
            issues.append(f"fields[{i}] kind={kind} missing a resolved column")
        if kind == "event" and not f.get("edge"):
            issues.append(f"fields[{i}] kind=event without edge")
    return (not issues), issues
