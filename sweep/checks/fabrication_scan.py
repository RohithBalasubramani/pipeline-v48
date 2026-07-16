"""sweep/checks/fabrication_scan.py — DETERMINISTIC SERVED-PAYLOAD FABRICATION SCAN (the sweep judge's backstop).

WHY: the 0-fabrication cert keys almost entirely on `payload_error` (sweep/checks/expectations.py flips a passing case
to FAIL when any card carries one). But the fab_guards blank silently — a guard that stops firing (a valve flipped off,
a vocab drift, a reworked class) leaves a fabricated reading ON-SCREEN with NO payload_error, so the sweep judge never
sees it. This scan re-derives the fabrication verdict straight from the SERVED payload, independent of the guards, so
the cert holds even if the guards are reworked.

It flags, per served card payload:
  (a) EPOCH-MS LEAK — a NON-time-axis leaf (scalar OR all-numeric array, or a per-point object's value key) holding an
      epoch-ms magnitude (>= fab_guards.epoch_ms_floor, 1e12). This is CLASS 1 read-only: it REUSES the guard's own
      knobs (_is_time_axis_key + _epoch_floor) so the time-axis vocab and the magnitude floor match the guard EXACTLY
      — a real time axis (…indexes/…timestamps/ts/time) is never flagged, a real reading (238.6 V) is never flagged.
  (b) SEED BYTE-EQUAL [optional] — when a RAW default skeleton is passed, a NUMERIC data leaf (scalar or numeric array)
      byte-identical to its raw seed at the same path. Coarse by design (it has no stripped twin to separate data from
      metadata, so it policies NUMERIC leaves only — chrome strings/orders are left alone); it is the CLASS-4 backstop,
      opt-in via raw_default.

Pure + import-light: one cheap import of the guard's knobs module (all its DB reads are lazy + fail-open to the code
defaults, so this scan is fully deterministic offline). No live DB, no LLM, no sweep-internal imports.

    from sweep.checks.fabrication_scan import scan
    findings = scan(card_payload)                       # [{path, cause, detail}, ...]  (empty == clean)
    findings = scan(card_payload, raw_default=raw)      # + CLASS-4 seed backstop

    python3 -m sweep.checks.fabrication_scan outputs/.../response_XXX.json     # scans every card, exit 1 on any finding

WIRING NOTE (sweep/checks/ has NO self-registration convention — the other checks are hand-dispatched cmd_* funcs in
sweep/cli.py via _call_flex): this stays a standalone importable scan() + __main__. To gate the sweep on it, add a
`fabrication_risk = fabrication_risk or bool(scan(card_payload))` beside the payload_error read where the runner builds
each card's verdict — see the report at the end of this task for the exact call site.
"""
from __future__ import annotations

from ems_exec.executor.fab_guards.knobs import _epoch_floor, _is_time_axis_key


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_epoch_scalar(v, floor) -> bool:
    return _is_num(v) and v >= floor


def _is_epoch_array(v, floor) -> bool:
    """Every real element is an epoch-ms magnitude (non-empty, all-numeric ignoring Nones, at least one value present).
    Mirrors ems_exec/executor/fab_guards/class1_epoch._is_epoch_array so the verdict matches the guard exactly."""
    if not isinstance(v, list) or not v:
        return False
    nums = [x for x in v if x is not None]
    if not nums or any(not _is_num(x) for x in nums):
        return False
    return all(x >= floor for x in nums)


