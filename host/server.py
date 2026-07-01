"""host/server.py — V48 preview API.

Wraps run_pipeline(prompt) and joins each selected card to its ground-truth payload
(cmd_catalog.card_payloads: card_id -> story_id + payload) so a frontend can render the
chosen cards. Stdlib only (no Flask). Run from anywhere:

    python3 host/server.py            # binds 0.0.0.0:8770 (env V48_HOST_PORT)

Endpoints
    GET  /api/health           -> {ok, sb_base}
    POST /api/run  {prompt, asset_id?}  -> the pipeline result + per-card payloads

NOTE: each card's `payload` is Layer 2's `exact_metadata` (the byte-identical CMD_V2 default + the AI's morphs;
run/layer2_all.py sets payload=exact_metadata). _enrich_card sends it as the ONLY source — no card_payloads fallback.
The DATA leaves are filled live on the frontend from the ems_backend frame (frames[card.endpoint]).
"""
import json
import os
import sys
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# pipeline_v48 root = parent of host/
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from run.harness import run_pipeline                       # noqa: E402
from validate.payload_lookup import card_payloads_for      # noqa: E402
from layer2.emit.data.consumer_binding import page_endpoint  # noqa: E402
from config.app_config import cfg                          # noqa: E402  DB-tunable operational knobs

SB_BASE = os.environ.get("STORYBOOK_URL", "http://100.90.185.31:6008").rstrip("/")
PORT = int(os.environ.get("V48_HOST_PORT", "8770"))


def _sb_url(story_id):
    if not story_id:
        return None
    return f"{SB_BASE}/iframe.html?id={story_id}&viewMode=story&shortcuts=false&nav=false"


def _story_render(story_id, import_path):
    """How to render this card in OUR frontend EXACTLY like EMS: run the card's Storybook STORY render function
    (the bespoke `render: (args) => <CardComposer .../>` glue) with the pipeline payload — import-only, CMD_V2 untouched.
    {module: the .stories.tsx under CMD_V2/src, export: the Story export name}. None when the card has no story."""
    if not story_id or not import_path:
        return None
    module = import_path.replace("./src/", "").lstrip("/")             # path under the cmd2 symlink
    export = "".join(p.capitalize() for p in story_id.split("--")[-1].split("-"))  # main-heatmap-card-story → MainHeatmapCardStory
    return {"module": module, "export": export, "via": "story"}


def _enrich_card(card, page_key, val_by_id, l2_out, l3_out=None, frame_status=None):
    """The payload is Layer 2's `exact_metadata` — the ONLY source (NO card_payloads fallback). The default payload is
    merely Layer 2's input; it is never shown raw. If Layer 2 emitted nothing for this card, payload is None (the
    frontend shows it as not-rendered — honest, not masked). On an accepted swap, the FINAL card is the swap target:
    render_card_id + payload follow the target (it has a different shape).

    The Layer-3 render envelope (`l3_out`) is the render-guarantee VERDICT for this card: render|partial|honest_blank
    with a machine reason, the per-slot verified values, the suppress_default_leaves (NO-SEED-LEAK force-blank list), and
    a coverage/date_control flag. It rides onto the card as `render` so the frontend safe-renderer knows exactly what to
    draw or blank. The per-endpoint {ok,why} (`frame_status`) is the reason channel [ER-6]."""
    cid = card.get("card_id")
    l2 = l2_out or {}
    l3 = l3_out or {}
    swap = l2.get("swap_decision") or {"action": "keep"}
    render_card_id = swap.get("swap_to_id") or cid           # the card actually drawn (swap target if swapped)
    payload = l3.get("exact_metadata") if l3.get("exact_metadata") is not None else l2.get("payload")
    consumer = (l2.get("data_instructions") or {}).get("consumer") or {}
    endpoint = consumer.get("endpoint")
    fstat = (frame_status or {}).get(endpoint) or {}

    # NO-SEED-LEAK [VC-01/02]: the render-guarantee VERDICT the frontend obeys — the L3 suppress_default_leaves (paths to
    # force-blank), the render verdict, and the watermark. A numeric that equals its seed with no live provenance is
    # force-blanked on the FE using these paths; the watermark 'live' means every shown numeric is live-verified.
    render_verdict = l3.get("render_verdict")
    suppress = l3.get("suppress_default_leaves") or []       # the L3-named seed-leaking paths (already blanked in payload)
    reason = l3.get("reason") or (fstat.get("why") if fstat.get("ok") is False else None)

    return {
        "card_id": cid,
        "render_card_id": render_card_id,
        "title": card.get("title"),
        "story": card.get("analytical_story"),
        "role": card.get("role_in_story"),
        "slot": card.get("slot"),
        "size": card.get("size"),
        "payload": payload,
        "endpoint": endpoint,                                # which frames[endpoint] this card's CMD V2 mapper consumes
        "is_history": consumer.get("is_history"),            # date-navigable card?
        "swap": swap,
        "conforms": l2.get("conforms"),
        "fill_source": l2.get("fill_source"),                # always "live-frontend" — DATA fills on the FE from the ems_backend frame
        "fill_ok": l2.get("fill_ok"),
        "fill_why": l2.get("fill_why"),
        "data_instructions": l2.get("data_instructions"),
        "validation": val_by_id.get(cid),
        "has_payload": payload is not None,
        "payload_error": l2.get("exception") or (l2.get("failure") or {}).get("detail"),
        # ── RENDER-GUARANTEE channel (Layer 3 verdict + frame reason) ─────────────────────────────────────────────
        "render": {
            "verdict": render_verdict,                       # render | partial | honest_blank | None (L3 skipped)
            "answerability": l3.get("answerability"),
            "reason": reason,                                # human/machine reason for a blank/partial/frame-empty
            "coverage_note": l3.get("coverage_note"),        # 'N of M feeders reporting' for aggregates
            "date_control": l3.get("date_control"),          # enabled | disabled (ER-7 no-history domains)
            "slots": l3.get("slots"),                        # {slot: {value|None, blank_reason, fidelity_note, source}}
            "suppress_default_leaves": suppress,             # NO-SEED-LEAK: FE force-blanks these payload paths
            "watermark": l3.get("watermark") or "live",      # provenance stamp; a blanked slot carries None, never a seed
        },
        "frame_status": {"endpoint": endpoint, "ok": fstat.get("ok"), "why": fstat.get("why")},  # ER-6 reason channel
    }


