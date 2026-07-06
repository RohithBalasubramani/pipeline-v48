"""tools/prompt_ab.py — ITEM 19 A/B harness for the RESTRUCTURED emit system prompt variant.

Replays LOGGED Layer-2 emit calls (outputs/logs/ai_r_*.jsonl / outputs/_log_archive/**) through TWO system prompts:
  v1 — the LIVE prompt, replayed BYTE-VERBATIM from the logged request (source of truth for what actually runs);
  v2 — layer2/prompts/data_instructions_v2.md (the rules-first VARIANT), composed with the SAME per-call dynamic
       content EXTRACTED from the logged v1 system message (closed/retired endpoint sets, the per-card RECOVERY
       LIBRARY block, roster-section presence) — so the ONLY difference between the arms is the prompt structure.

Everything else in the request (model, temperature=0, seed, response_format, chat_template_kwargs, user message)
is copied from the logged call. Calls go to :8200 SEQUENTIALLY with a throttle sleep. Per arm we score:
  · parse_ok / conforms / answerability / data_note
  · slot fidelity  — emitted slots ∈ the user message's FILLABLE DATA-LEAF SLOTS list (verbatim)
  · column fidelity — live raw/bucketed/event columns ∈ the DB SCHEMA basket (verbatim)
  · gate replay — layer2.gates.gate_data_instructions (+ enforce_honest_blank telemetry) over a basket
    RECONSTRUCTED from the logged user message → issues + honest-blank (gate-blank) count; gate_roster when the
    card has a roster_spec; gate_exact_metadata against the printed STATIC-CONFIG default skeleton.
  · tokens in/out + latency.

STRICTLY OFFLINE from the live pipeline: nothing in layer2/ imports this file, and the v2 file is read ONLY here.
Usage:
  python tools/prompt_ab.py --sample            # the built-in 8-card sample (thermal / panel-roster / PQ / walls)
  python tools/prompt_ab.py --call FILE:LINE …  # explicit logged calls
  python tools/prompt_ab.py --sample --dry      # compose + score prompts only, no LLM calls
Writes outputs/prompt_ab_sample.md (override with --out)."""
import argparse
import json
import os
import re
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

LOG_DIR = os.path.join(ROOT, "outputs", "logs")
V2_PATH = os.path.join(ROOT, "layer2", "prompts", "data_instructions_v2.md")
URL = os.environ.get("PROMPT_AB_URL", "http://localhost:8200/v1/chat/completions")
THROTTLE_S = float(os.environ.get("PROMPT_AB_THROTTLE", "2"))
TIMEOUT_S = float(os.environ.get("PROMPT_AB_TIMEOUT", "300"))

# The built-in sample: (log file, 0-based line) — chosen for coverage: 2 thermal, 2 panel-roster, 2 PQ,
# 1 five-walls honesty (UPS transfer readiness), 1 group/$ctx card on the NEWEST logged prompt variant.
SAMPLE = [
    ("ai_r_f3b19721cb.jsonl", 6),    # card 74  Thermal Life (transformer, THERMAL walls)
    ("ai_r_d06f6da969.jsonl", 42),   # card 61  Thermal Timeline (DG engine-cooling, sibling-unit °C case)
    ("ai_r_99879f110d.jsonl", 33),   # card 17  Daily Power Demand by Feeder (panel ROSTER)
    ("ai_r_ab957fb3ac.jsonl", 25),   # card 9   Total Feeder Consumption / Supply (panel ROSTER)
    ("ai_r_99879f110d.jsonl", 38),   # card 23  PQ Issues KPI Strip (harmonics-pq, roster)
    ("ai_r_a77b8e4dd2.jsonl", 7),    # card 48  Distortion & Harmonic Profile (PQ single-asset)
    ("ai_r_d7be9457fc.jsonl", 4),    # card 54  Transfer readiness (five physical walls)
    ("ai_r_92a2bfb0ae.jsonl", 238),  # card 46  Current History (group $ctx + roster, newest prompt)
]


