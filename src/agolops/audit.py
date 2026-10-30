"""Content audit: classify portal items by governance findings.

Input is a list of plain dicts, one per item, with the keys the notebook
pulls off each ``arcgis.gis.Item``. Timestamps are epoch milliseconds, as
the REST API returns them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

MS_PER_DAY = 86_400_000


@dataclass(frozen=True)
class AuditFinding:
    item_id: str
    title: str
    owner: str
    finding: str
    detail: str


def _days_since(epoch_ms: int | None, now_ms: int) -> float | None:
    if not epoch_ms:
        return None
    return (now_ms - epoch_ms) / MS_PER_DAY


def audit_items(
    items: list[dict],
    now_ms: int | None = None,
    stale_days: int = 365,
    orphan_owners: set[str] | None = None,
) -> list[AuditFinding]:
    """Classify items. One item can yield several findings.

    Checks (each one maps to a real cleanup action an admin can take):
    - ``stale``: not modified in ``stale_days`` and never viewed in the last year
    - ``no_description``: missing/boilerplate description (undiscoverable content)
    - ``no_thumbnail``: default thumbnail (unprofessional in galleries)
    - ``public_unreviewed``: shared to everyone but missing description or terms
    - ``orphaned``: owner no longer in the org (left/offboarded)
    - ``no_delete_protection``: production-looking item without delete protection
    """
    now_ms = now_ms or int(datetime.now(timezone.utc).timestamp() * 1000)
    orphan_owners = orphan_owners or set()
    findings: list[AuditFinding] = []

    def add(item: dict, finding: str, detail: str) -> None:
        findings.append(
            AuditFinding(
                item_id=item.get("id", "?"),
                title=item.get("title") or "(untitled)",
                owner=item.get("owner", "?"),
                finding=finding,
                detail=detail,
            )
        )

    for item in items:
        modified_days = _days_since(item.get("modified"), now_ms)
        views = item.get("numViews", 0)

        if modified_days is not None and modified_days > stale_days and views == 0:
            add(item, "stale", f"last modified {modified_days:.0f} days ago, zero views")

        description = (item.get("description") or "").strip()
        if len(description) < 20:
            add(item, "no_description", f"description length {len(description)}")

        if not item.get("thumbnail"):
            add(item, "no_thumbnail", "default thumbnail")

        if item.get("access") == "public" and (
            len(description) < 20 or not (item.get("licenseInfo") or "").strip()
        ):
            add(item, "public_unreviewed", "public without description and terms of use")

        if item.get("owner") in orphan_owners:
            add(item, "orphaned", f"owner {item.get('owner')!r} not in org")

        title = (item.get("title") or "").lower()
        looks_production = any(k in title for k in ("prod", "production", "master", "official"))
        if looks_production and not item.get("protected", False):
            add(item, "no_delete_protection", "production-named item is deletable")

    return findings


def summarize(findings: list[AuditFinding]) -> dict[str, int]:
    out: dict[str, int] = {}
    for f in findings:
        out[f.finding] = out.get(f.finding, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))
