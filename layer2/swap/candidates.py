"""layer2/swap/candidates.py — the ±15% card_grid_size swap pool: off-page, render_real, NOT in template, AND
**only cards that live on one of the available pages** (config/available_pages) — the pipeline never swaps in a
card from a page we don't serve. [contract 4, #13, user 2026-06-30 'only these cards available']

RENDER-CAPABLE FILTER [META-05, FR-5]: every candidate must ALSO (a) have a RECOVERABLE default payload (own or
component-sibling — a target with none would ship an ungated example payload) and (b) be a REGISTERED front-end
renderer id (quality_policy 'registered_card_ids' row; empty row = fail-open) — a target with no renderer is a
permanent 'not wired' blank. Applied HERE, inline in pool(), before the AI (or the force-renderable enforcer) ever
sees the pool (the old grounding.swap_settle.swappable_pool helper was dead code, deleted 2026-07-12). Both policies
are editable DB rows, not code lists."""
from data.db_client import q
from config.app_config import cfg
from config import swap as _swap   # lazy module attrs — read per call so DB row edits reach the pool live
from config.available_pages import available_page_keys
from grounding.swap_settle import is_registered
from grounding.default_assemble import has_default


def _pool_verdicts():
    """Feasibility verdicts a swap TARGET may carry — the renderable-pool side of config.feasibility's vocab (DB knob
    cmd_catalog.app_config 'feasibility.pool_verdicts'), NOT a hardcoded list in the SQL. Default: render_real only.
    Read per call (an import-time read pinned the boot value for process life)."""
    return tuple(str(v) for v in cfg("feasibility.pool_verdicts", ["render_real"]))


def __getattr__(name):
    if name == "POOL_VERDICTS":         # kept as a module attr (tests read it) — re-reads the DB knob per access
        return _pool_verdicts()
    raise AttributeError(f"module 'layer2.swap.candidates' has no attribute {name!r}")

# The generic metric-affinity vocabulary/score HOME moved to domain/metric_affinity.py (grounding/swap_settle replays
# the same re-rank and must not import a layer — the settle↔candidates lazy-import cycle is dead). Aliased under the
# historical private names so this module's own call sites and the affinity tests keep working. The min-token knob is
# read per call there (lazy, campaign style). [cycle-kill 2026-07-12]
from domain.metric_affinity import metric_tokens as _metric_tokens, affinity as _affinity   # noqa: F401


def _available_card_ids():
    """card_ids that appear on one of the available pages — the swap universe."""
    keys = available_page_keys()
    if not keys:
        return set()
    inlist = ",".join(f"$a${k}$a$" for k in keys)
    return {int(x[0]) for x in q("cmd_catalog",
            f"SELECT DISTINCT card_id FROM page_layout_cards WHERE card_id IS NOT NULL AND page_key IN ({inlist})") if x and x[0]}


def pool(card_id, page_key, template_card_ids, *, width=None, height=None, metric=None):
    """Swap candidate pool for one slot. Ranked by SIZE-fit (closest ±SIZE_TOLERANCE first), truncated to
    SWAP_POOL_MAX. When `metric` (the pipeline's 1a metric) is given, a SOFT metric-affinity re-rank runs BEFORE the
    truncation: metric-relevant cards (metric token in title/analytical_role/card_purpose/visualization) surface first,
    size stays the tiebreak. It never DROPS a size-fit candidate — off-metric ones only fall after — so a page with no
    metric-specific card still returns its full size pool. `metric=None` (or a token-less metric) → byte-identical to
    the pure-size pool. Generic for any metric; no per-card/per-metric branch."""
    if not width or not height:
        r = q("cmd_catalog", f"SELECT width_px, height_px FROM card_grid_size WHERE card_id={int(card_id)} LIMIT 1")
        if r and r[0] and r[0][0]:
            width, height = int(r[0][0]), int(r[0][1])
    if not width or not height:
        return []
    tol, pool_max = _swap.SIZE_TOLERANCE, _swap.SWAP_POOL_MAX   # per-call reads (PEP-562 lazy knobs)
    lo_w, hi_w = width * (1 - tol), width * (1 + tol)
    lo_h, hi_h = height * (1 - tol), height * (1 + tol)
    page_ids = {int(x[0]) for x in q("cmd_catalog",
                f"SELECT card_id FROM page_layout_cards WHERE page_key=$a${page_key}$a$ AND card_id IS NOT NULL") if x and x[0]}
    forbidden = page_ids | {int(t) for t in (template_card_ids or [])} | {int(card_id)}
    available = _available_card_ids()                              # ★ only swap among cards on the available pages
    verdict_in = ",".join(f"$a${v}$a$" for v in _pool_verdicts())  # renderable-pool verdicts = the DB knob, not a literal
    rows = q("cmd_catalog", f"""
        SELECT g.card_id, c.title, coalesce(c.analytical_role,''), coalesce(c.card_purpose,''),
               coalesce(c.visualization,''), g.width_px, g.height_px
        FROM card_grid_size g JOIN cards c ON c.id=g.card_id JOIN card_feasibility f ON f.card_id=g.card_id
        WHERE c.status='live' AND f.verdict IN ({verdict_in})
          AND g.width_px BETWEEN {lo_w:.0f} AND {hi_w:.0f}
          AND g.height_px BETWEEN {lo_h:.0f} AND {hi_h:.0f}
        ORDER BY abs(g.width_px-{width}) + abs(g.height_px-{height})""")
    tokens = _metric_tokens(metric)                               # () when no metric → pure-size path (unchanged)
    out = []
    for x in rows:
        if not x or not x[0]:
            continue
        cid = int(x[0])
        if cid in forbidden or cid not in available:              # ★ off-page, off-template, AND on an available page
            continue
        # ★ render-capable only [META-05, FR-5]: registered renderer + recoverable default — filtered BEFORE the
        # closest-N truncation so the AI still sees up to SWAP_POOL_MAX genuinely swappable candidates.
        if not is_registered(cid) or not has_default(cid, page_key):
            continue
        cand = {"card_id": cid, "title": x[1], "analytical_role": x[2] or None,
                "card_purpose": (x[3] or "")[:200] or None, "visualization": x[4] or None,
                "width_px": int(x[5]), "height_px": int(x[6])}
        if not tokens:
            # no metric → today's behavior exactly: closest-first, early-break at the cap (byte-identical output).
            out.append(cand)
            if len(out) >= pool_max:
                break
        else:
            # metric present → materialize ALL size-fit renderable survivors (no early break) so a metric-relevant
            # card beyond the size-closest-N is still visible to the affinity re-rank below.
            out.append((_affinity(cand, tokens), cand))
    if not tokens:
        return out
    # ★ SOFT metric-affinity re-rank: relevant-first, SQL size-ascending order kept as the stable tiebreak (Python's
    # sort is stable, so equal-affinity candidates retain closest-first size order). Truncate AFTER ranking so a
    # voltage-role card outranks a size-closer off-metric one, yet no size-fit candidate is dropped before ranking.
    out.sort(key=lambda t: -t[0])
    return [cand for _aff, cand in out[:pool_max]]
