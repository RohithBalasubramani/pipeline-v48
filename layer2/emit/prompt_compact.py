"""layer2/emit/prompt_compact.py — the OVERSIZED-PROMPT compaction engine [monoliths F9, 2026-07-12].

Extracted from user_message.py (prompt assembly is one concern; the c24 oversize rebuild engine is another with its
own DB-knob family). DB-config, generic (NO card ids) [db/seed_emit_coherence.sql]:
  emit.prompt_char_budget       — user-message char budget (0 = off). Over it, the message is REBUILT compacted:
  emit.oversize_array_exemplars — skeleton arrays longer than this show only their first K elements + a marker
                                  (the AI authors the visible exemplars; omitted tail ships byte-identical defaults
                                  via enforce_exact_metadata — nothing is lost, nothing fabricated);
  emit.oversize_basket_cap      — DB SCHEMA lines cap (rank order kept; a '+N more' trailer says the rest exist);
  emit.oversize_sibling_exemplars — sibling per-element slot lines (panels[0..9].kw) collapse to K exemplars + ONE
                                  summary line per [*] group (the shape is identical; binding stays per-element).
[atomic; honesty-preserving — the compacted message announces itself in its own header]"""


def _compact_arrays(node, keep):
    """The skeleton with every list longer than `keep` truncated to its first `keep` elements + ONE marker string.
    Display-only: the AI is told the omitted tail ships as byte-identical defaults (enforce_exact_metadata restores
    any array whose shape drifted), so the compaction can never fabricate or lose a rendered default."""
    if isinstance(node, dict):
        return {k: _compact_arrays(v, keep) for k, v in node.items()}
    if isinstance(node, list):
        if len(node) > keep:
            return [_compact_arrays(v, keep) for v in node[:keep]] + [
                f"… +{len(node) - keep} more identical-shape elements (byte-identical defaults — do NOT author them; "
                f"they ship as defaults / are rebuilt live)"]
        return [_compact_arrays(v, keep) for v in node]
    return node


def _compact_catalog(catalog, keep):
    """(kept_entries, summary_lines) — collapse sibling per-element slot lines (…panels[0].kw / …panels[1].kw / …)
    to the first `keep` exemplars per [*]-normalized group + ONE summary line naming the omitted index range. The
    contract is unchanged: the omitted slots are STILL real, bindable leaf paths (one field per element index) — only
    their near-identical prompt lines are folded (the card-77 lesson: never HIDE slots silently; the summary line
    keeps them named)."""
    import re as _re
    star = _re.compile(r"\[\d+\]")
    kept, counts, first_idx = [], {}, {}
    for e in catalog:
        norm = star.sub("[*]", str(e.get("slot")))
        n = counts.get(norm, 0)
        counts[norm] = n + 1
        if norm != str(e.get("slot")) and n == 0:
            first_idx[norm] = str(e.get("slot"))
        if n < keep or norm == str(e.get("slot")):
            kept.append(e)
    summaries = []
    for norm, n in counts.items():
        if n > keep and norm != first_idx.get(norm, norm):
            summaries.append(f"  slot={norm}  — ×{n} sibling elements total; only the first {keep} lines are shown "
                             f"(prompt budget). The OTHER indices are REAL fillable slots with the SAME shape: bind "
                             f"each element path [i].<key> the same way (its OWN member/phase column) — or leave them "
                             f"to the roster when this card is roster-served. NEVER invent a different token.")
    return kept, summaries


def maybe_compact(build_fn, card_in):
    """build_fn(card_in) — rebuilt with build_fn(card_in, oversize=True) when the plain message exceeds the
    emit.prompt_char_budget knob AND the compacted rebuild is actually smaller. The knob at 0/absent = off."""
    from config.app_config import cfg as _cfg
    msg = build_fn(card_in)
    budget = int(_cfg("emit.prompt_char_budget", 36000) or 0)
    if budget and len(msg) > budget:
        compacted = build_fn(card_in, oversize=True)
        if len(compacted) < len(msg):
            return compacted
    return msg
