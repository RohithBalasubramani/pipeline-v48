"""tools/wall_corpus_replay.py — WALL CORPUS-REPLAY HARNESS (read-only over layer2.gates).

Loads EVERY archived + fresh Layer-2 emit call (outputs/_log_archive/**/ai_r_*.jsonl +
outputs/logs/ai_r_*.jsonl), parses each response's data_instructions (unparseable → counted + skipped),
reconstructs the run's COLUMN BASKET from the logged user message's DB SCHEMA block (all three historical
header dialects), and replays each emit through the CURRENT deterministic walls:

    layer2.gates.gate_roster              (build.py ordering: roster normalizes BEFORE the fields gate)
    layer2.gates.gate_data_instructions   (which runs layer2.gates.enforce_honest_blank as its pre-pass)

The gates are IMPORTED and used read-only — this tool never edits them. Output = a baseline snapshot:

    outputs/wall_replay_baseline.json     (full machine-readable baseline, incl. every FP suspect)
    outputs/wall_replay_baseline.md       (human report)

reporting, per wall rule:
  · fields blanked (by WHICH rule: membership / reuse-smear / quantity / axis / expectation / boundary / const),
  · suspected FALSE POSITIVES — a blanked bind whose column quantity MATCHES the slot's own quantity
    (same/compatible class) is flagged for human/agent review (plus rule-(i) blanks on emits whose prompt
    showed a TRUNCATED basket — the replay basket is smaller than the run's real one, a replay artifact),
  · bypass counts ($ctx-sourced fields, group cards, rule-(i) const/frame/time exemptions).

ACCEPTANCE HARNESS for every future wall change (standard: ALL fabrications caught, ZERO legit binds harmed):
re-run this tool after touching layer2/gates.py / layer2/quantity_class.py / the quantity.* config rows and
diff per_rule counts + false_positive_suspects against the committed baseline — new blanks must be real
fabrications; vanished blanks must be intended releases.

Run:  PYTHONPATH=. python3.11 tools/wall_corpus_replay.py            (from the pipeline_v48 root)
      … --max-files 20 --fresh-only                                   (smoke)
Config rows (cmd_catalog app_config, code-default fallback — config-first mandate):
      wall_replay.corpus_globs (json), wall_replay.md_fp_cap (int), wall_replay.rule_examples_cap (int)

REPLAY FIDELITY NOTES (approximations vs the live build path, all conservative):
  · basket = the prompt's DB SCHEMA lines (column/metric/name_hint(kind)/unit/has_data/rank + the
    ✗ FAILED-VALIDATION verdict marker). An OVERSIZED prompt caps those lines ('+N more' trailer) — such an
    emit is stamped basket_truncated and its rule-(i) blanks are auto-flagged as replay artifacts, never
    counted as real catches.
  · exact_metadata passed for sibling-unit/label slot evidence is the AI's RAW skeleton (the live path passes
    the enforce_exact_metadata-healed one); nameplate presence is unknown in the prompt → default PRESENT
    (identical to the live basket, which carries no nameplate fold either).
"""
import argparse
import copy
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from glob import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
# `layer2` also exists as a package one level up (backend/layer2) — pin THIS pipeline's package (conftest pattern).
for _m in [m for m in list(sys.modules) if m == "layer2" or m.startswith("layer2.")]:
    _f = getattr(sys.modules[_m], "__file__", "") or ""
    if not os.path.abspath(_f).startswith(ROOT):
        del sys.modules[_m]

from config.app_config import cfg                                       # noqa: E402
from layer2.gates import gate_data_instructions, gate_roster            # noqa: E402  (read-only use)
from layer2 import quantity_class as qc                                 # noqa: E402  (FP-suspect classification)

_DEFAULT_GLOBS = ["outputs/_log_archive/**/ai_r_*.jsonl", "outputs/logs/ai_r_*.jsonl"]