# ── logged-call loading ───────────────────────────────────────────────────────────────────────────────────────────
def load_call(fname, line_no):
    path = fname if os.path.isabs(fname) else os.path.join(LOG_DIR, fname)
    with open(path) as fh:
        for i, line in enumerate(fh):
            if i == line_no:
                rec = json.loads(line)
                msgs = rec["request"]["messages"]
                sysm = "\n".join(m["content"] for m in msgs if m["role"] == "system")
                usr = "\n".join(m["content"] for m in msgs if m["role"] == "user")
                if len(sysm) < 40000:
                    raise SystemExit(f"{fname}:{line_no} is not an L2 emit call (system msg {len(sysm)} chars)")
                return {"rec": rec, "system_v1": sysm, "user": usr, "src": f"{os.path.basename(path)}:{line_no}"}
    raise SystemExit(f"{fname}:{line_no}: line not found")


# ── v2 composition (dynamic content extracted from the logged v1 prompt — the arms differ ONLY in structure) ─────
_ROSTER_BEGIN, _ROSTER_END = "<!--ROSTER:BEGIN-->", "<!--ROSTER:END-->"


def extract_dynamic(sys_v1):
    m_live = re.search(r"THE CLOSED SET — ONLY these endpoints EXIST \(emit EXACTLY one\): (\[[^\]]*\])", sys_v1)
    m_ret = re.search(r"★ RETIRED — DO NOT EXIST, NEVER emit: (\[[^\]]*\])", sys_v1)
    m_lib = re.search(r"```\n(.*?)```", sys_v1, flags=re.S)
    return {
        "live": m_live.group(1) if m_live else "[]",
        "retired": m_ret.group(1) if m_ret else "[]",
        "library": (m_lib.group(1).rstrip("\n") if m_lib else "(recovery library unavailable — emit NO derived fields; honest-degrade)"),
        "roster": "## ROSTER (member-scope)" in sys_v1,
    }


def compose_v2(sys_v1):
    dyn = extract_dynamic(sys_v1)
    out = open(V2_PATH, errors="replace").read().strip()
    out = out.replace("{{LIVE_ENDPOINTS}}", dyn["live"]).replace("{{RETIRED_ENDPOINTS}}", dyn["retired"])
    b, e = out.find(_ROSTER_BEGIN), out.find(_ROSTER_END)
    if b != -1 and e != -1:
        if dyn["roster"]:
            out = out.replace(_ROSTER_BEGIN + "\n", "").replace(_ROSTER_END + "\n", "")
        else:
            out = out[:b] + out[e + len(_ROSTER_END) + 1:]
    out = out.replace("{{RECOVERY_LIBRARY}}", dyn["library"])
    return out


# ── user-message context reconstruction (for gate replay + fidelity metrics) ─────────────────────────────────────
def parse_user_ctx(usr):
    ctx = {"is_group": "GROUP CARD: true" in usr, "card": None, "page": None, "title": None,
           "basket": {"columns": []}, "slots": set(), "roster_spec": None, "default_payload": None}
    m = re.search(r"RUN: \S+\s+CARD: (\d+)\s+PAGE: (\S+)", usr)
    if m:
        ctx["card"], ctx["page"] = int(m.group(1)), m.group(2)
    m = re.search(r"^  title: (.+)$", usr, flags=re.M)
    ctx["title"] = m.group(1).strip() if m else "?"
    # DB SCHEMA lines: "  column | metric=?| name_hint=… | unit | qty=… | data=Y  [★ REAL-LOGGED|✗ FAILED-VALIDATION]"
    for line in usr.splitlines():
        lm = re.match(r"^  (\w+) \| (.*\| )?name_hint=\S+ \|(.*)\| qty=(\S+) \| data=(\w)(.*)$", line)
        if lm:
            ctx["basket"]["columns"].append({
                "column": lm.group(1), "unit": (lm.group(3) or "").strip(), "qty": lm.group(4),
                "has_data": lm.group(5) == "Y",
                "verdict": "fail" if "FAILED-VALIDATION" in (lm.group(6) or "") else None,
            })
    # nameplate presence (the '—' convention)
    m = re.search(r"NAMEPLATE .*?: (.*)", usr)
    if m:
        vals = dict(re.findall(r"(\w+)=([^\s|]+)", m.group(1)))
        rated = any(v not in ("—", "-", "None", "null") for k, v in vals.items() if k.startswith("rated"))
        ctx["basket"]["nameplate"] = {"rated_present": rated}
    for sm in re.finditer(r"^  slot=(\S+)", usr, flags=re.M):
        ctx["slots"].add(sm.group(1))
    m = re.search(r"roster_spec \(VERBATIM[^)]*\): (\{.*)$", usr, flags=re.M)
    if m:
        try:
            ctx["roster_spec"] = json.loads(m.group(1))
        except Exception:
            ctx["roster_spec"] = None
    # the printed STATIC-CONFIG default payload (JSON object between the METADATA SHAPE line and FILLABLE SLOTS)
    m = re.search(r"METADATA SHAPE \+ STATIC-CONFIG DEFAULTS[^\n]*\n(\{.*?\n\})\n\n★ FILLABLE", usr, flags=re.S)
    if m:
        try:
            ctx["default_payload"] = json.loads(m.group(1))
        except Exception:
            ctx["default_payload"] = None
    return ctx


