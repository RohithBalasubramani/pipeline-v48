# Django lens audit — ems_backend (pipeline_v45)

Date: 2026-07-12
Scope: `/home/rohith/desktop/BFI/backend/layer2/pipeline_v45/ems_backend`
Reviewer lens: django (settings hygiene, ORM, WS consumers, REST, auth, migrations, deps, V48 data-source fit, legacy endpoints).
Conduct: read-only; every finding cites files/lines personally read.

## Verdict

The data-broker core (`lt_panels/services.py`, the dispatcher/strategy WS pattern, column-tolerance,
IST bucketing) is genuinely good engineering: read-only, parametrized SQL, single-flight cache, circuit
breakers, registry-driven routing. The problems are concentrated in **(1) production settings hygiene —
this app is configured as a dev toybox**, **(2) an auth system that is fully built but wired to AllowAny so
nothing is enforced**, **(3) a committed Keycloak admin secret**, **(4) an InMemoryChannelLayer that caps
the WS tier at a single process**, and **(5) a large volume of hardcoded per-site data + an entire
duplicated `assets/` app that V48 never calls.** None of the data-path SQL is injectable; the risks are
operational and organizational, not correctness-of-query.

---

## Findings (ranked)

### 1. [Critical] Committed Keycloak admin-client secret in source (git-tracked)
`kcauth/keycloak_config.py:31`
```python
KEYCLOAK_ADMIN_CLIENT_SECRET: str = os.environ.get("KC_ADMIN_CLIENT_SECRET", "SwNbUunGlyDZaxWJoxpTUAwDYuuJqxB5")
```
`git ls-files` confirms the file is tracked and the secret is in history since commit `009c5f5`. This is the
service-account secret for `neuract_owner`, the client used by `keycloak_admin.get_service_account_token()`
which then creates users, sets passwords, and assigns roles (`kcauth/views.py:68-77`, `:161-178`). Anyone
with repo read access can mint that token and administer the Keycloak realm. The env-var fallback pattern
is correct; the literal default must be removed and the secret rotated.
- Fix: delete the literal, require the env var (fail closed if unset), rotate the Keycloak secret, scrub git history.
- safe_or_breaking: breaking (deployments without `KC_ADMIN_CLIENT_SECRET` set will start failing until env is provided — which is the point).

### 2. [Critical] Production settings are dev defaults across the board
`backend/settings.py:23-28,60-63,86-87,117`
- `SECRET_KEY = 'django-insecure-...'` hardcoded and committed (line 23).
- `DEBUG = True` (line 26) — leaks tracebacks/env on any 500, and DRF/Django render verbose error pages.
- `ALLOWED_HOSTS = ['*']` (line 28).
- `CORS_ALLOW_ALL_ORIGINS = True` **with** `CORS_ALLOW_CREDENTIALS = True` (lines 86-87) — any origin may send credentialed requests; the two together are the classic misconfig that defeats CORS.
- `DEFAULT_PERMISSION_CLASSES = ['AllowAny']` (lines 60-63) — see finding 3.
- DB `PASSWORD: ''` with `USER: 'postgres'` (line 117) — empty superuser password.

This is one Critical because collectively they mean the service has no server-side trust boundary in
production. Move all of these to env-driven config (django default is fine: `os.environ`), default DEBUG
False, pin ALLOWED_HOSTS, replace CORS-all with an allowlist.
- safe_or_breaking: breaking (tightening CORS/ALLOWED_HOSTS/DEBUG changes what requests succeed).

### 3. [Critical] Complete auth/permission stack exists but is disabled globally
`backend/settings.py:56-63`, `kcauth/permissions.py` (whole file), `kcauth/ws_auth.py:23-24`
The project ported a full Keycloak JWT auth layer — `KeycloakAuthentication`, `RequireLoggerRead/Write`,
`SafeOrWrite`, and a WS middleware — but `DEFAULT_PERMISSION_CLASSES` is `AllowAny` and a tree-wide grep shows
**no view or viewset sets `permission_classes` to any of the Require* classes** (only reference outside kcauth
is the comment at settings.py:54). `kcauth/ws_auth.py:23-24` explicitly notes the WS middleware is "not wired
into asgi.py"; `backend/asgi.py:27` confirms WS uses bare `AuthMiddlewareStack` with no Keycloak gate. Net:
every REST endpoint and every WebSocket is fully anonymous. All MFM telemetry, topology, config
(thresholds/nameplates), and the entire site model are readable by anyone who can reach the port. For an
enterprise EMS this is an unauthenticated data-exposure surface.
- Additionally the public auth endpoints are intentionally unauthenticated: `kcauth/views.py:45-48,155-158,196-198` make `register`, `assign_role`, and `roles` (POST/DELETE) `AllowAny` — anyone can self-register a Keycloak user and (via assign_role) grant the `neuract-admin` client role. That is a privilege-escalation path, not just read exposure.
- Fix: set a sane default permission (at minimum `IsAuthenticated` / `SafeOrWrite`), wire `KeycloakWsAuthMiddleware` in asgi, and remove/lock down the public role-assignment endpoints.
- safe_or_breaking: breaking (clients must now present tokens).

