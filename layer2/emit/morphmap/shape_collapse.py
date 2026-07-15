"""layer2/emit/morphmap/shape_collapse.py — collapse the shown skeleton's DATA tier to live-fill markers
[emit diet Stage 2, forensics 2026-07-15].

THE Mechanism-A root cause: the METADATA SHAPE block showed morph-map cards their stored skeleton VERBATIM —
including the zero-filled DATA grids (card 24's `timeline.periods[*].panels[*]` harmonic matrix, 3.5K chars of
`{"h3":0.0,…}` objects). The model copied AND EXPANDED that temptation into `morphs` (obs row 4485: 14,614 completion
tokens, 89% zero-filled grid) — pure fabricated-data retype the producer rejects anyway (tokens/latency/timeout are
the only effect). Prohibition text alone was demonstrably ignored; this removes the temptation at the source: every
DATA-tier subtree (dp.data_paths — the same classification the morph producer's reject guard uses) is replaced by ONE
ASCII marker naming its element count, so the shown shape stays honest ("there are N slots here, the executor fills
them") with nothing to copy. Morph-map cards only — a full-author (no-skeleton) card must still see typed
placeholders to copy byte-identically. [atomic; generic — zero card ids]"""
import copy

from layer2.emit.metadata.producer import _get, _has, _set


def _marker(value):
    n = len(value) if isinstance(value, (list, dict)) else 1
    return f"<<DATA: {n} element(s), filled LIVE by the executor - NEVER a morph, never re-typed>>"


def collapse_data_tier(skeleton, data_paths):
    """A DEEP COPY of `skeleton` with every subtree addressed by `data_paths` replaced by its live-fill marker.
    Parents collapse first (shortest path wins); a path whose ancestor already collapsed is skipped. A path absent
    from the skeleton is skipped (never raises — the shown shape must always compose). The input skeleton is NEVER
    mutated (it is the cached card_payloads row)."""
    out = copy.deepcopy(skeleton)
    for p in sorted({str(p) for p in (data_paths or []) if p}, key=len):
        try:
            if not _has(out, p):
                continue
            _set(out, p, _marker(_get(out, p)))
        except Exception:
            continue
    return out
