"""Scheduled hosted-layer refresh: the decision logic.

The notebook fetches fresh source rows and hands them here with the target
layer's current state; this module decides *what to do* and the notebook
executes it with the arcgis API. Splitting it this way makes the dangerous
part — "should we overwrite production?" — a pure, tested function.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RefreshPlan:
    action: str  # "replace" | "abort"
    reason: str
    chunks: int = 0
    chunk_size: int = 0


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_against_layer(
    rows: list[dict],
    layer_fields: list[str],
    required_fields: list[str],
    key_field: str,
) -> ValidationResult:
    """Pre-flight: would these rows load cleanly into the target layer?"""
    result = ValidationResult()
    if not rows:
        result.errors.append("source returned zero rows")
        return result

    layer_set = {f.lower() for f in layer_fields}
    row_fields = set(rows[0])
    missing_in_layer = sorted(f for f in row_fields if f.lower() not in layer_set)
    if missing_in_layer:
        result.errors.append(f"source fields not in target layer: {missing_in_layer}")

    for f in required_fields:
        nulls = sum(1 for r in rows if r.get(f) in (None, ""))
        if nulls:
            result.errors.append(f"{nulls} rows have null {f!r}")

    keys = [r.get(key_field) for r in rows]
    dupes = len(keys) - len(set(keys))
    if dupes:
        result.errors.append(f"{dupes} duplicate values in key field {key_field!r}")

    ragged = sum(1 for r in rows if set(r) != row_fields)
    if ragged:
        result.warnings.append(f"{ragged} rows have inconsistent fields")
    return result


def plan_refresh(
    new_count: int,
    current_count: int,
    validation: ValidationResult,
    max_shrink_pct: float = 20.0,
    chunk_size: int = 500,
) -> RefreshPlan:
    """Decide whether the refresh is safe to execute.

    The shrink guard is the lesson every ops team learns exactly once: an
    upstream outage returns a near-empty extract, the scheduled job happily
    truncates production, and Monday starts with a restore. A big shrink is
    *possible* but must be a human decision, so the plan aborts and says why.
    """
    if not validation.ok:
        return RefreshPlan("abort", "validation failed: " + "; ".join(validation.errors))

    if current_count > 0:
        shrink = (current_count - new_count) / current_count * 100.0
        if shrink > max_shrink_pct:
            return RefreshPlan(
                "abort",
                f"new data has {new_count} rows vs {current_count} current "
                f"({shrink:.0f}% shrink > {max_shrink_pct:.0f}% guard); "
                "refusing to truncate — rerun with a higher guard if intentional",
            )

    chunks = max(1, -(-new_count // chunk_size))  # ceil
    return RefreshPlan("replace", "validated", chunks=chunks, chunk_size=chunk_size)
