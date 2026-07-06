"""layer1b/basket/avg_phase.py — mark an AVG column DERIVABLE-FROM-PHASE.

WHY: a neuract meter can leave an aggregate `*_avg` column empty (0 rows) while its per-phase siblings ARE logged
(voltage_ll_avg empty but voltage_ry/yb/br logged; current_avg empty but current_r/y/b logged). A blind has_data=false
would honest-blank a card that is actually fillable — the avg is the mean of the logged phases. So when an avg column is
present-but-empty AND its phase columns are logged, we FLAG it `derivable` (avg-from-phase) so Layer 2 / the executor can
compute it from the phases rather than blank it. This flag is NOT a fabricated value: it is a pointer to the real logged
phase columns whose mean IS the avg. A genuinely-empty avg with NO logged phases stays honest-blank.

NAME-PATTERN based (applies to every meter, no card-ids, no per-asset hardcoding). The ONE place to tune the
avg↔phase naming convention. [SEAM 4: logged-column floor + avg-from-phase]
"""
import re

# an aggregate-average column: <family>_avg or <family>_ll_avg / <family>_ln_avg (line-line / line-neutral avg forms).
_AVG = re.compile(r"^(?P<family>.+?)_(?:ll_|ln_)?avg$")

# per-phase suffix set for the SAME family (three-phase R/Y/B, line-line RY/YB/BR, line-neutral R_N/Y_N/B_N).
# NOTE: ordered longest-first so the r_n/y_n/b_n line-neutral forms match before the bare r/y/b.
_PHASE_SUFFIXES = ("_r_n", "_y_n", "_b_n", "_ry", "_yb", "_br", "_r", "_y", "_b")


def _avg_family(col):
    """(family, kind) if `col` is an aggregate-average column, else None. kind distinguishes ll/ln so we only pair an
    avg with the matching phase form (a line-line avg with the RY/YB/BR phases; a line-neutral avg with R_N/Y_N/B_N)."""
    c = col.lower()
    m = _AVG.match(c)
    if not m:
        return None
    fam = m.group("family")
    if c.endswith("_ll_avg"):
        return (fam, "ll")
    if c.endswith("_ln_avg"):
        return (fam, "ln")
    return (fam, "any")


# the phase suffixes that belong to each avg kind (so voltage_ll_avg pairs with ry/yb/br, voltage_ln_avg with r_n/y_n/b_n)
_AVG_KIND_PHASES = {
    "ll": ("_ry", "_yb", "_br"),
    "ln": ("_r_n", "_y_n", "_b_n", "_r", "_y", "_b"),
    "any": _PHASE_SUFFIXES,
}


def phase_sources(col, all_cols, logged):
    """The LOGGED per-phase columns whose mean IS the avg `col`, or [] when `col` is not an avg column or has no logged
    phases. all_cols = every real column of the table; logged = the set with real (non-null) data over the window.

    A column is avg-from-phase DERIVABLE when it is an aggregate `*_avg` and >= 2 of its same-family phase columns are
    LOGGED (an average from a single phase is not an average; require at least two)."""
    af = _avg_family(col)
    if not af:
        return []
    fam, kind = af
    want = _AVG_KIND_PHASES[kind]
    srcs = []
    for c in all_cols:
        if c == col or c not in logged:
            continue
        cl = c.lower()
        # same family + a phase suffix valid for this avg kind
        for suf in want:
            if cl.endswith(suf) and cl[: -len(suf)] == fam:
                srcs.append(c)
                break
    return sorted(srcs) if len(srcs) >= 2 else []
