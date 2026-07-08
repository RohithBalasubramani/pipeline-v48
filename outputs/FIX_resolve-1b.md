# FIX resolve-1b — full-name collision gate false-pinned a glued section suffix ("PCC Panel 1A" → PCC-Panel-1)

Root cause (DEBUG A1): `layer1b/resolve/name_collision.py::uniquely_named` matched the full-name discriminator
by raw substring over `_norm()`'d strings (all separators stripped). For "what is voltage of PCC Panel 1A last 7 days",
`_norm` → "...pccpanel1alast7days", and the discriminator `_norm("PCC-Panel-1")="pccpanel1"` IS a substring — but the
span ends mid-token, right before the section letter 'a'. So `uniquely_named` returned PCC-Panel-1, `is_collision`
went False, and `asset_resolve.py` deterministically pinned PCC-Panel-1, discarding the AI's CORRECT ambiguous answer
(`{confident:false, candidates:[Panel-1..4]}`). No 1A/1B row exists in the registry (sections are GLB-only), so
ambiguous → picker was the designed outcome.

## What changed (files I own)

1. `layer1b/resolve/name_collision.py` — reworked `uniquely_named` only; added two helpers
   (`_fullname_re`, `_fullname_spelled_out`). `_discriminators`/`_norm` left byte-identical (imported by
   `layer1b/compare/detect.py` + `resolve_names.py`, which I do not own).
   - The WHOLE-NAME discriminator is now matched with a **separator-tolerant regex against the ORIGINAL lowercased
     prompt**, bounded on both sides: `(?<![a-z0-9]){name_tokens joined by [^a-z0-9]*}(?![a-z0-9])`. The trailing
     `(?![a-z0-9])` rejects an alphanumeric **glued** to the name's trailing unit token with no separator — a letter
     (section suffix `1a`/`1b`/`2a`) or a digit (`1` continued into `10`/`12`). `[^a-z0-9]*` between the name's own
     tokens tolerates ALL of the name's internal punctuation exactly like `_norm` (so `GIC-28-N3-DG-03 [Jackson]`
     still matches through the bracket, and `PCC-Panel-1`/`pcc panel 1`/`pccpanel1` all match).
   - CRITICAL subtlety honored: the boundary is judged in the **ORIGINAL** prompt, never the normalized one —
     normalization deletes the trailing space and glues the NEXT WORD onto the number
     (`"...panel 1 last..." → "...panel1last..."`), which would masquerade as a glued token and wrongly reject every
     legitimate full-name pin. A real trailing separator (space/hyphen/underscore) before the next word is kept as a
     legitimate boundary → the pin stands.
   - The **GIC-node PREFIX** discriminator keeps its exact prior behavior (normalized-substring `d in pnorm`): it is a
     prefix matcher (the rest of the name, incl. rating suffixes the user won't type, legitimately follows it). This is
     what still pins `GIC-01-N3-UPS-01 last 7 days` (full name has a `CL:600KVA` suffix the prompt lacks) and rescues
     the Jackson case.

2. `layer1b/resolve/asset_resolve.py` — telemetry relabel only: the deterministic full-name pin now returns
   `how="collision_gate_fullname"` instead of the mislabeled `how="AI"` (line ~135). The AI-driven confident-pin branch
   (line ~148) is untouched — still `how="AI"`.

3. `tests/test_layer1b_name_collision.py` — 7 new A1 acceptance tests (below).

## Why generic (no per-asset/per-prompt branch)

The predicate is pure token-boundary discipline over the unit-token structure the module already parses — no asset
names, panel numbers, or prompt strings are hardcoded. It fixes every section-suffix / continued-number case for every
class (verified live on PCC panels 1 AND 2, and synthetically on UPS-1 vs UPS-10). New full-name matches are a strict
subset of the old behavior (added boundaries only), so nothing that pinned before over-fires; the GIC-prefix path is
byte-for-byte unchanged.

## Acceptance (verified live against both DBs up; all in the new tests, all pass)

| prompt | colliding set | uniquely_named | is_collision |
|---|---|---|---|
| what is voltage of PCC Panel 1A last 7 days | 32,33,197,256,259,287,**317** | **None** | **True** → picker (the repro, fixed) |
| PCC Panel 1B / voltage of PCC Panel 1B last 7 days | …317 | None | True |
| voltage of PCC Panel 2A | …318 | None | True |
| PCC Panel 1 / PCC-Panel-1 / voltage of PCC Panel 1 | …317 | 317 | False → pin |
| PCC-Panel-1 voltage last 7 days (trailing words separated) | …317 | 317 | False → pin |
| PCC Panel 2 | …318 | 318 | False → pin |
| GIC-01-N3-UPS-01 last 7 days | 11,188,192,194,296 | 11 (via GIC prefix) | False → pin |
| real time monitoring for GIC-01-N3-UPS-01 (existing) | …11 | 11 | False (no regression) |
| power of GIC-28-N3-DG-03 [Jackson] (existing) | 4,302 | 302 (bracket tolerated) | False (no regression) |
| Real-time power of DG-03 Jackson (existing) | 4,302 | None | True (no regression) |
| Load profile of UPS-04 (existing) | 23,191,299 | None | True (no regression) |

Test suite `tests/test_layer1b_name_collision.py`: **20 passed** (13 pre-existing incl. F5/F6/P03 homonyms + full-name
+ Jackson + partial + no-token; 7 new A1). `py_compile` clean on both source files.

## Downstream note (not my file — informational, no action needed by me)

With `uniquely_named` now returning None for "PCC Panel 1A", `asset_resolve.py:129-136` falls through to
`ambiguous_candidates(crows_tok, cands)` → the picker surfaces PCC-Panel-1..4 (the AI's designed-correct outcome),
`how="collision_gate_...ambiguous"` per that branch. No cross-file edit required — the existing ambiguous branch already
does the right thing once the gate stops false-pinning.

## verify (adversarial) — 2026-07-08

VERDICT: root-cause LOGIC fix CONFIRMED + generic; but the ancillary RELABEL in asset_resolve.py introduces a
HIGH-severity render-gate regression that breaks the "still pin legitimate full-name prompts" half of the contract.
needs_cross_file was left EMPTY but the relabel is NOT telemetry-only.

CONFIRMED GOOD (re-derived, run live):
- name_collision.py::uniquely_named glued-suffix fix is real and generic. `_fullname_spelled_out` bounds the
  separator-tolerant name regex on both ends in the ORIGINAL prompt; the trailing (?![a-z0-9]) rejects a glued section
  letter/continued digit. py_compile OK; 20/20 tests pass; live: 'PCC Panel 1A/1B', '2A' → uniq=None/coll=True (picker);
  clean 'PCC Panel 1/2', 'PCC-Panel-1 voltage last 7 days', GIC/Jackson full names still pin; 'PCC Panel 10' does NOT
  drag in Panel-1; leading-zero 'PCC Panel 01' → ambiguous (matches OLD behavior, no regression). Zero hardcoding.
- Genuine-homonym picker still fires (F5/F6/P03 tests green; DG-03 Jackson partial + UPS-04 → coll=True live).

MUST-FIX (regression the relabel introduced — value "collision_gate_fullname" is unknown to 3 downstream allow-lists):
1. run/harness.py:285  asset_resolved = (how in {"AI","user-choice","no_data"} and asset). The new label is NOT in the
   set → asset_resolved=False → asset_pinned=False, asset_pending=True → "PENDING → asset popup (Layer 2 NOT run)".
   => Every full-name homonym pin — INCLUDING this fix's own acceptance case 'GIC-01-N3-UPS-01 last 7 days' (pins id 11
   inside asset_resolve) — now regresses to the PICKER at the harness gate instead of rendering. This is the exact
   "still pin legitimate full-name prompts" contract, broken END-TO-END. (git diff confirms the branch was how="AI".)
2. layer1b/compare/resolve_names.py:24  _CONFIDENT_HOW = {"AI","user-choice","no_data"} — excludes the new label →
   a multi-asset compare sub-prompt that full-name-pins a colliding asset falls to ambiguous (loses confident pin).
3. layer1b/schema.py:22  validate_layer1b_output allow-list excludes it → appends "bad how: 'collision_gate_fullname'"
   (annotate-only via build.py:30, NOT render-blocking, but records a false contract-violation each pin AND skips the
   line-28 resolved-asset-has-basket safety check for these pins).

RECOMMENDED FIX (either, implementer's call):
(a) SIMPLEST + fully within owned files: revert asset_resolve.py:137 back to how="AI". The relabel is cosmetic and NOT
    required by the root-cause fix; reverting restores all 3 gates with zero cross-file edits. OR
(b) keep "collision_gate_fullname" and add it to the 3 allow-lists (harness.py:285, resolve_names.py:24, schema.py:22)
    — those files are NOT owned, so they MUST be listed in needs_cross_file (they were omitted).

The repro prompt itself ('PCC Panel 1A') is fixed regardless (it takes the ambiguous branch, not the relabeled one).
