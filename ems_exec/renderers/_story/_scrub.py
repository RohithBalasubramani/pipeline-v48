"""ems_exec/renderers/_story/_scrub.py — the DETERMINISTIC anti-fabrication post-check for the RTM/feeder AI-summary.

The narrator (_insight) turns a PRE-JUDGED story into one prose sentence. Even with the story's numbers/verdicts already
computed, a free-text model can INVENT a figure the grounded facts deliberately left blank — the card-8 defect was
'GIC-01-N8-BPDB-01 … 217.0 kW (72.0% load)' when the grounded `load_pct` was None (no nameplate rating denominator).
217/0.72 = 301 kVA has NO DB source: it is a fabricated percentage.

This module is the belt to the prompt-guard's braces. Given the SAME grounded story the narrator saw, it strips any
'<n>% load / loading / utilisation' clause the story did NOT ground:
  · a feeder whose grounded load_pct is a real number → its own '<n>% load' survives (real fact, never touched);
  · a feeder (or a whole panel) with NO grounded load_pct → every '% load' phrase is removed and replaced with the
    honest 'load n/a', so a fabricated denominator can never survive to the panel.

Pure prose surgery — never invents a number, never raises. A load %/PF/kW that IS in the grounded facts is preserved
verbatim; only an UNGROUNDED percent-load is dropped. [atomic; honest-degrade; deterministic]
"""
from __future__ import annotations

import re

# a percentage that is asserted as a LOAD/LOADING/UTILISATION figure, in any of the narrator's phrasings:
#   '72.0% load', '72 % loading', 'load of 72%', 'loaded to 72 %', 'utilisation 72%', '72% utilization'
# Each pattern optionally eats a wrapping '(...)' and a trailing ', <severity word>' so the clause is removed cleanly
# (no stranded '(' / ')' or double-comma). The replacement re-wraps in parens when the clause was parenthesised.
_PCT = r"[-+]?\d+(?:\.\d+)?\s*%"
_LOAD_WORD = r"(?:load(?:ing|ed)?|utili[sz]ation|utili[sz]ed)"
_SEV = r"(?:\s*,\s*(?:critical|warning|normal|review|accounting|ok|stable))?"
_PCT_BEFORE = re.compile(                                                       # '(72% load, critical)' / '72% loading'
    r"(?P<lp>\()?\s*(?P<pct>%s)(?:\s+of)?\s+%s%s\s*(?P<rp>\))?" % (_PCT, _LOAD_WORD, _SEV), re.IGNORECASE)
_PCT_AFTER = re.compile(                                                        # 'load of 72%' / 'loaded to 72 %'
    r"(?P<lp>\()?\s*%s(?:\s+(?:of|at|to))?\s+(?P<pct>%s)(?:\s+of\s+(?:capacity|rated|nameplate))?%s\s*(?P<rp>\))?"
    % (_LOAD_WORD, _PCT, _SEV), re.IGNORECASE)
# a leftover, now-empty '(…)' or double punctuation the removal can strand
_EMPTY_PARENS = re.compile(r"\(\s*[,;]?\s*\)")
_DANGLING = re.compile(r"\s+([,.;])")
_SPACE_BEFORE_PAREN = re.compile(r"\(\s+")
_MULTISPACE = re.compile(r"\s{2,}")


def grounded_load_pcts(story):
    """The set of load-% NUMBERS the story actually grounds (leader + single-feeder shapes). A '% load' clause in the
    narrated text is only legitimate if its number is in this set; anything else is a fabricated denominator."""
    out = set()
    if not isinstance(story, dict):
        return out
    for node in (story.get("leading_feeder"), story.get("load")):
        if isinstance(node, dict):
            lp = node.get("load_pct")
            if isinstance(lp, (int, float)) and not isinstance(lp, bool):
                out.add(round(float(lp)))
    return out


def _pct_value(match_text):
    m = re.search(r"[-+]?\d+(?:\.\d+)?", match_text)
    return round(float(m.group())) if m else None


def scrub(text, story):
    """Return `text` with every UNGROUNDED '<n>% load/loading/utilisation' clause removed (replaced by 'load n/a'),
    while any '% load' whose number IS in the grounded facts is kept verbatim. Non-str / no-op → returned unchanged."""
    if not isinstance(text, str) or "%" not in text:
        return text
    allowed = grounded_load_pcts(story)

    def _repl(m):
        val = _pct_value(m.group("pct") or "")
        if val is not None and val in allowed:
            return m.group(0)                       # a real, grounded load % — untouched
        lp, rp = m.group("lp"), m.group("rp")       # re-wrap in parens iff the clause was parenthesised
        return (" (load n/a)" if (lp and rp) else " load n/a ")

    out = _PCT_BEFORE.sub(_repl, text)
    out = _PCT_AFTER.sub(_repl, out)
    out = _EMPTY_PARENS.sub("", out)
    out = _SPACE_BEFORE_PAREN.sub("(", out)
    out = _DANGLING.sub(r"\1", out)
    out = _MULTISPACE.sub(" ", out).strip()
    return out
