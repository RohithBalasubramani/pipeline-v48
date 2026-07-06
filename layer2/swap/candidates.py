"""layer2/swap/candidates.py — the ±15% card_grid_size swap pool: off-page, render_real, NOT in template, AND
**only cards that live on one of the available pages** (config/available_pages) — the pipeline never swaps in a
card from a page we don't serve. [contract 4, #13, user 2026-06-30 'only these cards available']

RENDER-CAPABLE FILTER [META-05, FR-5]: every candidate must ALSO (a) have a RECOVERABLE default payload (own or
component-sibling — a target with none would ship an ungated example payload) and (b) be a REGISTERED front-end
renderer id (quality_policy 'registered_card_ids' row; empty row = fail-open) — a target with no renderer is a
permanent 'not wired' blank. Applied HERE, before the AI (or the force-renderable enforcer) ever sees the pool, via
grounding.swap_settle.swappable_pool. Both policies are editable DB rows, not code lists."""
from data.db_client import q
from config.app_config import cfg
from config.swap import SIZE_TOLERANCE, SWAP_POOL_MAX
from config.available_pages import available_page_keys
from grounding.swap_settle import is_registered
from grounding.default_assemble import has_default

# feasibility verdicts a swap TARGET may carry — the renderable-pool side of config.feasibility's vocab (DB knob
# cmd_catalog.app_config 'feasibility.pool_verdicts'), NOT a hardcoded list in the SQL. Default: render_real only.
POOL_VERDICTS = tuple(str(v) for v in cfg("feasibility.pool_verdicts", ["render_real"]))


def _available_card_ids():
    """card_ids that appear on one of the available pages — the swap universe."""
    keys = available_page_keys()
    if not keys:
        return set()
    inlist = ",".join(f"$a${k}$a$" for k in keys)
    return {int(x[0]) for x in q("cmd_catalog",
            f"SELECT DISTINCT card_id FROM page_layout_cards WHERE card_id IS NOT NULL AND page_key IN ({inlist})") if x and x[0]}


def pool(card_id, page_key, template_card_ids, *, width=None, height=None):
    if not width or not height:
        r = q("cmd_catalog", f"SELECT width_px, height_px FROM card_grid_size WHERE card_id={int(card_id)} LIMIT 1")
        if r and r[0] and r[0][0]:
            width, height = int(r[0][0]), int(r[0][1])
    if not width or not height:
        return []
    lo_w, hi_w = width * (1 - SIZE_TOLERANCE), width * (1 + SIZE_TOLERANCE)
    lo_h, hi_h = height * (1 - SIZE_TOLERANCE), height * (1 + SIZE_TOLERANCE)
    page_ids = {int(x[0]) for x in q("cmd_catalog",
                f"SELECT card_id FROM page_layout_cards WHERE page_key=$a${page_key}$a$ AND card_id IS NOT NULL") if x and x[0]}
    forbidden = page_ids | {int(t) for t in (template_card_ids or [])} | {int(card_id)}
    available = _available_card_ids()                              # ★ only swap among cards on the available pages
    verdict_in = ",".join(f"$a${v}$a$" for v in POOL_VERDICTS)     # renderable-pool verdicts = the DB knob, not a literal
    rows = q("cmd_catalog", f"""
        SELECT g.card_id, c.title, coalesce(c.analytical_role,''), coalesce(c.card_purpose,''),
               coalesce(c.visualization,''), g.width_px, g.height_px
        FROM card_grid_size g JOIN cards c ON c.id=g.card_id JOIN card_feasibility f ON f.card_id=g.card_id
        WHERE c.status='live' AND f.verdict IN ({verdict_in})
          AND g.width_px BETWEEN {lo_w:.0f} AND {hi_w:.0f}
          AND g.height_px BETWEEN {lo_h:.0f} AND {hi_h:.0f}
        ORDER BY abs(g.width_px-{width}) + abs(g.height_px-{height})""")
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
        out.append({"card_id": cid, "title": x[1], "analytical_role": x[2] or None,
                    "card_purpose": (x[3] or "")[:200] or None, "visualization": x[4] or None,
                    "width_px": int(x[5]), "height_px": int(x[6])})
        if len(out) >= SWAP_POOL_MAX:
            break
    return out
