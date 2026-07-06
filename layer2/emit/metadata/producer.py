"""layer2/emit/metadata/producer.py — author exact_metadata = the harvested byte-identical DEFAULTS + the AI's
declared MORPHS overlaid. Non-morphed leaves are the default VERBATIM (the §B4 byte-identical invariant, guaranteed
by construction). The AI DECIDES the morphs; this deterministic producer does the copy+overlay labour. [skeleton metadata_producer.py, SIGNATURES author_exact_metadata]"""
import copy
import re

from layer2.emit.metadata.split import split, DATA_SLOT

_SEG = re.compile(r"([^.\[\]]+)|\[(\d+)\]")


def _segs(path):
    return [int(b) if b else a for a, b in _SEG.findall(path)]


def _get(o, path):
    cur = o
    for s in _segs(path):
        cur = cur[s]
    return cur


def _has(o, path):
    cur = o
    for s in _segs(path):
        try:
            cur = cur[s]
        except (KeyError, IndexError, TypeError):
            return False
    return True


def _set(o, path, val):
    segs = _segs(path)
    cur = o
    for s in segs[:-1]:
        cur = cur[s]
    cur[segs[-1]] = val


def _metadata_default(default_payload, stored):
    """The default payload as the pure METADATA tier (exact_metadata's base): every DATA leaf reset to a TYPED
    placeholder (scalar→0, array/series→[]) + fabricated narrative scrubbed. This is the STORED, inspectable DB
    skeleton (card_payloads.payload_stripped, built by scripts/build_stripped_payloads.py) — the SINGLE source of
    truth. It is returned verbatim (deep-copied: callers mutate the base). NO on-the-fly strip fallback: 155/155 rows
    are built, so a NULL here means the builder was never run for this card — that is a HARD error, not something to
    silently re-strip at request time (a silent per-run strip would hide a missing row and drift from the certified
    seedless column). Run scripts/build_stripped_payloads.py."""
    if stored is None:
        raise ValueError(
            "card_payloads.payload_stripped is NULL for this card — the stored seedless skeleton is missing. "
            "Runtime stripping has been retired; run scripts/build_stripped_payloads.py to build the row.")
    return copy.deepcopy(stored)


def metadata_reference(default_payload, stored):
    """The STRIPPED default (data leaves → typed placeholders) — the correct byte-identity REFERENCE for the gate +
    enforce. exact_metadata is built from THIS, so the gate must compare against it, not the raw seed-bearing default;
    otherwise a stripped data leaf (0/[]) reads as a byte-identity 'violation' and gets reverted to the seed.
    `stored` = the pre-built card_payloads.payload_stripped row (REQUIRED — NULL raises, see _metadata_default)."""
    return _metadata_default(default_payload, stored)


def _leaf_paths(node, prefix=""):
    """Every (dotted/indexed leaf path, value) in a nested dict/list — the diff walker for undeclared_morphs."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _leaf_paths(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _leaf_paths(v, f"{prefix}[{i}]")
    else:
        yield prefix, node


def undeclared_morphs(default_payload, ai_exact_metadata, morphed, stored, cap=40):
    """TELEMETRY ONLY [A1 _morphed contract]: the metadata leaf paths where the AI's authored exact_metadata DIFFERS
    from the stored skeleton default but was NOT declared in `_morphed` — i.e. authored changes produce() silently
    reverts (the 2-of-6812 compliance finding). NO auto-promote: this diff never ships a value, it only makes the
    silent no-op VISIBLE (sweeps count it; the prompt now says _morphed is REQUIRED). DATA-tier paths are excluded
    (re-filled data leaves are the known strip-guard behavior, not a morph); `_`-prefixed keys skipped. Capped list
    (default 40 paths) so telemetry never bloats the output. Never raises."""
    try:
        from validate.leaf_classify import classify
        data_paths = {d["path"] for d in (classify(default_payload).get("data_leaves") or [])}
        base = _metadata_default(default_payload, stored)
        declared = set(morphed or [])
        out = []
        for path, val in _leaf_paths(ai_exact_metadata or {}):
            if len(out) >= cap:
                break
            if not path or path.split(".")[0].startswith("_") or path in declared:
                continue
            if path in data_paths or any(dp == path or dp.startswith(path + ".") or dp.startswith(path + "[")
                                         or path.startswith(dp + ".") or path.startswith(dp + "[")
                                         for dp in data_paths):
                continue
            if _has(base, path) and _get(base, path) != val:
                out.append(path)
        return out
    except Exception:
        return []


def produce(default_payload, ai_exact_metadata, morphed, stored):
    """Return (exact_metadata, applied[], rejected[]). exact_metadata = the SOURCE-stripped metadata (data leaves →
    typed placeholders) + valid METADATA morphs only. A morph on a DATA leaf is REJECTED: data never comes from the AI
    or the seed — it fills LIVE from the frame. This is what stops the AI copying a seed number (activePowerAvgKw=389.2)
    straight back onto the stripped placeholder. [strip-at-source is only sound if morphs can't re-add data]"""
    from validate.leaf_classify import classify                  # value-aware data/metadata classifier
    data_paths = {d["path"] for d in (classify(default_payload).get("data_leaves") or [])}
    base = _metadata_default(default_payload, stored)            # the STORED seedless skeleton (single source of truth)
    applied, rejected = [], []
    for path in (morphed or []):
        # SYMMETRIC data guard [family-3 container integrity]: reject a morph ON a data leaf, ABOVE one (an ancestor
        # replace wipes the container), *or BELOW one* (a path INSIDE a data container — series[0].values /
        # sparkline[3].loadPct — re-adds seed data INSIDE the stripped roster, and a wrong-typed value there breaks the
        # FE's structural contract). The container and its elements stay byte-identical-stripped; only true metadata
        # OUTSIDE the data tier is morphable. [strip-at-source is only sound if morphs can't re-add data]
        if path in data_paths or any(dp == path or dp.startswith(path + ".") or dp.startswith(path + "[")
                                     or path.startswith(dp + ".") or path.startswith(dp + "[")
                                     for dp in data_paths):
            rejected.append(f"{path}: DATA leaf — morphs are metadata-only (data fills live from the frame)"); continue
        if not _has(base, path):
            rejected.append(f"{path}: morph path is not a real metadata leaf"); continue
        if not _has(ai_exact_metadata or {}, path):
            rejected.append(f"{path}: declared morphed but no value in exact_metadata"); continue
        val = _get(ai_exact_metadata, path)
        if isinstance(val, str) and any(t in val for t in ("=>", "function(", "React.", "px solid")):
            rejected.append(f"{path}: morph value is chrome ({val!r})"); continue
        _set(base, path, val)
        applied.append(path)
    return base, applied, rejected
