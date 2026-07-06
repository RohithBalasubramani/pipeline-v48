"""scripts/rescan_stripped_payloads.py — prove card_payloads.payload_stripped is at ZERO across EVERY seed class.

The verification harness for the stored skeletons (run AFTER scripts/build_stripped_payloads.py):
  1. CLASS COUNTERS over all rows — each residual seed class must be 0:
       numeric        — a NONZERO number outside the design-chrome/dictionary subtrees (vocab.chrome_subtree_keys +
                        role_scrub.dictionary_subtree_keys are the ONLY sanctioned nonzero-number homes).
       temporal       — a string matching the concrete date/clock detector (scrub.temporal_pattern).
       string_role    — an active/derived/event assertion string or fabricated MFM pointer (the role_scrub classes),
                        proven via the fixed-point check below (a survivor would change under a re-scrub).
       boolean        — a boolean array containing ANY true (an occurrence assertion at rest).
       embedded       — an annotation string embedding a measurement beside a numeric data sibling
                        (scrub.embedded_number_pattern + measured_annotation_keys role).
       axis_strings   — an all-numeric-string array at an axis role key (vocab.numeric_axis_keys).
       event_skeleton — a non-empty list at an event-parent key (role_scrub.event_parents).
  2. FIXED-POINT (covers string_role + everything else the strip owns): re-running the canonical strip+scrub over the
     STORED skeleton must be byte-identical — payload_stripped is a fixed point of its own builder (idempotence).
  3. DICTIONARY PRESERVATION — two tiers matching the strip's KEEP contract:
       strict — every *Vocab / enum-map (complianceWords/eventTypeKeys/driverCodeMap/eventModeOrder) / design-chrome
                (vocab.chrome_subtree_keys — bandThresholds/IEEE limits/…) subtree survives BYTE-IDENTICAL.
       mixed  — a presentation container (legend/statusLegend/palette/presentation) keeps every lookup WORD: its
                string leaves are preserved EXCEPT the two sanctioned data transforms that legitimately reach inside
                (a numeric-STRING KPI value beside a label — legend[].value '2' is a seed count = data; a
                narrative_slots KEY — trendLabel — scrubbed by the key rule since before this harness).

Exit 0 = all classes ZERO, every row a fixed point, every dictionary preserved. Exit 1 otherwise (offenders printed).
Run:  PYTHONPATH=/home/rohith/desktop/BFI/backend/layer2/pipeline_v48 \
      /home/rohith/.pyenv/versions/3.11.9/bin/python3.11 scripts/rescan_stripped_payloads.py
"""
import json
import sys

from data.db_client import q
from grounding.default_assemble import _CLOCK_STR, _strip_and_scrub
from grounding.exemplar_reduce import reduce_repeated
from grounding.measured_annotation_scrub import _annotation_keys, _is_num, _pattern
from grounding.role_scrub import _dictionary_subtree_keys, _event_parents
from validate.leaf_classify import _chrome_subtree_keys, _num_str, _numeric_axis_keys


def _jload(v):
    return v if isinstance(v, (dict, list)) else json.loads(v)


def scan_classes(payload, dict_keys, chrome_keys, event_parents, axis_keys, ann_keys, emb_pat):
    """The per-row residual-seed class hits: [(class, path, value), ...]."""
    hits = []

    def walk(o, path):
        if isinstance(o, dict):
            has_num_sib = any(_is_num(v) for v in o.values())
            for k, v in o.items():
                kl = str(k).lower()
                if "vocab" in kl or kl in dict_keys or kl in chrome_keys:
                    continue                                     # sanctioned dictionary / design-chrome subtree
                child = f"{path}.{k}" if path else k
                if isinstance(v, str):
                    if _CLOCK_STR.search(v):
                        hits.append(("temporal", child, v))
                    if has_num_sib and kl in ann_keys and emb_pat.search(v):
                        hits.append(("embedded", child, v))
                elif _is_num(v):
                    if v != 0:
                        hits.append(("numeric", child, v))
                elif isinstance(v, list):
                    if v and all(isinstance(x, bool) for x in v) and any(v):
                        hits.append(("boolean", child, f"{sum(v)} true"))
                    if v and all(isinstance(x, str) and _num_str(x) for x in v) and kl in axis_keys:
                        hits.append(("axis_strings", child, v[:3]))
                    if kl in event_parents and v:
                        hits.append(("event_skeleton", child, f"{len(v)} elements"))
                    walk(v, child)
                elif isinstance(v, dict):
                    walk(v, child)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")

    walk(payload, "")
    return hits


