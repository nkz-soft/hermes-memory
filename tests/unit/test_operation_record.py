"""The ingestion operation record of ARCHITECTURE.md §18 (User Story 1).

Checks 1-7 of specs/003-logging-telemetry-baseline/contracts/observability.md.

Two claims here are worth more than the rest. One record per operation, carrying every field §18
names — an import that reports nothing per conversation cannot be trusted at the scale this
project targets. And a failed operation is *both* recorded and re-raised: a context manager that
swallowed the exception would produce an identical log line, and the run would carry on as though
the conversation had been handled.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from hermes_memory.observability import OperationStatus, get_logger, ingestion_operation

from .conftest import Rendered

SECTION_18_FIELDS = {
    "source",
    "source_id",
    "project",
    "bank",
    "document_id",
    "start_time",
    "duration_ms",
    "status",
    "error",
}
"""The field set of ARCHITECTURE.md §18, as a set rather than a sample (SC-001)."""

AN_OPERATION = {
    "source": "chatgpt",
    "source_id": "abc-123",
    "bank": "engineering-global",
    "project": "hermes-memory",
    "document_id": "chatgpt:abc-123",
}


def test_one_record_carries_every_field_section_18_names(rendered: Rendered) -> None:
    """Check 1 — the whole field set, not the fields someone remembered (FR-003, SC-001)."""
    with ingestion_operation(**AN_OPERATION):
        pass

    record = rendered.one()

    missing = sorted(SECTION_18_FIELDS - set(record))
    assert not missing, f"Missing from the record: {missing}"
    assert record["event"] == "ingestion.operation"
    assert record["source"] == "chatgpt"
    assert record["source_id"] == "abc-123"
    assert record["bank"] == "engineering-global"
    assert record["project"] == "hermes-memory"
    assert record["document_id"] == "chatgpt:abc-123"


def test_the_nullable_fields_are_present_even_when_unknown(rendered: Rendered) -> None:
    """A field is always present; only its value may be null (data-model.md).

    An operation that failed before classification has no project and no document id. Omitting the
    keys would make a reader unable to tell "not classified" from "this importer forgot".
    """
    with ingestion_operation(source="chatgpt", source_id="abc-123", bank="engineering-global"):
        pass

    record = rendered.one()

    assert record["project"] is None
    assert record["document_id"] is None
    assert record["error"] is None


def test_a_clean_exit_is_imported(rendered: Rendered) -> None:
    """Check 3, first third (FR-004)."""
    with ingestion_operation(**AN_OPERATION):
        pass

    assert rendered.one()["status"] == OperationStatus.IMPORTED.value == "imported"


def test_the_body_can_say_it_skipped(rendered: Rendered) -> None:
    """Check 3, second third — unchanged since a previous run is not the same as imported."""
    with ingestion_operation(**AN_OPERATION) as operation:
        operation.skipped()

    assert rendered.one()["status"] == "skipped"


def test_a_failure_is_recorded_and_still_reaches_the_caller(rendered: Rendered) -> None:
    """Checks 3 and 5, and the most important assertion in this file (FR-006).

    Both halves matter. A context manager that recorded the failure and swallowed it would produce
    exactly the same log line, and the caller would carry on believing the conversation was
    handled. Deciding that one failure must not abort a run is §18's instruction to the *caller*;
    this surface does not get to make it.
    """
    with (
        pytest.raises(RuntimeError, match="the export was truncated"),
        ingestion_operation(**AN_OPERATION),
    ):
        raise RuntimeError("the export was truncated")

    record = rendered.one()

    assert record["status"] == "failed"
    assert record["error"] is not None
    assert "the export was truncated" in record["error"]
    assert "RuntimeError" in record["error"]


def test_the_duration_is_measured_rather_than_supplied(rendered: Rendered) -> None:
    """Check 4 — a caller cannot report a duration it did not spend (FR-005)."""
    with (
        pytest.raises(TypeError),
        ingestion_operation(**AN_OPERATION, duration_ms=0),  # type: ignore[call-arg]
    ):
        pass


def test_the_duration_and_start_time_describe_the_operation(rendered: Rendered) -> None:
    """`duration_ms` is a number and `start_time` parses as an aware timestamp (data-model.md)."""
    with ingestion_operation(**AN_OPERATION):
        pass

    record = rendered.one()

    assert isinstance(record["duration_ms"], int | float)
    assert record["duration_ms"] >= 0

    start = datetime.fromisoformat(record["start_time"])
    assert start.tzinfo is not None, "start_time must be an aware timestamp, in UTC"


def test_context_reaches_records_emitted_inside_the_operation(rendered: Rendered) -> None:
    """Check 6, first half — bound once, carried by everything inside (FR-007)."""
    with ingestion_operation(**AN_OPERATION):
        get_logger().info("sanitized the conversation")

    inside, terminal = rendered.records()

    assert inside["event"] == "sanitized the conversation"
    assert inside["source_id"] == "abc-123"
    assert inside["document_id"] == "chatgpt:abc-123"
    assert terminal["event"] == "ingestion.operation"


def test_context_does_not_outlive_the_operation(rendered: Rendered) -> None:
    """Check 6, second half — context that leaks makes every later record a lie (FR-007)."""
    with ingestion_operation(**AN_OPERATION):
        pass

    get_logger().info("afterwards")

    afterwards = rendered.records()[-1]

    assert afterwards["event"] == "afterwards"
    assert "source_id" not in afterwards
    assert "document_id" not in afterwards


def test_context_does_not_outlive_a_failed_operation(rendered: Rendered) -> None:
    """The path that actually leaks: unbinding on the happy path only is the usual mistake."""
    with pytest.raises(RuntimeError), ingestion_operation(**AN_OPERATION):
        raise RuntimeError("boom")

    get_logger().info("afterwards")

    afterwards = rendered.records()[-1]

    assert "source_id" not in afterwards


def test_two_operations_in_sequence_do_not_share_context(rendered: Rendered) -> None:
    """Check 7 — the second conversation must not inherit the first one's identity."""
    with ingestion_operation(source="chatgpt", source_id="first", bank="engineering-global"):
        pass
    with ingestion_operation(source="chatgpt", source_id="second", bank="engineering-global"):
        pass

    first, second = rendered.records()

    assert first["source_id"] == "first"
    assert second["source_id"] == "second"


def test_the_status_vocabulary_is_closed(rendered: Rendered) -> None:
    """Check 3 — three outcomes and no others, so a typo is a failure and not a value (FR-004)."""
    assert {status.value for status in OperationStatus} == {"imported", "skipped", "failed"}
