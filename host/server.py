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
Layer 3 is RETIRED (archive/layer3_archive_20260702.tar.gz) and the legacy EMS backend is retired too — neither is imported.

THIS FILE = the HTTP surface (Handler + build_response + the response dump). The serve-boundary seams are atomic host
siblings, re-exported byte-compatibly: host/enrich.py (the FE card build + blank-reason wording + emit-gap merge),
host/exec_cards.py (the parallel per-card executor fan-out), host/payload_store.py (the skeleton/raw-default caches).
"""
from obs.errfmt import fmt_exc as _fmt_exc   # the ONE exception string [EH F4]
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
from config import neuract_dsn as _neuract_dsn             # noqa: E402  DB-driven neuract DSN (code-default fallback)
from host.enrich import (                                  # noqa: E402,F401  the FE card build (re-exported for tests)
    _enrich_card, _merge_emit_gaps, _gap_note, _no_data_reason, _asset_has_logged_data, _per_metric_blank_reason)
from host.exec_cards import (                              # noqa: E402  the parallel executor fan-out + shared seam
    _date_window_for, fill_one_card, _special_handling_map, _registry_mfm_id)
from host.payload_store import _skeleton_payload, _raw_default_payload, _as_json  # noqa: E402,F401

# SB_BASE + _attach_l2_notes HOME moved to host/notes.py — multi_asset shares them and the only way in was a lazy
# back-import of this module (server↔multi_asset cycle). Re-exported so tests/callers keep working. [cycle-kill 2026-07-12]
from host.notes import SB_BASE, _attach_l2_notes           # noqa: E402,F401  (shared serve-boundary home)

from config.endpoints import HOST_PORT as PORT         # noqa: E402  the ONE :8770 home (config F7)


# _window_from_preset HOME moved to host/notes.py (window_from_preset) so the MULTI-asset path applies the same
# prompt-derived default (api-design H4). Re-exported under the old name for tests/callers. [2026-07-12]
from host.notes import window_from_preset as _window_from_preset   # noqa: E402,F401


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
    # assembly each multi-asset compare lane reuses (host/multi_asset). The page-level `frames`/`frame_status`/
    # `live_frame` wire fields are RETIRED (frontend F14, 2026-07-12 — they were always {}/{}/None; the honest
    # fetch-reason is per-card: card.frame_status / card.render.reason).
    from host.assemble import assemble_cards
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
        "kind": "dashboard",                                    # discriminant for the FE PipelineResult union (the
        # knowledge response carries kind:"knowledge"); makes host/web/src/types.ts DashboardResult non-optional. [R10]
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


def _traced_captured(kind, path, req, fn):
    """Wrap one request body in the obs trace (obs/middleware) + the replay capture session (replay/capture) —
    fn() -> (code, resp dict); the wrappers see the RESP dict (trace summary / bundle artifact) while the HTTP code
    rides beside. Fail-open: if either layer can't import, the request runs bare, byte-identical."""
    try:
        from obs.middleware import run_traced
        from replay.capture import captured
    except Exception:
        return fn()
    box = {}

    def _inner():
        code, resp = fn()
        box["code"] = code
        return resp

    fields = {"prompt": (req or {}).get("prompt"), "asset_id": (req or {}).get("asset_id")}
    resp = run_traced(kind, fields, lambda: captured(kind, req, _inner, path=path))
    return box.get("code", 200), resp


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
                return self._send(500, {"ok": False, "error": _fmt_exc(e)})
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
        # AI DECISION INSPECTOR — read-only views over the obs_* trace store (pg-first, per-trace jsonl fallback):
        #   /api/inspector/traces?n=50   newest-first execution list
        #   /api/inspector/trace?id=t_…  one execution: trace summary + stage tree + every AI decision
        #                                (prompt/model/params/candidates/selected/rejected/reasoning/confidence/
        #                                 latency/tokens/output — shaped by obs/decision_view via host/inspector_api)
        if self.path.startswith("/api/inspector"):
            try:
                from urllib.parse import urlparse, parse_qs
                from host import inspector_api
                u = urlparse(self.path)
                qs = parse_qs(u.query)
                if u.path.rstrip("/") == "/api/inspector/traces":
                    n = max(1, min(200, int((qs.get("n") or ["50"])[0])))
                    return self._send(200, {"ok": True, "traces": inspector_api.traces(n)})
                if u.path.rstrip("/") == "/api/inspector/trace":
                    tid = (qs.get("id") or [""])[0].strip()
                    if not tid:
                        return self._send(400, {"ok": False, "error": "id required (?id=t_…)"})
                    return self._send(200, {"ok": True, **inspector_api.trace_detail(tid)})
                return self._send(404, {"ok": False, "error": "unknown inspector endpoint"})
            except Exception as e:
                traceback.print_exc()
                return self._send(500, {"ok": False, "error": _fmt_exc(e)})
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
            code, resp = _traced_captured("frame", "/api/frame", req, lambda: handle_frame(req))
            return self._send(code, resp)

        if not self.path.startswith("/api/run"):
            return self._send(404, {"ok": False, "error": "not found"})
        code, resp = _traced_captured("run", "/api/run", req, lambda: handle_run(req))
        return self._send(code, resp)


