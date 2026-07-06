"""tools/replay_item17_guided_asset_resolve.py — ITEM 17 stage 1 OFFLINE PROOF: replay logged L1 ASSET RESOLVER calls
LIVE against :8200 WITH guided_json ON, then check (a) 100% parse and (b) decision parity vs the logged answers.

Corpus: outputs/logs/ai_r_*.jsonl + outputs/_log_archive/**/ai_r_*.jsonl (full request+response per call). Each logged
user message is SELF-CONTAINED (it embeds the candidate listing of its day), so a replay needs no DB/registry access.

The flag is turned on IN-PROCESS ONLY (llm.client._cfg is wrapped so llm.guided_json.asset_resolve reads 'on') — the
DB row stays 'off', so nothing outside this process sees guided decoding. The replay exercises the REAL item-17 path:
call_qwen(stage='asset_resolve', json_schema=ASSET_ANSWER_SCHEMA) → response_format json_schema.

Decision-parity rules (per the item-17 acceptance):
  · logged UNAMBIGUOUS (confident:true, exactly 1 name): the replay must pin the SAME name — a different pin = FAIL;
  · logged EMPTY (confident:true, names:[]): the replay must stay empty — a pin out of nowhere = FAIL;
  · logged AMBIGUOUS (confident:false): a divergent candidate set is ACCEPTABLE iff still non-confident and every
    replayed candidate is a VALID name from that call's own candidate listing; a confident pin here = FAIL.

Run (sequential, small, throttled):
    PYTHONPATH=. python3.11 tools/replay_item17_guided_asset_resolve.py [N] [guided|both]   # default N=40, guided

`both` is the CONTROL experiment: each case is replayed twice — guided (flag on, json_schema attached) AND plain
(today's default json_object path) — so a divergence vs the LOG can be attributed: if plain == guided but both differ
from the log, the drift predates item 17 (older system prompt / server state at logging time) and the flag itself
changes nothing; only guided != plain would implicate guided decoding.
"""
import glob
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from llm import client                                     # noqa: E402
from layer1b.resolve.answer_schema import ASSET_ANSWER_SCHEMA  # noqa: E402

THROTTLE_S = 0.3


def _parse_answer(text):
    """The pipeline's own extraction: strip <think>, first {...} blob, json.loads. None if unparseable."""
    txt = re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL)
    m = re.search(r"\{.*\}", txt, re.DOTALL)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def _listing_names(user_msg):
    """The valid VERBATIM names embedded in this call's own candidate listing (field before the first tab)."""
    names = set()
    in_listing = False
    for line in user_msg.splitlines():
        if line.startswith("CANDIDATES ("):
            in_listing = True
            continue
        if in_listing:
            if not line.strip() or line.startswith("CLASSES PRESENT"):
                break
            names.add(line.split("\t")[0].strip())
    return names


def _prompt_of(user_msg):
    m = re.search(r"PROMPT: (.+?)\nJSON:", user_msg, re.DOTALL)
    return (m.group(1) if m else user_msg[-120:]).strip()[:120]


def collect(n_wanted):
    """Newest-first, deduped by user message, only records whose LOGGED answer parsed (else no decision to compare)."""
    files = glob.glob(os.path.join(ROOT, "outputs/logs/ai_r_*.jsonl")) + \
        glob.glob(os.path.join(ROOT, "outputs/_log_archive/**/ai_r_*.jsonl"), recursive=True)
    files.sort(key=os.path.getmtime, reverse=True)
    seen, cases = set(), []
    for fp in files:
        with open(fp) as f:
            for line in f:
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                msgs = (r.get("request") or {}).get("messages") or []
                if len(msgs) != 2 or "L1 ASSET RESOLVER" not in (msgs[0].get("content") or ""):
                    continue
                user = msgs[1].get("content") or ""
                if "YOUR PREVIOUS REPLY WAS NOT USABLE" in user:      # parse-retry follow-up, not a fresh decision
                    continue
                key = user
                if key in seen:
                    continue
                seen.add(key)
                content = ((((r.get("response") or {}).get("choices") or [{}])[0]).get("message") or {}).get("content")
                logged = _parse_answer(content)
                if logged is None:
                    continue                                          # logged call itself failed → nothing to compare
                cases.append({"system": msgs[0]["content"], "user": user, "logged": logged, "src": os.path.basename(fp)})
                if len(cases) >= n_wanted:
                    return cases
    return cases


