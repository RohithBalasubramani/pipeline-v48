"""scripts/audit_role_scrub_coverage.py -- OFFLINE build-time coverage audit for grounding.role_scrub (T1-13).

ZERO-RUNTIME TOOL. The pipeline NEVER imports this file. It is an operator-run analyzer that surfaces the ONE
structural blind spot in grounding.role_scrub.scrub_active_string_leaves: the scrub blanks an ACTIVE, data-derived
STRING leaf only when its SLOT ROLE is recognised by a `role_scrub.*` vocabulary (a known active-state parent, a known
verdict/identity key, a *tone suffix, an event parent, a metric-value parent, an MFM pointer). A payload that ships a
NEW active-state key under an UNRECOGNISED parent (e.g. `customWidget.verdict='Elevated'`) falls through EVERY rule and
its fabricated Storybook value replays as if live. Type-strip + narrative-scrub already ran (this reads payload_stripped,
the persisted output of grounding.default_assemble.strip_to_placeholders), so a non-empty string still standing there is,
by construction, a string NO deterministic policy touched.

FLOW (AI proposes, deterministic filters gate, a HUMAN applies):
  1. Read card_payloads.payload_stripped for every story.
  2. collect_survivors(): deep-copy each tree, re-run scrub_active_string_leaves(copy, SENTINEL), parallel-walk the
     original vs the scrubbed copy. A non-empty, non-numeric, non-placeholder string leaf that is EQUAL in both trees
     survived every vocab rule. Dictionary subtrees the scrub keeps (*Vocab / legend / bandThresholds / ...) are skipped
     exactly as the scrub's walk skips them -- they are legitimate lookup chrome, not blind spots. (pure fn)
  3. dedup_survivors(): unique by (parent_key, key, value), capped at --limit (default 400). (pure fn)
  4. Reachability probe (mirror copilot/build/alias_build.py): LLM down -> print + exit 0, never a partial artifact.
  5. ONE batched LLM call classifies each survivor {live_assertion, rule_row, token} against the role-scrub taxonomy.
  6. post_validate(): keep ONLY proposals whose rule_row is a real seeded role_scrub.* row AND whose token literally
     appears as a key/parent in the survivor set; drop dictionary-subtree-key collisions and non-live-assertion items.
     The model can never invent a row name or a token this way. (pure fn)
  7. build_sql(): emit outputs/proposed_role_scrub_additions_<tag>.sql -- a COMMENTED-OUT, human-review INSERT ...
     ON CONFLICT DO UPDATE with MERGED json lists. NOTHING is applied; the operator uncomments after review and re-runs
     scripts/build_stripped_payloads.py (payload_stripped is derived from these rows).

The survivor-collection and post-validation are PURE, importable, offline-testable functions (tests/test_role_scrub_audit.py).
Every DB / LLM import is lazy (inside main) so importing this module has NO side effects and needs no services.

Run:  PYTHONPATH=/home/rohith/desktop/BFI/backend/layer2/pipeline_v48 python3 scripts/audit_role_scrub_coverage.py \
        --tag 2026-07-14 --limit 400
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys

SENTINEL = "\x00SENTINEL\x00"
DEFAULT_LIMIT = 400

# Values that are a strip/host PLACEHOLDER, never a fabricated datum -- skipped as survivors (empty is skipped too).
# "\u2014" is the em-dash the host renders for an honest-blank scalar (kept as an escape for ASCII-safe source).
PLACEHOLDER_STRINGS = {SENTINEL, "\u2014", "-", "--", "n/a", "na", "null", "none"}

# Code-default mirror of the role_scrub.* list rows (db/seed_role_scrub_vocab.sql). Used only if cmd_catalog has no
# seeded rows to merge into, so the SQL builder can still produce a complete merged list. Kept in step with the seed.
KNOWN_ROLE_SCRUB_DEFAULTS = {
    "role_scrub.derived_pick_parents": ["worst", "selectedpanel"],
    "role_scrub.active_value_keys": [
        "label", "statuslabel", "statuskey", "tone", "dstone", "status", "key", "driver", "driverkey", "cause",
        "causekey", "insightkey", "ieeestate", "availability", "severity", "severitylabel", "severityaction",
        "table", "id", "panel", "deltatone"],
    "role_scrub.active_state_parents": [
        "status", "statusbadge", "badge", "freshness", "ieeebadge", "state", "service"],
    "role_scrub.roster_parents": ["panels", "periods"],
    "role_scrub.roster_identity_keys": ["id", "panel"],
    "role_scrub.roster_blank_keys": ["status", "cause", "causekey", "driver", "driverkey", "table"],
    "role_scrub.event_parents": ["anomalies", "events", "event", "anomaly"],
    "role_scrub.event_value_keys": ["title", "label", "type", "severity", "status"],
    "role_scrub.dictionary_subtree_keys": [
        "statusvocab", "insightvocab", "causevocab", "drivervocab", "notevocab", "vocab", "compliancewords",
        "eventtypekeys", "drivercodemap", "eventmodeorder", "eventcolumn", "statuslegend", "bandthresholds",
        "legend", "palette", "presentation"],
    "role_scrub.global_active_keys": [
        "ieeestate", "filterstate", "availability", "capacitorbank", "severityaction", "severitylabel",
        "insightkey", "statuslabel", "statuskey", "mode"],
    "role_scrub.reference_line_parents": ["referencelines", "watchlines"],
    "role_scrub.metric_value_parents": [
        "stats", "stat", "metrics", "metric", "kpis", "kpi", "kpicells", "kpicell", "cells", "tiles",
        "scorecells", "summarystats", "quickstats"],
    "role_scrub.metric_value_keys": ["value", "displayvalue"],
}
# Scalar (non-list) role_scrub rows -- a token cannot be MERGED into these; a proposal targeting one is flagged, not merged.
SCALAR_ROLE_SCRUB_ROWS = {"role_scrub.tone_key_suffix", "role_scrub.mfm_pointer_pattern"}


# -- deterministic helpers (pure, offline) -------------------------------------------------------------

def _is_numeric_str(s):
    """Mirror grounding.role_scrub._is_numeric: a string that reads as a number (incl. thousands/percent) is a datum
    already handled by leaf_classify, not a role blind spot."""
    try:
        float(str(s).replace(",", "").replace("%", "").strip())
        return True
    except (TypeError, ValueError):
        return False


def _is_placeholder_str(s):
    return s.strip().lower() in PLACEHOLDER_STRINGS or s == SENTINEL


def _default_dict_subtree_keys():
    """The dictionary-subtree KEEP keys, from the live role_scrub policy when importable (code defaults when the DB is
    absent), else the seed mirror. Skipping these mirrors the scrub's own walk, which never descends into them."""
    try:
        from grounding.role_scrub import _dictionary_subtree_keys  # lazy: no import-time DB/config dependency
        keys = _dictionary_subtree_keys()
        if keys:
            return set(keys)
    except Exception:
        pass
    return set(KNOWN_ROLE_SCRUB_DEFAULTS["role_scrub.dictionary_subtree_keys"])


