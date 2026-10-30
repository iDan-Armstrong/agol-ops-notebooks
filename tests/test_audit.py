from __future__ import annotations

from agolops.audit import MS_PER_DAY, audit_items, summarize

NOW = 1_700_000_000_000  # fixed 'now' so tests are deterministic


def item(**overrides) -> dict:
    base = {
        "id": "abc123",
        "title": "Facilities 2024",
        "owner": "daniel",
        "modified": NOW - 10 * MS_PER_DAY,
        "numViews": 42,
        "description": "Health facility locations, updated monthly from the registry.",
        "thumbnail": "thumbnail/custom.png",
        "access": "org",
        "licenseInfo": "Internal use",
        "protected": True,
    }
    base.update(overrides)
    return base


def kinds(findings) -> set[str]:
    return {f.finding for f in findings}


def test_clean_item_has_no_findings() -> None:
    assert audit_items([item()], now_ms=NOW) == []


def test_stale_requires_old_and_unviewed() -> None:
    old_unviewed = item(modified=NOW - 400 * MS_PER_DAY, numViews=0)
    old_but_viewed = item(modified=NOW - 400 * MS_PER_DAY, numViews=5)
    assert "stale" in kinds(audit_items([old_unviewed], now_ms=NOW))
    assert "stale" not in kinds(audit_items([old_but_viewed], now_ms=NOW))


def test_no_description_and_public_unreviewed() -> None:
    findings = kinds(audit_items([item(description="", access="public")], now_ms=NOW))
    assert {"no_description", "public_unreviewed"} <= findings


def test_public_with_description_and_terms_is_fine() -> None:
    findings = kinds(audit_items([item(access="public")], now_ms=NOW))
    assert "public_unreviewed" not in findings


def test_orphaned_owner() -> None:
    findings = audit_items([item(owner="ghost")], now_ms=NOW, orphan_owners={"ghost"})
    assert "orphaned" in kinds(findings)


def test_production_item_without_delete_protection() -> None:
    findings = kinds(audit_items([item(title="Roads PROD", protected=False)], now_ms=NOW))
    assert "no_delete_protection" in findings
    assert "no_delete_protection" not in kinds(
        audit_items([item(title="Roads PROD", protected=True)], now_ms=NOW)
    )


def test_summarize_sorts_by_count() -> None:
    items = [item(description=""), item(description=""), item(thumbnail=None)]
    counts = summarize(audit_items(items, now_ms=NOW))
    assert counts["no_description"] == 2
    assert list(counts)[0] == "no_description"