def classify(ans):
    conf = bool(ans.get("confident", False))
    names = [n for n in (ans.get("names") or []) if n]
    if conf and len(names) == 1:
        return "unambiguous"
    if conf and not names:
        return "empty"
    return "ambiguous"


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    mode = sys.argv[2] if len(sys.argv) > 2 else "guided"
    cases = collect(n)
    print(f"collected {len(cases)} unique logged asset-resolver calls (newest first); mode={mode}\n")

    # flag ON in-process only: wrap _cfg so llm.guided_json.asset_resolve = 'on'; every other row = the real config
    real_cfg = client._cfg
    client._cfg = lambda k, d: "on" if k == "llm.guided_json.asset_resolve" else real_cfg(k, d)

    parsed = 0
    match = 0
    acceptable = []
    fails = []
    control_same = control_diff = 0
    for i, c in enumerate(cases, 1):
        t0 = time.time()
        out = client.call_qwen(c["system"], c["user"], stage="asset_resolve",
                               json_schema=ASSET_ANSWER_SCHEMA, timeout=150, on_error="marker")
        dt = time.time() - t0
        prompt = _prompt_of(c["user"])
        if mode == "both":
            # CONTROL: the same call on today's DEFAULT path (no json_schema → json_object, byte-identical legacy)
            plain = client.call_qwen(c["system"], c["user"], stage="asset_resolve", timeout=150, on_error="marker")
            same = (classify(plain) == classify(out)
                    and [x for x in (plain.get("names") or []) if x] == [x for x in (out.get("names") or []) if x]
                    and set(x for x in (plain.get("candidates") or []) if x)
                    == set(x for x in (out.get("candidates") or []) if x))
            control_same += 1 if same else 0
            control_diff += 0 if same else 1
            if not same:
                print(f"      CONTROL-DIFF guided={json.dumps(out)[:130]}")
                print(f"                   plain ={json.dumps(plain)[:130]}")
            time.sleep(THROTTLE_S)
        if "_llm_error" in out or not isinstance(out, dict):
            fails.append((prompt, f"NO PARSE / transport: {out}"))
            print(f"[{i:>2}/{len(cases)}] PARSE-FAIL {dt:5.1f}s  {prompt!r}")
            time.sleep(THROTTLE_S)
            continue
        ok_shape = isinstance(out.get("names", []), list) and isinstance(out.get("confident", False), bool)
        if not ok_shape:
            fails.append((prompt, f"BAD SHAPE: {json.dumps(out)[:200]}"))
            print(f"[{i:>2}/{len(cases)}] SHAPE-FAIL {dt:5.1f}s  {prompt!r}")
            time.sleep(THROTTLE_S)
            continue
        parsed += 1
        logged, kind = c["logged"], classify(c["logged"])
        new_kind = classify(out)
        lnames = [x for x in (logged.get("names") or []) if x]
        nnames = [x for x in (out.get("names") or []) if x]
        lcand = [x for x in (logged.get("candidates") or []) if x]
        ncand = [x for x in (out.get("candidates") or []) if x]
        verdict = "MATCH"
        if kind == "unambiguous":
            if new_kind == "unambiguous" and nnames[0] == lnames[0]:
                match += 1
            else:
                verdict = "FAIL(pin)"
                fails.append((prompt, f"logged pin {lnames} -> replay {json.dumps(out)[:160]}"))
        elif kind == "empty":
            if new_kind == "empty":
                match += 1
            else:
                verdict = "FAIL(pin-from-empty)"
                fails.append((prompt, f"logged empty -> replay {json.dumps(out)[:160]}"))
        else:  # logged ambiguous
            if new_kind == "unambiguous":
                verdict = "FAIL(pin-on-ambiguous)"
                fails.append((prompt, f"logged ambiguous {lcand[:4]}... -> replay PIN {nnames}"))
            elif set(ncand) == set(lcand):
                match += 1
            else:
                valid = _listing_names(c["user"])
                bad = [x for x in ncand if x not in valid]
                if bad:
                    verdict = "FAIL(invalid-candidate)"
                    fails.append((prompt, f"replay candidates not in listing: {bad[:4]}"))
                else:
                    verdict = "DIVERGE-OK"
                    acceptable.append((prompt, f"candidates {sorted(set(lcand) ^ set(ncand))[:6]} differ, all valid"))
        print(f"[{i:>2}/{len(cases)}] {verdict:<22} {dt:5.1f}s  kind={kind:<11} {prompt!r}")
        time.sleep(THROTTLE_S)

    client._cfg = real_cfg
    total = len(cases)
    print("\n──── ITEM 17 REPLAY PROOF ────")
    print(f"replayed          : {total}")
    print(f"parsed            : {parsed}/{total}  ({100.0 * parsed / max(total, 1):.1f}%)")
    print(f"decision match    : {match}/{total}")
    print(f"acceptable diverge: {len(acceptable)} (ambiguous, all candidates valid)")
    if mode == "both":
        print(f"guided == plain   : {control_same}/{control_same + control_diff} "
              "(flag-on vs today's default path, same server/day)")
    print(f"FAILS             : {len(fails)}")
    for p, d in acceptable:
        print(f"  ~ {p!r}: {d}")
    for p, d in fails:
        print(f"  ✗ {p!r}: {d}")
    sys.exit(0 if (parsed == total and not fails) else 1)


if __name__ == "__main__":
    main()