def _skip_subtree_key(kl, dict_keys):
    """True when descending into key `kl` (lowercased) would enter a lookup-dictionary subtree the scrub keeps
    byte-identical -- the same test the scrub's walk applies ('vocab' substring OR membership)."""
    return "vocab" in kl or kl in dict_keys


# -- pure fn #1: survivor collection -------------------------------------------------------------------

def collect_survivors(story_id, tree, scrub_fn, ph=SENTINEL, dict_keys=None):
    """PURE. Deep-copy `tree`, run `scrub_fn(copy, ph)` (grounding.role_scrub.scrub_active_string_leaves in prod, a
    fake in tests), then parallel-walk the ORIGINAL against the SCRUBBED copy. Collect every non-empty string leaf that
    is EQUAL in both trees (i.e. the scrub did NOT blank it -> it survived every vocab rule), EXCLUDING:
      - strings inside a dictionary subtree (mirrors the scrub's own walk skip; legitimate lookup chrome),
      - numeric-looking strings (data already zeroed by leaf_classify),
      - placeholder strings (SENTINEL / em-dash / n-a / ...).
    `parent_chain` matches the scrub's `ancestors` model: the lowercased key chain of the CONTAINING objects, a list
    index contributing NO key -- so a collected token maps 1:1 onto what a role_scrub.* parent/key list would test.
    Returns a list of {story_id, path, parent_chain, parent_key, key, value}. Never mutates the caller's tree."""
    if dict_keys is None:
        dict_keys = _default_dict_subtree_keys()
    dict_keys = {str(k).strip().lower() for k in dict_keys}

    original = tree
    scrubbed = copy.deepcopy(tree)
    try:
        scrub_fn(scrubbed, ph)
    except Exception:
        # A scrub blow-up must not sink the audit; treat the copy as unscrubbed (everything then reads as surviving).
        scrubbed = copy.deepcopy(tree)

    out = []

    def walk(orig, scrub, parent_chain, path):
        if isinstance(orig, dict):
            scrub_d = scrub if isinstance(scrub, dict) else {}
            for k in list(orig.keys()):
                kl = str(k).lower()
                if _skip_subtree_key(kl, dict_keys):
                    continue                                  # never descend into a kept dictionary subtree
                ov = orig[k]
                sv = scrub_d.get(k)
                child_path = (path + "." + str(k)) if path else str(k)
                if isinstance(ov, str):
                    val = ov.strip()
                    if not val or _is_placeholder_str(ov) or _is_numeric_str(val):
                        continue
                    # survived iff the scrub left the leaf byte-identical (a blanked leaf is now `ph`, i.e. != ov)
                    if isinstance(sv, str) and sv == ov:
                        out.append({
                            "story_id": story_id,
                            "path": child_path,
                            "parent_chain": list(parent_chain),
                            "parent_key": parent_chain[-1] if parent_chain else "",
                            "key": kl,
                            "value": ov,
                        })
                else:
                    walk(ov, sv, parent_chain + [kl], child_path)
        elif isinstance(orig, list):
            scrub_l = scrub if isinstance(scrub, list) else []
            for i, ov in enumerate(orig):
                sv = scrub_l[i] if i < len(scrub_l) else None
                child_path = path + "[" + str(i) + "]"
                if isinstance(ov, str):
                    continue                                  # a bare list-of-strings has no key/parent to add a rule for
                walk(ov, sv, parent_chain, child_path)

    walk(original, scrubbed, [], "")
    return out