# ── corpus parsing ────────────────────────────────────────────────────────────────────────────────────────────────
_SCHEMA_HDR = re.compile(r"^\s*\((column(?: \| [a-z_]+)+)\)\s*$", re.M)
_RUN_HDR = re.compile(r"^RUN:\s*(\S+)\s+CARD:\s*(\S+)\s+PAGE:\s*(\S+)")
_GROUP_HDR = re.compile(r"^GROUP CARD:\s*(true|false)", re.M)
_HANDLING = re.compile(r"handling_class:\s*([\w-]+)")
_ROSTER_SPEC = re.compile(r"^\s*roster_spec \(VERBATIM.*?\):\s*(\{.*\})\s*$", re.M)
_TRUNC = re.compile(r"lower-ranked columns not shown")


def _corpus_files(globs, fresh_only=False):
    pats = [g for g in globs if not fresh_only or "_log_archive" not in g]
    files = []
    for g in pats:
        files += glob(os.path.join(ROOT, g), recursive=True)
    return sorted(set(files))


def _emit_user_message(rec):
    """The L2-emit user message of a logged :8200 call, or None when the call is not an L2 emit."""
    try:
        msgs = rec["request"]["messages"]
        um = [m for m in msgs if m.get("role") == "user"][-1]["content"]
    except (KeyError, IndexError, TypeError):
        return None
    if isinstance(um, str) and um.startswith("RUN: ") and "DB SCHEMA" in um and "CARD:" in um.splitlines()[0]:
        return um
    return None


