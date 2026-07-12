-- db/seed_prompt_corpus.sql — the PROMPT-CORPUS rows: categories (+budgets), templates, vocabulary, corpus.* knobs.
-- The generator (validation/corpus/generate.py) grounds these over the live universe (registry_lt_mfm, pcc_panel_alias,
-- homonym tokens) and multiplies through the mutation engine (validation/corpus/mutators/) — budgets below sum to
-- ~31k cases; raise a budget row to grow a lane, no code edit. Code-default mirror: validation/corpus/store.py.
--
-- Idempotent (ON CONFLICT). Run:
--   psql -h localhost -p 5432 -d cmd_catalog -f db/prompt_corpus_schema.sql
--   psql -h localhost -p 5432 -d cmd_catalog -f db/seed_prompt_corpus.sql

-- ── categories: expected outcome + post-expansion budget (the corpus-size dial) ─────────────────────────────────────
INSERT INTO prompt_category (category, expect, budget, note) VALUES
  ('single_asset',    'cards',                    9000, 'grounded <metric> x UNIQUE asset (confident pin)'),
  ('historical',      'cards',                    6000, 'single_asset + time window'),
  ('panel_aggregate', 'cards',                    2500, 'panel-overview via alias + incomer/outgoing scope'),
  ('compare_2',       'compare:2',                2000, '2-asset same-class compare'),
  ('compare_3',       'compare:3',                 700, '3-asset compare'),
  ('compare_5',       'compare:5|picker',          250, '5-asset compare (picker acceptable at this width)'),
  ('compare_mixed',   'compare:2|picker',          500, 'cross-class compare pairs'),
  ('ambiguous',       'picker',                   1500, 'bare homonym tokens / bare classes -> honest picker'),
  ('invalid',         'empty|picker|unavailable',  400, 'nonexistent asset names -> NEVER cards, NEVER a crash'),
  ('alias',           'cards|picker',             2000, 'alias + short-token spellings of real names'),
  ('mutated',         'cards|picker',             2500, 'mangled spellings (tolerance probes, see mutate.py)'),
  ('knowledge',       'knowledge',                 400, 'concept Q&A -> knowledge lane'),
  ('off_domain',      'refused',                   300, 'off-domain guardrail'),
  ('sld',             'cards',                     350, 'single line diagram view'),
  ('view_3d',         'cards',                     350, '3d asset view'),
  ('narrative',       'cards',                    1500, 'summary/report cards'),
  ('sankey',          'cards',                     250, 'energy flow distribution'),
  ('mixed',           'cards|compare:2',           800, 'multi-intent prompts')
ON CONFLICT (category) DO UPDATE SET expect = EXCLUDED.expect, budget = EXCLUDED.budget, note = EXCLUDED.note;

