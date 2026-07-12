# Completeness Critic — prod-readiness audit 2026-07-12

Role: cross-dimension gap analysis over the 15 lens docs in this directory, vs the user's requested
scope (35 areas + 20 workflows) and the prior-audit context (AUDIT_REPORT.md, EXECUTED_AND_FOLLOWUPS.md).
READ-ONLY; contested facts below were re-resolved live (file reads, `ls`, SELECT-only psql on :5432/:5433,
git status of both repos). Timestamps matter: the tree was edited by concurrent sessions DURING the audit
(host/server.py 07:58, host/multi_asset.py 07:59, fill.py extraction 07:41, AUDIT_REPORT.md itself 07:42),
so several lens docs describe file states that no longer exist.

---

## A. Contradictions BETWEEN dimension docs (with live resolution)

### A1. The `kind:"dashboard"` envelope stamp — four docs, three different states. RESOLVED LIVE.
- host-api OBS-1: "the server never stamps kind; types.ts declares it required" (read pre-07:38).
- fixes-verification #17/OBS-1/OBS-2: server.py:97 stamps it; types.ts comment says it does NOT.
- frontend Verified-OK: "server stamps kind only on the knowledge branch; DashboardResult.kind stays optional".
- followups-triage §A.b: stamp landed 07:38 single-path only.
- **Live truth (probed)**: `host/server.py:98` stamps `"kind":"dashboard"` (mtime 07:58);
  `host/multi_asset.py` (mtime 07:59 — edited AFTER every lens) still has NO kind stamp;
  `types.ts:136-138` declares `kind:"dashboard"` **required** ("[R10 completed]").
  So **every multi-asset response violates the required TS discriminant right now**, and the running
  host (pid 561102, started 07:35) serves neither stamp. The one-line multi fix recommended by three
  lenses did not land even though multi_asset.py was edited after the audits.

### A2. R3 `::timestamptz` index apply — triage/config docs vs AUDIT_REPORT sixth pass. RESOLVED LIVE.
- followups-triage R3 row + OBS-7: "DDL NOT applied — C3 seq-scans persist; owner-gated."
- config-db Verified-OK: schema_migrations = 0 rows; seed files "NOT yet applied".
- AUDIT_REPORT item 23 (added ~07:42, after those lenses ran): "R3 index APPLIED + knob flipped ON".
- **Live truth (probed)**: `neuract.ts_imm()` function EXISTS on :5433, **240 ts_imm expression
  indexes** exist in schema neuract (claim said 241 indexable), `app_config.neuract.ts_index_fn = ts_imm`,
  and `schema_migrations` now has exactly **1 row** (`seed_ts_index_fn.sql`). The triage table's owner
  queue (OBS-7) and config-db's ledger state are stale. Residue: the knob is process-cached — the
  RUNNING host still emits `::timestamptz` (seq scans) until the pending restart, and no lens verified
  post-restart index usage from the pipeline's own reads.

### A3. `pipeline_v45/ems_backend`: symlink or divergent copy? RESOLVED LIVE — security OBS-1 is void.
- security OBS-1 (medium): "The move copied, not relocated ... split-brain deployment hazard: a fix
  committed to the git-tracked tree does NOT reach the running service."
- fixes-verification #16 + refactor-integrity: "old path is a SYMLINK → ../../ems_backend (07:28)".
- **Live truth (probed)**: `pipeline_v45/ems_backend` is a symlink (lrwxrwxrwx, 07:28) → `../../ems_backend`.
  There is ONE tree; edits to the tracked tree DO reach the running Daphne. Security's medium finding
  should be re-verdicted (the residual real item is only doc/unit-path hygiene), so nobody executes its
  "repoint the unit or delete the copy" fix against a phantom problem.

### A4. `validation/` alias: sweep doc contradicts itself and refactor-integrity.
sweep-validation-admin:11 claims "One code home, no duplication", while its own OBS-1 proves
`sweep/cli.py`'s dotted `validation.*` imports load every analyzer TWICE, and refactor-integrity OBS-2
proves the alias is not identity-preserving for `import validation.x`. The header claim should be
corrected before anyone cites it; the OBS-1 fix (string-replace 11 sites) is prerequisite to trusting
any sweep-run metrics.