def dedup_survivors(survivors, limit=DEFAULT_LIMIT):
    """PURE. Unique the survivors by (parent_key, key, value) -- the same (role-slot, token, value) surfaces once no
    matter how many stories carry it -- preserving first-seen order, then cap the batch at `limit`."""
    seen = set()
    unique = []
    for s in survivors:
        sig = (s.get("parent_key", ""), s.get("key", ""), s.get("value", ""))
        if sig in seen:
            continue
        seen.add(sig)
        unique.append(s)
    if limit and limit > 0:
        return unique[:limit]
    return unique


# -- pure fn #2: post-validation of the LLM proposals --------------------------------------------------

def _survivor_token_set(survivors):
    """Every key AND parent-chain entry (lowercased) present across the survivor set -- the ONLY tokens a proposal may
    reference. Anything outside this set is an LLM invention and is dropped."""
    toks = set()
    for s in survivors:
        if s.get("key"):
            toks.add(str(s["key"]).lower())
        for a in s.get("parent_chain", []) or []:
            if a:
                toks.add(str(a).lower())
    return toks


def post_validate(proposals, survivors, seeded_rows, dict_keys=None):
    """PURE. Deterministic gate over the LLM proposals. Keep a proposal ONLY when ALL hold:
      - live_assertion is truthy (the model judged the survivor a live, data-derived assertion, not static chrome),
      - rule_row is a REAL seeded role_scrub.* row name (never an invented target),
      - token literally appears as a key/parent in the survivor set (never an invented token),
      - token is NOT itself a dictionary-subtree key (adding a lookup-chrome key as an active rule would be wrong).
    Returns the kept proposals, each normalised to {live_assertion, rule_row, token, index?}."""
    if dict_keys is None:
        dict_keys = _default_dict_subtree_keys()
    dict_keys = {str(k).strip().lower() for k in dict_keys}
    seeded = {str(r).strip() for r in (seeded_rows or ())}
    tokens = _survivor_token_set(survivors)

    kept = []
    for p in proposals or ():
        if not isinstance(p, dict):
            continue
        if not bool(p.get("live_assertion")):
            continue
        rule_row = str(p.get("rule_row", "")).strip()
        token = str(p.get("token", "")).strip().lower()
        if rule_row not in seeded:
            continue                                          # invented / unknown rule row
        if not token or token not in tokens:
            continue                                          # invented token (not in any survivor)
        if token in dict_keys or "vocab" in token:
            continue                                          # dictionary-subtree collision
        out = {"live_assertion": True, "rule_row": rule_row, "token": token}
        if "index" in p:
            out["index"] = p["index"]
        kept.append(out)
    return kept