-- ── templates: surface phrasings with slots the fill engine grounds ─────────────────────────────────────────────────
INSERT INTO prompt_template (tkey, category, template, expect, weight, note) VALUES
  ('single_asset.metric_for_asset', 'single_asset', '<metric> for <asset>',                 NULL, 3, 'canonical form'),
  ('single_asset.asset_metric',     'single_asset', '<asset> <metric>',                     NULL, 2, 'name-first'),
  ('single_asset.show_metric_of',   'single_asset', 'show me <metric> of <asset>',          NULL, 2, ''),
  ('single_asset.whats_metric',     'single_asset', 'what''s the <metric> for <asset>',     NULL, 1, ''),
  ('single_asset.dashboard',        'single_asset', '<metric> dashboard for <asset>',       NULL, 1, ''),
  ('single_asset.how_is_on',        'single_asset', 'how is <asset> doing on <metric>',     NULL, 1, ''),
  ('historical.metric_asset_window','historical',   '<metric> for <asset> <window>',        NULL, 3, 'canonical'),
  ('historical.window_first',       'historical',   '<window> <metric> for <asset>',        NULL, 1, ''),
  ('historical.show_asset_window',  'historical',   'show <asset> <metric> <window>',       NULL, 1, ''),
  ('historical.metric_window',      'historical',   '<metric> <window>',          'cards|picker', 1, 'no asset — routing probe ("power quality last week")'),
  ('panel_aggregate.metric_panel',  'panel_aggregate', '<metric> for <panel>',              NULL, 3, ''),
  ('panel_aggregate.scoped',        'panel_aggregate', '<metric> for <scope> <panel>',      NULL, 2, 'incomer scope words'),
  ('panel_aggregate.overview',      'panel_aggregate', 'overview of <panel>',               NULL, 1, ''),
  ('compare_2.compare_and',         'compare_2',    'compare <asset1> and <asset2>',        NULL, 2, 'no metric'),
  ('compare_2.compare_metric',      'compare_2',    'compare <asset1> and <asset2> <metric>', NULL, 2, ''),
  ('compare_2.vs',                  'compare_2',    '<asset1> vs <asset2> <metric>',        NULL, 2, ''),
  ('compare_2.which_higher',        'compare_2',    'which has higher <metric>, <asset1> or <asset2>', NULL, 1, ''),
  ('compare_3.compare_and',         'compare_3',    'compare <asset1> and <asset2> and <asset3> <metric>', NULL, 1, ''),
  ('compare_3.commas',              'compare_3',    'compare <asset1>, <asset2>, <asset3> <metric>', NULL, 1, ''),
  ('compare_5.compare_and',         'compare_5',    'compare <asset1> and <asset2> and <asset3> and <asset4> and <asset5> <metric>', NULL, 1, ''),
  ('compare_mixed.compare_and',     'compare_mixed','compare <asset1> and <asset2> <metric>', NULL, 1, 'fill crosses classes'),
  ('ambiguous.dashboard_token',     'ambiguous',    'show me the dashboard for <token>',    NULL, 2, 'bare homonym'),
  ('ambiguous.metric_class',        'ambiguous',    '<metric> for <class>',                 NULL, 2, 'bare class'),
  ('ambiguous.bare_token',          'ambiguous',    '<token>',                              NULL, 1, 'just the token'),
  ('invalid.metric_for',            'invalid',      '<metric> for <invalid>',               NULL, 2, ''),
  ('invalid.bare',                  'invalid',      '<invalid> dashboard',                  NULL, 1, ''),
  ('alias.metric_panel',            'alias',        '<metric> for <panel>',                 NULL, 2, 'panel slot fills with ALIAS spellings'),
  ('alias.metric_short',            'alias',        '<metric> for <asset>',                 NULL, 2, 'asset slot fills with SHORT unit token'),
  ('mutated.metric_for',            'mutated',      '<metric> for <asset>',                 NULL, 1, 'asset then name-mangled'),
  ('knowledge.concept',             'knowledge',    '<concept>',                            NULL, 1, ''),
  ('off_domain.prompt',             'off_domain',   '<offdomain>',                          NULL, 1, ''),
  ('sld.for_panel',                 'sld',          'single line diagram for <panel>',      NULL, 2, ''),
  ('sld.sld_of',                    'sld',          'sld of <panel>',                       NULL, 1, ''),
  ('view_3d.of_panel',              'view_3d',      '3d view of <panel>',                   NULL, 2, ''),
  ('view_3d.show_asset',            'view_3d',      'show <asset> in 3d',                   NULL, 1, ''),
  ('narrative.summary_terse',       'narrative',    'summary <asset>',                      NULL, 2, 'terse form'),
  ('narrative.give_summary',        'narrative',    'give me a summary of <asset>',         NULL, 2, ''),
  ('narrative.performing',          'narrative',    'how is <asset> performing today',      NULL, 1, ''),
  ('narrative.brief_report',        'narrative',    'brief report on <asset>',              NULL, 1, ''),
  ('sankey.flow_panel',             'sankey',       'energy flow distribution for <panel>', NULL, 1, ''),
  ('mixed.window_summary',          'mixed',        '<metric> for <asset> <window> and summarize anomalies', NULL, 1, ''),
  ('mixed.metric_plus_summary',     'mixed',        '<metric> for <asset> and give me a summary', NULL, 1, '')