### A5. followups-triage — the execution queue — was stale on ≥2 rows within the hour.
Its monoliths F4-F10 row (meta_path hook "still installed", fill.py 672 lines) was already false when
written (ems-exec OBS-5: hook deleted, fill.py 620, extraction landed 07:39-07:41), and its R3 row is
now false (A2). Section E's suggested execution order must be re-baselined against the current tree
before the main session executes it, or work gets re-planned/duplicated.

### A6. AUDIT_REPORT.md is a moving target the verification lens partially missed.
fixes-verification (07:43) verified "22 of 22 claims" and cites AUDIT_REPORT:310-311 ("kind stamp ...
genuinely remaining") — text that no longer exists: AUDIT_REPORT (mtime 07:42) now contains a SIXTH
pass (items 23-25) declaring that item done. Items 23-25 were therefore **never independently verified
by any dimension** (see B1).

---

## B. Claims asserted but unverified

### B1. Fixes 23-25 sat outside every lens's scope.
- Item 23 (R3 apply): now verified by THIS critic (A2) — but only via live probes today; no lens checked
  index USAGE (EXPLAIN through the pipeline door) post-restart.
- Item 24 (kind stamp): verified single-path only; multi-path hole confirmed (A1).
- Item 25 (SECRET_KEY + .env plumbing): `.env`/`.env.example` exist (probed); NOT verified: that
  settings.py actually loads it (django-environ), that `.env` is gitignored in the tracked tree, and the
  Keycloak rotation remains genuinely open (security OBS-6's re-arm trap applies).

### B2. No full pytest suite run exists for the FINAL tree state.
Every lens ran collect-only (992/1029) plus spot runs (39+28+15+21+32+3 tests). The "228 passed" /
"882 suite green" claims predate today's churn; fill.py/field_routing/series_router landed 07:41 and
server.py/multi_asset.py were edited 07:58-59 — AFTER all test evidence. A concurrent session's full run
(PID 560898) was observed but its result was never read. There is no recorded suite-green for the code
that will actually be committed/restarted.

### B3. Replay engine never executed.
obs-replay says so explicitly ("a live pinned replay was NOT executed ... structural + unit-level
verification only"). The engine's core promise — pinned re-execution reproduces a run — is unproven
against the new pooled q() engine, the trace layer, and today's tape seams.

### B4. "Nightly pg_dump stays the recovery source of truth" (AUDIT_REPORT R9) — no lens verified any
pg_dump job exists (no timer/cron was found by tests-ci TC-4, which actually suggests it does NOT).
Backup/DR posture is asserted, not audited.

### B5. Registry mirror freshness. All 1b resolution reads are "cmd_catalog registry_* mirror-first,
live fallback" (scripts/sync_neuract_registry.py). No lens checked when the mirror was last synced vs
live lt_mfm — a stale mirror silently mis-resolves assets (the exact class the panel-topology memory
warns about). One SELECT comparing row counts/max-updated between registry_lt_mfm and live lt_mfm closes it.

### B6. The prompt-testing framework itself is broken AND unexercised.
sweep OBS-3 empirically proved zeroed metrics/failures bundles, abs-path session ids, a dead `coverage`
subcommand, and a dropped `determinism --session`. No lens ran a live sweep (forbidden). Net: the
30,747-case corpus has never been run end-to-end, and if it were run today its reports would be wrong.
The release-gating instrument is doubly ungated.

---

## C. Scope areas / workflows NO dimension covered

### C1. Live end-to-end workflow validation — the entire requested list. (LARGEST GAP)
None of the 20 requested workflows was exercised this round: single asset, panel aggregate, compare,
historical, DateSync, knowledge, off-domain, alias, ambiguous picker, invalid/mechanical/electrical
assets, AI summaries, SLD, 3D, Sankey, multi-page, degradation, zero-fabrication, parallel execution,
replay, prompt-test-framework. All lenses were read-only by constraint (no POST /api/run). The last
zero-fabrication/render cert is 2026-07-07 — it predates today's ~590-file drift (pooled DB engine,
gates/ split, fill.py split, always-v2 emit path, metadata_resolve extraction, obs layer). The only live
workflow evidence today is one passively-observed honest-terminal outage (followups §D.16) and an
offline SSR gate over 2 archived responses / 8 cards (frontend). A post-restart live smoke matrix
(one prompt per workflow, per-leaf REAL/EMPTY diffed as in the deep-validation-sweep method) is the
single highest-value missing check.

### C2. Performance/latency — no dimension. R2 (pooled engine) and R3 (240 indexes) both landed today;
nobody re-measured. Prior baseline p50 37.8s / p99 219s / l2_emit 19.8s-per-card is unexamined against
the new stack; the R3 "80×" claim rests on one probe table checked by the applying session. The
profiler/ package exists (mine + live modes) and was not run.

### C3. Memory usage — no dimension. Found-by-accident items exist (admin store._CACHE unbounded,
sweep OBS-5; obs queue bounded), but nobody measured RSS/growth of the long-running :8770 process with
the new TTLCaches, connection pool, obs sinks, and 1.2GB of log writers.

### C4. Concurrency under load — static only. data-layer OBS-3 (both neuract doors now serialize on ONE
lock with connect() inside it) and OBS-5 (unbounded concurrent connections) are analyses, not tests;
"parallel execution" (multi-asset lanes + L2 fan-out + concurrent /api/run) was never exercised. The
prior concurrency lens was not re-run as a dimension this round.

