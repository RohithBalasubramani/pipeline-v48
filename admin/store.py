"""admin/store.py — the ONE disk door: (path, mtime, size)-keyed parse cache + per-run file enumeration.

Every admin sibling reads through `cached(path, parser)` so a file is parsed ONCE per version — ai_*.jsonl rows can be
MBs, so parsers return SLIM extracts (never cache a full response doc / raw LLM bodies; the trace-detail endpoints
re-read on demand). Thread-safe (the stdlib server is threading); a changed file re-parses lazily on next read."""
import glob
import json
import os
import threading

from admin.config import LOGS_DIR, NOTES_DIR, RUN_ID_RE

_LOCK = threading.Lock()
_CACHE = {}          # path -> (mtime, size, parsed)


def cached(path, parser):
    """parser(path) result, re-computed only when (mtime, size) changed. None if the file is missing/unreadable."""
    try:
        st = os.stat(path)
        key = (st.st_mtime, st.st_size)
    except OSError:
        return None
    with _LOCK:
        hit = _CACHE.get(path)
        if hit and (hit[0], hit[1]) == key:
            return hit[2]
    try:
        val = parser(path)
    except Exception:
        val = None
    with _LOCK:
        _CACHE[path] = (key[0], key[1], val)
    return val


def jsonl(path):
    """Parse a .jsonl file → list of dicts (bad lines skipped — append-only logs can have a torn last line)."""
    out = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if isinstance(rec, dict):
                out.append(rec)
    return out


def jdoc(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return json.load(f)


# ── per-run file families ─────────────────────────────────────────────────────────────────────────────────────────────
FAMILIES = {
    "pipeline": ("pipeline_{rid}.jsonl", LOGS_DIR),
    "ai":       ("ai_{rid}.jsonl", LOGS_DIR),
    "failures": ("failures_{rid}.jsonl", LOGS_DIR),
    "sql":      ("sql_{rid}.jsonl", LOGS_DIR),
    "response": ("response_{rid}.json", LOGS_DIR),
    "notes":    ("{rid}.json", NOTES_DIR),
}


def files_for(rid):
    """{family: absolute path} for the files that EXIST for this run id."""
    out = {}
    for fam, (pat, d) in FAMILIES.items():
        p = os.path.join(d, pat.format(rid=rid))
        if os.path.exists(p):
            out[fam] = p
    return out


def run_ids(sink="real"):
    """All run ids seen on disk (union across families). sink='real' keeps only r_<10-hex>; 'all' includes dev noise
    (default / pytest / r_test_*)."""
    ids = set()
    for fam, (pat, d) in FAMILIES.items():
        pre, suf = pat.split("{rid}")
        for p in glob.glob(os.path.join(d, f"{pre}*{suf}")):
            name = os.path.basename(p)
            rid = name[len(pre):len(name) - len(suf)] if suf else name[len(pre):]
            if rid:
                ids.add(rid)
    if sink != "all":
        ids = {r for r in ids if RUN_ID_RE.match(r)}
    return sorted(ids)


def last_ts(rid):
    """Last activity for a run = the newest mtime across its files (epoch seconds), or None."""
    ts = [os.path.getmtime(p) for p in files_for(rid).values() if os.path.exists(p)]
    return max(ts) if ts else None