def handle_frame(req):
    """The /api/frame body → (code, resp). Module-level so the replay engine re-runs the EXACT same entry."""
    try:
        exact_metadata = req.get("exact_metadata") or (req.get("payload") if isinstance(req.get("payload"), dict) else None)
        data_instructions = req.get("data_instructions") or {}
        date_window = req.get("date_window")
        # REFETCH bundle (enrich.py) — the per-card facts the consumer/payload do NOT carry. Back-compat: fall
        # back to the legacy top-level / consumer fields so an older FE build still works.
        refetch = req.get("refetch") or {}
        consumer = (data_instructions.get("consumer") or {}) or (req.get("consumer") or {})
        asset_table = refetch.get("asset_table") or req.get("asset_table") or consumer.get("asset_table")
        asset_name = refetch.get("asset_name")
        member_scope = refetch.get("member_scope") or "outgoing"
        default_payload = refetch.get("_default_payload") if "_default_payload" in refetch else req.get("_default_payload")
        render_card_id = refetch.get("render_card_id") or req.get("render_card_id") or req.get("card_id")
        if exact_metadata is None or not asset_table:
            return 400, {"ok": False, "error": "exact_metadata + asset_table required"}
        # RC2b NARROW-FIX — make the FE pick AUTHORITATIVE over the L2-baked consumer.range so _honor_range (which
        # is widen-only, keyed on consumer.range) anchors to the pick instead of re-widening a narrower window.
        # Request-object only (the response is just the payload) → no served-card side effect.
        if isinstance(date_window, dict) and date_window.get("range") and isinstance(consumer, dict):
            consumer = dict(consumer); consumer["range"] = date_window.get("range")
            data_instructions = {**data_instructions, "consumer": consumer}
        window = _date_window_for(consumer, date_window)
        # SPECIAL DISPATCH [RC1] — a panel_aggregate/topology/narrative/3d card must NOT be re-filled by a plain
        # run_card (a panel trend card is is_history=true today → its date control is enabled). Route through the
        # SAME fill_one_card the page fan-out uses; derive the lt_mfm member id from the table/name (NOT
        # consumer.mfm_id — a different id-space).
        handling_class = _special_handling_map([render_card_id]).get(int(render_card_id)) if render_card_id else None
        mfm_id = _registry_mfm_id({"table": asset_table, "name": asset_name})
        payload = fill_one_card(cid=render_card_id, render_card_id=render_card_id, handling_class=handling_class,
                                exact_metadata=exact_metadata, data_instructions=data_instructions,
                                asset_table=asset_table, db_link=_neuract_dsn.dsn(), window=window,
                                requested_window=date_window, default_payload=default_payload,
                                mfm_id=mfm_id, asset_name=asset_name, member_scope=member_scope)
        from host.display_dash import apply as _dash    # same serve-boundary display policy as /api/run
        from ems_exec.executor import roster_stats as _rstats
        _rstats.pop(payload)                             # telemetry key never rides to the FE
        payload = _dash(payload, default_payload)
        return 200, {"ok": True, "why": "ok", "endpoint": consumer.get("endpoint"), "payload": payload}
    except Exception as e:
        traceback.print_exc()
        return 500, {"ok": False, "error": _fmt_exc(e)}


def handle_run(req):
    """The /api/run body → (code, resp). Module-level so the replay engine re-runs the EXACT same entry
    (knowledge gate → natural-compare pre-flight → multi/single response build → response dump)."""
    try:
        prompt = (req.get("prompt") or "").strip()
        if not prompt:
            return 400, {"ok": False, "error": "prompt required"}
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
            # KNOWLEDGE-GATE TRACE [admin dashboard]: bind the run id BEFORE the gate's LLM call so it lands in
            # ai_<rid>.jsonl (it used to inherit the PREVIOUS run's id — the ai-attribution leak the log audit
            # flagged). run_id is the same deterministic make_run_id(prompt) run_pipeline will derive, so the
            # gate call and the pipeline share one trace family. A terminal (knowledge/off_scope) prompt gets a
            # `knowledge` stage record + a run_id'd response dump — it becomes a viewable run in the admin
            # console instead of vanishing (dashboard prompts skip the spine record: their file must still
            # START at PROMPT for the executions splitter).
            from run.run_id import make_run_id
            from obs import ai_log
            _rid = make_run_id(prompt)
            ai_log.set_run_id(_rid)
            from knowledge.ems import ask as _ems_ask
            _k = _ems_ask(prompt, history)
            if _k["kind"] in ("knowledge", "off_scope"):
                from obs.stage import stage as _stage
                _stage(_rid, "knowledge", kind=_k["kind"], refused=_k["refused"],
                       answer_chars=len(_k.get("answer") or ""))
                resp = {"ok": True, "prompt": prompt, "run_id": _rid, "kind": "knowledge",
                        "answer": _k["answer"], "refused": _k["refused"]}
                _dump_response(resp)
                return 200, resp
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
        return 200, resp
    except Exception as e:
        traceback.print_exc()
        return 500, {"ok": False, "error": _fmt_exc(e)}


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
