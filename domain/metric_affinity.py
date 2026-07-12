"""domain/metric_affinity.py — the ONE generic metric-affinity vocabulary/score, shared by the swap POOL builder
(layer2/swap/candidates: soft re-rank before truncation) and the swap SETTLE post-pass (grounding/swap_settle:
deterministic replay re-rank). Home moved out of layer2/swap/candidates so grounding never imports a layer —
the swap_settle↔candidates lazy-import cycle is dead. [cycle-kill 2026-07-12]

Generic — no per-metric list: works for any metric word ('voltage','current','energy','thd',…) or phrase.
The minimum-token-length knob is read PER CALL (lazy, campaign style) so a DB knob edit needs no restart."""
import re

from config.app_config import cfg


def _min_token_len():
    """minimum affinity-token length — drop 1-2 char noise ('pf' is a real metric so keep len>=2). Editable knob."""
    return int(cfg("swap.affinity_min_token_len", 2))


def metric_tokens(metric):
    """GENERIC affinity vocabulary from the pipeline's 1a metric: lowercased alnum tokens of the metric string
    (len >= knob), deduped. None/blank/too-short → () → pure-size behavior (fully backward-compatible)."""
    if not metric:
        return ()
    min_len = _min_token_len()
    toks = [t for t in re.split(r"[^a-z0-9]+", str(metric).lower()) if len(t) >= min_len]
    return tuple(dict.fromkeys(toks))            # dedupe, preserve order


def affinity(cand, tokens):
    """SOFT metric-relevance score of a swap candidate: the count of metric tokens that appear (substring,
    case-insensitive) anywhere in the card's catalog text (title / analytical_role / card_purpose / visualization).
    0 = off-metric (deprioritized, NEVER dropped). Generic — the same computation for every metric and every card."""
    if not tokens:
        return 0
    text = " ".join(str(cand.get(k) or "") for k in
                    ("title", "analytical_role", "card_purpose", "visualization")).lower()
    return sum(1 for t in tokens if t in text)