def dict_subtrees(payload, dict_keys):
    """{path: subtree} for every dictionary/design-chrome subtree in a payload (the byte-identity KEEP set)."""
    out = {}

    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                kl = str(k).lower()
                child = f"{path}.{k}" if path else k
                if "vocab" in kl or kl in dict_keys:
                    out[child] = v
                    continue
                walk(v, child)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")

    walk(payload, "")
    return out


def _string_words(subtree, narrative, num_str):
    """{leaf_path: string} of a MIXED presentation container's lookup WORDS — every string leaf EXCEPT the two
    sanctioned data transforms (a numeric-STRING measured value; a narrative_slots key)."""
    out = {}

    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                child = f"{path}.{k}" if path else k
                if isinstance(v, str):
                    if str(k).lower() not in narrative and not num_str(v):
                        out[child] = v
                else:
                    walk(v, child)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")

    walk(subtree, "")
    return out


def main():
    from grounding.default_assemble import _narrative_slots
    dict_keys = _dictionary_subtree_keys()
    chrome_keys = _chrome_subtree_keys()
    event_parents = _event_parents()
    axis_keys = _numeric_axis_keys()
    ann_keys = _annotation_keys()
    emb_pat = _pattern()
    narrative = _narrative_slots()
    mixed_dicts = {"legend", "statuslegend", "palette", "presentation"}   # WORD-preservation tier (numbers are data)

    rows = q("cmd_catalog", "SELECT story_id, payload, payload_stripped FROM card_payloads ORDER BY story_id")
    counts = {k: 0 for k in ("numeric", "temporal", "boolean", "embedded", "axis_strings", "event_skeleton")}
    offenders, not_fixed_point, dict_broken, null_rows = [], [], [], []

    for story_id, raw, stored in rows:
        if stored is None:
            null_rows.append(story_id)
            continue
        raw, stored = _jload(raw), _jload(stored)
        for cls, path, val in scan_classes(stored, dict_keys, chrome_keys, event_parents, axis_keys,
                                           ann_keys, emb_pat):
            counts[cls] += 1
            offenders.append((cls, story_id, path, val))
        # fixed point: the stored skeleton must be invariant under its own strip+scrub (string_role incl.)
        if reduce_repeated(_strip_and_scrub(stored), stored) != stored:
            not_fixed_point.append(story_id)
        # dictionary preservation — strict tier: *Vocab / enum-map / chrome subtrees BYTE-IDENTICAL;
        # mixed tier (legend/statusLegend/palette/presentation): every lookup WORD preserved.
        raw_dicts = dict_subtrees(raw, dict_keys | chrome_keys)
        stored_dicts = dict_subtrees(stored, dict_keys | chrome_keys)
        for p, v in raw_dicts.items():
            if p not in stored_dicts:
                continue                                          # collapsed exemplar sibling (paths beyond [0])
            leaf = p.rsplit(".", 1)[-1].split("[", 1)[0].lower()
            if leaf in mixed_dicts:
                rw = _string_words(v, narrative, _num_str)
                sw = _string_words(stored_dicts[p], narrative, _num_str)
                for wp, word in rw.items():
                    if wp in sw and sw[wp] != word:
                        dict_broken.append((story_id, f"{p}{wp} ({word!r} → {sw[wp]!r})"))
            elif stored_dicts[p] != v:
                dict_broken.append((story_id, p))

    print(f"rescan_stripped_payloads: rows={len(rows)}  null_stripped={len(null_rows)}")
    print("  class counts (all must be 0): " + "  ".join(f"{k}={v}" for k, v in counts.items()))
    print(f"  string_role/fixed-point violations: {len(not_fixed_point)}")
    print(f"  dictionary subtrees broken: {len(dict_broken)}")
    for cls, sid, path, val in offenders[:50]:
        print(f"    LEAK [{cls}] {sid} :: {path} = {str(val)[:70]}")
    for sid in not_fixed_point[:20]:
        print(f"    NOT-FIXED-POINT {sid}")
    for sid, p in dict_broken[:20]:
        print(f"    DICT-BROKEN {sid} :: {p}")
    ok = not offenders and not not_fixed_point and not dict_broken and not null_rows
    print("RESULT:", "ZERO — all classes clean, idempotent, dictionaries preserved" if ok else "LEAKS FOUND")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