# ── the LLM call (sequential, throttled, raw replay of the logged request shape) ─────────────────────────────────
def call_llm(rec_request, system_msg, user_msg):
    req = {k: v for k, v in rec_request.items() if k != "messages"}
    req["messages"] = [{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}]
    data = json.dumps(req).encode()
    t0 = time.time()
    r = urllib.request.Request(URL, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=TIMEOUT_S) as resp:
        body = json.loads(resp.read().decode())
    dt = time.time() - t0
    usage = body.get("usage") or {}
    content = ((body.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    return {"content": content, "tok_in": usage.get("prompt_tokens"), "tok_out": usage.get("completion_tokens"),
            "latency_s": round(dt, 1), "finish": (body.get("choices") or [{}])[0].get("finish_reason")}


# ── scoring ──────────────────────────────────────────────────────────────────────────────────────────────────────
def _gates(out, ctx):
    """Replay the REAL deterministic gates over the emission (both arms judged by the same yardstick). Never raises —
    on import/DB failure returns gate_available=False and the fidelity metrics still stand."""
    g = {"gate_available": False, "gate_issues": [], "gate_blanked": [], "meta_issues": 0, "meta_reverted": 0,
         "roster_issues": []}
    try:
        from layer2.gates import gate_data_instructions, gate_roster, gate_exact_metadata
        import copy
        di = copy.deepcopy(out.get("data_instructions") or {})
        em = out.get("exact_metadata") or {}
        ok, issues = gate_data_instructions(di, ctx["basket"], is_group_card=ctx["is_group"],
                                            answerability=out.get("answerability"), exact_metadata=em)
        g["gate_available"] = True
        g["gate_issues"] = issues
        g["gate_blanked"] = di.get("_honest_blanked") or []
        if ctx.get("roster_spec") and (out.get("data_instructions") or {}).get("roster"):
            rok, rissues, _norm = gate_roster((out["data_instructions"] or {}).get("roster"),
                                              ctx["roster_spec"], ctx["basket"])
            g["roster_issues"] = rissues
        if ctx.get("default_payload") is not None and isinstance(em, dict):
            morphed = em.get("_morphed") or []
            em2 = {k: v for k, v in em.items() if k != "_morphed"}
            mok, missues = gate_exact_metadata(em2, ctx["default_payload"], morphed=morphed)
            g["meta_issues"] = len(missues)
    except Exception as e:  # pragma: no cover — gate replay is best-effort
        g["gate_error"] = f"{type(e).__name__}: {e}"
    return g


def score(resp, ctx):
    s = {"parse_ok": False, "conforms": None, "answerability": None, "data_note": None, "n_fields": 0,
         "bad_slots": [], "bad_cols": [], "omitted_slots": 0, "roster_entries": 0,
         "tok_in": resp.get("tok_in"), "tok_out": resp.get("tok_out"), "latency_s": resp.get("latency_s"),
         "finish": resp.get("finish")}
    try:
        out = json.loads(resp["content"])
        s["parse_ok"] = True
    except Exception:
        return s, None
    s["conforms"] = out.get("conforms")
    s["answerability"] = out.get("answerability")
    s["data_note"] = out.get("data_note")
    di = out.get("data_instructions") or {}
    fields = di.get("fields") or []
    s["n_fields"] = len(fields)
    bound = set()
    basket_cols = {c["column"] for c in ctx["basket"]["columns"]}
    for f in fields:
        if not isinstance(f, dict):
            continue
        slot = f.get("slot")
        bound.add(slot)
        if ctx["slots"] and slot not in ctx["slots"]:
            s["bad_slots"].append(slot)
        col = f.get("column")
        if col and f.get("kind") in ("raw", "bucketed", "event") and f.get("source") in ("live", "test-db") \
                and col not in basket_cols:
            s["bad_cols"].append(col)
    s["omitted_slots"] = len(ctx["slots"] - bound) if ctx["slots"] else 0
    s["roster_entries"] = len(di.get("roster") or [])
    ep = (di.get("ems_backend") or {}).get("endpoint")
    s["endpoint"] = ep
    s.update(_gates(out, ctx))
    return s, out


# ── report ───────────────────────────────────────────────────────────────────────────────────────────────────────
def fmt_row(name, a, b):
    return f"| {name} | {a} | {b} |"


def card_section(call, ctx, sv1, sv2, len1, len2):
    L = []
    L.append(f"### card {ctx['card']} — {ctx['title']}  ({ctx['page']})   [{call['src']}]")
    L.append("")
    L.append(f"system-prompt chars: v1={len1}  v2={len2}  ({(len2 - len1) * 100 // max(len1, 1)}%)")
    L.append("")
    L.append("| metric | v1 (live) | v2 (variant) |")
    L.append("|---|---|---|")
    for key, label in [("parse_ok", "parse_ok"), ("conforms", "conforms"), ("answerability", "answerability"),
                       ("n_fields", "fields emitted"), ("omitted_slots", "slots omitted"),
                       ("roster_entries", "roster entries"), ("endpoint", "endpoint")]:
        L.append(fmt_row(label, sv1.get(key), sv2.get(key)))
    L.append(fmt_row("bad slots (not in list)", len(sv1.get("bad_slots") or []), len(sv2.get("bad_slots") or [])))
    L.append(fmt_row("bad columns (not in basket)", len(sv1.get("bad_cols") or []), len(sv2.get("bad_cols") or [])))
    if sv1.get("gate_available") or sv2.get("gate_available"):
        L.append(fmt_row("gate issues", len(sv1.get("gate_issues") or []), len(sv2.get("gate_issues") or [])))
        L.append(fmt_row("gate-blanked leaves", len(sv1.get("gate_blanked") or []), len(sv2.get("gate_blanked") or [])))
        L.append(fmt_row("roster issues", len(sv1.get("roster_issues") or []), len(sv2.get("roster_issues") or [])))
        L.append(fmt_row("metadata byte-issues", sv1.get("meta_issues"), sv2.get("meta_issues")))
    L.append(fmt_row("tokens in/out", f"{sv1.get('tok_in')}/{sv1.get('tok_out')}",
                     f"{sv2.get('tok_in')}/{sv2.get('tok_out')}"))
    L.append(fmt_row("latency s", sv1.get("latency_s"), sv2.get("latency_s")))
    for tag, sv in (("v1", sv1), ("v2", sv2)):
        if sv.get("data_note"):
            L.append(f"- {tag} data_note: {sv['data_note']}")
    for tag, sv in (("v1", sv1), ("v2", sv2)):
        for gi in (sv.get("gate_issues") or [])[:4]:
            L.append(f"- {tag} gate: {gi}")
        for gb in (sv.get("gate_blanked") or [])[:4]:
            L.append(f"- {tag} blanked: {gb}")
        if sv.get("gate_error"):
            L.append(f"- {tag} gate_error: {sv['gate_error']}")
    L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--call", action="append", default=[], help="FILE:LINE of a logged L2 emit call (repeatable)")
    ap.add_argument("--sample", action="store_true", help="run the built-in 8-card sample")
    ap.add_argument("--dry", action="store_true", help="compose + report prompt sizes only; no LLM calls")
    ap.add_argument("--out", default=os.path.join(ROOT, "outputs", "prompt_ab_sample.md"))
    args = ap.parse_args()

    picks = list(SAMPLE) if args.sample else []
    for c in args.call:
        f, ln = c.rsplit(":", 1)
        picks.append((f, int(ln)))
    if not picks:
        ap.error("nothing to run: use --sample and/or --call FILE:LINE")

    sections, agg = [], {"v1": [], "v2": []}
    for fname, ln in picks:
        call = load_call(fname, ln)
        ctx = parse_user_ctx(call["user"])
        sys_v2 = compose_v2(call["system_v1"])
        len1, len2 = len(call["system_v1"]), len(sys_v2)
        print(f"[{call['src']}] card={ctx['card']} {ctx['title']!r} sys v1={len1} v2={len2}", flush=True)
        if args.dry:
            sections.append(f"### card {ctx['card']} — {ctx['title']} [{call['src']}] — DRY: sys v1={len1} v2={len2}\n")
            continue
        r1 = call_llm(call["rec"]["request"], call["system_v1"], call["user"])
        time.sleep(THROTTLE_S)
        r2 = call_llm(call["rec"]["request"], sys_v2, call["user"])
        time.sleep(THROTTLE_S)
        s1, _o1 = score(r1, ctx)
        s2, _o2 = score(r2, ctx)
        agg["v1"].append(s1)
        agg["v2"].append(s2)
        sections.append(card_section(call, ctx, s1, s2, len1, len2))
        print(f"    v1: parse={s1['parse_ok']} conforms={s1['conforms']} ans={s1['answerability']} "
              f"fields={s1['n_fields']} gate_blank={len(s1.get('gate_blanked') or [])} tok={s1['tok_in']}/{s1['tok_out']}", flush=True)
        print(f"    v2: parse={s2['parse_ok']} conforms={s2['conforms']} ans={s2['answerability']} "
              f"fields={s2['n_fields']} gate_blank={len(s2.get('gate_blanked') or [])} tok={s2['tok_in']}/{s2['tok_out']}", flush=True)

    hdr = ["# prompt A/B — v1 (live emit prompt) vs v2 (data_instructions_v2.md variant)",
           "", f"generated: {time.strftime('%Y-%m-%d %H:%M:%S')}   url: {URL}   calls: {len(agg['v1'])} cards x 2 arms",
           "", "v2 is composed from layer2/prompts/data_instructions_v2.md with the SAME dynamic content extracted from",
           "the logged v1 call (endpoint sets, per-card recovery library, roster presence); the user message and every",
           "sampling knob are identical — the arms differ ONLY in system-prompt structure.", ""]
    if agg["v1"]:
        def tot(svs, key, ln=False):
            vals = [(len(s.get(key) or []) if ln else s.get(key)) for s in svs]
            nums = [v for v in vals if isinstance(v, (int, float))]
            return sum(nums)
        hdr += ["## aggregate", "", "| metric | v1 | v2 |", "|---|---|---|",
                fmt_row("parse_ok", sum(1 for s in agg['v1'] if s['parse_ok']), sum(1 for s in agg['v2'] if s['parse_ok'])),
                fmt_row("conforms=true", sum(1 for s in agg['v1'] if s['conforms'] is True), sum(1 for s in agg['v2'] if s['conforms'] is True)),
                fmt_row("fields emitted", tot(agg['v1'], 'n_fields'), tot(agg['v2'], 'n_fields')),
                fmt_row("bad slots", tot(agg['v1'], 'bad_slots', ln=True), tot(agg['v2'], 'bad_slots', ln=True)),
                fmt_row("bad columns", tot(agg['v1'], 'bad_cols', ln=True), tot(agg['v2'], 'bad_cols', ln=True)),
                fmt_row("gate issues", tot(agg['v1'], 'gate_issues', ln=True), tot(agg['v2'], 'gate_issues', ln=True)),
                fmt_row("gate-blanked leaves", tot(agg['v1'], 'gate_blanked', ln=True), tot(agg['v2'], 'gate_blanked', ln=True)),
                fmt_row("honest answers (partial/none + data_note)",
                        sum(1 for s in agg['v1'] if s['answerability'] in ('partial', 'none') and s['data_note']),
                        sum(1 for s in agg['v2'] if s['answerability'] in ('partial', 'none') and s['data_note'])),
                fmt_row("tokens in (sum)", tot(agg['v1'], 'tok_in'), tot(agg['v2'], 'tok_in')),
                fmt_row("tokens out (sum)", tot(agg['v1'], 'tok_out'), tot(agg['v2'], 'tok_out')), ""]
    body = "\n".join(hdr) + "\n" + "\n".join(sections)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        f.write(body)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
