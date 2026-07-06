"""layer1a/parse/page_key_fallback.py — FAIL-CLOSED page_key resolution.

Returns (resolved_key_or_None, how) where how ∈ {'verbatim','segment','substring','missing','ambiguous','no_match'}.
A partial/truncated model answer is recovered ONLY when it maps to exactly ONE candidate:
  · 'segment'   — it equals the tail segment after '/' of exactly one key (never flips the shell silently).
  · 'substring' — it is a substring of exactly one key.
Ambiguity across shells (e.g. a bare 'voltage-current' matching the DG, feeder AND panel pages) or no match returns
(None, ...) so the caller FAILS CLOSED instead of silently routing to an arbitrary shell-sorted keys[0].
[hardening: silent keys[0] misroute + wrong-shell substring flip]
"""


def resolve_page_key(pk, keys):
    if pk in keys:
        return pk, "verbatim"
    if not pk:
        return None, "missing"
    p = str(pk).strip().lower()
    seg = [k for k in keys if k.lower().rsplit("/", 1)[-1] == p]
    if len(seg) == 1:
        return seg[0], "segment"
    sub = [k for k in keys if p in k.lower()]
    if len(sub) == 1:
        return sub[0], "substring"
    return None, ("ambiguous" if (seg or sub) else "no_match")