# -- SQL emission (commented, human-review) ------------------------------------------------------------

def build_sql(kept_proposals, current_rows, runtag):
    """Render a COMMENTED-OUT review script: for each affected role_scrub.* LIST row, one INSERT ... ON CONFLICT DO
    UPDATE whose value is the CURRENT list MERGED with the proposed tokens (deduped, order-preserving). Scalar rows
    (tone_key_suffix / mfm_pointer_pattern) are noted, never merged. NOTHING is applied -- every line is a comment."""
    current_rows = current_rows or {}
    # group tokens by rule_row (order-preserving, deduped)
    by_row = {}
    for p in kept_proposals or ():
        by_row.setdefault(p["rule_row"], [])
        if p["token"] not in by_row[p["rule_row"]]:
            by_row[p["rule_row"]].append(p["token"])

    lines = []
    lines.append("-- outputs/proposed_role_scrub_additions_" + str(runtag) + ".sql")
    lines.append("-- AUTO-PROPOSED role_scrub vocab additions (scripts/audit_role_scrub_coverage.py, tag=" + str(runtag) + ").")
    lines.append("-- REVIEW before applying; re-run build_stripped_payloads.py after.")
    lines.append("-- Every statement below is COMMENTED OUT and is NEVER applied automatically. Uncomment to apply.")
    lines.append("--")
    if not by_row:
        lines.append("-- (no validated additions this run)")
        return "\n".join(lines) + "\n"

    for row_name in sorted(by_row):
        tokens = by_row[row_name]
        if row_name in SCALAR_ROLE_SCRUB_ROWS:
            lines.append("-- rule_row " + row_name + " is a SCALAR (not a token list) -- MANUAL review of: "
                         + ", ".join(tokens))
            lines.append("--")
            continue
        current = current_rows.get(row_name)
        if not isinstance(current, list):
            current = list(KNOWN_ROLE_SCRUB_DEFAULTS.get(row_name, []))
        merged = list(current)
        added = []
        for t in tokens:
            if t not in merged:
                merged.append(t)
                added.append(t)
        if not added:
            lines.append("-- rule_row " + row_name + " -- all proposed tokens already present ("
                         + ", ".join(tokens) + "); no change")
            lines.append("--")
            continue
        key = "vocab." + row_name
        note = ("AUDIT-PROPOSED " + str(runtag) + ": +[" + ", ".join(added)
                + "] -- REVIEW; re-run build_stripped_payloads.py")
        lines.append("-- rule_row " + row_name + "  (+" + str(len(added)) + " token(s): " + ", ".join(added) + ")")
        lines.append("-- INSERT INTO app_config (key, value, data_type, section, note) VALUES")
        lines.append("--  ('" + key + "',")
        lines.append("--   '" + json.dumps(merged) + "',")
        lines.append("--   'json', 'vocab',")
        lines.append("--   '" + note.replace("'", "''") + "')")
        lines.append("-- ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;")
        lines.append("--")
    return "\n".join(lines) + "\n"


