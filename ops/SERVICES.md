# V48 runtime services — THE port map (single source of truth) [audit R4, 2026-07-12]

Every long-running process the V48 system touches, who calls whom, and how each is managed.
If you add a service or move a port: update this file + the unit in `ops/` (or `copilot/deploy/`) in the same change.

## Services

| Port  | Service              | Entrypoint                              | Managed by                          | Depends on |
|-------|----------------------|-----------------------------------------|-------------------------------------|------------|
| 5188  | web frontend (Vite)  | `host/web` (`npx vite`)                 | `ops/v48-web.service` (user unit)   | 8770, 8772, 8790 (proxied), CMD_V2 tree via `@cmd-v2` |
| 8770  | host API             | `host/server.py`                        | `ops/v48-host.service` (user unit)  | 8200 (LLM), 5432, 5433 |
| 8790  | admin console API    | `admin/server.py`                       | `ops/v48-admin.service` (user unit) | run outputs + obs traces (file-backed) |
| 8772  | copilot API          | `copilot/server.py`                     | `copilot/deploy/ems-copilot.service`| 8201 (its own model), 5433 (read-only) |
| 8201  | copilot LLM          | vLLM Qwen3-4B-Instruct-2507-FP8         | `copilot/deploy/vllm-copilot.service`| GPU |
| 8200  | pipeline LLM         | vLLM Qwen3.6-35B-A3B-FP8 (64K ctx)      | SYSTEM `vllm.service`               | GPU |
| 5432  | Postgres (local)     | cmd_catalog                             | system postgres                     | — |
| 5433  | Postgres tunnel      | ssh -L → 10.90.200.91:5432 (neuract)    | SYSTEM `ops/db-tunnel.service` (hardened 2026-07-07) | FortiClient VPN |
| 3107  | CMD_V2 app           | separate repo `/home/rohith/CMD_V2`     | separate project                    | same DBs; NOT called by V48 |
| 8470  | kit-preview editor   | 3D preset designer                      | separate project                    | — |

**3D GLB media (RETIRED SERVICE, 2026-07-12):** the legacy EMS service (:8890, BFI/backend) used to serve `/media/3d/glb/*.glb` for asset_3d
cards. The web origin now serves them itself from `host/web/public/media/` (Vite public dir — dev AND build), and the
`viewer.glb_media_base` knob is root-relative `/media/`, so any origin the page loads from (localhost or LAN IP)
serves its own models. Its directory under BFI/backend remains only as CMD_V2-era history; V48 has zero runtime dependency
on it. New models: drop the .glb into `host/web/public/media/3d/glb/` (scripts/seed_dg_asset3d.py targets it).

## Call graph (runtime)

```
browser ── :5188 vite ──proxy /api──────► :8770 host ──► run/ pipeline ──► :8200 vLLM (every AI decision)
                 │                              │                     └──► :5432 cmd_catalog · :5433 → neuract
                 ├──proxy /copilot────► :8772 copilot ──► :8201 Qwen3-4B  └► :5433 (read-only index refresh)
                 └──proxy /admin/api──► :8790 admin  ──► outputs/ + obs traces (no DB writes)
```

## Failure semantics (what dies when a dependency dies)

- **:5433 tunnel down** → pipeline serves the honest `data_unavailable` terminal (run/degrade_gate; fingerprints in
  `data/outage.py`); TTL caches self-heal within `cache.resolution_ttl_s` after the flap; the pooled `q()` engine
  (data/db_client.py) discards stale connections and retries once on a fresh connect.
- **:8200 vLLM down** → layer1a raises the fail-closed `llm transport/parse failure` → same honest terminal.
  Contention ≠ outage: keep `layer2.emit_concurrency` ≤ 4; sweeps ≤ 2-3 page-concurrency.
- **:8772 / :8201 copilot down** → typeahead suggestions vanish; pipeline unaffected (zero coupling by contract).
- **:8790 admin down** → traces stop being browsable; pipeline unaffected (obs sinks are fail-open).

## Install

```bash
bash ops/install-units.sh          # user units: v48-host, v48-admin, v48-web (+ copilot pair)
systemctl --user enable --now v48-host v48-admin v48-web
# system units (root): db-tunnel.service (ops/), vllm.service (already installed)
```

Stop hand-run terminal copies first — they hold the ports. The historical `host_restart.log` / `vite_restart.log`
workflow is superseded by `journalctl --user -u v48-host -f`.
