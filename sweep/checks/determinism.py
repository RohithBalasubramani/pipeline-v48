"""validation/checks/determinism.py — SAME-PROMPT REPEAT comparison: the pipeline routes with guided_json and fills
from live data, so re-running one prompt must land on the SAME page, the SAME card set, the SAME outcome, and the SAME
payload SHAPE — only the numbers inside may move with the live feed. This check re-runs each case `repeats` times and
diffs the STRUCTURAL fingerprint across repeats: page_key, sorted card_ids / render_card_ids, outcome, n_groups, and
per-card payload leaf-path sets (paths only, values ignored; list indices collapsed to [*] because a live series
legitimately gains/loses buckets between runs — that is data motion, not nondeterminism).

Runs SEQUENTIALLY on purpose: determinism must not fight vLLM contention (>2-3 concurrent /api/run manufactures fake
'llm timeout' failures) — a parallel determinism check would blame the pipeline for its own load. A transport failure
on any repeat makes the case incomparable and is reported as an inconsistency diff, never a raised exception."""
from __future__ import annotations

import json
import os
import urllib.request

from sweep import config
from sweep.response import parse, ascii_safe


def _post_run(prompt: str) -> dict:
    req = urllib.request.Request(config.BASE_URL + "/api/run",
                                 data=json.dumps({"prompt": prompt}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=config.RUN_TIMEOUT_S) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _leaf_paths(o, path: str = "", out: set | None = None) -> set:
    """Sorted-later set of leaf PATH strings (like checks/datesync._num_leaves but paths only, every leaf type,
    list indices collapsed to [*] so series length changes read as data motion, not structure drift)."""
    out = set() if out is None else out
    if isinstance(o, dict):
        for k, v in o.items():
            _leaf_paths(v, f"{path}.{ascii_safe(k)}", out)
    elif isinstance(o, list):
        for x in o:
            _leaf_paths(x, f"{path}[*]", out)
        if not o:
            out.add(f"{path}[*]")
    else:
        out.add(path or ".")
    return out


def _fingerprint(raw: dict) -> dict:
    """The structural identity of one /api/run response — what must NOT move across repeats."""
    p = parse(raw)
    structure = {}
    for c in (raw or {}).get("cards") or []:
        if isinstance(c, dict):
            cid = ascii_safe(c.get("card_id"))
            structure[cid] = sorted(_leaf_paths(c.get("payload")))
    return {
        "page_key": p["page_key"],
        "card_ids": sorted(ascii_safe(cr["card_id"]) for cr in p["cards"]),
        "render_card_ids": sorted(ascii_safe(cr["render_card_id"]) for cr in p["cards"]),
        "outcome": p["outcome"],
        "n_groups": p["n_groups"],
        "payload_structure": structure,
    }


def _diff(base: dict, other: dict, n: int) -> list[str]:
    diffs: list[str] = []
    for key in ("page_key", "outcome", "n_groups", "card_ids", "render_card_ids"):
        if base[key] != other[key]:
            diffs.append(f"repeat {n}: {key} {base[key]!r} -> {other[key]!r}")
    bs, os_ = base["payload_structure"], other["payload_structure"]
    for cid in sorted(set(bs) | set(os_)):
        a, b = bs.get(cid), os_.get(cid)
        if a is None or b is None:
            continue                                  # membership drift already reported via card_ids
        if a != b:
            gained = sorted(set(b) - set(a))[:3]
            lost = sorted(set(a) - set(b))[:3]
            diffs.append(f"repeat {n}: card {cid} payload structure drifted "
                         f"(+{len(set(b) - set(a))} paths e.g. {gained}, -{len(set(a) - set(b))} e.g. {lost})")
    return diffs


def run_determinism(cases: list[dict], repeats: int = 3, *, session_id: str = "adhoc") -> dict:
    """Re-run each case `repeats` times sequentially, diff structural fingerprints against the first repeat.
    Returns {cases:[{id,prompt,consistent,diffs}], n_consistent, n_inconsistent}; also written to
    sessions/<session_id>/determinism.json. Never raises: bad cases / transport errors become diffs."""
    rows: list[dict] = []
    for case in cases or []:
        case = case if isinstance(case, dict) else {}
        prompt = case.get("prompt") or ""
        cid = ascii_safe(case.get("id") or "?")
        diffs: list[str] = []
        base = None
        if not prompt:
            diffs.append("case has no prompt")
        else:
            for n in range(1, max(1, int(repeats)) + 1):
                try:
                    raw = _post_run(prompt)
                except Exception as e:
                    diffs.append(f"repeat {n}: transport {type(e).__name__}: {ascii_safe(e)[:160]}")
                    continue
                try:
                    fp = _fingerprint(raw)
                except Exception as e:                # a malformed response is itself an inconsistency, not a crash
                    diffs.append(f"repeat {n}: unparseable response ({type(e).__name__}: {ascii_safe(e)[:120]})")
                    continue
                if base is None:
                    base = fp
                else:
                    diffs.extend(_diff(base, fp, n))
        rows.append({"id": cid, "prompt": ascii_safe(prompt), "consistent": not diffs, "diffs": sorted(diffs)})

    result = {
        "cases": rows,
        "n_consistent": sum(1 for r in rows if r["consistent"]),
        "n_inconsistent": sum(1 for r in rows if not r["consistent"]),
        "repeats": max(1, int(repeats)),
    }
    try:
        sdir = config.session_dir(session_id)
        with open(os.path.join(sdir, "determinism.json"), "w") as f:
            json.dump(result, f, indent=1, sort_keys=True)
    except Exception as e:                            # disk trouble degrades to a note, never a raise
        result["write_error"] = f"{type(e).__name__}: {ascii_safe(e)[:120]}"
    return result