# -- LLM taxonomy prompt -------------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You audit an electrical-monitoring dashboard payload for FABRICATED live values that a deterministic scrubber "
    "missed. The scrubber (role_scrub) BLANKS a STRING leaf when its slot ROLE is a live, data-derived assertion -- a "
    "verdict/status, a derived pick (which panel scored worst), an event/anomaly title, a KPI text descriptor, an "
    "operating mode, a fabricated meter pointer. It KEEPS lookup-dictionary/enum/legend/palette chrome and pure "
    "presentation labels/units/colors. Each input line is a STRING that SURVIVED the scrubber. For each, decide if the "
    "VALUE is a live, data-derived assertion that SHOULD be blanked (live_assertion=true) or is legitimate static "
    "chrome (units, colors, axis labels, captions, option-set text -> live_assertion=false).\n"
    "If live_assertion is true, name the role_scrub.* row that should learn a new token, and the token (a KEY or a "
    "PARENT key from that same line) to add. Choose the row by role:\n"
    "  role_scrub.active_state_parents  -- add a PARENT key that names an active-state object (status/badge-like)\n"
    "  role_scrub.active_value_keys     -- add a verdict/identity KEY blanked inside an active-state/derived-pick object\n"
    "  role_scrub.global_active_keys    -- add a KEY that asserts the live condition by its OWN name, any parent\n"
    "  role_scrub.derived_pick_parents  -- add a PARENT key whose whole object is a data-derived pick\n"
    "  role_scrub.roster_parents / roster_blank_keys -- roster list parent / derived per-row fact key\n"
    "  role_scrub.event_parents / event_value_keys   -- event/anomaly list parent / asserted-what-happened key\n"
    "  role_scrub.metric_value_parents / metric_value_keys -- KPI/stat container parent / datum key\n"
    "The token MUST be the 'key' or one of the 'parent_chain' entries on the SAME line. Never invent a row name or a "
    "token. Reply with ONE JSON object: {\"proposals\":[{\"index\":<int>,\"live_assertion\":<bool>,"
    "\"rule_row\":\"role_scrub.*\",\"token\":\"<key-or-parent>\"}]} -- one entry per input line, echoing its index."
)


def _llm_user_payload(survivors):
    """One compact JSON line per survivor (index + the role slot the model reasons over)."""
    lines = []
    for i, s in enumerate(survivors):
        lines.append(json.dumps({
            "index": i,
            "path": s.get("path"),
            "parent_chain": s.get("parent_chain"),
            "key": s.get("key"),
            "value": s.get("value"),
        }))
    return "SURVIVORS (one per line):\n" + "\n".join(lines)


# -- live I/O (lazy; never touched at import) ----------------------------------------------------------

def _llm_is_up(timeout=3.0):
    """Reachability probe for the pipeline vLLM endpoint (mirror copilot/build/alias_build.py's is_up guard). A GET on
    <base>/models that lists the configured model == up. Any error == down. No completion is spent."""
    try:
        import urllib.request
        from llm.config import LLM_URL, MODEL
        base = LLM_URL.rsplit("/chat/completions", 1)[0].rstrip("/")
        req = urllib.request.Request(base + "/models")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = json.loads(r.read().decode())
        return any(m.get("id") == MODEL for m in body.get("data", []))
    except Exception:
        return False


def _propose(survivors):
    """ONE batched classification call to the pipeline LLM. Returns the parsed proposals list (or [] on any LLM error;
    the caller has already confirmed reachability, so this only guards a mid-call transport blip)."""
    from llm.client import call_qwen
    result = call_qwen(_SYSTEM_PROMPT, _llm_user_payload(survivors),
                       stage="role_scrub_audit", on_error="marker")
    if not isinstance(result, dict) or "_llm_error" in result:
        print("  [llm] classification call failed ("
              + str((result or {}).get("_llm_error", "non-dict reply")) + ") -- emitting header-only", file=sys.stderr)
        return []
    props = result.get("proposals")
    return props if isinstance(props, list) else []


