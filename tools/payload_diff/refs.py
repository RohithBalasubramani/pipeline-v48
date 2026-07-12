"""tools/payload_diff/refs.py — turn a CLI execution reference into a snapshot. One grammar everywhere:

    <ref>            = <what>[@<occurrence>]        (occurrence: 0-based, negatives from the end; default -1 = latest)
    <what>           = snapshot file path | saved label | run id (r_xxxxxxxxxx) | the prompt text itself

A label matches the newest outputs/diffs/snapshots/<label>_*.json. A prompt hashes to its run id (run/run_id.py
logic). When BOTH refs of a diff land on the SAME run_id with no explicit occurrences, they default to previous-vs-
latest (@-2 vs @-1) — the natural same-prompt comparison."""
import os
import re

from tools.payload_diff import logs as L
from tools.payload_diff import snapshot as S

_RUN_ID = re.compile(r"^r_[0-9a-f]{10}$")
_OCC = re.compile(r"^(.*)@(-?\d+)$")


def parse(ref):
    """ref → (what, occurrence|None)."""
    m = _OCC.match(ref)
    if m and not os.path.exists(ref):                  # a real path containing '@' beats the occurrence syntax
        return m.group(1), int(m.group(2))
    return ref, None


def _label_path(label):
    if not os.path.isdir(S.SNAP_DIR):
        return None
    hits = sorted(f for f in os.listdir(S.SNAP_DIR) if f.startswith(f"{label}_") and f.endswith(".json"))
    return os.path.join(S.SNAP_DIR, hits[-1]) if hits else None


def resolve(ref, occurrence=None):
    """One ref → a snapshot dict. File > label > run id > prompt."""
    what, occ = parse(ref)
    occ = occurrence if occurrence is not None else occ
    if os.path.exists(what) and os.path.isfile(what):
        snap = S.load(what)
        if occ is not None and occ != snap["meta"].get("occurrence"):
            raise SystemExit(f"{what} is a frozen snapshot of occurrence {snap['meta'].get('occurrence')} — "
                             f"@{occ} can't rewind it; snapshot that occurrence from logs instead")
        return snap
    lp = _label_path(what)
    if lp:
        return S.load(lp)
    run_id = what if _RUN_ID.match(what) else L.make_run_id(what)
    if not (L.stage_log(run_id) or L.response_json(run_id)):
        kind = "run id" if _RUN_ID.match(what) else f"prompt (run id {run_id})"
        raise SystemExit(f"no execution found for {kind} {what!r} — no logs under outputs/logs/ and no such "
                         f"snapshot file/label; run `capture` first or check `list`")
    return S.build(run_id, occurrence=(occ if occ is not None else -1),
                   prompt=(None if _RUN_ID.match(what) else what))


def resolve_pair(ref_a, ref_b):
    """Two refs → (snap_a, snap_b), defaulting a same-run_id pair with no explicit occurrences to @-2 vs @-1."""
    what_a, occ_a = parse(ref_a)
    what_b, occ_b = parse(ref_b)
    same_target = (what_a == what_b and occ_a is None and occ_b is None
                   and not os.path.exists(what_a) and not _label_path(what_a))
    if same_target:
        rid = what_a if _RUN_ID.match(what_a) else L.make_run_id(what_a)
        n = len(L.segment_executions(L.stage_log(rid)))
        if n < 2:
            raise SystemExit(f"{what_a!r} has only {n} logged execution(s) — need two to compare; "
                             f"use `rerun` to run it again and diff against the previous one")
        occ_a, occ_b = -2, -1
    return resolve(ref_a, occ_a), resolve(ref_b, occ_b)
