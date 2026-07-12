# Security — production-readiness differential audit (2026-07-12, post-R5/R6)

Lens: security. Differential pass over the prior security lens
(`docs/audit_2026-07-12/security.md`) + the R5/R6 "Fixes Applied" claims in
`AUDIT_REPORT.md`. Focus: (a) regressions from today's concurrent moves, (b) NEW
issues, (c) half-applied refactors / drifted facades, (d) "Fixed/EXECUTED" claims
that are not actually true now.

Scope: pipeline_v48 (host :8770, copilot :8772, admin :8790, vLLM :8200/:8201) +
the MOVED Django `ems_backend` now at `/home/rohith/desktop/BFI/backend/ems_backend`.

READ-ONLY. Findings appended incrementally.

---

## Findings (appended as discovered)

### VERIFIED-OK: R5/R6 fixes landed in BOTH ems_backend trees (no lost fix)
The move copied, not relocated: `pipeline_v45/ems_backend` (untracked, still on disk,
RUNNING per systemd) and `backend/ems_backend` (git-tracked) are BYTE-IDENTICAL
(`diff -rq` = 0 differences; md5 of settings.py, keycloak_config.py, kcauth/views.py,
lt_panels+assets/serializers.py, backend/urls.py, requirements.txt all IDENTICAL).
So R5/R6 fixes are effective at runtime after the pending Daphne restart:
- `backend/settings.py:30` SECRET_KEY env-driven (dev fallback + stderr warning);
  `:35` DEBUG default False; `:37` ALLOWED_HOSTS env; `:118-129` CORS allow-all now
  forces credentials=False (credentialed-wildcard hole closed); `:156-165` DB creds env.
- `kcauth/keycloak_config.py:36` admin secret now `os.environ.get(..., "")` — committed
  literal `SwNbUun...` GONE, fail-closed default. (Prior audit C2 = FIXED.)
- `lt_panels/serializers.py:55` + `assets/serializers.py:54` db_link dropped. (R6 = done.)
- `backend/urls.py:39` `/healthz`; `requirements.txt` present.

### OBS-1 (medium): Running Django uses the UNTRACKED old tree; git tracks a divergent copy
`~/.config/systemd/user/cmdv2-ems-backend.service` `WorkingDirectory=/home/rohith/desktop/
BFI/backend/layer2/pipeline_v45/ems_backend` (daphne :8899, bound 127.0.0.1). But git only
tracks `backend/ems_backend` (169 files staged "A"); `pipeline_v45/ems_backend` is untracked
(0 files in `git ls-files`). Today they are byte-identical, so no live vuln, but this is a
split-brain deployment hazard created by today's move: any future security fix committed to
the git-tracked tree does NOT reach the running service, and edits to the running tree are
invisible to git/review. `ops/SERVICES.md:18` documents the app at `backend/ems_backend`,
contradicting the unit. Fix (owner-gated): repoint the unit at the tracked tree (and restart)
or delete the untracked copy. Positive: :8899 binds 127.0.0.1, not 0.0.0.0.

### OBS-2 (medium): admin console :8790 — new unauth 0.0.0.0 service absent from prior lens
`admin/server.py:166` binds `("0.0.0.0", PORT=8790)`, `:40` `Access-Control-Allow-Origin: *`,
zero auth on every `/admin/api/*` GET and on `POST /admin/api/replay` (which re-fires prompts
at the live host API — an LLM-compute + pipeline-drive amplifier from any LAN/Tailscale host).
The prior security lens H2/H3 enumerated 8770/8772/8899/8200/8201 but NOT :8790 (the Pipeline
Explorer admin console was built today). Same class as H2/H3 but a distinct, uncovered port
that also exposes the full run-artifact corpus (prompts, AI calls, SQL) read-only to anyone.
RUNTIME-CONFIRMED: `curl http://127.0.0.1:8790/admin/api/health` returns
`{"ok":true,"logs_dir":"…/outputs/logs","n_runs":340}` with no auth; `ss -ltnp` shows
8770/8772/8790/8200/8201 all listening on `0.0.0.0` (:8899 Django is NOT — consistent with its
127.0.0.1 unit bind).
No `cfg('api.token')` shared-secret was implemented on ANY pipeline port (grep for
api.token/X-Agent-Token/Authorization in host/ copilot/ admin/ = 0 hits) — the R5/R6 pipeline
recommendation is NOT done (acknowledged "remaining", but note :8790 was never listed).