def _fetch_seeded_rows():
    """The live role_scrub.* rows from cmd_catalog.app_config -> ({row_name: current_value}, {row_name}). Falls back to
    the code-default mirror if the DB has no rows (so the SQL merge still lists a complete value)."""
    current, names = {}, set()
    try:
        from data.db_client import pg_connect
        conn = pg_connect("cmd_catalog")
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT key, value FROM app_config WHERE key LIKE 'vocab.role_scrub.%%'")
                for key, value in cur.fetchall():
                    row_name = key[len("vocab."):] if key.startswith("vocab.") else key
                    names.add(row_name)
                    try:
                        current[row_name] = json.loads(value) if isinstance(value, str) else value
                    except Exception:
                        current[row_name] = value
        finally:
            conn.close()
    except Exception as e:
        print("  [db] app_config role_scrub read failed (" + type(e).__name__ + ") -- using code-default mirror",
              file=sys.stderr)
    if not names:
        current = {k: list(v) for k, v in KNOWN_ROLE_SCRUB_DEFAULTS.items()}
        names = set(KNOWN_ROLE_SCRUB_DEFAULTS.keys()) | SCALAR_ROLE_SCRUB_ROWS
    else:
        names |= SCALAR_ROLE_SCRUB_ROWS
    return current, names


def _read_payloads():
    """(story_id, tree) for every card, from cmd_catalog.card_payloads.payload_stripped (jsonb -> dict via psycopg2;
    a str is parsed defensively). A NULL/empty skeleton is skipped."""
    from data.db_client import pg_connect
    conn = pg_connect("cmd_catalog")
    rows = []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT story_id, payload_stripped FROM card_payloads ORDER BY story_id")
            for story_id, payload in cur.fetchall():
                if payload is None:
                    continue
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except Exception:
                        continue
                rows.append((story_id, payload))
    finally:
        conn.close()
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description="Offline coverage audit for grounding.role_scrub (T1-13).")
    ap.add_argument("--tag", default="manual",
                    help="run tag stamped into the output filename/header (Date.now is unavailable here).")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                    help="max unique survivors sent to the LLM in one batch (default 400).")
    ap.add_argument("--out", default=None, help="output .sql path (default outputs/proposed_role_scrub_additions_<tag>.sql).")
    ap.add_argument("--dump-only", action="store_true",
                    help="collect + print survivors and exit; skip the LLM and SQL emission.")
    args = ap.parse_args(argv)

    # lazy: the real scrub (import-safe; falls back to code-default vocab if cmd_catalog is unreachable).
    from grounding.role_scrub import scrub_active_string_leaves

    payloads = _read_payloads()
    all_survivors = []
    for story_id, tree in payloads:
        all_survivors.extend(collect_survivors(story_id, tree, scrub_active_string_leaves))
    survivors = dedup_survivors(all_survivors, limit=args.limit)
    print("survivors: " + str(len(all_survivors)) + " raw across " + str(len(payloads))
          + " cards, " + str(len(survivors)) + " unique (capped at " + str(args.limit) + ")")

    if args.dump_only:
        for s in survivors:
            print(json.dumps(s, sort_keys=True))
        return 0

    if not _llm_is_up():
        print("LLM endpoint unreachable - aborting")
        return 0

    proposals = _propose(survivors)
    current_rows, seeded_names = _fetch_seeded_rows()
    kept = post_validate(proposals, survivors, seeded_names)
    print("proposals: " + str(len(proposals)) + " from LLM, " + str(len(kept)) + " passed deterministic validation")

    sql = build_sql(kept, current_rows, args.tag)
    out_path = args.out or os.path.join(_repo_root(), "outputs",
                                        "proposed_role_scrub_additions_" + str(args.tag) + ".sql")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(sql)
    print("wrote " + out_path + " (REVIEW before applying; NEVER auto-applied)")
    return 0


def _repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


if __name__ == "__main__":
    sys.exit(main())