# Wall-clock ceiling for the WHOLE parallel frame-fetch fan-out (all endpoints together). A single retired/cold-connect
# endpoint used to cost ~60s serially and (×N endpoints) drop the whole page; PARALLEL + a budget means a slow endpoint
# degrades to ok=False+why='frame budget exceeded' instead of sinking every other card's frame. [ER-8]
_FRAME_BUDGET_S = cfg("ems_backend.frame_budget_s", float(os.environ.get("V48_FRAME_BUDGET_S", "45")))


def _card_frames(l2, date_window=None, run_id="-"):
    """The ems_backend frames the page's cards render from: ONE frame per DISTINCT endpoint (cards sharing an endpoint
    share a frame), fetched IN PARALLEL with the user's date_window (history endpoints re-window). Returns
    (frames, frame_status): frames={endpoint: frame} for the FE mappers; frame_status={endpoint:{ok,why}} the reason
    channel threads onto each card [ER-6]. A per-endpoint failure/timeout is an honest {ok:False, why} — never a silent
    drop with no reason. [date-nav; ER-6/8 parallel+budget]"""
    try:
        from workers.fill.sources.ems_backend_source import fetch_frame
        from obs.stage import stage
        from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as _FTimeout
    except Exception:
        return {}, {}
    # one representative consumer per endpoint (params identical across same-endpoint cards on a page), and the MERGED
    # row-scope recovery map per endpoint = {target_column: fn} from EVERY card on that endpoint whose AI emitted a
    # data_instructions.fields[] entry with kind=="derived" and scope=="row". This is the AI→executor seam: the host
    # ships these recipes to ems_backend, whose fill_derived(row) hook runs registry.run(fn, {"row": row}) per row.
    by_endpoint, derived_by_endpoint = {}, {}
    for o in (l2 or {}).values():
        di = (o or {}).get("data_instructions") or {}
        c = di.get("consumer") or {}
        ep = c.get("endpoint")
        if not (ep and c.get("mfm_id")):
            continue
        by_endpoint.setdefault(ep, c)
        dmap = derived_by_endpoint.setdefault(ep, {})
        for f in (di.get("fields") or []):
            if not isinstance(f, dict) or f.get("kind") != "derived" or (f.get("scope") or "row") != "row":
                continue
            tgt, fn = f.get("target_column"), f.get("fn")
            if tgt and fn:
                dmap[tgt] = fn                                   # last writer wins (same target+fn across cards = identical)

    frames, frame_status = {}, {}
    if not by_endpoint:
        return frames, frame_status

    def _fetch(ep, consumer):
        return fetch_frame(consumer, date_window=date_window, derived_map=(derived_by_endpoint.get(ep) or None))

    deadline = time.time() + _FRAME_BUDGET_S
    with ThreadPoolExecutor(max_workers=max(2, len(by_endpoint))) as ex:
        futs = {ex.submit(_fetch, ep, c): ep for ep, c in by_endpoint.items()}
        for fut in as_completed(futs):
            ep = futs[fut]
            remaining = max(0.0, deadline - time.time())
            try:
                frame, ok, why = fut.result(timeout=remaining or 0.01)
                if ok:
                    frames[ep] = frame                          # keep EVERY frame with a shape (queue / buckets / widgets)
                frame_status[ep] = {"ok": bool(ok), "why": (why if not ok else "ok")}
                stage(run_id, "frame", endpoint=ep, ok=ok, why=(why if not ok else "ok"),
                      derived=sorted((derived_by_endpoint.get(ep) or {}).keys()))
            except _FTimeout:
                frame_status[ep] = {"ok": False, "why": "frame budget exceeded"}
                stage(run_id, "frame", endpoint=ep, ok=False, why="frame budget exceeded")
            except Exception as e:
                frame_status[ep] = {"ok": False, "why": f"{type(e).__name__}: {e}"}
                stage(run_id, "frame", endpoint=ep, ok=False, why=f"{type(e).__name__}: {e}")
    return frames, frame_status


