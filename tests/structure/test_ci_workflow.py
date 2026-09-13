"""The CI workflow keeps the promises `contracts/checks.md` makes about it.

CI cannot be unit-tested — the only honest proof that it reports is a pull request that runs it.
What can be asserted here is the set of properties that rot silently: that it still runs all four
checks, that `uv sync` still carries `--locked`, and that it still needs no secret and therefore
still runs on pull requests from forks.

The file is read as text rather than parsed as YAML, deliberately: no YAML parser is a dependency
of this project, and adding one to assert four substrings would put a runtime-shaped dependency in
the lock file for nothing (FR-011).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _workflow() -> str:
    assert WORKFLOW.exists(), f"The CI workflow is missing at {WORKFLOW.relative_to(REPO_ROOT)}."
    return WORKFLOW.read_text(encoding="utf-8")


def test_runs_on_pull_requests_to_main() -> None:
    """Every pull request is checked automatically (FR-008)."""
    text = _workflow()

    assert re.search(r"^on:", text, re.MULTILINE), "The workflow declares no triggers."
    assert "pull_request:" in text, "The workflow does not trigger on pull requests."
    assert re.search(r"branches:\s*\[\s*main\s*\]", text), (
        "The workflow does not name main as the branch its pull-request trigger targets."
    )


def test_runs_every_check_in_the_contract() -> None:
    """All four checks of contracts/checks.md run in CI, not a subset."""
    text = _workflow()
    checks = {
        "C1 environment install": "uv sync",
        "C2 lint": "ruff check",
        "C3 format": "ruff format --check",
        "C4 tests": "pytest",
    }

    missing = [name for name, command in checks.items() if command not in text]

    assert not missing, (
        f"The workflow does not run these checks from contracts/checks.md: {missing}. "
        "A check that runs only locally is a check that stops running."
    )


def test_install_is_locked() -> None:
    """CI installs from the committed lock file rather than re-resolving (FR-009).

    Without --locked, CI can quietly resolve a different dependency set than a contributor has,
    and a local pass and a CI pass stop meaning the same thing.
    """
    text = _workflow()

    assert "uv sync --locked" in text, (
        "The workflow runs `uv sync` without --locked, so it may re-resolve dependencies "
        "instead of failing when uv.lock disagrees with pyproject.toml."
    )


def test_needs_no_secrets_so_forks_can_run_it() -> None:
    """The workflow reads no secret and asks for no write access (Principle V).

    This is what lets it run unchanged on a pull request from a fork, and it is the property
    most likely to be lost by accident when a later step is added.
    """
    text = _workflow()

    assert "secrets." not in text, (
        "The workflow references a repository secret. None of the four checks needs one, "
        "and requiring one stops the workflow running on pull requests from forks."
    )
    assert re.search(r"permissions:\s*\n\s*contents:\s*read", text), (
        "The workflow does not declare `permissions: contents: read`. "
        "It only reads the repository; say so rather than inheriting the default token scope."
    )
