"""run/reflect.py — the reflect-loop helpers: turn Layer-2 answerability GAPS into (a) re-route FEEDBACK for Layer 1a
and (b) a human-readable LOOP-2 note when a re-route still cannot answer. Single concern: gap → words. [degrade-loop]

A card is a GAP when Layer 2 set answerability="none" (no real column — even a substitute — serves its core question).
Loop 1 = re-route 1a with this feedback; Loop 2 = if still gapped, explain why for the user. No fabrication anywhere."""


def _card_titles(l1a):
    return {c["card_id"]: c.get("title") for c in ((l1a or {}).get("cards") or [])}


def asset_supports(l1b):
    """What the asset ACTUALLY measures — has_data column labels — so 1a can pick an answerable template."""
    cols = ((l1b or {}).get("column_basket") or {}).get("columns") or []
    seen, labels = set(), []
    for c in cols:
        if c.get("has_data"):
            lab = c.get("label") or c.get("column")
            if lab and lab not in seen:
                seen.add(lab)
                labels.append(lab)
    return labels


def gap_summary(l1a, gaps):
    """[(title, why)] for the cards Layer 2 could not answer (answerability=none) OR hard-failed (no valid emit —
    the `exception` fallback covers the run_2_all per-card exception envelope, which has no data_note/failure)."""
    titles = _card_titles(l1a)
    return [(titles.get(o.get("card_id"), o.get("card_id")),
             o.get("data_note") or (o.get("failure") or {}).get("reason") or o.get("exception")
             or "no real column serves its data")
            for o in gaps]


def build_feedback(l1a, l1b, gaps):
    """Re-route instruction for Layer 1a: which cards failed + why, and what the asset CAN answer."""
    asset = ((l1b or {}).get("asset") or {}).get("name") or "this asset"
    page = (l1a or {}).get("page_key")
    supports = asset_supports(l1b)
    lines = [f"The template '{page}' has card(s) that CANNOT be answered by {asset}'s data:"]
    lines += [f"  - {t}: {why}" for t, why in gap_summary(l1a, gaps)]
    lines.append(f"{asset} actually measures: {', '.join(supports[:40]) if supports else '(no time-series columns)'}.")
    lines.append("Pick a DIFFERENT template whose cards CAN be answered with those measurements; "
                 "avoid a template centered on the missing quantities above.")
    return "\n".join(lines)


def build_loop2_note(l1a, gaps):
    """User-facing explanation when the re-routed template STILL cannot answer (loop-2 note)."""
    page = (l1a or {}).get("page_key")
    items = "; ".join(f"{t} ({why})" for t, why in gap_summary(l1a, gaps))
    return (f"After re-routing to '{page}', these still cannot be answered from the available data: {items}. "
            f"The requested information isn't recorded for this asset on any available template.")


def build_honest_terminal_note(l1a, gaps):
    """User-facing explanation for the HONEST TERMINAL (reflect.reroute_on='hard_failure'): every emit CONFORMED, the
    gapped cards simply cover quantities this asset does not measure — the routed page is KEPT and those cards render
    their real component with per-leaf honest blanks + the reason. This note replaces the old destructive re-route:
    the words survive, the page discard does not. [per-leaf degradation: honest-blank is a PASS]"""
    page = (l1a or {}).get("page_key")
    items = "; ".join(f"{t} ({why})" for t, why in gap_summary(l1a, gaps))
    return (f"'{page}' answers the prompt as routed; these cards cover quantities not recorded for this asset and "
            f"render honest-blank per-leaf with the reason: {items}.")
