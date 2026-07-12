"""config/metric_class.py — thin reader over cmd_catalog.metric_class (page → required column class).

The per-(asset,page) feasibility gate input: which column CLASS a page needs (energy-power needs power+energy; power-
quality needs thd; voltage-current needs voltage+current). Combined with schema_map.has_quantity(fingerprint, class) a
caller can decide whether a resolved meter's table can actually render the routed page, else no_class honest-degrade.
[DS-07, class-vs-page, SCADA-pin]  NO hardcoded page→class map in logic code — it READS this table.
"""
from data.db_client import q


def required_classes(page_key):
    """The set of column classes `page_key` requires → ['power','energy',...] (empty if the page is unconstrained)."""
    rows = q("cmd_catalog",
             f"SELECT required_class FROM metric_class WHERE page_key='{_esc(page_key)}' ORDER BY required_class")
    return [r[0] for r in rows]


from config.policy_read import esc as _esc  # the ONE shared SQL-quote escape  # noqa: E402