def _response_content(rec):
    try:
        return rec["response"]["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        return ""


def _parse_emit_json(content):
    """The emit response as a dict, or None (unparseable / truncated / non-dict)."""
    for text in (content, content.strip().strip("`").replace("json\n", "", 1)):
        try:
            d = json.loads(text)
            return d if isinstance(d, dict) else None
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def _cell_value(cell):
    """'name_hint=raw' → 'raw', 'qty=power' → 'power', 'data=Y' → 'Y', plain cells verbatim."""
    head, _, tail = cell.partition("=")
    return tail if head in ("name_hint", "qty", "data", "kind", "has_data") and _ else cell


def parse_basket(um):
    """(basket, truncated) reconstructed from the DB SCHEMA block. Handles all three logged header dialects:
    (column|metric|kind|unit|has_data|rank), (…|name_hint|…|data|rank), (…|name_hint|…|qty|data|rank)."""
    m = _SCHEMA_HDR.search(um)
    if not m:
        return None, False
    names = [n.strip() for n in m.group(1).split("|")]
    cols, truncated = [], False
    for line in um[m.end():].lstrip("\n").splitlines():
        if not line.strip():
            break
        if _TRUNC.search(line):
            truncated = True
            break
        if not line.startswith("  ") or " | " not in line:
            break
        cells = [c.strip() for c in line.split(" | ")]
        if len(cells) < len(names):
            continue
        row = {}
        for name, cell in zip(names, cells):
            row[name] = _cell_value(cell)
        rank_txt = (row.get("rank") or "").split("  ")[0].strip()          # strip the ✗/★ marker after the rank cell
        entry = {
            "column": row.get("column"),
            "metric": row.get("metric") or None,
            "kind": row.get("name_hint") or row.get("kind") or "raw",
            "unit": row.get("unit") or None,
            "has_data": (row.get("data") or row.get("has_data") or "").startswith("Y"),
            "rank": int(rank_txt) if rank_txt.isdigit() else None,
        }
        if "✗ FAILED-VALIDATION" in line:
            entry["verdict"] = "fail"
            entry["validate_reasons"] = ["failed pre-L2 data validation (prompt ✗ marker)"]
        if entry["column"]:
            cols.append(entry)
    # an EMPTY block under the header is a real EMPTY basket (the asset logs no metric columns — the card-74
    # honest-none family), not a parse failure: replay it as columns=[] so the gate's empty-basket carve-out runs.
    return {"columns": cols}, truncated


def parse_header(um):
    first = um.splitlines()[0]
    m = _RUN_HDR.match(first)
    run_id, card_id, page = (m.group(1), m.group(2), m.group(3)) if m else (None, None, None)
    g = _GROUP_HDR.search(um)
    is_group = bool(g and g.group(1) == "true")
    h = _HANDLING.search(um)
    return {"run_id": run_id, "card_id": card_id, "page": page,
            "is_group_card": is_group, "handling_class": h.group(1) if h else None}


def parse_roster_spec(um):
    m = _ROSTER_SPEC.search(um)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


# ── rule attribution ──────────────────────────────────────────────────────────────────────────────────────────────
# reason substrings → wall rule, checked most-specific first (mirrors layer2/gates.py reason texts verbatim).
_RULE_MAP = [
    ("reused across distinct scalar slots", "rule_ii_reuse_smear"),
    ("axis slot bound to", "rule_iiib_axis_coherence"),
    ("never an expected/forecast value", "rule_iiic_expectation"),
    ("topology boundary quantity", "rule_iiid_boundary"),
    ("has no real DB source", "rule_iv_const_source"),
    ("const rating leaf honest-blanks", "rule_iv_const_source"),
    ("nameplate rating denominator is empty", "rule_i_membership"),
    ("not measured on this asset", "rule_i_membership"),                  # derived base column(s) missing
    ("not in this asset's schema", "rule_i_membership"),
    ("not measured by this meter (no ", "rule_iii_quantity_wall"),
    ("failed pre-L2 data validation", "rule_i_membership"),
]

_GATE_ISSUE_MAP = [
    ("not in basket (hallucinated)", "hallucinated_column"),
    ("failed pre-L2 data validation", "validate_fail_column"),
    ("data_instructions.fields is empty", "fields_empty"),
    ("bad source", "bad_source"),
    ("missing a resolved column", "missing_column"),
    ("kind=derived without fn", "derived_without_fn"),
    ("without base_columns", "derived_without_base_columns"),
    ("kind=const without a value", "const_without_value"),
    ("source=$ctx on a non-group card", "ctx_on_non_group_card"),
    ("kind=event without edge", "event_without_edge"),
]

_ROSTER_ISSUE_MAP = [
    ("no roster recipe", "roster_without_recipe"),
    ("not in card recipe", "slot_not_in_recipe"),
    ("not in recipe (invented)", "element_key_invented"),
    ("honest-null in recipe", "honest_null_rebound"),
    ("not in basket (hallucinated)", "roster_column_hallucinated"),
    ("differs from recipe", "agg_differs_from_recipe"),
    ("bad scope", "bad_scope"),
    ("!= recipe", "fixed_key_changed"),
    ("cap ", "cap_exceeded"),
]


def _bucket(text, table, default="other"):
    for needle, name in table:
        if needle in text:
            return name
    return default


# ── FP-suspect classification (mirrors the gate's slot-side evidence order; read-only reuse of quantity_class) ────
def _slot_side_class(f):
    return (qc.slot_class(f.get("slot")) or qc.unit_class(f.get("unit"))
            or qc.unit_class(f.get("_sibling_unit")) or qc.name_class(f.get("_sibling_label")))


def _source_side(f, col_by_name):
    if f.get("kind") == "derived" and f.get("fn"):
        return f"fn:{f.get('fn')}", qc.name_class(f.get("fn"))
    if f.get("column"):
        entry = col_by_name.get(f.get("column")) or {"column": f.get("column")}
        return f"col:{f.get('column')}", qc.column_class(entry)
    if f.get("kind") == "const":
        return f"const:{f.get('value')!r}", None
    return None, None


def _fp_suspect(f, rule, reason, col_by_name, basket_truncated):
    """A review-flag record when the blanked bind's column quantity MATCHES the slot's quantity (same or
    compatible class — per the harness spec, such a blank deserves human/agent review), or when a rule-(i)
    membership blank fired on a TRUNCATED replay basket (a replay artifact, not a live catch)."""
    bind, ccls = _source_side(f, col_by_name)
    scls = _slot_side_class(f)
    match = None
    if scls and ccls:
        if scls == ccls:
            match = "same"
        elif qc.compatible(scls, ccls):
            match = "compatible"
    artifact = basket_truncated and rule == "rule_i_membership"
    if match is None and not artifact:
        return None
    return {"rule": rule, "slot": f.get("slot"), "kind": f.get("kind"), "source": f.get("source"),
            "bind": bind, "slot_class": scls, "source_class": ccls, "quantity_match": match,
            "replay_artifact_basket_truncated": artifact, "reason": reason}


# ── the replay itself ─────────────────────────────────────────────────────────────────────────────────────────────
def replay_emit(resp, um, hdr):
    """One emit through gate_roster → gate_data_instructions (build.py ordering). Returns a result dict."""
    di = copy.deepcopy(resp.get("data_instructions"))
    if not isinstance(di, dict):
        return {"skip": "data_instructions_not_object"}
    basket, truncated = parse_basket(um)
    if basket is None:
        return {"skip": "no_schema_block"}
    col_by_name = {c["column"]: c for c in basket["columns"]}
    fields_optional = hdr.get("handling_class") in set(
        cfg("gates.fields_optional_classes", ["nav_index", "narrative_ai", "topology_sld", "asset_3d", "panel_aggregate"]))
    out = {"basket_truncated": truncated, "basket_columns": len(basket["columns"]),
           "roster_issues": [], "gate_issues": [], "blanked": [], "fields_total": 0,
           "ctx": Counter(), "fp_suspects": []}
    try:
        # roster gate FIRST (load-bearing ordering — a roster-served card legitimately emits fields: [])
        rspec = parse_roster_spec(um)
        if rspec or di.get("roster"):
            _ok_r, r_issues, di["roster"] = gate_roster(di.get("roster") or [], rspec, basket)
            if not rspec:                                                  # build.py's no-recipe normalization
                r_issues = [i for i in r_issues if "no roster recipe" not in i]
                if di.get("roster") == [] and (resp.get("data_instructions") or {}).get("roster"):
                    out["roster_issues"].append("roster emitted for a card with no roster recipe (normalized to [])")
            out["roster_issues"] += r_issues
        orig_fields = [f for f in (di.get("fields") or []) if isinstance(f, dict)]
        out["fields_total"] = len(orig_fields)
        for f in orig_fields:                                              # bypass telemetry BEFORE the walls run
            if f.get("source") == "$ctx":
                out["ctx"]["ctx_fields"] += 1
                if f.get("column") or f.get("fn"):
                    out["ctx"]["ctx_fields_with_measured_bind"] += 1
            if f.get("kind") in ("time", "const", "text") or f.get("source") in ("const", "frame", "$ctx"):
                out["ctx"]["rule_i_exempt_fields"] += 1
        _ok_d, d_issues = gate_data_instructions(
            di, basket, is_group_card=hdr["is_group_card"], fields_optional=fields_optional,
            answerability=resp.get("answerability"),
            exact_metadata=resp.get("exact_metadata") if isinstance(resp.get("exact_metadata"), dict) else None)
        out["gate_issues"] = d_issues
        reasons = list(di.get("_honest_blanked") or [])
        kept_ids = {id(f) for f in (di.get("fields") or []) if isinstance(f, dict)}
        dropped = [f for f in orig_fields if id(f) not in kept_ids]
        for f, reason in zip(dropped, reasons):                            # 1:1, both in field-index order
            rule = _bucket(reason, _RULE_MAP, default="rule_unmapped")
            out["blanked"].append({"rule": rule, "reason": reason, "slot": f.get("slot")})
            if f.get("source") == "$ctx":
                out["ctx"]["ctx_fields_blanked"] += 1
            fp = _fp_suspect(f, rule, reason, col_by_name, truncated)
            if fp:
                out["fp_suspects"].append(fp)
        for f in (di.get("fields") or []):
            if isinstance(f, dict) and f.get("source") == "$ctx":
                out["ctx"]["ctx_fields_kept"] += 1
                if (f.get("column") and f.get("column") not in col_by_name):
                    out["ctx"]["ctx_kept_with_offbasket_column"] += 1      # the rule-(i) $ctx exemption in action
    except Exception as e:                                                 # a malformed emission (non-dict field, …)
        return {"skip": f"replay_error:{type(e).__name__}", "error": str(e)[:200]}
    return out


def run(globs, *, fresh_only=False, max_files=0):
    files = _corpus_files(globs, fresh_only=fresh_only)
    if max_files:
        files = files[:max_files]
    stats = Counter()
    rules = defaultdict(lambda: {"fields_blanked": 0, "emits": set(), "examples": []})
    gate_issues, roster_issues, bypass = Counter(), Counter(), Counter()
    per_card = defaultdict(lambda: Counter())
    fp_suspects, skip_examples = [], defaultdict(list)
    seen = set()
    examples_cap = int(cfg("wall_replay.rule_examples_cap", 3))
    for path in files:
        stats["files"] += 1
        rel = os.path.relpath(path, ROOT)
        try:
            fh = open(path, encoding="utf-8", errors="replace")
        except OSError:
            stats["files_unreadable"] += 1
            continue
        with fh:
            for line_no, line in enumerate(fh, 1):
                stats["records"] += 1
                if "DB SCHEMA" not in line:                                # cheap prefilter: not an L2 emit call
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    stats["records_unparseable_json"] += 1
                    continue
                um = _emit_user_message(rec)
                if um is None:
                    continue
                stats["emit_calls"] += 1
                digest = hashlib.sha1((um + _response_content(rec)).encode("utf-8", "replace")).hexdigest()
                if digest in seen:
                    stats["emit_duplicates"] += 1
                    continue
                seen.add(digest)
                resp = _parse_emit_json(_response_content(rec))
                if resp is None or "data_instructions" not in resp:
                    stats["emits_response_unparseable"] += 1
                    continue
                hdr = parse_header(um)
                res = replay_emit(resp, um, hdr)
                if "skip" in res:
                    key = res["skip"].split(":")[0]
                    stats[f"emits_skipped_{key}"] += 1
                    if len(skip_examples[key]) < examples_cap:
                        skip_examples[key].append({"file": rel, "line": line_no, "run": hdr["run_id"],
                                                   "card": hdr["card_id"], "detail": res.get("error")})
                    continue
                stats["emits_replayed"] += 1
                stats["fields_seen"] += res["fields_total"]
                stats["fields_blanked"] += len(res["blanked"])
                if res["basket_truncated"]:
                    stats["emits_basket_truncated"] += 1
                if not res["basket_columns"]:
                    stats["emits_empty_basket"] += 1
                if hdr["is_group_card"]:
                    bypass["group_card_emits"] += 1
                    bypass["group_card_fields"] += res["fields_total"]
                bypass.update(res["ctx"])
                emit_key = f"{rel}:{line_no}"
                loc = {"file": rel, "line": line_no, "run": hdr["run_id"], "card": hdr["card_id"],
                       "page": hdr["page"]}
                for b in res["blanked"]:
                    r = rules[b["rule"]]
                    r["fields_blanked"] += 1
                    r["emits"].add(emit_key)
                    if len(r["examples"]) < examples_cap:
                        r["examples"].append({**loc, "reason": b["reason"]})
                for i in res["gate_issues"]:
                    gate_issues[_bucket(i, _GATE_ISSUE_MAP)] += 1
                for i in res["roster_issues"]:
                    roster_issues[_bucket(i, _ROSTER_ISSUE_MAP)] += 1
                pc = per_card[hdr["card_id"] or "?"]
                pc["emits"] += 1
                pc["fields"] += res["fields_total"]
                pc["blanked"] += len(res["blanked"])
                pc["fp_suspects"] += len(res["fp_suspects"])
                for fp in res["fp_suspects"]:
                    fp_suspects.append({**loc, **fp})
    return {"stats": stats, "rules": rules, "gate_issues": gate_issues, "roster_issues": roster_issues,
            "bypass": bypass, "per_card": per_card, "fp_suspects": fp_suspects, "skip_examples": skip_examples,
            "files": len(files)}


# ── baseline serialization ────────────────────────────────────────────────────────────────────────────────────────
def _sha(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]
    except OSError:
        return None


def build_baseline(res, globs):
    stats = res["stats"]
    rules = {k: {"fields_blanked": v["fields_blanked"], "emits_touched": len(v["emits"]),
                 "examples": v["examples"]}
             for k, v in sorted(res["rules"].items())}
    fp = res["fp_suspects"]
    return {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool": "tools/wall_corpus_replay.py",
        "acceptance_standard": "all fabrications caught, zero legit binds harmed — diff per_rule + "
                               "false_positive_suspects against this baseline after every wall change",
        "walls_provenance": {"layer2/gates.py": _sha(os.path.join(ROOT, "layer2", "gates.py")),
                             "layer2/quantity_class.py": _sha(os.path.join(ROOT, "layer2", "quantity_class.py"))},
        "corpus": {"globs": globs, "files": res["files"], **{k: stats[k] for k in sorted(stats) if k != "files"}},
        "totals": {
            "emits_replayed": stats["emits_replayed"],
            "fields_seen": stats["fields_seen"],
            "fields_blanked": stats["fields_blanked"],
            "blank_rate": round(stats["fields_blanked"] / stats["fields_seen"], 4) if stats["fields_seen"] else 0,
            "false_positive_suspects": len(fp),
            "fp_replay_artifacts_basket_truncated": sum(1 for s in fp if s["replay_artifact_basket_truncated"]),
        },
        "per_rule": rules,
        "gate_issue_classes": dict(sorted(res["gate_issues"].items())),
        "roster_issue_classes": dict(sorted(res["roster_issues"].items())),
        "bypass": dict(sorted(res["bypass"].items())),
        "per_card": {k: dict(v) for k, v in sorted(res["per_card"].items(), key=lambda kv: str(kv[0]))},
        "skip_examples": {k: v for k, v in sorted(res["skip_examples"].items())},
        "false_positive_suspects": fp,
    }


def render_md(b):
    cap = int(cfg("wall_replay.md_fp_cap", 60))
    L = ["# Wall corpus-replay baseline", "",
         f"Generated {b['generated']} by `{b['tool']}` — gates sha {b['walls_provenance']['layer2/gates.py']}, "
         f"quantity_class sha {b['walls_provenance']['layer2/quantity_class.py']}.", "",
         f"**Acceptance standard:** {b['acceptance_standard']}.", "",
         "## Corpus", ""]
    c = b["corpus"]
    L += [f"- files: {b['corpus']['files']}  ·  records: {c.get('records', 0)}  ·  L2 emit calls: "
          f"{c.get('emit_calls', 0)} (dupes {c.get('emit_duplicates', 0)})",
          f"- emits replayed: {b['totals']['emits_replayed']}  ·  response unparseable (skipped): "
          f"{c.get('emits_response_unparseable', 0)}  ·  other skips: "
          f"{sum(v for k, v in c.items() if k.startswith('emits_skipped_'))}",
          f"- emits with a TRUNCATED prompt basket (rule-(i) blanks are replay artifacts there): "
          f"{c.get('emits_basket_truncated', 0)}", "",
          "## Totals", "",
          f"- fields seen: {b['totals']['fields_seen']}  ·  fields blanked: {b['totals']['fields_blanked']} "
          f"(rate {b['totals']['blank_rate']})",
          f"- suspected false positives: {b['totals']['false_positive_suspects']} "
          f"(of which {b['totals']['fp_replay_artifacts_basket_truncated']} are truncated-basket replay artifacts)",
          "", "## Per-rule blanks", "", "| rule | fields blanked | emits touched |", "|---|---|---|"]
    for k, v in b["per_rule"].items():
        L.append(f"| {k} | {v['fields_blanked']} | {v['emits_touched']} |")
    L += ["", "## Gate issue classes (gate_data_instructions)", "", "| class | count |", "|---|---|"]
    for k, v in b["gate_issue_classes"].items():
        L.append(f"| {k} | {v} |")
    L += ["", "## Roster issue classes (gate_roster)", "", "| class | count |", "|---|---|"]
    for k, v in b["roster_issue_classes"].items():
        L.append(f"| {k} | {v} |")
    L += ["", "## Bypass counts", "", "| bypass | count |", "|---|---|"]
    for k, v in b["bypass"].items():
        L.append(f"| {k} | {v} |")
    L += ["", f"## Suspected false positives (first {cap} — full list in wall_replay_baseline.json)", "",
          "A blanked bind whose column quantity MATCHES its slot's quantity (or a rule-(i) blank on a "
          "truncated replay basket). Review each: a real catch stays; a harmed legit bind is a wall bug.", "",
          "| file:line | run | card | rule | slot | bind | slot_cls | src_cls | match | artifact |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for s in b["false_positive_suspects"][:cap]:
        L.append(f"| {s['file']}:{s['line']} | {s['run']} | {s['card']} | {s['rule']} | {s['slot']} | {s['bind']} "
                 f"| {s['slot_class']} | {s['source_class']} | {s['quantity_match']} "
                 f"| {'Y' if s['replay_artifact_basket_truncated'] else ''} |")
    L += ["", "## How to use (future wall changes)", "",
          "1. `PYTHONPATH=. python3.11 tools/wall_corpus_replay.py --out-json /tmp/after.json --out-md /tmp/after.md`",
          "2. Diff `per_rule`, `bypass`, `false_positive_suspects` vs this committed baseline.",
          "3. Standard: every NEW blank must be a real fabrication; every VANISHED blank must be an intended "
          "release; the FP-suspect list must not grow with quantity-matching binds.", ""]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-json", default=os.path.join(ROOT, "outputs", "wall_replay_baseline.json"))
    ap.add_argument("--out-md", default=os.path.join(ROOT, "outputs", "wall_replay_baseline.md"))
    ap.add_argument("--max-files", type=int, default=0, help="cap corpus files (smoke)")
    ap.add_argument("--fresh-only", action="store_true", help="outputs/logs only (skip the archive)")
    args = ap.parse_args(argv)
    globs = list(cfg("wall_replay.corpus_globs", _DEFAULT_GLOBS) or _DEFAULT_GLOBS)
    res = run(globs, fresh_only=args.fresh_only, max_files=args.max_files)
    baseline = build_baseline(res, globs)
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(baseline, f, indent=1, default=str)
    with open(args.out_md, "w", encoding="utf-8") as f:
        f.write(render_md(baseline))
    t = baseline["totals"]
    print(f"wall_corpus_replay: {t['emits_replayed']} emits replayed "
          f"({baseline['corpus'].get('emits_response_unparseable', 0)} unparseable skipped) — "
          f"{t['fields_blanked']}/{t['fields_seen']} fields blanked, "
          f"{t['false_positive_suspects']} FP suspects "
          f"({t['fp_replay_artifacts_basket_truncated']} truncation artifacts)")
    print(f"baseline → {args.out_json}\nreport   → {args.out_md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
