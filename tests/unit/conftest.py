"""Shared fixtures for the settings suites.

Every test here runs against an environment this file controls. A developer's own `HERMES_*`
variables, or a `.env` sitting in their checkout, would otherwise decide whether the suite passes
— which is the failure mode that makes a configuration test worthless.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

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
