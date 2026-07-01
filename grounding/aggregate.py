"""grounding/aggregate.py — deterministic PRE unit for AGGREGATE (panel-overview / Sankey) cards. NO AI, NO fetching of
raw rows here; it consumes the topology fan-out from data.lt_panels.panel_members and pure policy from config.*, and
produces the aggregate FACT-SHEET pieces the POST assembler + L3 fact-sheet need:

  · aggregate_coverage(mfm_id) — the N-of-M coverage verdict + sentence for a panel: reporting/expected feeders, a
        complete|partial|orphan status decided by the EDITABLE feeder_coverage_partial_pct policy, and the honest
        reason string. Members are de-duplicated + recursed to leaves by panel_members (never lt_mfm_incoming).
        [TOPO-01/03/04/05/06/07, DS-08, VC-04/08]
  · aggregate_power(per_feeder) — the SIGN-SAFE feeder-power sum: each feeder scalar goes through normalizers.power_sign
        (magnitude + reverse flag) so a distribution panel can NEVER report the nonsensical Σ(signed) = -270 kW; a mixed
        direction set is surfaced, not silently absorbed. [VC-03]
  · buckets_widgets_prep(buckets, value_keys) — the deterministic buckets→widgets SUB-SHAPE prep (the envelope
        assembler's rule for a history {buckets} frame feeding a widgets-reading aggregate mapper); a shape with no rule
        returns a machine reason instead of a silent swap. [ER-3, VC-08]

Every threshold / convention is a cmd_catalog row (config.quality_policy); every sentence is a reason_template row.
ZERO hardcoded numbers or reason strings. [grounding fact: topology_members / aggregate integrity]
"""
from __future__ import annotations

from config import quality_policy as qp
from config import reason_templates as rt
from data.lt_panels.panel_members import panel_members
from grounding.normalizers import power_sign


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  COVERAGE — the N-of-M sentence + verdict for an aggregate panel
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def aggregate_coverage(mfm_id, meaningful=False):
    """The coverage fact-sheet for aggregate panel `mfm_id`. Resolves its de-duplicated leaf members via panel_members
    (FROM-side fan-out, recursed through empty aggregates, has_data-filtered), then classifies:

      status='orphan'   — no outgoing topology at all → caller renders single-asset or 'no topology mapped'. [TOPO-01/07]
      status='empty'    — has members but 0 report → honest-blank ('downstream meters not reporting'). [TOPO-05]
      status='partial'  — reporting < expected AND coverage% < feeder_coverage_partial_pct → labelled partial. [DS-08/VC-04]
      status='complete' — all expected members report (or coverage% >= threshold).

    Returns {status, reporting_count, expected_count, coverage_pct, members, reason, partial(bool)}.
    `reason` is a human sentence from the reason_template rows (never a hardcoded string); None when complete.
    """
    res = panel_members(mfm_id, meaningful=meaningful)
    expected = res["expected_count"]
    reporting = res["reporting_count"]
    members = res["members"]

    if res["orphaned"]:
        return {"status": "orphan", "reporting_count": 0, "expected_count": 0,
                "coverage_pct": None, "members": [], "partial": False,
                "reason": rt.reason("no_topology", asset=_asset_label(mfm_id))}

    coverage_pct = (100.0 * reporting / expected) if expected else 0.0
    partial_threshold = qp.num("feeder_coverage_partial_pct", 50.0)

    if reporting == 0:
        # members exist but none report → whole subtree silent → honest blank (empty_feeders reason carries 0/N)
        return {"status": "empty", "reporting_count": 0, "expected_count": expected,
                "coverage_pct": 0.0, "members": members, "partial": True,
                "reason": rt.reason("empty_feeders", reporting=0, expected=expected)}

    if reporting < expected:
        # some feeders missing → ALWAYS disclose the partial count. When coverage dips under the policy threshold it is
        # a hard 'partial' verdict (downgrade the KPI); above threshold it still carries the caveat sentence.
        return {"status": "partial", "reporting_count": reporting, "expected_count": expected,
                "coverage_pct": coverage_pct,
                "partial": (coverage_pct < partial_threshold) if partial_threshold is not None else True,
                "members": members,
                "reason": rt.reason("empty_feeders", reporting=reporting, expected=expected)}

    # all expected members report → complete, no caveat
    return {"status": "complete", "reporting_count": reporting, "expected_count": expected,
            "coverage_pct": 100.0, "members": members, "partial": False, "reason": None}


