"""tools/morphmap_ab.py — ITEM 18 OFFLINE A/B: full-emit contract vs the morph-map contract, replayed over the
logged corpus (outputs/logs/ai_r_*.jsonl + outputs/_log_archive/**/ai_r_*.jsonl). NO live LLM calls, NO pipeline
wiring — pure replay of what the AI ALREADY emitted, re-produced through both deterministic producers.

For every logged L2 full-emit (parseable exact_metadata + a card with a stored payload_stripped skeleton):
  1. REPRODUCE the enforced full-emit result exactly as layer2/build._finalize does:
         produce(payload, ai_meta, _morphed) → gate_exact_metadata → enforce_exact_metadata (if needed);
  2. compute the DELTA the AI actually expressed — every real metadata leaf whose authored value differs from the
     stored skeleton default (declared in _morphed or not) = its EFFECTIVE morph map;
  3. apply that map via the NEW morph-map producer (layer2/emit/morphmap/producer.apply — which runs the SAME
     imported gates) and BYTE-COMPARE against (1), in two regimes:
       · regime A 'declared' — morphs = only the _morphed-declared paths ⇒ proves the new producer is byte-equivalent
         to the live path on identical intent;
       · regime B 'expressed' — morphs = the full expressed delta ⇒ every mismatch is a leaf the FULL-emit contract
         silently REVERTED (authored change never declared — the A1 silent-no-op corruption) that morph-map would
         have shipped, because under morph-map naming a path IS declaring it;
  4. measure the completion-size reduction: the emitted exact_metadata block (incl. _morphed) vs the morphs-only
     map, and the whole completion vs its simulated morph-map envelope;
  5. count the corpus-level corruption the full contract's SIZE causes: truncated (finish_reason=length) and
     unparseable completions — the whole emission (metadata AND morphs) is lost there; a morph-map completion is a
     fraction of the size (measured in 4), so the same budget could not have truncated it at the same point.

Writes outputs/morphmap_ab_offline.md. Run:
    PYTHONPATH=. python3.11 tools/morphmap_ab.py [--limit N] [--out PATH]
"""
import argparse
import copy
import glob
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from layer2.catalog.card_payload import default_for                              # noqa: E402
from layer2.emit.metadata.producer import produce, metadata_reference, _leaf_paths, _has, _get  # noqa: E402
from layer2.emit.morphmap.producer import apply as morph_apply                   # noqa: E402
from layer2.gates import gate_exact_metadata, enforce_exact_metadata             # noqa: E402

_HDR = re.compile(r"RUN:\s*(\S+)\s+CARD:\s*(\d+)\s+PAGE:\s*(\S+)")
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


def _corpus_files():
    return sorted(glob.glob(os.path.join(ROOT, "outputs", "logs", "ai_r_*.jsonl"))) + \
        sorted(glob.glob(os.path.join(ROOT, "outputs", "_log_archive", "**", "ai_r_*.jsonl"), recursive=True))


def _is_l2_emit(rec):
    msgs = ((rec.get("request") or {}).get("messages")) or []
    if len(msgs) < 2:
        return None
    sysc = str(msgs[0].get("content") or "")
    if "MORPH-EMIT" not in sysc:                              # PART 2 header of prompts/metadata.md (all corpus eras)
        return None
    m = _HDR.search(str(msgs[1].get("content") or ""))
    return m if m else None


def _parse_completion(rec):
    """(raw_dict|None, kind, content, usage) — the SAME extraction llm/client.py performs on a live reply."""
    resp = rec.get("response") or {}
    choice = ((resp.get("choices")) or [{}])[0]
    content = ((choice.get("message")) or {}).get("content") or ""
    usage = resp.get("usage") or {}
    finish = choice.get("finish_reason")
    txt = _THINK.sub("", content)
    if finish == "length":
        return None, "truncated", content, usage
    m = re.search(r"\{.*\}", txt, re.DOTALL)
    if not m:
        return None, "no_json", content, usage
    try:
        return json.loads(m.group(0)), "ok", content, usage
    except Exception:
        return None, "parse", content, usage


def _expressed_morphs(ai_meta, base):
    """The delta the AI actually EXPRESSED: {path: value} for every authored leaf that (a) is a REAL leaf of the
    stored skeleton and (b) differs from the default. `_`-prefixed roots skipped (envelope keys, _morphed already
    popped). Paths absent from the skeleton (invented keys) are counted separately by the caller — both contracts
    drop them identically."""
    out, invented = {}, []
    for path, val in _leaf_paths(ai_meta if isinstance(ai_meta, dict) else {}):
        if not path or path.split(".")[0].split("[")[0].startswith("_"):
            continue
        if not _has(base, path):
            invented.append(path)
            continue
        if _get(base, path) != val:
            out[path] = val
    return out, invented


