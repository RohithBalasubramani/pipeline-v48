-- db/obs_schema.sql — V48 observability store (cmd_catalog). One execution = one obs_traces row (globally unique
-- trace_id) + N obs_stage_events + per-call obs_llm_calls / obs_db_queries. Idempotent (IF NOT EXISTS /
-- CREATE OR REPLACE VIEW): obs/sink_pg.py applies this file on writer start, so the store is zero-ops.
-- Apply by hand:  psql -U postgres -d cmd_catalog -f db/obs_schema.sql

CREATE TABLE IF NOT EXISTS obs_traces (
    trace_id          text PRIMARY KEY,          -- t_<uuid4> — THE globally unique execution identity
    kind              text,                      -- 'run' | 'frame' | 'multi' | 'cli'
    prompt            text,
    asset_id          text,
    run_ids           jsonb,                     -- legacy prompt-hash replay keys bound during the run (reflect loops append)
    started_at        timestamptz,
    ended_at          timestamptz,
    latency_ms        integer,
    status            text,                      -- 'ok' | 'degraded' | 'error'
    n_stages          integer,
    n_llm_calls       integer,
    tokens_prompt     bigint,
    tokens_completion bigint,
    n_db_queries      integer,
    rows_returned     bigint,
    degradation       jsonb,                     -- {data_unavailable, asset_no_data, validation_blocked, asset_pending, ...}
    warnings          jsonb,
    errors            jsonb,
    response_summary  jsonb                      -- {ok, page_key, n_cards, verdicts{}, ...}
);

CREATE TABLE IF NOT EXISTS obs_stage_events (
    id                bigserial PRIMARY KEY,
    trace_id          text NOT NULL,
    run_id            text,
    span_id           text,
    parent_span_id    text,
    seq               integer,                   -- event order within the trace
    kind              text,                      -- 'stage' | 'legacy'
    stage             text,                      -- request_received | knowledge_gate | page_selection | story_selection
                                                 -- | asset_resolution | layer2_card_ai | metadata_resolution | executor
                                                 -- | validation | renderer | response | *.card | legacy.<name>
    card_id           integer,
    ts_start          timestamptz,
    ts_end            timestamptz,
    latency_ms        integer,
    status            text,                      -- 'ok' | 'degraded' | 'error'
    confidence        jsonb,
    inputs            jsonb,
    outputs           jsonb,
    n_llm_calls       integer,
    tokens_prompt     bigint,
    tokens_completion bigint,
    n_db_queries      integer,
    rows_returned     bigint,
    validation        jsonb,
    degradation       jsonb,
    warnings          jsonb,
    errors            jsonb,
    attrs             jsonb
);

CREATE TABLE IF NOT EXISTS obs_llm_calls (
    id                bigserial PRIMARY KEY,
    trace_id          text,
    run_id            text,
    span_id           text,
    parent_span_id    text,                      -- the stage span this call ran under
    stage             text,                      -- llm.client stage key (route, l2_emit, knowledge_ems, ...)
    card_id           integer,
    ts                timestamptz,
    latency_ms        integer,
    model             text,
    prompt_system     text,
    prompt_user       text,
    response          text,
    tokens_prompt     integer,
    tokens_completion integer,
    finish_reason     text,
    attempt           integer,                   -- 0 = first send; 1 = the bounded parse-retry
    error_kind        text,                      -- timeout | http_<code> | transport | no_json | parse | truncated | over_budget
    params            jsonb,                     -- the call configuration: temperature/seed/response_format/url/timeout_s/max_tokens
    decision          jsonb                      -- the stage-declared decision context: kind/candidate_kind/candidates/… (AI Decision Inspector)
);

-- AI Decision Inspector migration (2026-07-12): a store created before params/decision existed gains the columns on
-- the next writer start (this file is re-applied on every sink_pg bootstrap; ADD COLUMN IF NOT EXISTS is idempotent).
ALTER TABLE obs_llm_calls ADD COLUMN IF NOT EXISTS params   jsonb;
ALTER TABLE obs_llm_calls ADD COLUMN IF NOT EXISTS decision jsonb;

CREATE TABLE IF NOT EXISTS obs_db_queries (
    id                bigserial PRIMARY KEY,
    trace_id          text,
    run_id            text,
    span_id           text,
    parent_span_id    text,
    stage             text,
    card_id           integer,
    ts                timestamptz,
    latency_ms        integer,
    db_name           text,
    sql_text          text,
    rows_returned     integer,
    error             text
);

