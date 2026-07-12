# Security Audit — pipeline_v48 + ems_backend (lens: security)

Date: 2026-07-12. Read-only pass. Every finding cites file:line I personally opened.
Scope: `/home/rohith/desktop/BFI/backend/layer2/pipeline_v48` and
`/home/rohith/desktop/BFI/backend/layer2/pipeline_v45/ems_backend`.

## Executive summary

The Django `ems_backend` (:8899) is the dominant security risk surface: it ships a **stack of
production-fatal defaults** (DEBUG on, committed SECRET_KEY, ALLOWED_HOSTS `*`, CORS-all + credentials,
AllowAny global permissions) AND a set of **publicly-reachable Keycloak admin endpoints** that let an
unauthenticated caller create users and grant themselves admin roles via a **hardcoded service-account
secret committed to source**. That chain is a full, network-reachable account-takeover.

The V48 pipeline itself (host :8770, copilot :8772, vLLM :8200/:8201) is comparatively clean on *code*
injection — the prompt-injection → SQL path is genuinely defended (LLM output is mapped to a DB-backed
asset registry by name, and every column is intersected against the live `information_schema` before it
touches SQL). Its weakness is **absence of any authn/authz on all four listening ports**, all bound to
`0.0.0.0`, plus unbounded resource use (request bodies, per-run disk logs) on those open ports.

SQL string-building via f-strings is pervasive but currently **internal-only** (table names are
DB-sourced, columns are allowlisted). It is a latent, not active, exploit — flagged so a future careless
call site is caught.

---

## CRITICAL

### C1. Public, unauthenticated Keycloak admin endpoints → account creation + privilege escalation
Files:
- `pipeline_v45/ems_backend/kcauth/views.py:45-47` (`register`, AllowAny + `authentication_classes([])`)
- `pipeline_v45/ems_backend/kcauth/views.py:155-193` (`assign_role`, AllowAny)
- `pipeline_v45/ems_backend/kcauth/views.py:196-262` (`roles` GET/POST/DELETE, AllowAny)
- routes: `pipeline_v45/ems_backend/kcauth/urls.py:5-9`

All three endpoints are decorated `@authentication_classes([])` + `@permission_classes([AllowAny])`, so
anyone who can reach :8899 can call them with no token. `register` creates a Keycloak user with an
attacker-chosen password; `assign_role/<username>` grants the `neuract-admin` client role; `roles/<username>`
POST grants `logger_read`/`logger_write`. Each uses `get_service_account_token()` (the hardcoded admin
secret, see C2) to perform the privileged Keycloak call on the caller's behalf. Exploit chain:
`POST /api/auth/register` → `POST /api/auth/assign-role/<me>` → `POST /api/auth/roles/<me> {"role":"logger_write"}`
= full admin, entirely unauthenticated. The docstrings literally say "Public endpoint" — this is deliberate
but wrong for production.
Fix (breaking): require an authenticated admin caller on `assign_role`/`roles` (attach
`RequireLoggerWrite`/an admin permission), and rate-limit/gate `register`.

### C2. Hardcoded Keycloak admin client secret committed to source
File: `pipeline_v45/ems_backend/kcauth/keycloak_config.py:31`
```
KEYCLOAK_ADMIN_CLIENT_SECRET: str = os.environ.get("KC_ADMIN_CLIENT_SECRET", "SwNbUunGlyDZaxWJoxpTUAwDYuuJqxB5")
```
This is a live-looking service-account secret for client `neuract_owner` (line 30) with realm-admin scope
(it drives user create, password set, role assign in `keycloak_admin.py`). Committed to git, it grants
full Keycloak realm control to anyone who reads the repo. Because it is the fallback default, it is used
whenever the env var is unset — i.e. the default deployment. This is what makes C1 devastating.
Fix (safe): remove the literal, require the env var (fail closed if absent), rotate the secret in Keycloak.

### C3. Django production-fatal settings bundle
File: `pipeline_v45/ems_backend/backend/settings.py`
- `SECRET_KEY = 'django-insecure-...'` hardcoded (line 23) — signs sessions/CSRF/password-reset; known key = forgeable sessions.
- `DEBUG = True` (line 26) — unhandled exceptions render Django's debug page leaking source, settings, env, SQL to any caller.
- `ALLOWED_HOSTS = ['*']` (line 28) — no Host validation; combined with DEBUG the debug page is served to anyone.
- `DEFAULT_PERMISSION_CLASSES = ['rest_framework.permissions.AllowAny']` (lines 60-62) — every DRF view is open; JWT auth (`kcauth/authentication.py`) validates a token if present but nothing *requires* one (grep for `permission_classes` finds only AllowAny occurrences outside `kcauth/permissions.py`). All MFM/asset telemetry, config, nav trees are readable unauthenticated.
Fix (breaking): env-driven SECRET_KEY, DEBUG=False, explicit ALLOWED_HOSTS, flip default permission to IsAuthenticated and opt specific endpoints open.

