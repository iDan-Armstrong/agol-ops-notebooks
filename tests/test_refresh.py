from __future__ import annotations

from agolops.refresh import plan_refresh, validate_against_layer

LAYER_FIELDS = ["facility_id", "facility_name", "facility_type", "beds"]
GOOD_ROWS = [
    {"facility_id": 1, "facility_name": "Alpha", "facility_type": "clinic", "beds": 10},
    {"facility_id": 2, "facility_name": "Bravo", "facility_type": "hospital", "beds": 200},
]


def validate(rows):
    return validate_against_layer(
        rows, LAYER_FIELDS, required_fields=["facility_name"], key_field="facility_id"
    )


def test_valid_rows_pass() -> None:
    assert validate(GOOD_ROWS).ok


def test_zero_rows_is_an_error() -> None:
    result = validate([])
    assert not result.ok and "zero rows" in result.errors[0]


def test_unknown_field_detected() -> None:
    rows = [dict(GOOD_ROWS[0], surprise_column=1)]
    result = validate(rows)
    assert any("surprise_column" in e for e in result.errors)


def test_null_required_and_duplicate_keys() -> None:
    rows = [
        dict(GOOD_ROWS[0], facility_name=None),
        dict(GOOD_ROWS[1], facility_id=1),
        GOOD_ROWS[0],
    ]
    result = validate(rows)
    assert any("null 'facility_name'" in e for e in result.errors)
    assert any("duplicate" in e for e in result.errors)


def test_plan_aborts_on_validation_failure() -> None:
    plan = plan_refresh(0, 100, validate([]))
    assert plan.action == "abort" and "validation failed" in plan.reason


def test_shrink_guard_trips() -> None:
    plan = plan_refresh(new_count=50, current_count=100, validation=validate(GOOD_ROWS))
    assert plan.action == "abort"
    assert "50% shrink" in plan.reason


def test_shrink_within_guard_proceeds() -> None:
    plan = plan_refresh(new_count=90, current_count=100, validation=validate(GOOD_ROWS))
    assert plan.action == "replace"


def test_growth_always_allowed_and_chunked() -> None:
    plan = plan_refresh(new_count=1250, current_count=100, validation=validate(GOOD_ROWS))
    assert plan.action == "replace"
    assert plan.chunks == 3 and plan.chunk_size == 500


def test_first_load_into_empty_layer() -> None:
    plan = plan_refresh(new_count=10, current_count=0, validation=validate(GOOD_ROWS))
    assert plan.action == "replace"
