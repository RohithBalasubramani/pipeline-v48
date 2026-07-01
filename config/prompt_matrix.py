"""config/prompt_matrix.py — thin reader over cmd_catalog.render_guarantee_matrix (+ render_guarantee_page_phrase).

The render-guarantee acceptance suite's 50-prompt matrix is a POLICY (which failure-mode asset×page×window each prompt
must exercise), so — per the V48 governing rule — it is an EDITABLE ROW set here, NOT hardcoded prompt literals in the
test. This accessor lives in cmd_catalog (:5432), which stays UP even when the live DATA DB tunnel (:5433) is down, so the
matrix ENUMERATES from config and never collapses to 0 on a tunnel outage. The test resolves each row's asset_selector
against the live registry when reachable, else falls back to the row's audit-named asset_name_hint.

Every row is editable: change coverage by editing render_guarantee_matrix, not the test code. Selectors are a tiny
predicate grammar (see match_selector) parsed here — no policy magic numbers in the test.
"""
from data.db_client import q


def rows():
    """All ENABLED matrix rows as dicts, in insertion/tag order. Each row:
    {tag, asset_selector, asset_name_hint, page_glob, time_window, phrasing, note}."""
    r = q("cmd_catalog",
          "SELECT tag, asset_selector, asset_name_hint, page_glob, time_window, phrasing, note "
          "FROM render_guarantee_matrix WHERE enabled IS NOT FALSE ORDER BY tag")
    out = []
    for tag, sel, hint, glob, win, phr, note in r:
        out.append({"tag": tag, "asset_selector": sel or "", "asset_name_hint": hint or "",
                    "page_glob": glob or "", "time_window": (win or ""), "phrasing": phr or "", "note": note or ""})
    return out


def page_phrases():
    """{page_seg: phrase} — the editable NL verb-phrase per page segment (the {page} token in a matrix phrasing)."""
    return {seg: phrase for seg, phrase in
            q("cmd_catalog", "SELECT page_seg, phrase FROM render_guarantee_page_phrase")}


def expand_pages(page_glob, live_page_keys):
    """Resolve a matrix row's page_glob to the concrete LIVE page_keys it targets. A '<shell>/*' glob fans out over every
    live page under that shell; a '|'-separated list targets each listed page_key; a bare page_key targets exactly one.
    Only page_keys actually present in `live_page_keys` (from cmd_catalog.page_specs) survive — DB-anchored, never invented."""
    live = set(live_page_keys)
    want = []
    for part in str(page_glob).split("|"):
        part = part.strip()
        if not part:
            continue
        if part.endswith("/*"):
            prefix = part[:-1]  # keep the trailing '/'
            want.extend(pk for pk in live if pk.startswith(prefix))
        elif part in live:
            want.append(part)
    # de-dup, stable
    seen, uniq = set(), []
    for pk in want:
        if pk not in seen:
            seen.add(pk)
            uniq.append(pk)
    return uniq


def match_selector(selector, reg_row):
    """True iff a registry row (dict with name/class/has_data) satisfies the row's asset_selector predicate. Grammar:
       - '|'  = OR of clauses; a clause is '&'-joined terms (all must hold).
       - term forms:  class=UPS  |  name~ups-04  |  !has_data  |  has_data  |  concept:<x> (never matches a real asset).
       A 'concept:' selector has no registry match by design (bare-concept prompts use the asset_name_hint verbatim)."""
    if not selector:
        return False
    name = (reg_row.get("name") or "").lower()
    cls = (reg_row.get("class") or "")
    has = bool(reg_row.get("has_data"))
    for clause in selector.split("|"):
        clause = clause.strip()
        if not clause:
            continue
        ok = True
        for term in clause.split("&"):
            term = term.strip()
            if not term:
                continue
            if term.startswith("concept:"):
                ok = False  # concepts never resolve to a concrete registry asset
            elif term == "has_data":
                ok = has
            elif term == "!has_data":
                ok = not has
            elif term.startswith("class="):
                ok = (cls == term.split("=", 1)[1].strip())
            elif term.startswith("name~"):
                ok = (term.split("~", 1)[1].strip().lower() in name)
            else:
                ok = False  # unknown term → clause fails (fail-closed, never silently true)
            if not ok:
                break
        if ok:
            return True
    return False