### OBS-3 (medium): admin run-id validation bypass — strict RUN_ID_RE defeated by adjacent OR
`admin/server.py:81`: `if not rid or not (RUN_ID_RE.match(rid) or rid in ("default","pytest")
or rid.startswith("r_"))`. `RUN_ID_RE = ^r_[0-9a-f]{10}$` (`admin/config.py:18`) is meant to
constrain the run-id, but the `or rid.startswith("r_")` branch makes ANY `r_`-prefixed string
pass (verified: `r_../../etc/passwd`, `r_x/../../y`, `r_%2e%2e` all pass). rid then flows
unsanitized into `store.files_for` → `os.path.join(LOGS_DIR, "response_{rid}.json")` /
`ai_{rid}.jsonl` and is `open()`ed (`admin/trace.py:120` `raw_response`, `:105` ai detail).
Practical arbitrary read is CONSTRAINED (mandatory `response_`/`ai_` filename prefix means the
first path component is never a traversable existing dir; mandatory `.json`/`.jsonl` suffix),
so this is a broken input-control / defense-in-depth defect rather than a confirmed file-read,
in a new unauthenticated 0.0.0.0 service. Fix (safe): drop the `startswith("r_")` branch; rely
on RUN_ID_RE (+ the "default"/"pytest" allowlist) only.

### OBS-4 (medium): "redact" module does size-bounding, NOT content redaction (misleading control)
`obs/redact.py:1-4` — its own docstring: "the ONE size-BOUNDING concern". `bound()` truncates
long strings/lists to a byte budget (`_cap_str`, `_MARK="…[truncated]"`) preserving shape; it
does NO PII/secret scrubbing. So full user prompts and asset telemetry are persisted verbatim
up to the (multi-KB) cap in `obs/event.py:46-53`, `obs/llm_tap.py:97-99`. The prior lens M3 /
AUDIT_REPORT R7 language ("redact/limit AI logs") implies a redaction control that does not
exist — anyone reading the code by module name assumes prompts are scrubbed. Not a new leak
class beyond M3, but a drifted expectation: the on-disk logs still contain raw prompt/response
text. Fix (owner-gated): either add real field redaction or rename to `bound`/`size_cap` so the
absence of content redaction is explicit.

