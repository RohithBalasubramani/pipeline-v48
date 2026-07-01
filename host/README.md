# host — V48 prompt → cards preview

A thin UI over the V48 pipeline: type a prompt, run **1a (route) ∥ 1b (asset)** → **validate**, and
render the chosen cards. Each card mounts its **real CMD_V2 Storybook story** (no bespoke charts) fed
the ground-truth payload from `cmd_catalog.card_payloads`.

> Layer 2 (the payload-morph layer) is not built yet, so the payload shown per card is the **default**
> story payload (the byte-match ground truth). When Layer 2 lands, the same response shape carries the
> morphed payload and the UI is unchanged.

## Run

**1. Backend API** (wraps `run_pipeline` + joins payloads). Needs the cmd_catalog DB + Qwen at :8200:

```bash
cd pipeline_v48
python3 host/server.py              # http://0.0.0.0:8770
# env: V48_HOST_PORT (8770), STORYBOOK_URL (http://100.90.185.31:6008), PSQL_USER (postgres)
```

**2. Frontend** (Vite dev server, proxies `/api` → :8770):

```bash
cd pipeline_v48/host/web
npm install
npm run dev                         # http://localhost:5188
# env: V48_HOST_API to point the proxy elsewhere
```

Open http://localhost:5188, type a prompt (or click an example).

## What you see
- **Header** — routed page, metric/intent, resolved asset (or AssetPicker when 1b is ambiguous), column-basket
  size, validation verdict, interdependency groups, run id + latency, and any layer errors.
- **Grid** — the selected cards laid out by their real `slot.region` / `slot_order`, sized by `size`. Each
  card renders its Storybook story; control/nav cards (no harvested payload) show a labelled placeholder.
  Expand any card for its **payload JSON + key_roles** (the per-leaf morph map) and slot/size metadata.

## Known gaps (pipeline, not the UI)
- **1b asset resolution** currently errors in this env: the registry repointed `lt_mfm.table_name` to
  `cmp_mfm_*` compat views (target_version1) but `layer1b/basket/col_dict.py` still reads the legacy
  `lt_panels` DB — part of the in-progress neuract migration (asset↔neuract mapping is pending a decision).
  The UI degrades gracefully: it surfaces the error and still renders every card with its default payload.
