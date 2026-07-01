"""SQLite schema (DDL) for copilot_index.sqlite — the suggestion corpus store.

One durable, inspectable, re-buildable table set: `entities` (assets/metrics/cards/
pages/areas/questions/time presets) + `aliases` (curated/embedded/llm search seeds).
"""

SCHEMA = """
DROP TABLE IF EXISTS entities;
DROP TABLE IF EXISTS aliases;
DROP TABLE IF EXISTS templates;
DROP TABLE IF EXISTS query_log;
CREATE TABLE entities (
  id INTEGER PRIMARY KEY,
  type TEXT NOT NULL,          -- asset|metric|card|page|area|question|time
  canonical TEXT NOT NULL,     -- resolution/verbatim form
  display TEXT NOT NULL,       -- clean label
  unit TEXT, class_scope TEXT, area TEXT,
  table_name TEXT, panel_id TEXT, kind TEXT,
  has_data INTEGER DEFAULT 1,
  popularity REAL DEFAULT 0,   -- semantic salience (e.g. how many cards render a metric)
  keywords TEXT,               -- extra searchable NL seeds (purpose/insight/answers)
  payload TEXT                 -- JSON extras (metrics list, question source, etc.)
);
CREATE TABLE aliases (
  entity_id INTEGER NOT NULL,
  alias TEXT NOT NULL,
  source TEXT,
  UNIQUE(entity_id, alias)
);
CREATE INDEX idx_entities_type ON entities(type);
CREATE INDEX idx_aliases_alias ON aliases(alias);
"""