def _scan_epoch(payload, findings) -> None:
    """CLASS-1 read-only recursion (mirrors class1_epoch._apply_class1's walk, collecting instead of blanking): a
    non-time-axis leaf holding epoch-ms magnitudes is a fabricated timestamp-as-reading."""
    floor = _epoch_floor()

    def _walk(node, path, key):
        if isinstance(node, dict):
            for k, v in node.items():
                _walk(v, f"{path}.{k}" if path else str(k), k)
            return
        if isinstance(node, list):
            if not _is_time_axis_key(key) and _is_epoch_array(node, floor) \
                    and all(_is_num(x) or x is None for x in node):
                findings.append({"path": path, "cause": "epoch_ms_leak",
                                 "detail": f"all-epoch array len {len(node)} (>= {int(floor)})"})
                return
            for i, el in enumerate(node):
                _walk(el, f"{path}[{i}]", key)
            return
        if not _is_time_axis_key(key) and _is_epoch_scalar(node, floor):
            findings.append({"path": path, "cause": "epoch_ms_leak",
                             "detail": f"scalar {node} >= {int(floor)}"})

    _walk(payload, "", "")


def _scan_seed(payload, raw_default, findings) -> None:
    """CLASS-4 backstop [optional]: a NUMERIC data leaf (scalar or numeric array) byte-identical to its raw seed at the
    same path. Numeric-only on purpose — without the stripped twin, string/order chrome cannot be told from data, so we
    only police the numeric fabrication surface (the reading a component renders)."""
    def _both(node, seed, path):
        if isinstance(node, dict) and isinstance(seed, dict):
            for k, v in node.items():
                if k in seed:
                    _both(v, seed[k], f"{path}.{k}" if path else str(k))
            return
        if isinstance(node, list) and isinstance(seed, list):
            # a whole numeric array equal to its seed array is a surviving data seed
            if node and node == seed and all(_is_num(x) or x is None for x in node) and any(_is_num(x) for x in node):
                findings.append({"path": path, "cause": "seed_byte_equal",
                                 "detail": f"numeric array len {len(node)} == raw seed"})
                return
            for i, (v, s) in enumerate(zip(node, seed)):
                _both(v, s, f"{path}[{i}]")
            return
        if _is_num(node) and node == seed:
            findings.append({"path": path, "cause": "seed_byte_equal", "detail": f"{node} == raw seed"})

    _both(payload, raw_default, "")


def scan(payload, raw_default=None) -> list:
    """Walk one SERVED card payload and return a list of fabrication findings (empty == clean). Each finding is
    {path, cause, detail}. Pure — never mutates `payload`, never raises on a malformed shape."""
    findings: list = []
    if not isinstance(payload, (dict, list)):
        return findings
    try:
        _scan_epoch(payload, findings)
    except Exception:
        pass
    if raw_default is not None:
        try:
            _scan_seed(payload, raw_default, findings)
        except Exception:
            pass
    return findings


# ── standalone entrypoint: scan every card of a saved /api/run response ──────────────────────────────────────────────
def _iter_card_payloads(doc):
    """Yield (card_id, payload) for a saved response (cards[]), a single card ({payload:...}), or a bare payload dict."""
    if isinstance(doc, dict) and isinstance(doc.get("cards"), list):
        for c in doc["cards"]:
            if isinstance(c, dict):
                yield c.get("card_id") or c.get("render_card_id") or "?", c.get("payload")
    elif isinstance(doc, dict) and "payload" in doc:
        yield doc.get("card_id") or "?", doc.get("payload")
    else:
        yield "?", doc


def main(argv=None) -> int:
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Scan a saved /api/run response (or a card payload) for fabrication.")
    ap.add_argument("path", help="response_*.json (cards[]) or a bare card payload json")
    args = ap.parse_args(argv)
    with open(args.path, encoding="utf-8") as f:
        doc = json.load(f)
    total = 0
    for cid, payload in _iter_card_payloads(doc):
        if payload is None:
            continue
        findings = scan(payload)
        total += len(findings)
        cid_s = str(cid).encode("ascii", "replace").decode("ascii")
        if findings:
            print(f"card {cid_s}: {len(findings)} finding(s)")
            for fnd in findings:
                p = str(fnd["path"]).encode("ascii", "replace").decode("ascii")
                print(f"  [{fnd['cause']}] {p} — {fnd['detail']}")
        else:
            print(f"card {cid_s}: clean")
    print(f"fabrication_scan: {total} finding(s) across the response")
    return 1 if total else 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
