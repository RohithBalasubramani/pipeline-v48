"""outputs/batch/audit_endpoints.py — AUDIT every card on every page + the pipeline's endpoint offer-list
against the ems_backend GROUND TRUTH (the live WS route table). Read-only: reports, proposes, applies nothing.

GROUND TRUTH (ems_backend/lt_panels/page_registry.py _PAGES):
  LIVE endpoints (11): overview, real-time-monitoring, energy-power, demand-profile, load-anomalies,
    energy-power-history, energy-distribution, voltage-current, voltage-history, current-history, power-quality-summary
  RETIRED (folded into power-quality-summary): distortion-harmonics, power-quality-history
Category coverage: every dispatcher serves {lt_panel,transformer,ht_panel,ups,apfc,sub_panel,pcc_panel};
  'dg' has NO strategy anywhere and mfm_type.code='dg' == category so the lt_panel fallback can't rescue it."""
import json
import os
import sys

sys.path.insert(0, "/home/rohith/desktop/BFI/backend/layer2/pipeline_v48")
from data.db_client import q
from layer2.emit.data.consumer_binding import canonical_screen, RETIRED_ENDPOINTS  # noqa: F401
from layer2.emit.data.endpoint_registry import (LIVE_ENDPOINTS, HISTORY_ENDPOINTS,
                                                HISTORY_BY_DOMAIN as HBD, PAGE_PRIMARY)

LIVE = LIVE_ENDPOINTS                          # DERIVED from ems_backend _PAGES (single source of truth)
RETIRED = {"distortion-harmonics", "power-quality-history"}
# the live screen each retired screen was folded INTO (for the repoint proposal)
RETIRED_TO_LIVE = {"distortion-harmonics": "power-quality-summary", "power-quality-history": "power-quality-summary"}

ROUTABLE_PAGES = {  # config/available_pages.py — the 9 pages 1a can actually route to
    "panel-overview-shell/energy-distribution", "panel-overview-shell/energy-power",
    "panel-overview-shell/harmonics-pq", "panel-overview-shell/real-time-monitoring",
    "panel-overview-shell/voltage-current", "individual-feeder-meter-shell/voltage-current",
    "individual-feeder-meter-shell/real-time-monitoring", "individual-feeder-meter-shell/energy-power",
    "individual-feeder-meter-shell/power-quality",
}


def repoint_target(bs):
    """given a backend_strategy whose canonical screen is RETIRED, propose the live backend_strategy
    (swap the consumer dir, keep the panel-suffix file). e.g.
    consumers/distortion_harmonics/lt_panel.py -> consumers/power_quality_summary/lt_panel.py"""
    scr = canonical_screen(bs)
    live = RETIRED_TO_LIVE.get(scr)
    if not live:
        return None
    parts = bs.strip("/").split("/")
    i = parts.index("consumers")
    parts[i + 1] = live.replace("-", "_")
    return "/".join(parts)


def classify(scr):
    if scr is None:
        return "no_endpoint"            # narrative / nav / 3d card — no data screen (fine)
    if scr in LIVE:
        return "live"
    if scr in RETIRED:
        return "retired"
    return "off_route"                  # an asset-dashboard consumer (assets/consumers/...) not in lt_panels route table


def main():
    # every card + its canonical backend_strategy, with the routable pages it appears on
    rows = q("cmd_catalog", """
        SELECT ch.card_id, c.title, ch.backend_strategy, ch.handling_class, ch.resolver_scope
        FROM card_handling ch JOIN cards c ON c.id = ch.card_id
        ORDER BY ch.card_id""")
    pages = q("cmd_catalog", """
        SELECT card_id, string_agg(DISTINCT page_key, ' ; ' ORDER BY page_key)
        FROM page_layout_cards WHERE card_id IS NOT NULL GROUP BY card_id""")
    page_by_card = {int(r[0]): r[1] for r in pages}

    buckets = {"live": [], "retired": [], "off_route": [], "no_endpoint": []}
    for cid, title, bs, hcls, scope in rows:
        scr = canonical_screen(bs)
        cls = classify(scr)
        on_pages = page_by_card.get(int(cid), "")
        on_routable = [p for p in (on_pages.split(" ; ") if on_pages else []) if p in ROUTABLE_PAGES]
        buckets[cls].append({"card_id": int(cid), "title": title[:48], "bs": bs, "screen": scr,
                            "handling": hcls, "routable_pages": on_routable, "all_pages": on_pages})

    print("=" * 80, "\nCARD ENDPOINT AUDIT  (", len(rows), "cards)\n", "=" * 80, sep="")
    for cls in ("retired", "off_route", "no_endpoint", "live"):
        items = buckets[cls]
        print(f"\n### {cls.upper()}  ({len(items)})")
        if cls == "live":
            print(f"  (all {len(items)} canonical endpoints are in the live route table — OK)")
            continue
        for it in items:
            rp = it["routable_pages"]
            flag = "  <<< ON A ROUTABLE PAGE — WILL FAIL" if (cls == "retired" and rp) else ("" if cls != "retired" else "  (off-route page only)")
            print(f"  card {it['card_id']:>3} | {it['screen'] or '-':22} | {it['handling']:22} | {it['title']}{flag}")
            if cls == "retired":
                print(f"           bs:  {it['bs']}")
                print(f"           ->   {repoint_target(it['bs'])}   (repoint)")
                if rp:
                    print(f"           on routable pages: {rp}")

    # the proposed DB repoints (retired cards only)
    repoints = [{"card_id": it["card_id"], "from": it["bs"], "to": repoint_target(it["bs"]),
                "title": it["title"], "routable_pages": it["routable_pages"]} for it in buckets["retired"]]

    # offer-list audit (consumer_binding)
    print("\n", "=" * 80, "\nPIPELINE OFFER-LIST AUDIT (consumer_binding.py)\n", "=" * 80, sep="")
    bad_hist = sorted(e for e in HISTORY_ENDPOINTS if e not in LIVE)
    bad_map = {k: [e for e in v if e not in LIVE] for k, v in HBD.items() if any(e not in LIVE for e in v)}
    bad_ep = {k: v for k, v in PAGE_PRIMARY.items() if v not in LIVE}
    print("HISTORY_ENDPOINTS not live:", bad_hist or "none")
    print("_HISTORY_BY_DOMAIN dead entries:", json.dumps(bad_map) if bad_map else "none")
    print("_ENDPOINT dead entries:", json.dumps(bad_ep) if bad_ep else "none")

    print("\n", "=" * 80, "\nCATEGORY COVERAGE\n", "=" * 80, sep="")
    print("dg (Diesel Generator): NO strategy on any dispatcher; mfm_type.code='dg'==category so lt_panel fallback")
    print("  cannot rescue it -> DG fails on ALL endpoints. (ems_backend fix: add a dg->lt_panel fallback or dg strategies.)")

    out = {"repoints": repoints, "offer_list": {"history_endpoints": bad_hist, "history_by_domain": bad_map, "endpoint": bad_ep},
           "summary": {k: len(v) for k, v in buckets.items()},
           "retired_on_routable": [r for r in repoints if r["routable_pages"]]}
    json.dump(out, open(os.path.join(os.path.dirname(__file__), "audit_endpoints.json"), "w"), indent=1)
    print("\nSUMMARY:", json.dumps(out["summary"]), "| retired-on-routable cards:", len(out["retired_on_routable"]))


if __name__ == "__main__":
    main()