CREATE INDEX IF NOT EXISTS obs_traces_started_idx      ON obs_traces (started_at DESC);
CREATE INDEX IF NOT EXISTS obs_traces_status_idx       ON obs_traces (status);
CREATE INDEX IF NOT EXISTS obs_stage_events_trace_idx  ON obs_stage_events (trace_id, seq);
CREATE INDEX IF NOT EXISTS obs_stage_events_stage_idx  ON obs_stage_events (stage, ts_start DESC);
CREATE INDEX IF NOT EXISTS obs_stage_events_card_idx   ON obs_stage_events (card_id) WHERE card_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS obs_llm_calls_trace_idx     ON obs_llm_calls (trace_id);
CREATE INDEX IF NOT EXISTS obs_llm_calls_stage_idx     ON obs_llm_calls (stage, ts DESC);
CREATE INDEX IF NOT EXISTS obs_db_queries_trace_idx    ON obs_db_queries (trace_id);
CREATE INDEX IF NOT EXISTS obs_db_queries_stage_idx    ON obs_db_queries (stage, ts DESC);

-- ── dashboard views ─────────────────────────────────────────────────────────────────────────────────────────────

-- one row per execution, newest first — the ops landing view
CREATE OR REPLACE VIEW obs_v_trace_summary AS
SELECT trace_id, kind, started_at, latency_ms, status,
       left(prompt, 80)                            AS prompt,
       response_summary->>'page_key'               AS page_key,
       (response_summary->>'n_cards')::int         AS n_cards,
       response_summary->'verdicts'                AS verdicts,
       n_llm_calls, tokens_prompt, tokens_completion, n_db_queries, rows_returned,
       degradation, errors
FROM obs_traces
ORDER BY started_at DESC;

-- per-stage latency percentiles (dashboards: stage health over a window)
CREATE OR REPLACE VIEW obs_v_stage_latency AS
SELECT stage,
       count(*)                                                    AS n,
       percentile_cont(0.5)  WITHIN GROUP (ORDER BY latency_ms)    AS p50_ms,
       percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)    AS p95_ms,
       percentile_cont(0.99) WITHIN GROUP (ORDER BY latency_ms)    AS p99_ms,
       max(latency_ms)                                             AS max_ms,
       sum(CASE WHEN status = 'error'    THEN 1 ELSE 0 END)        AS n_error,
       sum(CASE WHEN status = 'degraded' THEN 1 ELSE 0 END)        AS n_degraded
FROM obs_stage_events
WHERE kind = 'stage'
GROUP BY stage;

-- recent errors across stages + traces (alerting feed)
CREATE OR REPLACE VIEW obs_v_recent_errors AS
SELECT ts_start AS ts, trace_id, stage, card_id, status, errors, warnings
FROM obs_stage_events
WHERE status = 'error' OR jsonb_array_length(coalesce(errors, '[]'::jsonb)) > 0
ORDER BY ts_start DESC;

-- token spend per stage per day (cost/analytics)
CREATE OR REPLACE VIEW obs_v_token_spend AS
SELECT date_trunc('day', ts)::date AS day, stage,
       count(*)                    AS n_calls,
       sum(tokens_prompt)          AS tokens_prompt,
       sum(tokens_completion)      AS tokens_completion,
       avg(latency_ms)::int        AS avg_latency_ms,
       sum(CASE WHEN error_kind IS NOT NULL THEN 1 ELSE 0 END) AS n_failed
FROM obs_llm_calls
GROUP BY 1, 2
ORDER BY 1 DESC, tokens_prompt DESC NULLS LAST;

-- per-card lifecycle funnel (layer2 emit → executor fill → render verdict), one row per trace×card
CREATE OR REPLACE VIEW obs_v_card_funnel AS
SELECT trace_id, card_id,
       max(CASE WHEN stage LIKE 'layer2_card_ai%'      THEN status END) AS l2_status,
       max(CASE WHEN stage LIKE 'metadata_resolution%' THEN status END) AS metadata_status,
       max(CASE WHEN stage LIKE 'executor%'            THEN status END) AS exec_status,
       max(CASE WHEN stage LIKE 'renderer%'            THEN outputs->>'verdict' END) AS render_verdict,
       sum(latency_ms)  AS total_ms,
       sum(n_llm_calls) AS n_llm_calls
FROM obs_stage_events
WHERE card_id IS NOT NULL AND kind = 'stage'
GROUP BY trace_id, card_id;
