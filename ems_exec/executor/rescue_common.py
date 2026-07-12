"""ems_exec/executor/rescue_common.py — THE honest-blank path matcher the post-fill rescues share (dedup D5,
refactor campaign 2026-07-12).

The three sibling rescues (scalar_mean_fill / scalar_tile_fill / load_factor_fill) consume the SAME
`fill._honest_blank_paths` contract: tokens-tuples normalized both address-ways, `'*'` matching any index at its
position (DEFECT 56). Before this home the matcher lived 3× and a wildcard-form fix had to land three times.

The blank-value predicate half of D5 already has its home (lib/blank.is_blank_scalar — the executor/blank facade).
The window-reduce fill idioms were NOT hoisted: _try_fill (sibling-column + stat-map resolve) and _try_tile
(label/unit tile chrome) have diverged into genuinely different shapes — hoisting them now would be a rewrite,
not a dedup.
"""


def honest_blanked(path, hb, both_addresses=False):
    """True when `path` (a dotted walk path) matches a slot the AI EXPLICITLY honest-blanked. `hb` holds
    tokens-tuples already normalized both address-ways (bare + data.<slot>) by fill._honest_blank_paths; a '*'
    segment matches any index at that position. `both_addresses=True` ALSO probes the `data.<path>` form for a
    caller whose paths aren't pre-normalized (the load-factor rescue's dual-form probe)."""
    if not hb:
        return False
    from ems_exec.executor.paths import _toks
    forms = (path, f"data.{path}") if both_addresses else (path,)
    for form in forms:
        toks = tuple(_toks(form))
        if not toks:
            continue
        if toks in hb:
            return True
        for entry in hb:
            if len(entry) == len(toks) and all(e == t or e == "*" for e, t in zip(entry, toks)):
                return True
    return False