---

## HIGH

### H1. CORS wildcard + credentials on Django
File: `pipeline_v45/ems_backend/backend/settings.py:86-87`
```
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
```
`django-cors-headers` with allow-all + credentials reflects the caller's `Origin` and sets
`Access-Control-Allow-Credentials: true`, so **any** website a logged-in user visits can make
credentialed cross-origin calls (cookies/session) to :8899 and read the response. With C3's session auth
and admin, this is browser-driven CSRF/data-exfil. Fix (breaking): pin `CORS_ALLOWED_ORIGINS` to the known
frontends; never combine `*` with credentials.

### H2. No authn/authz on any exposed listening port (all bound 0.0.0.0)
- Host API `:8770` — `host/server.py:358` binds `("0.0.0.0", PORT)`; handlers do zero auth. `/api/run`, `/api/frame`, `/api/assets`, `/api/site` are fully open. Anyone on LAN/Tailscale drives the whole LLM pipeline (compute abuse), enumerates every asset (`/api/assets`), and reads all telemetry.
- Copilot `:8772` — `copilot/server.py:119` binds `0.0.0.0`; no auth on `/copilot/suggest` (per-keystroke LLM call) — an open LLM-compute amplifier.
- Django `:8899` — see C3 (AllowAny) + WebSocket consumers: `backend/asgi.py:27` wraps WS in `AuthMiddlewareStack` (Django session only), and the consumers never call the existing `kcauth/ws_auth.authenticate_ws` (grep shows `ws_auth` is imported nowhere in consumers); `ws_auth.py:22-24` even says "Enable when the frontend sends tokens." So every `ws/mfm/{id}/…` telemetry stream is open.
- vLLM `:8200`/`:8201` — `copilot/deploy/vllm-copilot.service` runs `vllm serve … --port 8201` with **no `--host`**, so vLLM defaults to `0.0.0.0`. Anyone on the network can submit arbitrary prompts to the models (GPU/compute abuse, and a lateral path to exfiltrate anything the models are fed).
Fix (breaking): put every service behind auth or bind to localhost/behind an authenticating reverse proxy; wire `authenticate_ws` into the consumers.

### H3. CORS wildcard on host + copilot enables victim-browser pipeline abuse
Files: `host/server.py:203-205`, `copilot/server.py:61-63` (`Access-Control-Allow-Origin: *`).
No credentials are used here, so it is not a data-theft CORS bug, but combined with H2 (no auth) it means
any web page can silently drive `/api/run` and `/copilot/suggest` from a victim's browser (SSRF-by-proxy
into the internal LLM/DB pipeline, GPU cost). Fix (safe): restrict origins to the known frontend.

---

## MEDIUM

### M1. Systemic f-string SQL with table/db identifiers — internal-only today, fragile
The pipeline has three DB clients and ~30 call sites that build SQL by string interpolation with ad-hoc,
inconsistent escaping:
- `data/db_client.q()` — `data/db_client.py:11-21` shells `psql -c <sql>`; SQL is fully caller-built.
- `layer1b/basket/col_dict.py:41,62` interpolate `{table}` raw into `FROM {CONSUMER_SCHEMA}."{table}"`.
- `grounding/meaningful.py:215` `FROM {DATA_SCHEMA}."{_esc(table)}"`.
- `ems_exec/data/neuract.py` builds all reads by f-string (`latest`/`series`/`bucketed`/`edge_count`/…),
  and `ems_exec/executor/load_factor_fill.py:127-133`.
- Escaping is per-caller and inconsistent: `$a$…$a$` dollar-quoting (`col_dict.py:18`), `_esc()`
  (`config/reason_templates.py:12`, `config/quality_policy.py:12`, `config/schema_map.py`), int-cast
  (`host/payload_store.py:88`, `host/exec_cards.py:80`), and raw `"{table}"` quoting elsewhere.

Why not Critical: I traced the tainted paths. Table names come from the DB registry
(`layer1b/resolve/asset_resolve.py:1-6` resolves the LLM's answer *by name* back to a registry row, never
using free-form model text as a table), and every column is intersected against the live schema before
use — `ems_exec/data/neuract.py:72-113` (`present_columns`/`_existing`) and, in Django,
`_VALID_COLUMN_NAME_RE`/`_VALID_COL` (`lt_panels/views.py:37,49`, `consumers/_base.py:48`,
`compare_view.py:18`). So user/LLM input cannot currently reach a SQL identifier slot un-allowlisted.
The risk is that this safety is a per-call-site convention, not a chokepoint: one new call site that
interpolates a value directly (or an admin who writes a hostile `table_name` into `lt_mfm`) is injectable.
`data/db_client.q` shelling to `psql` also means a broken quote is command-context, not just SQL-context.
Fix (safe): centralize identifier quoting (single `qtbl`/`qcol` used everywhere), move `q()` off the psql
subprocess to a parameterizing driver, and assert-allowlist table names at the door.