### C5. Release/commit integrity — uncovered, and the state is hazardous.
Probed: pipeline_v48 has a NESTED git repo (`pipeline_v48/.git`) with **347 modified / 241 untracked /
5 deleted** files vs its HEAD; the outer BFI repo sees the entire tree as ONE untracked directory (a
nested repo — the outer repo cannot commit it). Consequences no lens audited: (a) the nested HEAD is
not runnable (fill.py at HEAD lacks today's field_routing/series_router companions — mixed states);
(b) tracked tsconfig.json extends UNTRACKED tsconfig.cmdv2.json (frontend OBS-1 found the FE slice, but
nobody swept the whole tree for tracked-depends-on-untracked); (c) there is no record of what the
pending "mega-commit" will contain, in which repo, or whether _archive/ and outputs/ are excluded.

### C6. Restart orchestration — every lens defers to "the pending restart" but nobody owns it.
Inert-until-restart items now include: kind stamp (A1), ts_index_fn adoption (A2), obs run-id/jsonl
fixes (obs OBS-1/2), plus the stray half-alive server pid 562703 (followups OBS-3) that could seize
:8770 with stale code during that restart. Django side likewise: R5/R6 are inert until a Daphne restart
WITH env set, and security OBS-6's C1 re-arm trap must be sequenced with it. A single owner checklist
(kill stray → restart :8770 → verify kind/index-scan/obs attribution → Daphne restart with env + locked
role endpoints) does not exist in any doc.

### C7. DateSync / cross-card time-sync — not audited. Nobody read the sync_links/TimeSyncProvider
path (host/src) or DateSync.tsx beyond a known-open re-render note; sweep OBS-6 shows the datesync
CHECK is loaded under two module names and `determinism --session` collides sessions. The DateSync
workflow (change date on card A → interdependent card B refetches, honest on failure — FE F1 silent
.catch(() => {}) still open) is unvalidated.

### C8. SLD and 3D renderers — essentially untouched (Sankey got one positive check). asset_3d /
kitpreview / GLB media path appears only in refactor-integrity OBS-3 (the GLB-present test silently
SKIPs once the transition symlink is retired). No render validation of topology_sld or asset_3d cards.

### C9. Knowledge-gate internals — only the envelope and taping were verified. Route/answer quality and
off-domain refusal were not exercised (corpus off_domain pool is also 54/300 short, sweep notes).
NEW and unexamined: server.py:344 now branches on `_k["kind"] in ("knowledge","off_scope")` — an
`off_scope` kind appeared in the 07:58 edit window that no lens doc and no types.ts vocabulary mentions.

### C10. Copilot (:8772) internals — only its port exposure (security) and its coupling guard
(tests-ci TC-1: guard collects ZERO tests under pytest) were covered; retrieve→generate behavior and
its FE service path (PromptBar) were not audited this round.

---

## D. Minor cross-doc consistency notes (no action beyond doc edits)
- outputs/logs growth figures differ per lens (1.2G / 1417→1428→1424→1441 files) — same-morning growth,
  consistent, and itself evidence for the retention finding (obs OBS-2 / security OBS-5 / followups OBS-4).
- tests-ci "15 files use the live marker" vs fixes-verification "all 9 named files" — superset, not conflict.
- Three lenses independently converged on the PEP-562 frozen-from-import list (layer1a-1b OBS-1,
  layer2-grounding OBS-3, config-db OBS-3) — consistent; treat as one fix campaign, one test.
