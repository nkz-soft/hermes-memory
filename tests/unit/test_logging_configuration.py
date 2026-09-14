"""The pipeline itself: structured always, safe before configuration, idempotent, inert.

Checks 2 and 25-27 of specs/003-logging-telemetry-baseline/contracts/observability.md.

These assert over rendered output, through the `rendered` fixture. Read its docstring before
adding a test here — `structlog.testing.capture_logs` would make several of these pass vacuously.
"""

from __future__ import annotations

import json
import logging as stdlib_logging
import socket
from pathlib import Path

import pytest

from hermes_memory.observability import configure, get_logger
from hermes_memory.settings import load_settings

from .conftest import Rendered


def test_a_record_is_one_json_object_on_one_line(rendered: Rendered) -> None:
    """Check 2 — machine-readable, not a formatted sentence (FR-002)."""
    get_logger().info("parsed an export", conversations=41, source="chatgpt")

    line = rendered.lines()
    assert len(line) == 1

    record = json.loads(line[0])
    assert record["event"] == "parsed an export"
    assert record["conversations"] == 41
    assert record["source"] == "chatgpt"
    assert record["level"] == "info"
    assert "timestamp" in record


def test_a_record_emitted_before_configure_is_structured(rendered: Rendered) -> None:
    """Check 26 — the default has to be the safe one (FR-024).

    Nothing in this test configures anything. The moment a leak is likeliest is while reporting a
    failure — including a failure to load the settings `configure()` needs — so an unconfigured
    process must already be emitting through the real pipeline.
    """
    get_logger().warning("settings could not be loaded")

    assert rendered.one()["event"] == "settings could not be loaded"


def test_configuring_twice_emits_one_line(
    rendered: Rendered, complete_environment: dict[str, str]
) -> None:
    """Check 25 — a stacked handler is how structured logs quietly double-count (FR-023)."""
    settings = load_settings(env_file=None)
    configure(settings)
    configure(settings)

    get_logger().info("once")

    assert len(rendered.lines()) == 1


def test_configuring_twice_does_not_stack_stdlib_handlers(
    rendered: Rendered, complete_environment: dict[str, str]
) -> None:
    """The same claim one layer down, where the duplication would actually come from."""
    settings = load_settings(env_file=None)
    configure(settings)
    configure(settings)
    configure(settings)

    stdlib_logging.getLogger("httpx").warning("connection reset")

    assert len(rendered.lines()) == 1


def test_a_standard_library_record_is_structured_too(
    rendered: Rendered, complete_environment: dict[str, str]
) -> None:
    """FR-001 — httpx and urllib3 log through the standard library and never call our surface.

    Left alone they arrive unstructured *and* unredacted, which is how a request URL with
    credentials in it reaches a log (research.md R5).
    """
    configure(load_settings(env_file=None))

    stdlib_logging.getLogger("httpx").warning("connection reset")

    record = rendered.one()
    assert record["event"] == "connection reset"
    assert record["level"] == "warning"


def test_the_configured_level_is_applied(
    rendered: Rendered, complete_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The level is configuration, not a constant."""
    monkeypatch.setenv("HERMES_LOGGING__LEVEL", "ERROR")
    configure(load_settings(env_file=None))

    get_logger().info("beneath the threshold")
    get_logger().error("above it")

    assert [record["event"] for record in rendered.records()] == ["above it"]


def test_configure_makes_no_network_call(
    rendered: Rendered, complete_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Check 27, first half — configuring observability must not reach for a collector.

    The socket is broken rather than watched: a test that asserts "no connection was attempted"
    by inspecting a recorder still passes if the attempt happens somewhere it did not look.
    """

    def refuse(*arguments: object, **keywords: object) -> None:
        raise AssertionError("configure() attempted to open a socket")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)

    configure(load_settings(env_file=None))

    get_logger().info("still works")
    assert rendered.one()["event"] == "still works"


def test_configure_creates_no_file(
    rendered: Rendered,
    complete_environment: dict[str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Check 27, second half — no log file, no directory, nothing on disk (FR-019)."""
    monkeypatch.chdir(tmp_path)

    configure(load_settings(env_file=None))
    get_logger().info("still works")

    assert list(tmp_path.iterdir()) == []
