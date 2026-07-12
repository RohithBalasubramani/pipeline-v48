# Hardcoded Business Rules Audit — pipeline_v48 (2026-07-12)

Lens: magic numbers with domain meaning, hardcoded card ids / page names / asset names / table names, per-card/per-page
special-cases, prompt fragments that should be DB rows, and code-default-vs-seed divergence. Method: targeted grep of
all python (excluding tests) + reading of the derivations/gates/story layers.

## Overall assessment

**This is the codebase's strongest dimension.** The DB-driven-config discipline is real and pervasive: the derivations
layer — the place most likely to hide fabricated physics — is exemplary, every threshold is a `cfg()` call with the code
constant as a *documented mirror* of a seeded row. There is **zero hardcoded card-id branching in the executor**
(verified by grep: card numbers appear almost only in provenance comments). The genuine violations are few, already
found by other lenses, and small. The more interesting finding is the *shape* of the residual risk: because business
logic legitimately lives in DB rows now, the failure mode has moved from "hardcoded constant" to "unvalidated DB row"
(see H4).

---

## H1 — MEDIUM — `CARD_PAGE`: a hardcoded card-id → page map in code (the one true AI-first violation in the executor)

`ems_exec/renderers/_story/__init__.py:38-43`:
```python
CARD_PAGE = {8: "real-time-monitoring", 19: "voltage-current", 25: "harmonics-pq", 28: "individual-feeder"}
```
Used by `narrative_ai._page_key` when ctx omits `page_key`. A fifth narrative card or a renumber is a code edit — and
the codebase elsewhere goes to great lengths to avoid exactly this (`renderers/__init__.py:57-63` replaced a card-63
id-hardcode with a shape discriminator; `cmd_catalog.card_handling` exists to classify cards). Same finding as
`code-quality-exec` M9. **Recommendation:** move to a `cmd_catalog` row (a `card_handling` column or an `app_config`
json), keeping this dict as the code-default mirror — the established pattern. Safe.

## H2 — MEDIUM — `endpoint_registry._FALLBACK`: a hardcoded route snapshot that two docstrings claim is "derived"

`layer2/emit/data/endpoint_registry.py:8-18` — `_FALLBACK = [...]`, `PAGES = _FALLBACK`; nothing parses ems_backend's
route table, yet `consumer_binding/__init__.py:16-18` and `screen_map.py:3-5` both assert the endpoint truth "parses
ems_backend's OWN `_PAGES` … so this follows ems_backend automatically (no drift)". When ems_backend adds/renames a WS
route, the AI's closed endpoint set silently drifts. Same as `code-quality-layers` finding 4. **Recommendation:** either
actually derive it, or mirror it into a `cmd_catalog` row with this list as fallback, and fix the two lying docstrings +
add a parity test. Safe.

## H3 — MEDIUM — Django per-site model hardcoded in Python across four places (bind-by-display-name)

`ems_backend/lt_panels/electrical_equipment.py` (587-line topology tree), `lt_panels/views.py:252-432` (ASSETS_TREE /
BMS_TREE / _OVERVIEW_PAGES), `management/commands/seed_mfms.py` (179-row literal MFM list). The customer's single-line
topology, asset inventory and nav trees are literal dicts that bind to live data by **exact display-name string match** —
a DB rename silently unbinds a nav leaf, and onboarding a second site means editing code. Same as the `django` lens
finding 6. **Recommendation:** move the trees to a DB table (or derive from the existing incoming/outgoing M2M) and bind
by id/slug. Breaking (data migration; output shape preserved).

## H4 — MEDIUM — The risk has moved from "hardcoded rule" to "unvalidated DB rule"

Because the project correctly relocated per-card logic into rows (`roster_spec` JSONB DSL in `card_fill_recipe`,
`derivation_binding.expression`, quantity vocab), the new failure mode is a **typo'd row discovered only as an
honest-blank leaf at render time** — code would have failed at review/test. Concretely:
- `db/seed_roster_recipes.sql` (623 lines) is an unvalidated per-card fill DSL (`database` F16).
- `derivations/energy.py:305-315` bans reactive-energy-from-power in code, but `derivations/registry.py:303-325`
  consults `derivation_binding.expression` *first* — so a DB row can silently resurrect the banned fabrication class
  (`code-quality-exec` M6). The ban is code-enforced but DB-bypassable.

**Recommendation:** JSON-Schema-validate `roster_spec` and every `derivation_binding` row in the test suite; enforce the
reactive-energy ban at the dispatch layer (a banned-set checked in `_execute`), not only in the neutered fn. Safe.

## H5 — LOW — Import-time-frozen knobs: DB-driven in principle, code-frozen in practice

~14 modules resolve `cfg()` into module-level constants at import (`code-quality-layers` 5, `code-quality-platform` F2,
`code-quality-exec` M5): e.g. `layer2/gates.py:14`, `layer2/swap/candidates.py:19`, `renderers/panel_aggregate.py:66`,
`config/windows.py`, `config/intents.py`. These read the row once at import, so editing the row does nothing until a
restart — silently divergent from the "edit a row, no code change" contract stated in the adjacent comments, and (before
the 2026-07-12 `cfg()` never-cache-empty fix) frozen to the code default if cmd_catalog was down at boot.
**Recommendation:** wrap each in the call-time accessor pattern the neighbors already use. Safe.

## What is genuinely good (keep — do NOT "fix" these into rows prematurely)

- `ems_exec/derivations/power.py:31-56`, `nameplate.py:24-32` — every threshold (`_LF_ENERGIZED_FRACTION=0.02`,
  `_LF_CEILING_PCT=100`, `_LOADING_PLAUSIBLE_MAX_PCT=200`, `nominal_pf=0.8`) is a `cfg()` call with the constant as a
  **documented code-default mirror** of a seeded row, validated on read (`0 < v < 1` etc.). This is the model the rest
  of the codebase should be measured against.
- Zero hardcoded card-id branches in `ems_exec/executor` (grep-verified); card numbers appear in provenance comments,
  not control flow.
- Route/metric/intent enums are substituted into prompts from the same config the clamps read (`layer1a/route.py:76-80`)
  — prompt and code cannot drift on the closed vocabularies.
