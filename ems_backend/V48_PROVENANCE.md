# ems_backend — V48-local copy of the CMD EMS backend

> **Provenance:** copied verbatim from `/home/rohith/CMD/backend` on 2026-06-29 (user: *"for now copy the backend to v48 and rename it appropriately"*).
> Faithful copy — **148/148 `.py` files**, only `__pycache__/` + `*.pyc` excluded. Renamed folder `backend` → **`ems_backend`** (descriptive). Inner Django config package kept as `backend` (so `manage.py` → `backend.settings`, `ASGI_APPLICATION = backend.asgi.application` still resolve).

## Why a local copy (reverses the earlier "use CMD directly, no copy")
V48 Layer 2 fills card **DATA** by reusing these EMS **consumer strategies** (`lt_panels/consumers/<view>/<panel>.py`, `assets/consumers/<class>/<view>.py`) fed by `services.py` (`fetch_live`/`fetch_bucketed`/`fetch_window`/`resolve_range`). A V48-owned copy lets us **adapt** the consumers — chiefly to source columns from `mfm_type_id → lt_parameter` instead of the baked per-class literals (see `../findings/ems_backend_hardcoding.md`) — **without touching the live CMD backend**. `"for now"` = pragmatic; we may revisit driving live CMD directly.

## What it is (so we can run it)
- Django + Channels (WebSocket) app. Asset is a URL param: `ws/mfm/<int:mfm_id>/<page-endpoint>/` → dispatcher picks the **class-correct** strategy (`STRATEGIES[mfm_type.code]`).
- DB binding (`backend/settings.py`): `lt_panels_db` @ `localhost:5432` (the registry — `lt_mfm`/`lt_parameter`/`lt_mfm_type`); per-meter time-series read via each MFM's `db_link`/`table_name`/`panel_id`.
- `ALLOWED_HOSTS=['*']`. Entry: `manage.py` (`DJANGO_SETTINGS_MODULE=backend.settings`).

## V48 boundary rules
- **Do NOT edit the live `/home/rohith/CMD/backend`.** All V48 changes land here, in `ems_backend/`.
- Keep the copy's data-layer contract (`services.py`) intact — it's already fully table-parameterized + column-agnostic; the column-sourcing fix belongs in the **strategy base**, not the broker.
- Companion docs that ship with the copy (`ARCHITECTURE.md`, `WEBSOCKETS.md`, `WEBSOCKET_PARAMETERS_BY_MFM_TYPE.xlsx`, …) are the CMD originals — reference, not V48-authored.