### M2. Unbounded request-body read on open stdlib servers → memory-exhaustion DoS
Files: `host/server.py:243-244` and `:298`, `copilot/server.py:92-93`:
```
n = int(self.headers.get("Content-Length", "0")); req = json.loads(self.rfile.read(n) or b"{}")
```
No cap on `n`, no body/read timeout (stdlib `ThreadingHTTPServer` has neither). On unauthenticated
0.0.0.0 ports (H2), a single client sending a huge `Content-Length` forces an unbounded allocation/read,
and `daemon_threads=True` (`host/server.py:353`) spawns an unbounded thread per connection. Fix (safe):
reject oversized `Content-Length`, set a socket timeout, cap concurrent threads.

### M3. Unbounded, unrotated logging of prompts/responses to disk
- `host/server.py:181-192` `_dump_response` writes `outputs/logs/response_<run_id>.json` every run, no rotation/cap.
- `obs/ai_log.py:49-50` appends **every LLM request and response** (full prompts, which contain user input and asset data) to `outputs/logs/ai_<run_id>.jsonl` — data-at-rest with no retention limit.
- `copilot/logs/vllm-copilot.log` is a 333k-line file committed in the source tree (per subsystem map + git status noise).
Combined: unbounded disk growth (availability) and sensitive content persisted unencrypted with no
retention policy (confidentiality). Fix (safe): size/age rotation, exclude logs from git, redact/limit AI logs.

### M4. Empty-password postgres over the :5433 tunnel = network-reachable full DB access
Files: `config/databases.py:14-15` (`PG_USER=postgres`, `PG_PASSWORD=""`), `:31` (`db_link()` builds
`postgresql://postgres@host:port/...` with no password), `backend/settings.py:112-121` (Django DB
`USER: 'postgres', PASSWORD: ''`). For a purely local unix-socket `trust` this is fine, but the live data
DB is reached at `127.0.0.1:5433` (an SSH tunnel to archbox). Anyone who can open that TCP endpoint
authenticates as superuser `postgres` with no password. The security of the whole telemetry DB rests
entirely on the tunnel's network reachability, not on any DB credential. Fix (breaking): give the
read path a least-privilege, password-authenticated role; don't rely on `trust`/empty-password for a
TCP-reachable endpoint.

---

## LOW

### L1. `static()` serves MEDIA unconditionally + DEBUG error pages
`backend/urls.py:27` appends `static(settings.MEDIA_URL, document_root=MEDIA_ROOT)` unconditionally
(intended for DEBUG only). Django's `serve` sanitizes `..`, so no traversal, but it ships a dev file
server in prod and, with `DEBUG=True` (C3), any 500 leaks a full traceback + settings. Folds into C3.

### L2. DSN builds with un-encoded password in URL form
`config/neuract_dsn.py:52-57` — `dsn()` interpolates `password()` into the libpq URL without
`urllib.parse.quote`. Default is empty so it is inert today, but a DB-configured password containing URL
metacharacters would break/mis-parse the DSN (and could shift the connection target). `conn_kwargs()`
(the psycopg2 path) is safe. Fix (safe): quote the password or prefer `conn_kwargs`.

### L3. Broad `KEYCLOAK_ALLOWED_ISSUERS` incl. plaintext-http localhost/Tailscale issuers
`kcauth/keycloak_config.py:18-27` accepts a hardcoded set of `http://` issuer URLs (localhost proxies +
`100.90.185.31`). This widens the set of hosts whose tokens are trusted; acceptable for dev, but each extra
trusted issuer is attack surface if any of those proxies is spoofable on the LAN. Fix (safe): drive issuers
purely from env in production.

---

## Notes / positives (for balance)
- Prompt-injection → SQL/tool-exec is genuinely blocked: `asset_resolve.py` maps LLM output back to a
  DB registry by name; `neuract.py` allowlists columns against `information_schema`. This is good design.
- `ems_exec/derivations/evaluate.py:1-4,80-95` executes DB-stored formula expressions with a strict
  AST-whitelist interpreter — **no** `eval`/`exec`. Correct choice.
- No `pickle`, `yaml.load`, `os.system`, or `shell=True` found in either tree (grep clean; the only
  `__import__` is `validation/cli.py:30`, a test/CLI loader with an internal module name).
- Copilot correctly refuses to cache LLM-failure responses (`server.py:41-49`) — avoids a cache-poison DoS.
- DB access from the pipeline is read-only (SELECT/EXISTS); no write path found from the request surface.
