# Fix log — group: lazy-knobs — 2026-07-12

Findings: config-db OBS-3, layer1a-1b OBS-1, layer2-grounding OBS-3.
Defect class: module-level `from config.X import KNOB` (or `NAME = cfg(...)` at module top) evaluates the
PEP-562 lazy accessor ONCE at the consumer's import and pins the boot value for process life — a DB knob edit
(+ app_config.reload()) never reaches the site without a restart. Fix pattern: `from config import X as _x` +
`_x.KNOB` read per call (the in-tree house pattern, see gate_force_renderable's feasibility reads), or a
per-call cfg() read; where the name is an external contract (tests / barrel re-export) a module `__getattr__`
keeps the attribute visible while re-reading per access. cfg() is process-cached on success, so per-call
reads are cheap; healthy-path behavior with an unchanged DB is identical.

## Changes

### 1. layer1a/parse/template_feasibility_gate.py  [layer1a-1b OBS-1, config-db OBS-3]
`from config.feasibility import TEMPLATE_MAX_UNRENDERABLE_FRAC` → `from config import feasibility as _feas`;
`thr = _feas.TEMPLATE_MAX_UNRENDERABLE_FRAC ...` (per-call). `threshold=` override path untouched.

### 2. layer1a/db_reads/page_feasibility.py  [layer1a-1b OBS-1, config-db OBS-3]
`from config.feasibility import UNRENDERABLE_VERDICTS` → module import + `_feas.UNRENDERABLE_VERDICTS`
at the SQL-splice site (per-call).

### 3. layer1a/parse/metric_intent_defaults.py  [layer1a-1b OBS-1, config-db OBS-3]
`from config.intents import INTENT_DEFAULT, INTENT_VOCAB` → `from config import intents as _intents`; both
knobs read per call inside clamp_metric_intent (INTENT_DEFAULT read once per call into a local so both uses
inside one clamp see the same value — same intra-call consistency as before). Kills the split-brain
layer1a-1b OBS-1 describes (route.py reads intents.vocab live while the clamp used the pinned boot value).

### 4. layer1a/route.py  [layer1a-1b OBS-1, config-db OBS-3]
`from config.metrics import METRIC_VOCAB` → `from config import metrics as _metrics`; one per-call read
`_metric_vocab = _metrics.METRIC_VOCAB` inside route() feeds all 3 uses (prompt line, decision-inspector
vocab, route_answer_schema) — same single-object sharing as before, now per call. route_to() has no
METRIC_VOCAB use; untouched.

### 5. layer2/swap/gate_confidence.py  [config-db OBS-3, layer2-grounding OBS-3]
`from config.swap import MIN_CONFIDENCE` → `from config import swap as _swap` + `_swap.MIN_CONFIDENCE` in ok().

### 6. layer2/swap/gate_vague_reject.py  [config-db OBS-3, layer2-grounding OBS-3]
Same pattern for VAGUE_CRITERIA.

### 7. layer2/swap/candidates.py  [config-db OBS-3, layer2-grounding OBS-3]
- `from config.swap import SIZE_TOLERANCE, SWAP_POOL_MAX` → `from config import swap as _swap`; pool() reads
  `tol, pool_max = _swap.SIZE_TOLERANCE, _swap.SWAP_POOL_MAX` once per call (both SWAP_POOL_MAX uses and all
  4 tolerance uses see one consistent per-call value).
- `POOL_VERDICTS = tuple(... cfg(...))` import-time freeze → `_pool_verdicts()` per-call reader used at the
  verdict_in splice, plus a module `__getattr__` keeping `candidates.POOL_VERDICTS` visible (consumer:
  tests/test_layer2_swap_gates.py:195 reads the module attr) while re-reading the knob per access.
  (OBS-3 also notes `pool_verdicts` is not in config/feasibility._LAZY — not needed: this module reads the
  cfg key directly per call; adding a config-module home would touch a file outside this group's list.)

### 8. layer2/swap/gate_force_renderable.py  [layer2-grounding OBS-3]
`FORCED_SWAP_CONFIDENCE = cfg("swap.forced_swap_confidence", 2.0)` at import → `_forced_confidence()` per-call
helper used in enforce(), plus module `__getattr__` keeping `gate_force_renderable.FORCED_SWAP_CONFIDENCE`
(consumer: tests/test_layer2_swap_gates.py:104) as a per-access read. NOTE: a module `__getattr__` does NOT
intercept global-name lookups inside the module's own functions, hence the helper at the enforce() call site.
Its feasibility reads were already per-call (`_feas.`); untouched.

### 9. layer2/emit/instructions/consumer_binding/screen_map.py  [layer2-grounding OBS-3]
`_PAGE_TAIL_ALIAS = cfg("routes.page_tail_alias", ...)` at import → `_page_tail_alias()` read per
page_endpoint() call. Private name; grep confirms zero consumers outside this file.

### 10. layer2/emit/instructions/consumer_binding/domain.py  [layer2-grounding OBS-3]
`RETIRED_ENDPOINTS = set(cfg("routes.retired_endpoints", ...))` at import → `_retired_endpoints()` + module
`__getattr__` (the name is a public back-compat export via the package barrel + __all__).

### 11. layer2/emit/instructions/consumer_binding/__init__.py  [layer2-grounding OBS-3 — freeze chain of #10]
The barrel's module-level `from ...domain import RETIRED_ENDPOINTS` re-froze the knob at package import,
making fix #10 inert (emit.py:138 imports the name from the PACKAGE inside a function). Replaced with a
package `__getattr__` delegating to domain per access. `from ... import RETIRED_ENDPOINTS` and
`import *` (__all__) semantics preserved — verified by probe. OWNERSHIP NOTE: this file is not named in the
audit docs' site list but carries the same import-time-frozen knob from-import for the same knob; it is not
in the group's EXCLUDING list, and without it the listed site's fix has no effect. Judged in-scope; flagged
here for the orchestrator. emit.py itself (EXCLUDED file) needed no edit — its function-level from-import is
now fully lazy through the barrel.

### 12. layer2/catalog/card_grid_size.py  [layer2-grounding OBS-3]
`DEFAULT_VIEWPORT = cfg("card_grid_size.default_viewport", "1920x1080")` at import → per-call cfg() read at
the single defaulted-return site. Name deleted: tree-wide grep (v48 + backend/layer2 minus _archive/v47)
proves zero consumers of `DEFAULT_VIEWPORT` / `card_grid_size.DEFAULT` outside this file (verify-before-dead).

### config/swap.py — NO EDIT (checked per brief)
The layer2-grounding OBS-3 "PEP-562 conversion of config/swap.py is INEFFECTIVE" defect is located in the
CONSUMERS (gate_confidence / gate_vague_reject / candidates from-import the lazy attrs at their import —
fixed above as #5-#7). config/swap.py's own _LAZY + __getattr__ implementation is correct (raises
AttributeError on unknown names, matches config/feasibility.py / config/metrics.py); nothing to fix in-file.

## Test evidence (2026-07-12 ~08:15)

- `python3 -m py_compile` on all 12 edited files: OK.
- Import probe: all 12 modules import clean; module-attr contracts hold (candidates.POOL_VERDICTS,
  gate_force_renderable.FORCED_SWAP_CONFIDENCE, package RETIRED_ENDPOINTS via from-import, pkg-attr and
  star-import). Healthy-path outputs unchanged: clamp ('power factor','JUNK')→('pf','trend'),
  page_endpoint harmonics-pq→power-quality-summary / overview-sld-3d→overview, gate math, template gate
  drop/fallback.
- LAZINESS PROOF (the actual finding): monkeypatched app_config._CACHE with edited rows
  (swap.min_confidence=0.10, feasibility.pool_verdicts +static_chrome, swap.forced_swap_confidence=3.5,
  routes.retired_endpoints=["zzz"]) — every converted site picked the new value WITHOUT re-import:
  gate_confidence.ok(0.5)→True, POOL_VERDICTS→('render_real','static_chrome'), FORCED_SWAP_CONFIDENCE→3.5,
  enforce() stamps confidence=3.5, barrel RETIRED_ENDPOINTS→{"zzz"}. Cache reset after.
- Targeted offline pytest: tests/test_layer2_swap_gates.py, tests/test_swap_metric_affinity.py,
  tests/test_layer1a_routing.py, tests/test_residual_layer2_emit.py, tests/property/test_prop_intent_clamp.py,
  tests/property/test_prop_route_fail_closed.py → **58 passed, 1 skipped, 4 deselected(live)**;
  plus tests/test_layer2_card.py (direct card_grid_size/consumer_binding coverage) → **9 passed, 2 skipped,
  1 deselected**.

## Skipped

- config/swap.py edit — defect determined to live in consumers, not the module (see above).
- Adding `pool_verdicts` to config/feasibility._LAZY (mentioned in layer2-grounding OBS-3) — config/
  feasibility.py is not an audit-listed frozen SITE and not in this group's file list; the per-call cfg()
  read in candidates.py fully restores liveness without it.