### 4. [High] InMemoryChannelLayer caps the WebSocket tier at one process — no horizontal scale
`backend/settings.py:67-71`
```python
CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}
```
InMemoryChannelLayer is per-process and documented as dev-only. Every WS lives in a single Daphne worker,
so (a) you cannot run more than one Daphne process / replica for the WS tier without group messaging
silently breaking, and (b) all concurrent dashboards contend for one event loop. V48 opens **one WS per
card**, and PCC-aggregate pages fan out across all feeders (the code sizes the pool for "4 outgoings × 3
parallel = 12 conns per open WS", services.py:55-60) — a handful of enterprise users opening wide panels
saturates a single process. This is the scaling wall for the whole V48 render path, which routes all data
through `ws/mfm/<id>/<endpoint>/` (config/ems_backend.py:24-26).
- Fix: RedisChannelLayer + run N Daphne workers behind a load balancer; make the layer backend env-driven.
- safe_or_breaking: safe (behavior-preserving; adds a dependency and infra).

### 5. [High] `db_link` connection strings are serialized to anonymous clients
`lt_panels/serializers.py:44-58` (field list line 56), `assets/serializers.py:55`
`MFMSerializer.Meta.fields` includes `db_link`, and the ViewSet is `AllowAny` (finding 3), so
`GET /api/mfm/` returns every MFM's libpq connection string. Today the default is a passwordless unix-socket
DSN (`models.py:64-68`), but the field is a free-text `CharField` whose whole purpose is to point at
arbitrary telemetry databases — the moment a production/neuract MFM row carries host/user/password in its
DSN (the tunneled `:5433` neuract DB is exactly this shape), that credential is published on an
unauthenticated endpoint. `db_link` is internal wiring the frontend never needs.
- Fix: drop `db_link` (and arguably `table_name`) from the serialized fields; keep them server-side only.
- safe_or_breaking: breaking (any client reading `db_link` from the payload breaks — none should).

### 6. [High] Per-site model hardcoded in Python across four places — contradicts the DB-driven principle
`lt_panels/electrical_equipment.py` (587 lines, tree at :19, view at :580), `lt_panels/views.py:252-297` (ASSETS_TREE), `:326-397` (BMS_TREE), `:429-432` (_OVERVIEW_PAGES), `lt_panels/management/commands/seed_mfms.py` (292 lines, 179-row literal list at :27+)
The customer's electrical single-line topology, asset inventory, BMS tree, overview-page map, and the full
MFM seed list are all literal Python dicts, and they bind to live data by **exact display-name string match**
(`electrical_equipment._build_name_to_mfm_id` lowercases `MFM.name`, views.py:308-309/449). Any rename in the
DB silently unbinds a nav leaf (returns `mfm_id: null`); onboarding a second site means editing code and
redeploying. The project already has the tables to hold this (MFM topology M2M, ConfigField EAV), so this is
avoidable coupling. It is also brittle: the binding is name-based, not FK-based.
- Fix: move nav trees to a DB table (or derive the electrical tree from the existing incoming/outgoing M2M) and bind by id/slug, not display name.
- safe_or_breaking: breaking (data must be migrated into the DB; output shape preserved).

### 7. [High] `assets/` app is a ~1,500-line duplicate of `lt_panels/` that V48 (and, apparently, nothing current) consumes
`assets/services.py` (499 lines; header line 3: "Direct port of lt_panels/services.py"), `assets/consumers/_base.py` (447), `assets/consumers/_timefilters.py` (132) vs `lt_panels/consumers/_timefilters.py` (162), `assets/models.py` (260, parallel EAV clone), `assets/routing.py`
A tree-wide grep for `ws/asset` / `/api/asset/` across pipeline_v48 returns nothing — V48 drives only
`ws/mfm/<id>/<endpoint>/` (config/ems_backend.py:26, endpoint_registry.py). The assets app is a second copy
of the broker with one filter-column rename that the code itself admits is redundant
(`assets/services.py:16-19,36-39`: comment says the rename to `asset_id` was reverted and it still filters on
`panel_id`). Two pool dicts, two `_to_dt`s, two timefilter vocabularies that can drift. This doubles the
maintenance and audit surface for zero current consumer benefit, and it still exposes data on
`ws/asset/...` and `/api/assets/` (viewset) with no auth.
- Fix: confirm no live consumer (check CMD_V2 :3107 too, per house "verify before dead" rule) then delete the app, or collapse the shared broker into one module both apps import.
- safe_or_breaking: breaking (removes routes/endpoints; must confirm truly unused first).

### 8. [High] Zero automated tests over a 17.5k-LOC data broker with subtle timezone SQL
`lt_panels/tests.py` (3 lines: bare `from django.test import TestCase` + comment); no `tests` module under `assets/` or either `consumers/` tree
The `_bucket_expr` double-TZ-shift (services.py:256-302) is self-described as "subtle — bit us once already",
the event-reconstruction CTEs (services.py:658-1065) encode real correctness logic (rising-edge dedup,
per-type caps), and the range presets (services.py:327-397) have many hand-tuned IST-vs-UTC branches. All of
it is untested. This logic is duplicated in assets/services.py, so a fix in one place can silently diverge.
For enterprise production this is the single largest maintainability risk: any refactor of the bucketing/TZ
math has no safety net, and these are exactly the functions whose bugs produce plausible-but-wrong numbers
(the worst kind for an EMS).
- Fix: pytest suite over resolve_range, _bucket_expr, and the event-count reconstructors against a fixture table with known crossings.
- safe_or_breaking: safe (adds tests only).

### 9. [High] No dependency pinning anywhere — no requirements.txt / lock / pyproject
No `requirements*.txt`, `pyproject.toml`, `Pipfile`, or lock file exists under `pipeline_v45` or the repo
(searched `/home/rohith/desktop/BFI` for manifests naming daphne/jazzmin — none). The app runs against the
ambient pyenv 3.11.9 interpreter (the live Daphne at :8888 is `/home/rohith/.pyenv/versions/3.11.9/bin/...`).
Django 5.2, DRF, channels, daphne, psycopg[pool], jazzmin, PyJWT, requests are all unversioned. There is no
reproducible build; an enterprise deploy cannot recreate this environment, and a transitive upgrade can break
production silently.
- Fix: freeze a pinned `requirements.txt` (or pyproject with a lock) from the working interpreter.
- safe_or_breaking: safe.

### 10. [Medium] Aggregate WS re-runs the full feeder fan-out every tick — 2s cadence × N feeders forever
`lt_panels/consumers/overview/pcc_panel.py:155-162` (aggregate_render fans out over all children each call), `_overview_base.py:334-341` (tick loop calls aggregate_render unconditionally), `energy_distribution/pcc_panel.py:100-116` (`_load_topology` re-queries incoming/outgoing M2M — including `get_config` EAV lookups per MFM — on every render)
The single-flight cache (`_aggregate_cache.py`) only collapses the **initial** render; live ticks are
per-socket and each one re-walks the topology and issues one `fetch_live` per feeder. For a wide PCC panel
(the code cites 28 feeders) that's ~28 DB round-trips every 2s per open socket, plus ORM topology + N×2
`get_config` queries per tick in energy-distribution. With InMemoryChannelLayer's single process (finding 4)
this is the load that saturates the pool. The topology (M2M membership, rated-kW config) is static for the
socket's life and should be loaded once in `connect`, not per tick.
- Fix: cache topology + nameplate config on the strategy instance at connect; only re-fetch the live rows per tick.
- safe_or_breaking: safe (behavior-preserving; fewer queries).

### 11. [Medium] Config knobs hardcoded in source despite the project's DB-driven-config principle
`services.py:54-61` (`_POOL_MIN_SIZE=4`, `_POOL_MAX_SIZE=60`, `_POOL_TIMEOUT_SEC=30`), `services.py:40-41` (`Asia/Kolkata`), `_aggregate_cache.py:18` (`_TTL_SECONDS=6.0`), tick intervals scattered (`overview/pcc_panel.py:73` 2.0s, `_fanout_base.py:37,64` 2.0/30.0s), `assets/services.py:55-57` (same pool constants re-hardcoded)
The pool ceiling is the operational lever most likely to need tuning under enterprise load (it's explicitly
reasoned about in the comment), and the IST timezone is a per-deployment fact, yet none are env- or
DB-tunable. This is the same class of thing V48 deliberately moved into `cmd_catalog.app_config` (`cfg()`).
Ironic given the ConfigField EAV exists for per-MFM config.
- Fix: read pool sizes, TTL, tick intervals, and LOCAL_TZ from env (or app_config) with these values as fallbacks.
- safe_or_breaking: safe.

### 12. [Medium] `assets/` `AllowAny` REST + WS remain live legacy surface even if lt_panels is secured
`assets/views.py:34` (`AssetViewSet(ReadOnlyModelViewSet)` no permission_classes), `assets/serializers.py:55` (exposes `db_link`), `backend/urls.py:26`, `backend/asgi.py:21,27` (assets_ws routed)
Even after finding 3 is fixed at the DRF default level, this is a reminder that the assets app carries the
same db_link exposure (finding 5) and the same anonymous access, on routes nothing current calls. Folded into
finding 7's recommendation but flagged separately because if the team keeps assets/ they must also secure it.
- safe_or_breaking: breaking.

### 13. [Medium] Unbounded per-`db_link` pool dict is an untrimmed process-lifetime cache
`services.py:51,79-101` (`_POOLS` dict, never evicted; comment at :46-48 "never call pool.close()"), `assets/services.py:52`
Each distinct `db_link` string opens a pool of up to 60 connections held for the process lifetime. Because
`db_link` is per-MFM free text, a site with many distinct DSNs (or a typo'd/rotated DSN) accumulates pools
that are never closed — `n_distinct_db_links × 60` can exceed Postgres `max_connections` (the comment assumes
one DSN). Similarly `_TABLE_COLUMNS_CACHE` (services.py:127) never expires, so a schema change needs a manual
`invalidate_table_columns` call or a restart. Fine for the current single-DSN simulator; a latent scaling
footgun for multi-DB enterprise use.
- Fix: bound the pool dict (LRU with close-on-evict) or assert a small known DSN set; consider a TTL on the columns cache.
- safe_or_breaking: safe.

### 14. [Medium] Client-command frames reflected back verbatim in overview / fan-out dispatchers
`_overview_base.py:325-329` (`'received': cmd`), `_fanout_base.py:188-194` (`'received': cmd`)
The base live dispatcher was deliberately hardened to echo only `received_keys` and not the full payload
("don't give an attacker a reflected-payload amplifier", `_base.py:384-388`), but the overview and fan-out
dispatchers still echo the entire client `cmd` dict back in the ack. Minor (WS is same-origin-ish and small)
but it's an inconsistency with the stated hardening and a reflected-content vector.
- Fix: mirror the `_base.py` treatment — echo `received_keys` only.
- safe_or_breaking: breaking (ack shape changes) but trivially so.

### 15. [Medium] No health/readiness endpoint; observability is bare logging
`backend/urls.py:22-27`, `lt_panels/urls.py` (no health route); logging is module `logging.getLogger` with no `LOGGING` config in settings (grep for `LOGGING` in settings.py returned nothing)
For a service V48 depends on at request time (host fetches frames synchronously with a 60s ceiling,
config/ems_backend.py:17), there is no `/healthz` for load balancers / orchestration, and no structured
logging config — logs go wherever Daphne's root logger defaults. At enterprise scale you cannot tell a
tunnel flap from a slow query from process death.
- Fix: add a cheap `/healthz` (DB ping + pool stat) and a `LOGGING` dict (JSON to stdout).
- safe_or_breaking: safe.

### 16. [Medium] `_overview_base.py` ships a self-declared stub: WindowedKpi/Narrative slow loops never run
`_overview_base.py:19-22` (docstring: "this is the SKELETON. slow-cadence + range-filter loops are stubbed"), `:289` (`# TODO: spawn slow-cadence loop for WindowedKpi / Narrative widgets`), primitives defined but only live-tick widgets wired (`:331-355` tick loop handles only live/aggregate)
The overview widget envelope advertises `WindowedKpi` (range filters) and `Narrative` (AI summary) widget
kinds via `widget_descriptors` (`:178-192`), but the dispatcher never spawns their refresh loops, so a client
that mounts those widgets gets an initial value and nothing after. This is a partial feature shipped as if
complete; a consumer relying on windowed/narrative refresh silently gets stale data. Assets app has a fuller
`_widgets_base.py` (488 lines) doing similar work differently — two envelope implementations.
- Fix: either implement the slow loop or stop advertising those widget kinds until it exists; converge on one widget-envelope base.
- safe_or_breaking: safe (finishing the loop is additive).

### 17. [Low] Column-name allowlist regex triplicated; risk of drift
`lt_panels/views.py:37`, `lt_panels/consumers/_base.py:48`, `lt_panels/compare_view.py:18` (all `^[a-zA-Z][a-zA-Z0-9_]{0,62}$`), plus `services.py:824` `_VALID_BOOL_COL`
This regex is the SQL-identifier safety gate (columns are f-string-interpolated into SQL throughout
services.py). It is copy-pasted in at least four places, each with a comment saying "must agree with the
others". A future edit to one that loosens it (or a new call site that forgets it) reopens SQL injection on
the `?columns=` / `metric=` params. Defense-in-depth is real here, but the constant should live in one module.
- Fix: define once in services.py and import everywhere.
- safe_or_breaking: safe.

### 18. [Low] `fetch_config_row` / `fetch_phase_events` swallow all exceptions and return empty
`services.py:233-242` (bare `except Exception: return None`), `:732-737`, `:811-815`
These broadly catch to tolerate missing tables/columns (deliberate, per column-tolerance convention), but a
transient connection error, permission error, or a genuinely malformed query is indistinguishable from
"table absent" — the caller sees empty data, not an error. For an EMS "silently show nothing" can read as
"all-clear" on a safety-relevant PQ/event view. At least log at warning so operators can tell degradation from
absence.
- Fix: narrow the except (catch `psycopg.errors.UndefinedTable/UndefinedColumn`) and log everything else.
- safe_or_breaking: safe.

### 19. [Low] `pages_for_mfm` builds absolute ws:// URLs from `request.get_host()` and `is_secure()`
`page_registry.py:156-159,189-190`
Behind a reverse proxy (the enterprise norm), `request.is_secure()` is False unless `SECURE_PROXY_SSL_HEADER`
is set (it is not, settings.py has no such key), so `ws_url_abs` will advertise `ws://` even when the client
arrived over `wss://` — mixed-content failures in the browser. Minor because V48 builds its own URL
(config/ems_backend.py), but any consumer trusting `ws_url_abs` breaks behind TLS.
- Fix: set `SECURE_PROXY_SSL_HEADER` / `USE_X_FORWARDED_*` when adding the proxy, or drop the absolute URL.
- safe_or_breaking: safe.

### 20. [Low] `show_ui_builder: True` in Jazzmin admin left on
`backend/settings.py:196`
The Jazzmin UI-theme builder is enabled in the admin, which is a dev convenience that writes theme state and
adds surface to an admin that (per finding 3) is reachable. Cosmetic; turn off for production.
- safe_or_breaking: safe.

---

## Notes on what is good (so the team doesn't "fix" it)
- All timeseries SQL is parametrized; table/column names are the only interpolated parts and they pass through the identifier allowlist + `information_schema` introspection intersection (services.py:130-182, 434-456). No injection found in the data path.
- The dispatcher→STRATEGIES registry with programmatic routing derivation (page_registry.py → routing.py:17-26) is clean and is the right pattern; keep it.
- Circuit breakers on the live/aggregate loops (`_base.py:432-438,491-497`) and the single-flight initial-render cache (`_aggregate_cache.py`) are thoughtful reliability work.
- `_to_dt` naïve-datetime rejection (`_base.py:58-110`) and the energy-delta "what the meter said" approach (services.py:620-655) are correct, defensive choices.
- `distortion_harmonics/` + `power_quality_history/` consumer folders are still imported in `consumers/__init__.py:43-44` and re-exported in `__all__`, but `page_registry._PAGES` no longer routes them (they were folded into power-quality-summary, page_registry.py:100-117). They are dead as *routes* but live as *imports*; low priority and needs the "verify before dead" check before removal — not raised as a separate finding since they expose nothing routable.

## V48 data-source fit summary
V48 consumes this backend **only** through `ws/mfm/<mfm_id>/<endpoint>/` (config/ems_backend.py:24-26,
endpoint_registry.py canonical list). It does not call the REST viewset, `/api/compare/`, `/api/assets/`,
`/api/bms/`, `/api/ems/`, or any `ws/asset/` route. Everything under the assets app and the REST nav-tree /
compare surface is legacy relative to V48. The WS contract V48 relies on is served by lt_panels consumers and
is functionally solid; the gating risks for V48 at scale are the single-process channel layer (finding 4) and
the per-tick fan-out cost (finding 10).
