"""SQL for the ``current_estimates`` view — the single source of truth.

Reads (see ``repositories.py``) go through this view, which collapses the append-only
``estimates`` ledger to the latest publish per logical key. ``init_db`` creates it and the
test suites recreate it; all import it from here so the DDL is defined exactly once.
"""

from __future__ import annotations

CURRENT_ESTIMATES_VIEW = """
CREATE OR REPLACE VIEW current_estimates AS
SELECT DISTINCT ON (company_id, kpi_id, period_start, est_type, as_of) *
FROM estimates
ORDER BY company_id, kpi_id, period_start, est_type, as_of, published_at DESC;
"""
