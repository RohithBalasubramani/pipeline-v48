"""Prompt construction for the pure-AI suggestion step.

The model is given the user's partial text + a rich, grounded set of REAL EMS
entities (retrieved by retrieve.py from all the metadata tables) and asked for an
inline autofill + 5 complete query suggestions. It must use only the provided
entities — that is what keeps the suggestions real (no invented assets/metrics).
"""

SYSTEM = (
    "You are an autocomplete copilot for an EMS (Energy Management System) query box — exactly like "
    "Google search autocomplete. The user is typing a request that will generate an EMS dashboard. "
    "Your job is to COMPLETE the query they are typing — never to propose unrelated queries.\n\n"
    "Return STRICT JSON only (no prose, no markdown):\n"
    '{"autofill": "<the user\'s exact text continued into ONE complete query>", '
    '"suggestions": ["<q1>", "<q2>", "<q3>", "<q4>", "<q5>"]}\n\n'
    "Rules:\n"
    "- autofill MUST begin with the user's exact typed CHARACTERS (a character-level prefix). If the typed "
    "text does NOT end with a space, its LAST token is a HALF-TYPED WORD: the VERY NEXT character you output "
    "must be a LETTER that finishes THAT word — never a space, never a new token, until the word is complete.\n"
    "- PARTIAL TRAILING WORD (this is about the LAST word, WHEREVER it sits — first word or after a whole "
    "phrase): complete the half-typed final word into the whole word the operator means, then continue "
    "naturally. Examples: 'wh' => 'what is the active power for PCC Panel 1A' (NOT 'wh what ...'); 'volt' => "
    "'voltage unbalance on PCC Panel 1A' (NOT 'volt unbalance'); 'powe' => 'power factor total for PCC Panel 1A'; "
    "and mid-phrase (fragment is the LAST word after a phrase — THIS is the common case): "
    "'whats the current usage in pcc pane' => 'whats the current usage in pcc panel 1a' (finish 'pane'->'panel'); "
    "'show transformer 1 volt' => 'show transformer 1 voltage ll avg' (finish 'volt'->'voltage'); "
    "'ups batt' => 'ups battery health' (finish 'batt'->'battery'); 'ahu 5 temp' => 'ahu 5 temperature' "
    "(finish 'temp'->'temperature'). The completed word ALREADY contains the fragment, so DO NOT re-type the "
    "fragment before it — WRONG: 'transformer 1 volt voltage ll avg' (doubled 'volt'+'voltage'), 'ups batt "
    "battery health' (doubled 'batt'+'battery'), 'pcc pane 1a' (unfinished). NO split ('volt age'). "
    "Only AFTER a trailing space may you begin a brand-new token.\n"
    "- LEADING INTENT / QUESTION WORDS are half-typed words too — complete them exactly the same way, NEVER echo "
    "the raw fragment: 'compar' => 'compare <asset A> and <asset B> <metric>' (finish 'compar'->'compare'; NOT "
    "'compar power ...'); 'compare' => keep 'compare ...'; 'wha'/'wht' => 'what is the ...'; 'why' => 'why is "
    "the ...'; 'ho'/'hw' => 'how much ...'; 'sho'/'shw' => 'show ...'; 'lis' => 'list ...'; 'vs' after one asset "
    "=> 'compare'. The bare fragment ('compar', 'wha', 'sho') must NEVER appear followed by a space in autofill "
    "OR in any suggestion — always the FINISHED word.\n"
    "- EVERY suggestion must CONTINUE or REFINE what the user has already typed — keep their exact "
    "wording, their asset(s), and their intent, and only complete the thought: add the metric, a time "
    "window, a phase/scope, or a close variation. Each suggestion must START WITH the user's typed text "
    "AFTER finishing its half-typed final word — the SAME completion rule as autofill (typed 'compar' => "
    "every suggestion begins 'compare …', NEVER 'compar …'; typed 'volt' => begins 'voltage …', NEVER "
    "'volt …'). Never echo the raw half-typed fragment followed by a space. Do NOT switch to a different "
    "intent, a different metric family, or an unrelated question.\n"
    "- Honor the intent already present in the text: 'real-time / live / now / monitor / monitoring' => a "
    "live snapshot, NO historical window (never add 'last 7 days'/'this week' to a real-time request); "
    "'trend / history / over time' => add a time window; 'compare' => two named assets of the same kind.\n"
    "- Use ONLY the asset names, metrics and time ranges provided below; never invent assets/metrics/panels.\n"
    "- Keep each query short and operator-like.\n"
    "Example: typed 'real time monitoring for PCC Panel 1A' -> good = 'real time monitoring for PCC Panel 1A "
    "current and load', 'real time monitoring for PCC Panel 1A voltage and unbalance', 'real time monitoring "
    "for PCC Panel 1A power factor'; BAD = 'compare ...', 'voltage deviation ... last 7 days', a yes/no question."
)


def build_user(text, g):
    """Rich grounding drawn from all the EMS metadata tables (assets, metrics with
    units, relevant cards with what they answer + their real metric sets, relevant
    dashboards with objective, exemplar questions, real time ranges)."""
    L = [f'USER IS TYPING: "{text}"', "",
         "Ground every suggestion in these real EMS entities:"]

    if g.get("assets"):
        L.append("\nASSETS (real meters/panels — use these exact names):")
        for a in g["assets"][:12]:
            cls = a.get("class") or ""
            grp = a.get("area") or ""
            tag = " · ".join(x for x in [cls, grp] if x)
            L.append(f"- {a['display']}" + (f"  [{tag}]" if tag else ""))

    if g.get("metrics"):
        L.append("\nMETRICS (meaningful, ranked by how widely the EMS uses them):")
        for m in g["metrics"][:12]:
            u = f" ({m['unit']})" if m.get("unit") else ""
            L.append(f"- {m['display']}{u}")

    if g.get("times"):
        L.append("\nTIME RANGES: " + ", ".join(t["display"] for t in g["times"][:8]))

    if g.get("areas"):
        L.append("\nDASHBOARD AREAS: " + ", ".join(a["display"] for a in g["areas"][:5]))

    if g.get("pages"):
        L.append("\nRELEVANT DASHBOARDS:")
        for p in g["pages"][:5]:
            pl = p.get("payload") or {}
            obj = (pl.get("objective") or "")[:160]
            arch = pl.get("archetype", "")
            L.append(f"- {p['display']}" + (f" [{arch}]" if arch else "") + (f": {obj}" if obj else ""))

    if g.get("cards"):
        L.append("\nRELEVANT CARDS (what each answers + the metrics it shows):")
        for c in g["cards"][:8]:
            pl = c.get("payload") or {}
            q = (pl.get("question") or "")[:130]
            mets = ", ".join(pl.get("metrics", [])[:6])
            line = f"- {c['display']}"
            if q:
                line += f" — answers: {q}"
            if mets:
                line += f"  [metrics: {mets}]"
            L.append(line)

    if g.get("questions"):
        L.append("\nRELATED EMS QUESTIONS (background only — use a phrasing ONLY if it matches what the "
                 "user is already asking; otherwise ignore them):")
        L += [f"- {q['display']}" for q in g["questions"][:6]]

    L += ["",
          f'COMPLETE the user\'s current query: "{text}". Keep their wording, asset(s) and intent; '
          "every suggestion should continue/refine it (most should start with that text). "
          'Return JSON: {"autofill": "...", "suggestions": ["...", "...", "...", "...", "..."]}']
    return "\n".join(L)
