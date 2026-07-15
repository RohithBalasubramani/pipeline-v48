-- db/seed_pipeline_error_reason.sql — reason template for the PIPELINE-ERROR honest terminal (run/error_terminal.py).
-- A NON-outage layer exception that left the layer with no output historically shipped a silent ok=True 0-card page
-- [audit 2026-07-14, 01 F1: dangling-registry raise]. This template is the user-facing sentence the FE renders on the
-- existing data_unavailable wire (degrade.kind="pipeline_error" keeps it machine-distinct from an outage).
-- Apply: psql cmd_catalog -f db/seed_pipeline_error_reason.sql

INSERT INTO reason_template (cause, template) VALUES
 ('pipeline_error', 'A system error prevented building this page ({layer} failed). This is a pipeline defect, not missing data — the error has been recorded; please retry or report it.')
ON CONFLICT (cause) DO UPDATE SET template = EXCLUDED.template;
