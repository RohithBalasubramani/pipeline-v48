-- db/fix_enable_llm_admission_20260715.sql — ENABLE the global vLLM admission cap [audit 2026-07-14, 05 F2].
-- The per-run cap (layer2.emit_concurrency=4) is applied inside each run, so N concurrent /api/run requests put
-- 4xN large emits on the single :8200 vLLM at once — the documented contention that manufactures false 'timeout'
-- hard-fails on every multi-session sweep. The semaphore machinery shipped 2026-07-12 (llm/client.py, sized once
-- per process from llm.global_concurrency; acquisition fail-open with llm.admission_wait_s=60).
-- VALUE=8 rationale: exactly two pages' worth of the certified emit_concurrency=4 — the highest load level with
-- demonstrated decode margin at ~22K-token emits. Raise to 10 only after a clean multi-session sweep.
-- The AND value='0' guard never clobbers an operator-tuned value.
-- REQUIRES v48-host restart (semaphore sized once). Rollback: UPDATE ... value='0' + restart.
-- NOTE 2026-07-15: the operator enabled the cap at 4 (with admission_wait_s=300) before this landed - the
-- AND value='0' guard makes this file a documented NO-OP against that tuning; it applies only on a fresh DB.
-- Apply: psql -h localhost -p 5432 -U postgres -d cmd_catalog -f db/fix_enable_llm_admission_20260715.sql

UPDATE app_config SET value='8',
  note = 'Global cap on TOTAL in-flight vLLM calls per host process (BoundedSemaphore, sized once at first call). 0=off. Enabled 2026-07-15 (audit 05 F2): 8 = two pages of emit_concurrency=4. Fail-open acquisition (llm.admission_wait_s).'
  WHERE key='llm.global_concurrency' AND value='0';
