"""host/server.py — V48 preview API.

Wraps run_pipeline(prompt) and joins each selected card to its ground-truth payload
(cmd_catalog.card_payloads: card_id -> story_id + payload) so a frontend can render the
chosen cards. Stdlib only (no Flask). Run from anywhere:

    python3 host/server.py            # binds 0.0.0.0:8770 (env V48_HOST_PORT)

Endpoints
    GET  /api/health           -> {ok, sb_base}
    POST /api/run  {prompt, asset_id?}  -> the pipeline result + per-card payloads

DATA PATH (ems_exec — 2026-07-02): each card's `payload` is the COMPLETED CMD_V2 payload from
ems_exec.serve.run.run_card(exact_metadata, data_instructions, asset_table, db_link, window). run_card fills the payload
skeleton from NEURACT directly (real where the AI named a column/fn, honest None/'—' else; every seed number stripped) —
NO ws/mfm frame-fetch, NO Layer 2 frontend-fill, NO Layer 3. Feeder + asset + panel cards ALL go through run_card
per-card (panel-aggregate leaves simply honest-blank; aggregation deferred). `frames` is emitted EMPTY for back-compat.
Layer 3 is RETIRED (archive/layer3_archive_20260702.tar.gz) and the old ems_backend is archived too — neither is imported.

THIS FILE = the HTTP surface (Handler + build_response + the response dump). The serve-boundary seams are atomic host
siblings, re-exported byte-compatibly: host/enrich.py (the FE card build + blank-reason wording + emit-gap merge),
host/exec_cards.py (the parallel per-card executor fan-out), host/payload_store.py (the skeleton/raw-default caches).
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
from config.app_config import cfg                          # noqa: E402  DB-tunable operational knobs
from ems_exec.serve import run as ems_exec_run             # noqa: E402  per-card NEURACT executor (run_card)
from config import neuract_dsn as _neuract_dsn             # noqa: E402  DB-driven neuract DSN (code-default fallback)
from host.enrich import (                                  # noqa: E402,F401  the FE card build (re-exported for tests)
    _enrich_card, _merge_emit_gaps, _gap_note, _no_data_reason, _asset_has_logged_data, _per_metric_blank_reason)
from host.exec_cards import _run_cards, _date_window_for   # noqa: E402  the parallel executor fan-out
from host.payload_store import _skeleton_payload, _raw_default_payload, _as_json  # noqa: E402,F401

SB_BASE = os.environ.get("STORYBOOK_URL", "http://100.90.185.31:6008").rstrip("/")
PORT = int(os.environ.get("V48_HOST_PORT", "8770"))


def _attach_l2_notes(cards, l2):
    """B1 [residual 'fe' — invisible proxy notes]: attach Layer 2's card-level honesty disclosures to each served card
    as ADDITIVE fields. _enrich_card's whitelist dropped them — e.g. r_44796d791a card 70's 'kWh shown as a proxy for
    run-hours' data_note reached only the page-level notes.loop1, never the card the FE renders — so every emitted
    proxy/substitution note was invisible on the card itself.
      data_note        — the emit's plain-words proxy/substitution/blank explanation. Canonical home = the Layer 2
                         output's TOP level (layer2/build.py `out['data_note']`); falls back to the emit-variance
                         location inside data_instructions (the model sometimes nests it there — see r_44796d791a
                         card 71). Whitespace-only / non-string → None (honest, never fabricated).
      l2_answerability — Layer 2's OWN full/partial/none claim. Telemetry beside the verdict: render.answerability
                         (derived from the completed payload by validate/render_verdict) stays the single source of
                         truth; this is the AI's claim, served so a disagreement is visible.
    Generic (no card ids), additive (no existing field moves). Mutates + returns `cards`."""
    for c in cards or []:
        l2o = (l2 or {}).get(c.get("card_id")) or {}
        note = l2o.get("data_note") or (l2o.get("data_instructions") or {}).get("data_note")
        c["data_note"] = note.strip() if isinstance(note, str) and note.strip() else None
        c["l2_answerability"] = l2o.get("answerability")
    return cards


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

    # PER-CARD NEURACT EXECUTOR — the ONE data path (ems_exec). Every Layer-2 card (feeder / asset / panel alike) has its
    # payload COMPLETED by ems_exec.run_card straight from neuract: real where the AI named a column/fn, honest None/'—'
    # everywhere else, every seed number stripped. No ws/mfm frame-fetch, no asset-dashboard socket, no Layer 3. Panel-
    # aggregate leaves simply honest-blank per-card (aggregation deferred). `frames` is emitted EMPTY for FE back-compat.
    asset_table = (l1b.get("asset") or {}).get("table")
    db_link = _neuract_dsn.dsn()                              # DB-driven neuract DSN (config accessor + code-default)
    frames, frame_status = {}, {}                             # data no longer flows through endpoint frames
    if out.get("data_unavailable") or not asset_table:
        # INFRA-OUTAGE / no resolved table — 1a/1b never reached ground truth so Layer 2 never ran (or has no meter to
        # read). Emit ZERO cards (honest page-level terminal via data_unavailable + degrade.reason) rather than bare 1a
        # shells carrying no verdict — the silent verdict-less dead-end the guarantee forbids.
        completed_by_id, status_by_id, cards = {}, {}, []
    else:
        completed_by_id, status_by_id = _run_cards(l2, asset_table, db_link=db_link,
                                                    date_window=date_window, run_id=out.get("run_id"),
                                                    asset=(l1b.get("asset") or {}), page_key=page_key)
        cards = [_enrich_card(c, page_key, val_by_id, l2.get(c.get("card_id")),
                              completed=completed_by_id.get(c.get("card_id")),
                              run_ok=(status_by_id.get(c.get("card_id")) or {}).get("ok", True),
                              run_why=(status_by_id.get(c.get("card_id")) or {}).get("why"),
                              asset_table=asset_table)
                 for c in (l1a.get("cards") or [])]
    _attach_l2_notes(cards, l2)   # B1: serve data_note + l2_answerability per card (additive; see the helper)
    from obs.stage import stage
    stage(out.get("run_id") or "-", "RESPONSE", page=page_key, cards=len(cards),
          with_payload=sum(1 for c in cards if c.get("has_payload")), frames=[],
          rendered=sum(1 for c in cards if (c.get("render") or {}).get("verdict") in ("render", "partial")),
          partial=sum(1 for c in cards if (c.get("render") or {}).get("verdict") == "partial"),
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
        "frames": frames,                                        # EMPTY now — DATA rides on each card's `payload` (ems_exec-completed); kept for FE back-compat
        "frame_status": frame_status,                            # EMPTY now — the honest fetch-reason is per-card (card.frame_status / card.render.reason)
        "live_frame": None,                                      # back-compat FE field; always None under the ems_exec path (DATA rides on each card's `payload`)
        "date_window": date_window,
        "notes": out.get("notes") or {"loop1": [], "loop2": None},  # reflect-loop: best-effort substitutions + persistent-gap explain
        "errors": out.get("errors") or {},
    }


def _dump_response(resp):
    """Persist the full /api/run response to outputs/logs/response_<run_id>.json so a client timeout / disconnect never
    loses the per-run payload — the sweep + debugging read it FROM DISK (the pipeline already ran; the only thing a broken
    pipe costs is the wire copy). Keyed by run_id (matches pipeline_<run_id>.jsonl / ai_<run_id>.jsonl). Never raises."""
    try:
        rid = (resp or {}).get("run_id") or "default"
        d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "logs")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f"response_{rid}.json"), "w") as f:
            json.dump(resp, f)
    except Exception:
        pass


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
        # HEADER STATUS — site identity + LIVE dot. `site.name` is a DB-tunable app_config row; the LIVE flag is a REAL
        # probe of the live-data DB connection (DATA_DB = target_version1/neuract) — green iff that DB answers.
        if self.path.startswith("/api/site"):
            from data.db_client import q
            from config.databases import DATA_DB
            try:
                q(DATA_DB, "SELECT 1"); live = True
            except Exception:
                live = False
            return self._send(200, {"ok": True, "site": cfg("site.name", "PEGEPL · SEETARAMPUR"), "live": live})
        return self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", "0"))
            req = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:
            return self._send(400, {"ok": False, "error": f"bad body: {e}"})

        # PER-CARD date re-fetch: one card's CMD V2 date control changed → re-COMPLETE JUST that card's payload for the
        # new window via ems_exec.run_card (the SAME executor the page uses — no ws/mfm). The FE posts the card's own
        # {exact_metadata, data_instructions, asset_table, date_window}; the response `payload` is the re-filled CMD_V2
        # payload it swaps in. Honest-degrade: any error still returns a stripped+shape-complete payload (no seed leak).
        if self.path.startswith("/api/frame"):
            try:
                exact_metadata = req.get("exact_metadata") or (req.get("payload") if isinstance(req.get("payload"), dict) else None)
                data_instructions = req.get("data_instructions") or {}
                asset_table = req.get("asset_table") or ((req.get("consumer") or {}).get("asset_table"))
                consumer = (data_instructions.get("consumer") or {}) or (req.get("consumer") or {})
                window = _date_window_for(consumer, req.get("date_window"))
                if exact_metadata is None or not asset_table:
                    return self._send(400, {"ok": False, "error": "exact_metadata + asset_table required"})
                _rid = req.get("render_card_id") or req.get("card_id")
                payload = ems_exec_run.run_card(exact_metadata, data_instructions, asset_table,
                                                db_link=_neuract_dsn.dsn(), window=window,
                                                default_payload=req.get("_default_payload"),
                                                shape_ref=_raw_default_payload(_rid), card_id=_rid)
                from host.display_dash import apply as _dash    # same serve-boundary display policy as /api/run
                from ems_exec.executor import roster_stats as _rstats
                _rstats.pop(payload)                             # telemetry key never rides to the FE
                payload = _dash(payload, req.get("_default_payload"))
                return self._send(200, {"ok": True, "why": "ok", "endpoint": consumer.get("endpoint"),
                                        "payload": payload})
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
            # KNOWLEDGE PRE-ROUTE [separate pipeline, 2026-07-06]: a CONCEPTUAL electrical/mechanical question
            # ("what is voltage", "what are transformers") gets ONE restricted educator answer; off-domain prompts
            # ("who is George Bush") are refused; asset/data prompts fall through UNCHANGED to the card pipeline.
            # Skipped when the FE re-POSTs with a pinned asset_id (that is always a dashboard flow). Fail-open.
            if asset_id is None:
                from knowledge.route import classify as _kclassify
                from knowledge import answer as _kanswer
                _kind = _kclassify(prompt)
                if _kind == "knowledge":
                    resp = {"ok": True, "prompt": prompt, **_kanswer.answer(prompt)}
                    _dump_response(resp)
                    return self._send(200, resp)
                if _kind == "off_domain":
                    resp = {"ok": True, "prompt": prompt, **_kanswer.refuse()}
                    _dump_response(resp)
                    return self._send(200, resp)
            resp = build_response(prompt, asset_id=asset_id, date_window=date_window)
            _dump_response(resp)                              # persist server-side FIRST (robust to a client-side curl timeout)
            return self._send(200, resp)
        except Exception as e:
            traceback.print_exc()
            return self._send(500, {"ok": False, "error": f"{type(e).__name__}: {e}"})


class _Server(ThreadingHTTPServer):
    # Bursty connection robustness: a page fires many card requests + the live frontend polls while a sweep runs. The
    # stdlib default listen backlog (request_queue_size=5) drops connections under that burst → the browser sees
    # "Failed to fetch". A deeper backlog + daemon threads (so a slow /api/run never blocks accept or shutdown) keeps
    # the API reachable for the interactive frontend even while a batch sweep hammers it. allow_reuse_address avoids a
    # TIME_WAIT bind failure on a fast restart.
    request_queue_size = 128
    daemon_threads = True
    allow_reuse_address = True


def main():
    srv = _Server(("0.0.0.0", PORT), Handler)
    print(f"[host] V48 preview API on http://0.0.0.0:{PORT}  (storybook={SB_BASE})  [backlog={_Server.request_queue_size}]", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
