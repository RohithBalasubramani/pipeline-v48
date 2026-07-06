"""layer1a/catalog_compress.py — merge a page's purpose/theme/answers into ONE deduplicated story line for the router
catalog. [AI_QUALITY_BACKLOG item 21 / D5]

WHY: the PAGES block restated every page three times (purpose+theme+answers = ~10.4K of the 14.7K-char user message,
x27 router calls per sweep). The three DB fields are prose RESTATEMENTS of the same story, so the catalog carries the
UNION of their content words once, not three paraphrases of it.

HOW (generic, page-agnostic — no per-page rules): split each field into clauses, keep a clause only when it still ADDS
content tokens the page's kept story doesn't already carry. Field order theme -> answers -> purpose (compact framing
first, then the question keywords, then the longest/most-redundant field, which mostly dedups away). Granularity
keywords the routing rules key on (panel / feeder / single-generator / battery / fuel ...) appear in their FIRST
clause, which is always kept — recall is untouched (proven by tests/test_item21_catalog_compress.py against the
near-tie examples in layer1a/prompts/system.md).

DB knobs (cmd_catalog.app_config, code-default fallback — edit a row, no code change):
    route.story_min_new_tokens  (int, 4)     — clause kept when it adds >= this many unseen content tokens ...
    route.story_min_new_ratio   (number, 0.6) — ... AND >= this fraction of its content tokens is unseen (paraphrase
                                                clauses share few EXACT tokens; the ratio is what catches restatements)
    route.story_max_chars       (int, 320)   — per-page story cap, cut at a clause boundary (0 = uncapped). Theme +
                                               leading answer clauses fit; the cut tail is purpose restatement. The
                                               class-concern keywords (battery/fuel/engine/tap/thermal ...) also live
                                               VERBATIM in the page title, so a cap never erases them from the catalog.
"""
import re

from config.app_config import cfg

# grammar/glue words that never decide a route — clause NOVELTY is measured on the remaining content tokens
_STOP = frozenset(
    "a an and the of for to in into on with over across under between against versus vs is are was were be been "
    "how what which when where who whose why this that these those its it their our your one two three per each "
    "every by from at or as do does did done not no so than then there here now also both all any some more most "
    "other same own new via out up down off can could should would may might will just only ever never".split()
)

_LIST_MARK = re.compile(r"^[\s\-–—•·*]*(\(\d+\)|\d+[.)])?\s*")   # leading '- ' / '(1) ' / '2.' list markers
_CLAUSE_SPLIT = re.compile(r"(?<=[.?!;])\s+|\s+—\s+|\n+")        # sentence / em-dash / line boundaries
_WORD = re.compile(r"[a-z0-9][a-z0-9\-/]+")


def _clauses(text):
    """Sentence-level clauses with list markers / wrapping quotes stripped (the DB prose uses '- ' bullets and
    numbered '(1)' answer lists)."""
    out = []
    for part in _CLAUSE_SPLIT.split(text or ""):
        part = _LIST_MARK.sub("", part).strip().strip('"“”').strip()
        part = part.rstrip(".;,")
        if part:
            out.append(part)
    return out


def _tokens(clause):
    return {w for w in _WORD.findall(clause.lower()) if w not in _STOP}


def merge_story(purpose, theme, answers, *, min_new_tokens=None, min_new_ratio=None, max_chars=None):
    """ONE '; '-joined story line carrying the deduplicated content of theme+answers+purpose. Deterministic; never
    raises; '' when all three fields are empty."""
    min_new = int(min_new_tokens if min_new_tokens is not None else cfg("route.story_min_new_tokens", 4))
    ratio = float(min_new_ratio if min_new_ratio is not None else cfg("route.story_min_new_ratio", 0.6))
    cap = int(max_chars if max_chars is not None else cfg("route.story_max_chars", 320))
    seen, kept = set(), []
    for field in (theme, answers, purpose):
        for clause in _clauses(field):
            toks = _tokens(clause)
            fresh = toks - seen
            # keep when the clause ADDS content (enough NEW tokens, and mostly-new — a paraphrase re-mixes seen words)
            # — or unconditionally for the very first clause (never an empty story)
            if (toks and not kept) or (len(fresh) >= max(1, min_new)
                                       and len(fresh) / max(1, len(toks)) >= ratio):
                kept.append(clause)
                seen |= toks
    story = "; ".join(kept)
    if cap > 0 and len(story) > cap:
        acc, n = [], 0
        for clause in kept:
            if acc and n + len(clause) + 2 > cap:
                break
            acc.append(clause)
            n += len(clause) + 2
        story = "; ".join(acc)
    return story
