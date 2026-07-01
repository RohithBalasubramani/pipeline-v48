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


def _metadata_default(default_payload):
    """The default payload with DATA leaves dropped — the pure METADATA tier (exact_metadata's base)."""
    skel, _ = split(default_payload)

    def prune(o):
        if isinstance(o, dict):
            return {k: prune(v) for k, v in o.items() if v != DATA_SLOT}
        if isinstance(o, list):
            return [prune(v) for v in o]
        return o
    return prune(skel)


def produce(default_payload, ai_exact_metadata, morphed):
    """Return (exact_metadata, applied[], rejected[]). exact_metadata = defaults + valid AI morphs."""
    base = _metadata_default(default_payload)
    applied, rejected = [], []
    for path in (morphed or []):
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