ON CONFLICT (tkey) DO UPDATE SET category = EXCLUDED.category, template = EXCLUDED.template,
  expect = EXCLUDED.expect, weight = EXCLUDED.weight, note = EXCLUDED.note;

-- ── vocabulary lanes ────────────────────────────────────────────────────────────────────────────────────────────────
-- metric: meta = csv of asset classes it applies to ('' = every electrical-metered class) — mirrors layer1a routing
INSERT INTO prompt_vocab (kind, value, meta, note) VALUES
  ('metric', 'voltage and current',          '', ''),
  ('metric', 'energy and power',             '', ''),
  ('metric', 'power factor',                 '', ''),
  ('metric', 'power quality and harmonics',  '', ''),
  ('metric', 'load factor',                  '', ''),
  ('metric', 'demand profile',               '', ''),
  ('metric', 'load anomalies',               '', ''),
  ('metric', 'real time monitoring',         '', ''),
  ('metric', 'efficiency',                   'DG,Chiller,Transformer,UPS', ''),
  ('metric', 'operations and runtime',       'DG', ''),
  ('metric', 'fuel efficiency',              'DG', ''),
  ('metric', 'thermal oil',                  'Compressor,Dryer', ''),
  ('metric', 'pressure element',             'Compressor,Dryer', ''),
  ('metric', 'condenser performance',        'Chiller', ''),
  ('metric', 'overview',                     'Chiller,AHU,AirWasher,CoolingTower,Pump,Fan,Dryer', ''),
  ('window', 'today', '', ''), ('window', 'yesterday', '', ''),
  ('window', 'over the last hour', '', ''), ('window', 'over the last 30 minutes', '', ''),
  ('window', 'over the last 7 days', '', ''), ('window', 'over the last 30 days', '', ''),
  ('window', 'this month', '', ''), ('window', 'this week', '', ''),
  ('window', 'last week', '', ''), ('window', 'last month', '', ''),
  ('window', 'past 24 hours', '', ''), ('window', 'since monday', '', ''),
  ('conv_prefix', 'can you show me', '', ''), ('conv_prefix', 'please pull up', '', ''),
  ('conv_prefix', 'hey, i need', '', ''), ('conv_prefix', 'show me', '', ''),
  ('conv_prefix', 'i want to see', '', ''), ('conv_prefix', 'could you display', '', ''),
  ('conv_prefix', 'give me', '', ''), ('conv_prefix', 'let me see', '', ''),
  ('conv_prefix', 'bring up', '', ''), ('conv_prefix', 'pull up', '', ''),
  ('conv_prefix', 'i''d like to check', '', ''), ('conv_prefix', 'quickly show', '', ''),
  ('conv_suffix', 'please', '', ''), ('conv_suffix', 'right now', '', ''),
  ('conv_suffix', 'thanks', '', ''), ('conv_suffix', 'asap', '', ''),
  ('conv_suffix', 'on the main screen', '', ''), ('conv_suffix', 'for the plant', '', ''),
  ('conv_suffix', 'when you get a chance', '', ''), ('conv_suffix', 'quickly', '', ''),
  ('concept', 'what is power factor', '', ''), ('concept', 'explain THD', '', ''),
  ('concept', 'explain apparent power', '', ''), ('concept', 'how does a UPS work', '', ''),
  ('concept', 'what is a cooling tower', '', ''), ('concept', 'difference between kW and kVA', '', ''),
  ('concept', 'how does a diesel generator work', '', ''), ('concept', 'what causes voltage sag', '', ''),
  ('concept', 'explain load factor', '', ''), ('concept', 'what is reactive power', '', ''),
  ('off_domain', 'what''s the weather today', '', ''), ('off_domain', 'who won the cricket match', '', ''),
  ('off_domain', 'who is the prime minister of india', '', ''), ('off_domain', 'recommend me a movie', '', ''),
  ('off_domain', 'write a poem about the sea', '', ''), ('off_domain', 'capital of france', '', ''),
  ('invalid_asset', 'DG-999', '', ''), ('invalid_asset', 'ZZZ-Unknown-Plant-7', '', ''),
  ('invalid_asset', 'Fake-UPS-77', '', ''), ('invalid_asset', 'Transformer-99X', '', ''),
  ('invalid_asset', 'UPS-1000', '', ''), ('invalid_asset', 'Chiller-77Z', '', ''),
  -- scope_incomer mirrors a SUBSET of vocab.panel_member_direction (the full row stays the resolver's source of truth)
  ('scope_incomer', 'incomer', '', ''), ('scope_incomer', 'incoming', '', ''),
  ('scope_incomer', 'supply side', '', ''), ('scope_incomer', 'source side', '', ''),
  ('scope_incomer', 'upstream', '', ''),
  -- metric_abbrev: meta = the canonical phrase the abbreviation replaces (abbrev mutator does canonical -> value)
  ('metric_abbrev', 'pf',    'power factor', ''), ('metric_abbrev', 'thd',  'harmonics', ''),
  ('metric_abbrev', 'volts', 'voltage', ''),      ('metric_abbrev', 'amps', 'current', ''),
  ('metric_abbrev', 'kwh',   'energy', ''),       ('metric_abbrev', 'rtm',  'real time monitoring', ''),
  ('metric_abbrev', 'sld',   'single line diagram', ''),
  -- class_abbrev: meta = the canonical word inside asset NAMES (aliasing/abbrev mutators swap it)
  ('class_abbrev', 'tfr',    'transformer', ''), ('class_abbrev', 'xfmr', 'transformer', ''),
  ('class_abbrev', 'trafo',  'transformer', ''), ('class_abbrev', 'genset', 'generator', ''),
  ('class_abbrev', 'pnl',    'panel', ''),       ('class_abbrev', 'comp', 'compressor', ''),
  -- plural: value = plural form, meta = singular stem (plural mutator swaps both directions)
  ('plural', 'transformers', 'transformer', ''), ('plural', 'panels',   'panel', ''),
  ('plural', 'chillers',     'chiller', ''),     ('plural', 'pumps',    'pump', ''),
  ('plural', 'fans',         'fan', ''),         ('plural', 'anomalies','anomaly', ''),
  ('plural', 'compressors',  'compressor', ''),  ('plural', 'feeders',  'feeder', '')
ON CONFLICT (kind, value) DO UPDATE SET meta = EXCLUDED.meta, note = EXCLUDED.note;

-- ── corpus knobs ────────────────────────────────────────────────────────────────────────────────────────────────────
INSERT INTO app_config (key, value, data_type, section, note) VALUES
  ('corpus.seed', '48', 'int', 'corpus',
   'Deterministic RNG seed for corpus generation (per-case sub-seeded from sha1(case id) so row additions never '
   'reshuffle existing cases). Mirror: validation/corpus/generate.py. Read by generate().'),
  ('corpus.mutators', '["casing","spelling","abbrev","partial","plural","aliasing","conversational"]', 'json', 'corpus',
   'Enabled mutation families (validation/corpus/mutators/ registry names). Remove one to kill its variants corpus-wide. '
   'Mirror: validation/corpus/mutators/__init__.py _ALL. Read by enabled_mutators().'),
  ('corpus.mutations_per_case', '11', 'int', 'corpus',
   'Max mutation variants sampled per base case (deterministic per-case sample). Raising this multiplies corpus size '
   'toward each category budget. Mirror: validation/corpus/mutate.py. Read by expand_case().')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, data_type = EXCLUDED.data_type,
  section = EXCLUDED.section, note = EXCLUDED.note;