### OBS-5 (high): telemetry retention landed for PG only — on-disk logs (now 1.2 GB) still unbounded
`obs/sink_pg.py:78-119` added a real retention prune (`obs.retention_days` default 30) for the
`obs_*` Postgres tables — good. But the FILE sinks got nothing: `obs/sink_jsonl.py` has no
prune/rotate/gzip (grep clean); `host/server.py:138-146` `_dump_response` writes
`response_<rid>.json` every run with no cap; `obs/ai_log.py` STILL monkeypatches urllib.urlopen
to append every full LLM request/response to `ai_<rid>.jsonl` (`host/server.py:338-340` wires it
— the R7 "retire the urlopen monkeypatch, move logging into call_qwen" was NOT done). Measured
`outputs/logs` = **1.2 GB across 1424 files** (prior audit H15 cited 485 MB — it has ~2.5×'d).
So the R7 "telemetry retention" is HALF-applied: the DB side prunes, the disk side (the actual
bulk, containing raw prompts) grows unbounded. Fix (safe): add age/size prune + gzip to the
jsonl/response file sinks; exclude outputs/logs from git.

### OBS-6 (high): the mandated `KC_ADMIN_CLIENT_SECRET` env fix RE-ARMS the unauth C1 chain
Sequencing hazard between two acknowledged items. `kcauth/views.py:155-158` `assign_role` and
`:196-199` `roles` are STILL `@authentication_classes([])` + `@permission_classes([AllowAny])`
and perform privileged Keycloak calls via `get_service_account_token()` (assign `neuract-admin`,
grant realm roles). Today they FAIL only because `KEYCLOAK_ADMIN_CLIENT_SECRET` defaults to `""`
(`keycloak_config.py:36`) so the service-account token request is rejected — an accidental
fail-closed. But the AUDIT_REPORT's own "ACTION REQUIRED: set KC_ADMIN_CLIENT_SECRET + rotate"
(and kcauth cannot function without it) will REACTIVATE the full unauthenticated account-takeover
chain (register → assign_role → roles) the moment the secret is set, because the C1 role-endpoint
lock is still open ("genuinely remaining"). Anyone who sets the secret per the runbook without ALSO
locking the endpoints re-opens C1. Fix (owner-gated, do in ONE change): attach an admin permission
to `assign_role`/`roles` (+ rate-limit `register`) BEFORE/with setting the secret. Not a new vuln
(C1) but a genuine remediation-ordering trap introduced by the R5/R6 fail-closed default.

### VERIFIED-OK: SQL surface unchanged & improved through the new pooled engine
The R2 pooled `q(db, sql)` (`data/db_client.py`) still takes caller-built SQL (no params), but the
caller SQL strings are byte-unchanged, so prior M1's conclusion holds: identifiers are registry/
DB-derived, card_ids `int()`-cast (`layer2/catalog/*`), page_key/component dollar-quoted
(`$a$…$a$`, `layer2/build.py:22`, `swap/candidates.py:54`), table names from the registry. Asset
resolution maps the LLM's free-text answer to a registry row via IN-MEMORY dict lookup
(`layer1b/resolve/asset_resolve.py:97,111-117` `by_name`/`by_norm`/`by_alias`) — free-form
prompt/asset text never reaches a SQL slot. IMPROVEMENT: the default `pool` engine executes via
psycopg2 + `COPY(...) TO STDOUT`, so M1's "broken quote → psql COMMAND context" risk is now
off-by-default (only the `V48_DB_ENGINE=psql` rollback shells out). Sampled ~20 f-string sites; no
new user-text-to-SQL path.

### VERIFIED-OK: no committed secrets in either tree; C2 secret genuinely gone
`grep -rniE '(password|client_secret|api_key|secret_key|admin_secret)=<literal>'` over
`backend/ems_backend` + `pipeline_v48` (excl docs/example/dev-fallback) = 0 hits; no
`BEGIN PRIVATE KEY`, no `postgresql://user:pass@`, no `Bearer`/AWS keys. The C2 literal
`SwNbUunGlyDZaxWJoxpTUAwDYuuJqxB5` is GONE (env-only, fail-closed). Tracked env files
(`backend/.env.example` = placeholders; `frontend/.env.production.local` = public NEXT_PUBLIC_*
URLs, different subsystem) hold no real secrets. Only committed credential fallback is the Django
`_DEV_SECRET` (settings.py:29, known/flagged C3) + empty PG password (config/databases.py:15,
env-driven, unchanged M4). NOTE (low): committing `frontend/.env.production.local` at all is a
smell (`.env*.local` should be gitignored) even though its current content is non-secret.

### VERIFIED-OK: R6 db_link serializer fix complete; moved tree compiles
`lt_panels/serializers.py:55` + `assets/serializers.py:54` drop db_link from the anonymous REST
output. Remaining `db_link` refs are internal DB-fetch inputs in WS consumers / compare_view /
pcc_panel (correct — the connection string is used server-side, never serialized). `py_compile` of
all six moved-tree security files = OK (the move introduced no syntax breakage). Both ems_backend
trees byte-identical, so the running (untracked pipeline_v45) copy has the identical fixes.

### VERIFIED (unchanged, acknowledged-open): vLLM 8200/8201 still bind 0.0.0.0
`~/.config/systemd/user/vllm.service` (:8200) and `vllm-copilot.service` (:8201) ExecStart have no
`--host`, so vLLM defaults to 0.0.0.0 (verified full ExecStart blocks). The prior audit's "bind
vLLM to localhost" recommendation is NOT applied — but it is explicitly listed as remaining in
AUDIT_REPORT R5/R6, so this only CONFIRMS the open state (not a new/regressed finding).