def reporting_tables(mfm_id, meaningful=False):
    """Just the neuract table names of the members that actually report — the exact set POST should fetch + sum. Empty
    members are excluded from the fetch but stay in aggregate_coverage.expected_count (the honest denominator)."""
    res = panel_members(mfm_id, meaningful=meaningful)
    return [m["table"] for m in res["members"] if m["reporting"] and m["table"]]


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  SIGN-SAFE POWER SUM — never Σ(signed) = -270 kW  [VC-03]
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def aggregate_power(per_feeder):
    """Sum feeder active/apparent power the sign-safe way. `per_feeder` = iterable of raw scalar values (one per feeder);
    each goes through normalizers.power_sign so denorm garbage (-4.6e-44) is dropped and a genuine reverse feeder is
    summed by MAGNITUDE (per the negative_power_convention policy) — so a distribution panel's total is the load
    magnitude, never the nonsensical signed cancellation. [VC-03]

    Returns {total, contributing, dropped, any_reverse, directions}:
      total        — Σ magnitude over the contributing feeders (None if none contributed)
      contributing — count of feeders that yielded a usable reading
      dropped       — count dropped as denorm/None
      any_reverse  — True if any feeder was reverse-flow (surface it, don't hide it)
      directions    — per-feeder 'forward'/'reverse'/None (for the coverage/provenance note)
    """
    total = 0.0
    contributing = 0
    dropped = 0
    any_reverse = False
    directions = []
    for raw in per_feeder:
        s = power_sign(raw)
        directions.append(s["direction"])
        if s["value"] is None:
            dropped += 1
            continue
        total += s["value"]                 # value is magnitude under abs_with_flag; raw signed under keep_sign
        contributing += 1
        if s["reversed"]:
            any_reverse = True
    return {"total": (total if contributing else None), "contributing": contributing,
            "dropped": dropped, "any_reverse": any_reverse, "directions": directions}


# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
#  BUCKETS → WIDGETS SUB-SHAPE PREP  [ER-3, VC-08]
# ═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════
def buckets_widgets_prep(buckets, value_keys):
    """The deterministic buckets→widgets sub-shape rule the envelope assembler applies when a history {buckets} frame
    must feed a widgets-reading aggregate mapper (ER-3). A history bucket carries per-bucket ts + <col>_avg/_min/_max;
    this folds them into the trend sub-shape (`series`) each aggregate widget expects, WITHOUT inventing a widget shape.

    `buckets`    — the frame's list of bucket dicts (each {ts|bucket, <key>_avg, <key>_min, <key>_max, ...}).
    `value_keys` — the metric column bases the widget renders (e.g. ['active_power_total_kw']).

    Returns {ok, series, points, reason}:
      ok=True  → series = {key: [{ts, avg, min, max}, …]} + points = row count.
      ok=False → reason from reason_template ('frame_shape_mismatch' with the concrete why) — NEVER a silent pageFrame
                 swap; the caller honest-degrades with this reason. [ER-3]

    A NON-empty buckets frame that carries only a placeholder column (the pcc_panel_N_feedbacks empty-history case) →
    ok=False so a 0-row/placeholder history is disclosed, not shown as a flat-zero trend. [VC-08/ER-2]
    """
    if not buckets:
        return {"ok": False, "series": {}, "points": 0,
                "reason": rt.reason("frame_shape_mismatch", expected="widgets", actual="buckets(0)")}
    if not value_keys:
        return {"ok": False, "series": {}, "points": 0,
                "reason": rt.reason("frame_shape_mismatch", expected="widgets", actual="buckets(no-keys)")}

    series = {k: [] for k in value_keys}
    matched_any = False
    for b in buckets:
        ts = b.get("ts") or b.get("bucket") or b.get("bucket_ts") or b.get(_first_ts_key(b))
        for k in value_keys:
            avg = _pick(b, k, "_avg", k)
            if avg is None and (k + "_min") not in b and (k + "_max") not in b:
                # this bucket carries NO signal for this key (placeholder-only history) → skip, don't fabricate a 0
                continue
            matched_any = True
            series[k].append({
                "ts": ts,
                "avg": avg,
                "min": _pick(b, k, "_min"),
                "max": _pick(b, k, "_max"),
            })

    if not matched_any:
        # buckets present but none carry a real value for the requested keys → placeholder-only history (VC-08/ER-2)
        return {"ok": False, "series": {}, "points": 0,
                "reason": rt.reason("frame_shape_mismatch", expected="widgets", actual="buckets(placeholder-only)")}

    points = max((len(v) for v in series.values()), default=0)
    return {"ok": True, "series": series, "points": points, "reason": None}


# ── helpers ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _pick(bucket, base, suffix="_avg", *alts):
    """Read <base><suffix> from a bucket dict, falling back to plain <base> then any alt key. Numeric-cast, None-safe."""
    for key in (base + suffix, *alts):
        if key in bucket and bucket[key] not in (None, "", "NULL"):
            try:
                return float(bucket[key])
            except (TypeError, ValueError):
                return bucket[key]
    return None


def _first_ts_key(bucket):
    """The first key that looks like a timestamp (fallback when a bucket names its ts column oddly)."""
    for k in bucket:
        if "ts" in k.lower() or "time" in k.lower() or "bucket" in k.lower():
            return k
    return "ts"


def _asset_label(mfm_id):
    """A human label for an mfm_id in a reason sentence. Prefers the registry name; falls back to the id — kept tiny +
    fail-open so the reason channel never crashes. NO hardcoded names."""
    try:
        from config.databases import DATA_DB, DATA_SCHEMA
        from data.db_client import q
        rows = q(DATA_DB, f'SELECT name FROM {DATA_SCHEMA}.lt_mfm WHERE id={int(mfm_id)}')
        if rows and rows[0] and rows[0][0]:
            return rows[0][0]
    except Exception:
        pass
    return f"asset {mfm_id}"
