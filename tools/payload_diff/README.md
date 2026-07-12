# tools/payload_diff — execution comparison for pipeline_v48

Compare two pipeline executions across **page · cards · metadata · bindings · SQL · validation · renderer payload**
(+ an `app_config` drift check), with a one-line-per-dimension terminal summary and a self-contained HTML report
(dark/light, no external assets) under `outputs/diffs/`.

## What an "execution" is

One `/api/run` of the host. Every run already persists three artifacts keyed by `run_id = sha1(prompt)`:

| artifact | file | survives re-runs? |
|---|---|---|
| renderer payload (full API response) | `outputs/logs/response_<rid>.json` | **latest only** (overwritten) |
| stage log (1a/1b/validate/L2/exec/RESPONSE) | `outputs/logs/pipeline_<rid>.jsonl` | all (appended) |
| SQL trace (every neuract read; `obs/sql_trace.py`) | `outputs/logs/sql_<rid>.jsonl` | all (appended) |

Re-running the same prompt **appends** to the jsonl logs, so the tool segments them into executions
(`PROMPT → … → RESPONSE`) and lets you address one as `<ref>@<occurrence>` (0-based; negative from the end;
default `@-1` = latest). A **snapshot** freezes one execution (response + stage segment + SQL slice + app_config
fingerprint + git sha) into a self-contained JSON under `outputs/diffs/snapshots/` so later runs/changes can't
erase it.

## The four comparison recipes

```bash
# 1) same prompt, run again now (nondeterminism / flakiness check)
python3 -m tools.payload_diff rerun "energy and power for UPS-01 over the last 7 days"

#    …or compare the two most recent logged executions of a prompt (no fresh run):
python3 -m tools.payload_diff diff "energy for UPS-01" "energy for UPS-01"     # auto @-2 vs @-1

# 2) different prompts
python3 -m tools.payload_diff diff "energy for UPS-01" "energy for UPS-02"
python3 -m tools.payload_diff diff r_01f2a7f3f7 r_1bc17049b9                   # by run id

# 3) before/after a CODE change
python3 -m tools.payload_diff capture "energy for UPS-01" --label before
#   …edit code, restart the host…
python3 -m tools.payload_diff capture "energy for UPS-01" --label after
python3 -m tools.payload_diff diff before after

# 4) before/after a CONFIG change (cmd_catalog.app_config / DB knobs)
#   same as (3) — the report's `config` section names exactly the knob rows that moved between captures.
```

Housekeeping: `list [--grep S]` shows known runs; `snapshot <ref>` freezes without diffing;
`--tol 0.02` mutes numeric drift within ±2%; `--asset-id N` pins the asset (skips the picker).

## Reading the report

- **structural** entries (keys/shape/type/series-length) are what a code or emit change looks like;
  **value** entries are live-data drift and stay collapsed by default (`--expand-values` to open them).
- **⚠ emptied** (a leaf that was REAL in A and blank in B) and validation verdict falls
  (`render/partial → honest_blank`) are the headline regressions — they set **exit code 2**, so
  `rerun`/`diff` can gate a cert loop.
- A dimension whose source is missing on either side reports `n/a` with the reason (e.g. runs that
  predate the SQL trace) — every other dimension still diffs. Occurrences older than the latest have no
  response on disk (host overwrites it), so their page/cards/payload dims degrade to stage-log facts;
  `capture`/`rerun` snapshots keep the full wire response and never degrade.

## Pieces (one concern per file)

`logs.py` locate+segment run artifacts · `snapshot.py` freeze one execution · `capture.py` live run →
snapshot · `refs.py` CLI ref grammar · `extract.py` snapshot → dimension views · `align.py` card pairing
(asset-tag + card_id) · `deep_diff.py` structural/value/emptied classification · `diff.py` per-dimension
semantics · `report_term.py` / `report_html.py` renderers · `__main__.py` dispatch.

The SQL leg is fed by `obs/sql_trace.py` (hooked in `ems_exec/data/neuract.py:_run`, fail-open,
`V48_SQL_TRACE=0` disables). Runs recorded before that hook simply report `sql: n/a`.
