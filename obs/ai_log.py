"""obs/ai_log.py — monkeypatch urllib.urlopen -> log every :8200 call to outputs/logs/ai_<run_id>.jsonl. Import FIRST."""
import io
import json
import os
import urllib.request
from datetime import datetime

_RUN_ID = "default"
_OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "logs")
_orig = urllib.request.urlopen


def set_run_id(rid):
    global _RUN_ID
    _RUN_ID = rid or "default"


class _Tee:
    def __init__(self, data):
        self._b = io.BytesIO(data)

    def read(self, *a):
        return self._b.read(*a)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _logged(req, *a, **kw):
    resp = _orig(req, *a, **kw)
    try:
        url = getattr(req, "full_url", "")
        if ":8200" not in url:
            return resp
        data = resp.read()
        os.makedirs(_OUT, exist_ok=True)
        rec = {"ts": datetime.now().isoformat(), "run_id": _RUN_ID, "url": url}
        try:
            rec["request"] = json.loads(req.data) if getattr(req, "data", None) else None
        except Exception:
            rec["request"] = None
        try:
            rec["response"] = json.loads(data)
        except Exception:
            rec["response"] = None
        with open(os.path.join(_OUT, f"ai_{_RUN_ID}.jsonl"), "a") as f:
            f.write(json.dumps(rec) + "\n")
        return _Tee(data)
    except Exception:
        return resp


urllib.request.urlopen = _logged