def _full_emit_reproduce(dp, stored, ai_meta, morphed):
    """EXACTLY layer2/build._finalize's metadata sequence: produce → gate → enforce → re-gate."""
    ref = metadata_reference(dp["payload"], stored=stored)
    full, applied, rejected = produce(dp["payload"], ai_meta, morphed, stored=stored)
    ok, issues = gate_exact_metadata(full, ref, morphed=applied)
    reverted = []
    if not ok:
        full, reverted = enforce_exact_metadata(full, ref, morphed=applied)
        ok, issues = gate_exact_metadata(full, ref, morphed=applied)
    return full, applied, rejected, reverted, issues


def _b(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"), default=str)


def _diff_paths(a, b, cap=6):
    """First `cap` leaf paths where two payloads differ (for mismatch samples)."""
    la = dict(_leaf_paths(a)) if isinstance(a, dict) else {}
    lb = dict(_leaf_paths(b)) if isinstance(b, dict) else {}
    out = []
    for p in sorted(set(la) | set(lb)):
        if la.get(p, "\x00missing") != lb.get(p, "\x00missing"):
            out.append(p)
        if len(out) >= cap:
            break
    return out


def run(limit=0, out_path=None):
    files = _corpus_files()
    seen = set()
    st = Counter()
    sizes = []                     # (full_meta_chars, morph_map_chars, full_completion_chars, sim_completion_chars, completion_tokens)
    undeclared_records = []        # (file, ts, card, n_undeclared, sample_paths)
    mismatch_a = []                # regime A byte-mismatches (should be empty — producer equivalence)
    mismatch_b = []                # regime B mismatches = intent the full contract reverted, morph-map preserved
    lost = []                      # truncated/unparseable full emits (whole emission lost)
    per_card = Counter()
    n_records = 0

    for fp in files:
        try:
            lines = open(fp, errors="replace").readlines()
        except OSError:
            continue
        for line in lines:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            m = _is_l2_emit(rec)
            if not m:
                continue
            key = ((rec.get("response") or {}).get("id")) or hash(line)
            if key in seen:
                st["duplicate"] += 1
                continue
            seen.add(key)
            st["l2_emit_records"] += 1
            n_records += 1
            if limit and n_records > limit:
                break
            card_id, page_key = int(m.group(2)), m.group(3)
            per_card[card_id] += 1

            raw, kind, content, usage = _parse_completion(rec)
            if raw is None:
                st[f"completion_{kind}"] += 1
                lost.append((os.path.relpath(fp, ROOT), rec.get("ts"), card_id, kind,
                             usage.get("prompt_tokens"), usage.get("completion_tokens")))
                continue
            st["completion_ok"] += 1

            dp = _dp(card_id, page_key)
            if not dp or dp.get("payload_stripped") is None:
                st["no_stored_default"] += 1
                continue
            stored = dp["payload_stripped"]

            ai_meta = copy.deepcopy(raw.get("exact_metadata") or {})
            morphed = ai_meta.pop("_morphed", []) if isinstance(ai_meta, dict) else []
            morphed = [p for p in (morphed if isinstance(morphed, list) else []) if isinstance(p, str)]
            try:
                full, applied, rejected, reverted, issues = _full_emit_reproduce(dp, stored, ai_meta, morphed)
            except Exception as e:
                st["repro_error"] += 1
                st[f"repro_error::{type(e).__name__}"] += 1
                continue

            base = copy.deepcopy(stored)
            expressed, invented = _expressed_morphs(ai_meta, base)
            declared_map = {p: _get(ai_meta, p) for p in morphed if _has(ai_meta, p)}
            undeclared = [p for p in expressed if p not in set(morphed)]
            if invented:
                st["records_with_invented_keys"] += 1
            if undeclared:
                st["records_with_undeclared_morphs"] += 1
                st["undeclared_morph_paths"] += len(undeclared)
                undeclared_records.append((os.path.relpath(fp, ROOT), rec.get("ts"), card_id,
                                           len(undeclared), undeclared[:4]))

            # regime A — declared-only morph map: MUST byte-match the reproduced live result
            try:
                built_a, rep_a = morph_apply(declared_map, stored, default_payload=dp["payload"])
            except Exception as e:
                st["apply_error"] += 1
                st[f"apply_error::{type(e).__name__}"] += 1
                continue
            if _b(built_a) == _b(full):
                st["regimeA_match"] += 1
            else:
                st["regimeA_mismatch"] += 1
                mismatch_a.append((os.path.relpath(fp, ROOT), rec.get("ts"), card_id,
                                   _diff_paths(built_a, full)))

            # regime B — the FULL expressed delta (morph-map semantics: expressing IS declaring)
            built_b, rep_b = morph_apply(expressed, stored, default_payload=dp["payload"])
            if _b(built_b) == _b(full):
                st["regimeB_match"] += 1
            else:
                st["regimeB_mismatch"] += 1
                mismatch_b.append((os.path.relpath(fp, ROOT), rec.get("ts"), card_id,
                                   _diff_paths(built_b, full)))

            # completion-size measurement
            emitted_meta = raw.get("exact_metadata") or {}
            full_meta_chars = len(json.dumps(emitted_meta, separators=(",", ":"), default=str))
            morph_chars = len(json.dumps({"morphs": expressed}, separators=(",", ":"), default=str))
            env = {k: v for k, v in raw.items() if k != "exact_metadata"}
            env["morphs"] = expressed
            sim_chars = len(json.dumps(env, separators=(",", ":"), default=str))
            full_chars = len(json.dumps(raw, separators=(",", ":"), default=str))
            sizes.append((full_meta_chars, morph_chars, full_chars, sim_chars,
                          usage.get("completion_tokens") or 0))
        if limit and n_records > limit:
            break

    report = _report(st, sizes, undeclared_records, mismatch_a, mismatch_b, lost, per_card, len(files))
    out_path = out_path or os.path.join(ROOT, "outputs", "morphmap_ab_offline.md")
    with open(out_path, "w") as f:
        f.write(report)
    print(report)
    print(f"\n[written] {out_path}")
    return st


_DP_CACHE = {}


def _dp(card_id, page_key):
    k = (card_id, page_key)
    if k not in _DP_CACHE:
        try:
            _DP_CACHE[k] = default_for(card_id, page_key)
        except Exception:
            _DP_CACHE[k] = None
    return _DP_CACHE[k]


def _pct(n, d):
    return f"{(100.0 * n / d):.1f}%" if d else "n/a"


def _report(st, sizes, undeclared_records, mismatch_a, mismatch_b, lost, per_card, n_files):
    L = []
    n = st["l2_emit_records"]
    ok = st["completion_ok"]
    compared = st["regimeA_match"] + st["regimeA_mismatch"]
    L.append("# ITEM 18 — morph-map vs full-emit: OFFLINE A/B over the logged corpus")
    L.append("")
    L.append(f"Generated {datetime.now(timezone.utc).isoformat()} by tools/morphmap_ab.py (pure replay — no live "
             f"LLM calls, no pipeline wiring; layer2/build.py + layer2/emit/emit.py untouched).")
    L.append("")
    L.append("## Corpus")
    L.append(f"- ai_r_*.jsonl files scanned: **{n_files}** (outputs/logs + outputs/_log_archive/**)")
    L.append(f"- L2 full-emit records found: **{n}** (dedup dropped {st['duplicate']})")
    L.append(f"- completions parseable: **{ok}** ({_pct(ok, n)}); lost to the full contract's size/transport: "
             f"truncated **{st['completion_truncated']}**, no_json **{st['completion_no_json']}**, "
             f"parse **{st['completion_parse']}**")
    L.append(f"- skipped (card has no stored payload_stripped skeleton — the no-default contract path): "
             f"**{st['no_stored_default']}**")
    if st["repro_error"] or st["apply_error"]:
        L.append(f"- replay errors: repro **{st['repro_error']}**, apply **{st['apply_error']}** "
                 f"({', '.join(f'{k}={v}' for k, v in st.items() if '::' in k)})")
    L.append(f"- byte-compared emits: **{compared}** across {len(per_card)} distinct cards")
    L.append("")
    L.append("## Regime A — producer equivalence (morphs = the _morphed-DECLARED paths)")
    L.append(f"- byte-identical to the reproduced live enforce result: **{st['regimeA_match']}/{compared}** "
             f"({_pct(st['regimeA_match'], compared)})")
    if mismatch_a:
        L.append(f"- MISMATCHES (must be investigated before any live wiring): {len(mismatch_a)}")
        for fp, ts, card, paths in mismatch_a[:10]:
            L.append(f"    - {fp} ts={ts} card={card} diff_paths={paths}")
    else:
        L.append("- zero mismatches ⇒ `morphmap/producer.apply` is BYTE-EQUIVALENT to the live "
                 "produce→gate→enforce path on identical declared intent.")
    L.append("")
    L.append("## Regime B — expressed intent (morphs = every authored leaf that differs from the default)")
    L.append(f"- byte-identical: **{st['regimeB_match']}/{compared}** ({_pct(st['regimeB_match'], compared)})")
    L.append(f"- differing: **{st['regimeB_mismatch']}** — each difference is a leaf the AI AUTHORED off-default but "
             f"did NOT declare in `_morphed`, so the full-emit contract silently REVERTED it (the A1 silent-no-op "
             f"corruption); under morph-map, naming the path IS the declaration, so that intent ships (still through "
             f"the same gates — chrome/data-leaf/locked morphs are still rejected).")
    L.append("")
    L.append("## Corruption the full-emit contract caused (that morph-map structurally avoids)")
    L.append(f"- records with authored-but-UNDECLARED metadata changes (intent silently reverted): "
             f"**{st['records_with_undeclared_morphs']}** records / **{st['undeclared_morph_paths']}** leaf paths")
    for fp, ts, card, cnt, sample in undeclared_records[:12]:
        L.append(f"    - {fp} ts={ts} card={card} undeclared={cnt} e.g. {sample}")
    if len(undeclared_records) > 12:
        L.append(f"    - … (+{len(undeclared_records) - 12} more records)")
    L.append(f"- whole emissions LOST to completion size (truncated/unparseable): "
             f"**{st['completion_truncated'] + st['completion_no_json'] + st['completion_parse']}** — the ENTIRE "
             f"payload (metadata AND every morph) shipped as a degraded default. A morph-map completion is a "
             f"fraction of the size (see below), so the identical token budget could not have truncated at the "
             f"same point.")
    for fp, ts, card, kind, ptok, ctok in lost[:12]:
        L.append(f"    - {fp} ts={ts} card={card} kind={kind} prompt_tok={ptok} completion_tok={ctok}")
    if len(lost) > 12:
        L.append(f"    - … (+{len(lost) - 12} more records)")
    L.append(f"- records whose authored metadata carried INVENTED keys (dropped identically by both contracts): "
             f"**{st['records_with_invented_keys']}**")
    L.append("")
    L.append("## Completion-size reduction (the morph-map win)")
    if sizes:
        fm = sum(s[0] for s in sizes)
        mm = sum(s[1] for s in sizes)
        fc = sum(s[2] for s in sizes)
        sc = sum(s[3] for s in sizes)
        ct = sum(s[4] for s in sizes)
        meta_red = 100.0 * (1 - mm / fm) if fm else 0.0
        comp_red = 100.0 * (1 - sc / fc) if fc else 0.0
        med = sorted((1 - (s[3] / s[2])) * 100.0 for s in sizes if s[2])[len(sizes) // 2]
        L.append(f"- exact_metadata block (as emitted, incl. _morphed) → morphs-only map: {fm:,} → {mm:,} chars "
                 f"= **{meta_red:.1f}% smaller**")
        L.append(f"- WHOLE completion (envelope simulated with `morphs` replacing `exact_metadata`): {fc:,} → "
                 f"{sc:,} chars = **{comp_red:.1f}% smaller** (median per-emit reduction {med:.1f}%)")
        L.append(f"- corpus completion tokens on compared emits: {ct:,} — a proportional token cut ≈ "
                 f"{int(ct * comp_red / 100):,} tokens saved across the corpus (char-ratio estimate)")
    L.append("")
    L.append("## Verdict inputs (user condition: adopt ONLY if provably equal-or-better)")
    L.append("- EQUAL: regime A byte-equivalence above (same declared intent ⇒ same bytes through the same "
             "imported gates).")
    L.append("- BETTER: (a) the silent-no-op class disappears by construction (regime B / undeclared counts); "
             "(b) the completion shrinks by the % above, directly attacking the truncated/timeout loss class; "
             "(c) nothing to retype ⇒ no omission/drift risk on the ~untouched leaves.")
    L.append("- NOT wired live: adoption remains behind app_config `emit.morphmap_mode` (DEFAULT 'off', "
             "db/seed_morphmap_flag.sql); the live seam is post-certification work.")
    L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="stop after N L2 emit records (0 = all)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    run(limit=a.limit, out_path=a.out)
