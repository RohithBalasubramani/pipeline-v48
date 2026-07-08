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


def _window_from_preset(preset):
    """route-1a-timewindow: a prompt-derived TIME_WINDOWS preset ('last-7-days') → a concrete FE-vocabulary date_window
    {range,start,end,sampling}, or None. Mirrors the FE date-wiring (host/web/.../date-wiring.ts): the `range` TOKEN is
    the preset itself; start/end are the resolved span in the SITE timezone; sampling maps the preset's bucket to the FE
    sampling vocab. Start is computed by REUSING the executor's own ems_exec.window_policy._range_start (the SAME
    calendar-anchor / TIME_WINDOWS-lookback / last-N logic exec uses to honor a declared range) so the host default and
    the exec reads can never disagree. None in / unknown preset / any failure → None (the page keeps today/latest,
    unchanged). Never raises."""
    if not preset:
        return None
    try:
        from config.windows import TIME_WINDOWS, site_tz
        spec = (TIME_WINDOWS or {}).get(str(preset))
        if not spec:
            return None
        from datetime import datetime
        from ems_exec.executor.window_policy import _range_start   # reuse the canonical range→start resolver (no dup math)
        now = datetime.now(site_tz())
        start = _range_start(str(preset), now)
        if start is None:
            return None
        bucket = str(spec.get("bucket", "hour")).strip().lower()
        sampling = {"minute": "hourly", "15 min": "shift", "hour": "hourly",
                    "day": "day", "week": "week"}.get(bucket, "hourly")
        return {"range": str(preset), "start": start.isoformat(), "end": now.isoformat(), "sampling": sampling}
    except Exception:
        return None


def build_response(prompt, asset_id=None, date_window=None):
    t0 = time.time()
    out = run_pipeline(prompt, asset_id=asset_id)
    l1a = out.get("layer1a") or {}
    l1b = out.get("layer1b") or {}
    val = out.get("validation") or {}

    # PROMPT-DERIVED DATE WINDOW [route-1a-timewindow]: 1a extracted the relative time range ('last 7 days') from the
    # prompt as a preset (out["window"]). When the FE sent NO explicit date_window (a freshly typed prompt → api.ts posts
    # date_window:null), DEFAULT it to that preset resolved to a concrete {range,start,end,sampling}, so response.date_window
    # is non-null: the exec history seam (host/exec_cards._date_window_for) reads real start/end and the FE date bar
    # initializes to the asked range. An explicit FE pick ALWAYS wins (only fill when absent). No time phrase → out["window"]
    # None → date_window stays None → today/latest default unchanged.
    if not date_window:
        _prompt_window = _window_from_preset(out.get("window"))
        if _prompt_window:
            date_window = _prompt_window

    page_key = l1a.get("page_key")
    l2 = out.get("layer2") or {}                              # {card_id: Layer2CardOutput} — the payload source

    # PER-CARD NEURACT EXECUTOR (host/assemble.assemble_cards) — the ONE data path (ems_exec): every Layer-2 card (feeder
    # / asset / panel alike) has its payload COMPLETED from neuract for the RESOLVED asset — real where the AI named a
    # column/fn, honest None/'—' else, every seed number stripped. No ws/mfm frame-fetch, no Layer 3. The SAME per-asset
    # assembly each multi-asset compare lane reuses (host/multi_asset). `frames` stays EMPTY for FE back-compat.
    from host.assemble import assemble_cards
    frames, frame_status = {}, {}                             # data no longer flows through endpoint frames
    cards = assemble_cards(out, l1b.get("asset"), date_window)
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
            # MULTI-ASSET compare [author-once-per-class]: the picker returned 2+ ids → resolve them ALL in ONE run
            # (host/multi_asset.build_response_multi). Gated by the DB knob multi_asset.enabled (code default on); a
            # single-id (or absent) request stays on the untouched single-asset build_response path.
            _raw_ids = req.get("asset_ids")
            asset_ids = [a for a in _raw_ids if a is not None] if isinstance(_raw_ids, list) else []
            multi = len(asset_ids) >= 2 and bool(cfg("multi_asset.enabled", True))
            date_window = req.get("date_window")              # {range,start,end,sampling} from the FE date control (or None)
            history = req.get("history") or None              # prior knowledge turns (oldest-first) for follow-up context
            # KNOWLEDGE LAYER [separate pipeline, 2026-07-06]: ONE AI call routes + answers + rejects. A conceptual
            # electrical/mechanical question ("what is voltage") comes back answered; an off-scope prompt ("who is
            # George Bush") comes back refused; an asset/data prompt returns kind='dashboard' and falls through
            # UNCHANGED to the card pipeline. Skipped when the FE re-POSTs a pinned asset_id. Fail-open to dashboard.
            # `history` carries the earlier conceptual turns so a follow-up ("how is it measured") keeps context.
            if asset_id is None and not asset_ids:
                from knowledge.ems import ask as _ems_ask
                _k = _ems_ask(prompt, history)
                if _k["kind"] in ("knowledge", "off_scope"):
                    resp = {"ok": True, "prompt": prompt, "kind": "knowledge",
                            "answer": _k["answer"], "refused": _k["refused"]}
                    _dump_response(resp)
                    return self._send(200, resp)
                # NATURAL COMPARE [multi-asset gap fix]: a fresh 'compare A and B' prompt naming 2+ SPECIFIC full asset
                # names carries no picker ids, so the single-asset resolver would dead-end in the single picker. Split +
                # resolve EACH name through the SAME 1b resolver; if 2+ pin confidently, promote to the picker's compare
                # path (build_response_multi) with those ids. Only reached for a FRESH prompt (no asset_id/asset_ids from
                # the FE picker) — a homonym or single name returns [] and the single-asset path stays byte-identical.
                from host.multi_asset import natural_compare_ids
                _nat_ids = natural_compare_ids(prompt)
                if _nat_ids:
                    asset_ids = _nat_ids
                    multi = True
            if multi:
                from host.multi_asset import build_response_multi
                resp = build_response_multi(prompt, asset_ids, date_window=date_window)
            else:
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
