"""workers/fill/sources/ems_backend_source.py — DATA-fill source = LIVE, via V48's ems_backend WS dispatcher
(ws/mfm/<mfm_id>/<endpoint>/). Connect, read the snapshot frame the consumer emits, return it. Honest-degrade
(None, why) when ems_backend is unreachable / yields no frame — NEVER fabricate. [user: helpers use ems_backend]"""
import json
import time

from config.ems_backend import (ws_url, EMS_CONNECT_TIMEOUT, EMS_FRAME_TIMEOUT,
                                 EMS_FETCH_ATTEMPTS, EMS_RETRY_BACKOFF)
from workers.fill.sources.ems_window import query as _window_query


def fetch_frame(consumer, *, selection=None, date_window=None, derived_map=None):
    """consumer = data_instructions.consumer {mfm_id, endpoint, is_history, window/range, ...}. The date_window (the
    user's date pick) is applied via the URL QUERY (?range=&sampling=): the history consumer windows on connect and
    emits ONE snapshot for that range — so the FIRST snapshot already reflects the chosen date. Returns (frame|None, ok,
    why). `derived_map` ({target_column: fn}) = the AI's row-scope recovery recipes for this endpoint, appended to the
    query so ems_backend's executor fills each None target_column. [NOTE: do NOT also send a mid-connection re-window +
    wait for a 2nd snapshot — the consumer sends only one, so waiting blocks the recv until timeout and discards the good
    frame. That was the 'history slowness' bug.]"""
    mfm_id, endpoint = consumer.get("mfm_id"), consumer.get("endpoint")
    if not mfm_id or not endpoint:
        return None, False, "consumer missing mfm_id/endpoint"
    qs = _window_query(consumer, date_window, derived_map=derived_map)
    url = ws_url(mfm_id, endpoint) + (f"?{qs}" if qs else "")
    try:
        import websocket  # websocket-client (sync) — kept lazy so importing workers never needs the lib
    except Exception as e:  # pragma: no cover
        return None, False, f"websocket-client not available: {e}"
    # Retry TRANSIENT connection flakes (TIMEOUT / RESET / remote-disconnect — e.g. daphne under concurrent load): a
    # single dropped/slow connection shouldn't discard a card's data. A backend `type:error` answer (not configured/
    # registered) is a PERMANENT verdict that `_read_once` RETURNS (not raises), so it short-circuits with NO retry.
    why = "no attempt"
    for attempt in range(max(1, EMS_FETCH_ATTEMPTS)):
        try:
            return _read_once(url, selection)
        except Exception as e:                            # connection-level error -> transient, retry with backoff
            why = f"ems_backend unreachable: {type(e).__name__}: {str(e)[:120]}"
            if attempt + 1 < EMS_FETCH_ATTEMPTS:
                time.sleep(EMS_RETRY_BACKOFF * (attempt + 1))
    return None, False, why


def _read_once(url, selection):
    """ONE connect+read attempt. Returns (frame|None, ok, why) — a backend `type:error` frame is a PERMANENT answer
    (RETURNED, so fetch_frame won't retry it). RAISES on any connection-level error so fetch_frame CAN retry."""
    import websocket
    ws = None
    try:
        ws = websocket.create_connection(url, timeout=EMS_CONNECT_TIMEOUT)
        if selection:
            ws.send(json.dumps(selection))
        ws.settimeout(EMS_FRAME_TIMEOUT)
        # the consumer pushes its snapshot on connect (windowed from the URL query); return the FIRST snapshot frame.
        for _ in range(10):
            raw = ws.recv()
            if not raw:
                continue
            frame = json.loads(raw)
            if not isinstance(frame, dict):
                continue
            # backend ANSWERED with a reason (retired/unregistered endpoint, category not configured, etc.): surface it
            # verbatim and stop. Without this we'd ignore the error frame, recv() again, hit the server's close, and
            # mislabel that ConnectionReset as "unreachable" — hiding the real cause. (RETIRED_PQ_ENDPOINTS_FRONTEND_FIX.md)
            if frame.get("type") == "error":
                return None, False, frame.get("message") or "backend error"
            if frame.get("type") in (None, "snapshot"):
                return frame, True, "ok"
        return None, False, "no snapshot frame received"
    finally:
        try:
            if ws:
                ws.close()
        except Exception:
            pass
