"""A later span has somewhere to attach, and its records can be found (User Story 4).

Checks 30-32 of specs/003-logging-telemetry-baseline/contracts/observability.md.

This feature provides the tracer, not the tracing. The span around `retain` belongs to the feature
that makes the call; what has to exist first is a provider it can ask, and correlation that
happens without the caller threading identifiers through every signature.

Nothing is exported. No exporter is declared as a dependency, no destination is configured, and an
operator with no collector running is not asked to start one (research.md R11).
"""

from __future__ import annotations

import socket

import pytest

from hermes_memory.observability import configure, get_logger, get_tracer
from hermes_memory.settings import load_settings

from .conftest import Rendered


@pytest.fixture
def configured(complete_environment: dict[str, str]) -> None:
    configure(load_settings(env_file=None))


def test_a_span_can_be_started_and_ended(configured: None) -> None:
    """Check 30, first half — the attachment point exists (FR-018)."""
    with get_tracer(__name__).start_as_current_span("retain") as span:
        assert span is not None


def test_starting_a_span_makes_no_network_call(
    configured: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Check 30, second half — with no collector, nothing is exported and nothing is attempted.

    The socket is broken rather than watched: a recorder only proves that the attempt did not
    happen where the recorder was looking (FR-019).
    """

    def refuse(*arguments: object, **keywords: object) -> None:
        raise AssertionError("tracing attempted to open a socket")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)

    with get_tracer(__name__).start_as_current_span("retain"):
        pass


def test_a_record_inside_a_span_carries_the_identifiers(
    rendered: Rendered, configured: None
) -> None:
    """Check 31 — logs and traces can be joined afterwards (FR-020)."""
    with get_tracer(__name__).start_as_current_span("retain"):
        get_logger().info("inside a span")

    record = rendered.one()

    assert "trace_id" in record
    assert "span_id" in record
    assert record["trace_id"] != ""
    assert int(record["trace_id"], 16) != 0, "an all-zero trace id means the span was invalid"


def test_the_identifiers_are_lowercase_hexadecimal_of_the_conventional_width(
    rendered: Rendered, configured: None
) -> None:
    """The shape every tracing tool expects: 32 hex digits and 16, lower case."""
    with get_tracer(__name__).start_as_current_span("retain"):
        get_logger().info("inside a span")

    record = rendered.one()

    assert len(record["trace_id"]) == 32
    assert len(record["span_id"]) == 16
    assert record["trace_id"] == record["trace_id"].lower()
    assert record["span_id"] == record["span_id"].lower()


def test_a_record_outside_a_span_carries_neither(rendered: Rendered, configured: None) -> None:
    """Check 32 — empty identifiers on every line would double the noise for no information."""
    get_logger().info("outside a span")

    record = rendered.one()

    assert "trace_id" not in record
    assert "span_id" not in record


def test_a_record_after_a_span_has_ended_carries_neither(
    rendered: Rendered, configured: None
) -> None:
    """The identifiers follow the span, not the process."""
    with get_tracer(__name__).start_as_current_span("retain"):
        pass

    get_logger().info("afterwards")

    assert "trace_id" not in rendered.one()


def test_correlation_works_before_configure_is_called(rendered: Rendered) -> None:
    """The correlation slot is in the default pipeline too, not only in the configured one."""
    with get_tracer(__name__).start_as_current_span("retain"):
        get_logger().info("inside a span")

    assert "trace_id" in rendered.one()


def test_no_exporter_distribution_is_declared() -> None:
    """R11 — the provider is the seam; the feature that exports chooses its exporter then.

    Asserted rather than left as prose: an exporter arriving quietly would mean records leaving
    this machine, which is a decision with a different weight to it than adding a library.
    """
    from importlib.util import find_spec

    assert find_spec("opentelemetry.exporter") is None, (
        "An OpenTelemetry exporter is installed. Nothing in this project exports traces yet, and "
        "the feature that does should choose its exporter against a real collector."
    )
