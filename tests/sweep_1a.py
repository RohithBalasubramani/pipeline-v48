"""Extensive live sweep: run full Layer 1a (route+story+partition) over diverse prompts; validate each vs contract 2."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import obs.ai_log as ai  # noqa: E402

ai.set_run_id("sweep1a")
from layer1a.build import run_1a  # noqa: E402
from layer1a.schema import validate_layer1a_output  # noqa: E402
from layer1a.db_reads.page_specs import read_page_specs  # noqa: E402

KEYS = {s["page_key"] for s in read_page_specs()}
PROMPTS = [
    "voltage and current health for AHU-5",
    "real-time monitoring of PCC-1A panel",
    "real-time monitoring of PCC-2B panel",
    "energy and power overview for the main panel",
    "harmonics and power quality of the LT panel",
    "energy distribution and losses across feeders",
    "transformer thermal and insulation life",
    "UPS battery health and backup autonomy",
    "diesel generator engine cooling and runtime",
    "power quality spectrum and distortion analysis",
    "demand profile by feeder group",
    "AHU overview command screen",
    "compare consumption trend over the week",
    "",  # empty -> defaults + valid fallback
]

print(f"{'page_key':52s} {'metric':9s} {'intent':10s} cards story grp  ok   t")
print("-" * 100)
allpass = True
tot_cards = tot_story = 0
t0 = time.time()
for p in PROMPTS:
    s = time.time()
    out = run_1a(p)
    dt = time.time() - s
    probs = validate_layer1a_output(out, KEYS)
    ncards = len(out["cards"])
    nstory = sum(1 for c in out["cards"] if c["analytical_story"].strip())
    ngrp = len(out["interdependency_groups"])
    ok = not probs
    allpass = allpass and ok
    tot_cards += ncards
    tot_story += nstory
    print(f"{out['page_key']:52.52s} {out['metric']:9.9s} {out['intent']:10s} {ncards:5d} {nstory:5d} {ngrp:3d}  {'OK' if ok else 'X!':3s} {dt:4.1f}s"
          + ("" if ok else "  <- " + "; ".join(probs)))
print("-" * 100)
print(f"PROMPTS: {len(PROMPTS)}  |  contract-2 ALL PASS: {allpass}  |  story coverage: {tot_story}/{tot_cards}"
      f"  |  total {time.time()-t0:.1f}s")
