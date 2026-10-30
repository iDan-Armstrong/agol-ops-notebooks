"""agolops: ArcGIS Online administration logic, kept out of the notebooks.

Hosted notebooks are a great scheduler and a terrible place for logic: they
can't be unit-tested, diffed meaningfully, or code-reviewed line by line. So
the notebooks in this repo are thin — connect, call agolops, display — and
everything decision-shaped lives here, where pytest can reach it.

The functions take plain dicts (item properties, layer rows), not live
``arcgis`` objects, so tests need no portal and no license.
"""

from agolops.audit import AuditFinding, audit_items
from agolops.refresh import RefreshPlan, plan_refresh, validate_against_layer

__all__ = [
    "AuditFinding",
    "RefreshPlan",
    "audit_items",
    "plan_refresh",
    "validate_against_layer",
]

__version__ = "0.2.0"
