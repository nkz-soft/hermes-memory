"""Shared fixtures for the unit suites.

Every test here runs against an environment this file controls. A developer's own `HERMES_*`
variables, or a `.env` sitting in their checkout, would otherwise decide whether the suite passes
— which is the failure mode that makes a configuration test worthless.

The second half of this file serves the observability suites, and carries one warning worth
reading before writing a test against a log record: see `rendered`.
"""

from __future__ import annotations

import io
import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hermes_memory.observability import logging as observability_logging

PREFIX = "HERMES_"

COMPLETE_ENVIRONMENT = {
    "HERMES_HINDSIGHT__BASE_URL": "http://localhost:8088",
    "HERMES_HINDSIGHT__TOKEN": "hindsight-token-value",
    "HERMES_LLM__BASE_URL": "http://localhost:4000/v1",
    "HERMES_LLM__API_KEY": "llm-key-value",
}
"""Enough to load successfully, with both secrets set so leaks have something to leak."""


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Remove every `HERMES_*` variable, so each test starts from nothing."""
    for name in list(os.environ):
        if name.startswith(PREFIX):
            monkeypatch.delenv(name, raising=False)
    yield


@pytest.fixture
def complete_environment(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """A valid environment, returned so a test can state which variable it then breaks."""
    for name, value in COMPLETE_ENVIRONMENT.items():
        monkeypatch.setenv(name, value)
    return dict(COMPLETE_ENVIRONMENT)


@pytest.fixture
def env_file(tmp_path: Path):
    """Write a `.env` in a temporary directory and hand back its path."""

    def write(contents: str) -> Path:
        path = tmp_path / ".env"
        path.write_text(contents, encoding="utf-8")
        return path

    return write


class Rendered:
    """The bytes the process actually emitted, and the records parsed back out of them.

    Assertions are made against this — never against the event dictionary a caller built — because
    what has to be true is that *the output* carries no credential.
    """

    def __init__(self, stream: io.StringIO) -> None:
        self._stream = stream

    def text(self) -> str:
        """Everything written so far, verbatim. Use it for `assert secret not in ...`."""
        return self._stream.getvalue()

    def lines(self) -> list[str]:
        """The non-empty lines written so far."""
        return [line for line in self.text().splitlines() if line.strip()]

    def records(self) -> list[dict[str, Any]]:
        """Every line parsed as JSON. Fails the test if a line is not one object."""
        return [json.loads(line) for line in self.lines()]

    def one(self) -> dict[str, Any]:
        """The single record emitted, insisting there is exactly one."""
        records = self.records()
        assert len(records) == 1, (
            f"Expected exactly one record, got {len(records)}: {self.text()!r}"
        )
        return records[0]


@pytest.fixture
def rendered(monkeypatch: pytest.MonkeyPatch) -> Iterator[Rendered]:
    """Capture what the logging pipeline writes, rendered exactly as it would be in production.

    **Do not use `structlog.testing.capture_logs` in these suites.** It replaces the processor
    chain with a capturing one, so it hands back the event dictionary *as the caller built it* —
    credential intact, content intact, nothing redacted. A redaction test written against it
    passes while proving nothing, and it is the most natural thing to reach for. That is the one
    failure mode these tests exist to prevent
    (specs/003-logging-telemetry-baseline/research.md R13).

    The pipeline's own destination is redirected rather than `sys.stderr` itself, and that is not
    a shortcut: pytest reinstalls `sys.stderr` between fixture setup and the call phase when
    capturing is on, so a fixture that patched it would silently capture nothing and every
    assertion here would be made against an empty buffer. Redirecting the destination covers both
    paths out of the pipeline — structlog's own writer and the standard-library handler.
    """
    stream = io.StringIO()
    monkeypatch.setattr(observability_logging, "_destination", lambda: stream)
    yield Rendered(stream)


@pytest.fixture(autouse=True)
def pristine_pipeline() -> Iterator[None]:
    """Leave the logging configuration as this suite found it.

    A test that calls `configure()` would otherwise decide how every later test in the session
    renders, which turns an ordering change into a mystery failure. The standard-library handler
    is removed as well as structlog's configuration: left attached, it would go on writing into a
    buffer belonging to a test that finished.
    """
    yield

    observability_logging.install_default_pipeline()
    observability_logging.remove_standard_library_bridge()