def build_response(prompt, asset_id=None, date_window=None):
    t0 = time.time()
    out = run_pipeline(prompt, asset_id=asset_id)
    l1a = out.get("layer1a") or {}
    l1b = out.get("layer1b") or {}
    val = out.get("validation") or {}

    vcards = (val.get("payload") or {}).get("cards") or []
    val_by_id = {c.get("card_id"): c for c in vcards if isinstance(c, dict) and "card_id" in c}

    page_key = l1a.get("page_key")
    l2 = out.get("layer2") or {}                              # {card_id: Layer2CardOutput} — the payload source
    l3 = out.get("layer3") or {}                              # {card_id: render envelope} — the render-guarantee verdict
    frames, frame_status = _card_frames(l2, date_window, run_id=out.get("run_id"))  # (frames, {endpoint:{ok,why}})
    # INFRA-OUTAGE honest terminal — a live data source is unreachable, so 1a/1b never reached ground truth and Layer 2/3
    # never ran. Emit ZERO cards (an honest page-level terminal via `data_unavailable` + `degrade.reason`) rather than the
    # bare 1a card shells, which would carry NO render verdict — a silent verdict-less dead-end the guarantee forbids.
    if out.get("data_unavailable"):
        cards = []
    else:
        cards = [_enrich_card(c, page_key, val_by_id, l2.get(c.get("card_id")),
                              l3_out=l3.get(c.get("card_id")), frame_status=frame_status)
                 for c in (l1a.get("cards") or [])]
    from obs.stage import stage
    stage(out.get("run_id") or "-", "RESPONSE", page=page_key, cards=len(cards),
          with_payload=sum(1 for c in cards if c.get("has_payload")), frames=sorted(frames.keys()),
          rendered=sum(1 for c in cards if (c.get("render") or {}).get("verdict") == "render"),
          blank=sum(1 for c in cards if (c.get("render") or {}).get("verdict") == "honest_blank"),
          asset_pending=out.get("asset_pending"), elapsed_ms=int((time.time() - t0) * 1000))

    return {
        "ok": l1a.get("cards") is not None,
        "prompt": prompt,
        "run_id": out.get("run_id"),
        "elapsed_ms": int((time.time() - t0) * 1000),
        "sb_base": SB_BASE,
        "page": {
            "page_key": page_key,
            "page_title": l1a.get("page_title"),
            "shell": l1a.get("shell"),
            "metric": l1a.get("metric"),
            "intent": l1a.get("intent"),
            "story": l1a.get("story"),
            "layout": l1a.get("layout") or {},
            "groups": l1a.get("interdependency_groups") or [],
        },
        "asset_pending": out.get("asset_pending", False),       # True → 1b ambiguous OR validation gated; FE opens the asset-picker POPUP (Layer 2 NOT run yet)
        "asset_no_data": out.get("asset_no_data", False),       # True → asked asset RESOLVED but its neuract table is empty; FE shows a 'no data for <asset>' notice (Layer 2 NOT run)
        "validation_blocked": out.get("validation_blocked", False),  # True → validate=fail gated Layer 2; FE opens the picker ('this asset can't render <page>')
        "data_unavailable": out.get("data_unavailable", False),  # True → a LIVE data source (tunnel :5433) is unreachable; page is an honest terminal (no verdict-less cards). FE shows the degrade.reason notice
        "degrade": out.get("degrade"),                          # {kind:'data_unavailable', layer, detail, reason} — the machine-readable infra-outage reason (None in the healthy case)
        "asset": {
            "asset": l1b.get("asset"),                          # carries name/class even on no_data, so the FE can say WHICH asset is dark
            "how": l1b.get("how"),
            "candidates": l1b.get("candidate_list") or [],
            "n_columns": (l1b.get("column_basket") or {}).get("n_columns"),
        },
        "validation": {
            "verdict": val.get("verdict"),
            "how": val.get("how"),
            "policy": val.get("policy"),
            "data_summary": (val.get("data") or {}).get("summary"),
            "payload_summary": (val.get("payload") or {}).get("summary"),
        },
        "cards": cards,
        "frames": frames,                                        # {endpoint: ems_backend frame}; FE: frames[card.endpoint] → card's CMD_V2 mapper
        "frame_status": frame_status,                            # {endpoint: {ok, why}} — the reason channel (ER-6); empty/mismatched frames carry a why
        "live_frame": frames.get(page_endpoint(page_key)) or (next(iter(frames.values()), None)),  # back-comat: the page frame
        "date_window": date_window,
        "notes": out.get("notes") or {"loop1": [], "loop2": None},  # reflect-loop: best-effort substitutions + persistent-gap explain
        "errors": out.get("errors") or {},
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):                    # quieter logs
        sys.stderr.write("[host] " + (fmt % args) + "\n")

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        if self.path.startswith("/api/health"):
            return self._send(200, {"ok": True, "sb_base": SB_BASE})
        # ASSET RESOLUTION — empty/browse state: the FULL asset registry in the SAME shape as the ambiguous
        # candidate_list ({mfm_id,name,class,load_group,has_data}), reusing 1b's lt_mfm source. Optional ?q= filter.
        if self.path.startswith("/api/assets"):
            try:
                from urllib.parse import urlparse, parse_qs
                from layer1b.resolve.candidate_list import registry_for_picker   # registry → picker shape (single concern)
                term = parse_qs(urlparse(self.path).query).get("q", [""])[0]
                return self._send(200, {"ok": True, "assets": registry_for_picker(term)})
            except Exception as e:
                traceback.print_exc()
                return self._send(500, {"ok": False, "error": f"{type(e).__name__}: {e}"})
        return self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", "0"))
            req = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:
            return self._send(400, {"ok": False, "error": f"bad body: {e}"})

        # PER-CARD date re-fetch: one card's CMD V2 date control changed → re-fetch JUST its frame for the new window.
        if self.path.startswith("/api/frame"):
            try:
                from workers.fill.sources.ems_backend_source import fetch_frame
                consumer = req.get("consumer") or {}          # data_instructions.consumer of THE card
                # the card's OWN row-scope recovery map {target_column: fn} from its data_instructions.fields[]
                # (kind=="derived", scope=="row") so a date-nav re-fetch keeps the AI's recovered values too.
                dmap = {f.get("target_column"): f.get("fn")
                        for f in ((req.get("data_instructions") or {}).get("fields") or [])
                        if isinstance(f, dict) and f.get("kind") == "derived" and (f.get("scope") or "row") == "row"
                        and f.get("target_column") and f.get("fn")}
                frame, ok, why = fetch_frame(consumer, date_window=req.get("date_window"), derived_map=(dmap or None))
                return self._send(200, {"ok": ok, "why": why, "endpoint": consumer.get("endpoint"), "frame": frame})
            except Exception as e:
                traceback.print_exc()
                return self._send(500, {"ok": False, "error": f"{type(e).__name__}: {e}"})

        if not self.path.startswith("/api/run"):
            return self._send(404, {"ok": False, "error": "not found"})
        try:
            prompt = (req.get("prompt") or "").strip()
            if not prompt:
                return self._send(400, {"ok": False, "error": "prompt required"})
            asset_id = req.get("asset_id")
            date_window = req.get("date_window")              # {range,start,end,sampling} from the FE date control (or None)
            return self._send(200, build_response(prompt, asset_id=asset_id, date_window=date_window))
        except Exception as e:
            traceback.print_exc()
            return self._send(500, {"ok": False, "error": f"{type(e).__name__}: {e}"})


def main():
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[host] V48 preview API on http://0.0.0.0:{PORT}  (storybook={SB_BASE})", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
