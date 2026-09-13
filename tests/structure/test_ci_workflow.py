"""The CI workflow keeps the promises `contracts/checks.md` makes about it.

CI cannot be unit-tested — the only honest proof that it reports is a pull request that runs it.
What can be asserted here is the set of properties that rot silently: that it is still valid YAML
GitHub will actually run, that it still runs all four checks *as commands*, that `uv sync` still
carries `--locked`, and that it still needs no secret and therefore still runs on pull requests
from forks.

The workflow is parsed as YAML rather than matched as text. An earlier version of this file did
match text, and a code review demonstrated the consequence: a workflow with no steps at all
satisfied every assertion, because `ci.yml`'s own comments contain the strings being searched for,
and so did a workflow with deliberately invalid YAML appended. A check a comment can satisfy is
not a check. PyYAML is a development dependency only — FR-011 forbids adding a *runtime*
dependency, and this is in the same group as pytest and ruff.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _workflow() -> dict[str, Any]:
    """The parsed workflow. Fails if it is not valid YAML — GitHub would silently not run it."""
    assert WORKFLOW.exists(), f"The CI workflow is missing at {WORKFLOW.relative_to(REPO_ROOT)}."

    try:
        document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:  # pragma: no cover - only on a broken workflow
        raise AssertionError(
            f".github/workflows/ci.yml is not valid YAML, so GitHub will not run it: {error}"
        ) from error

    assert isinstance(document, dict), "The workflow did not parse to a mapping."
    return document


def _triggers(document: dict[str, Any]) -> dict[str, Any]:
    """The `on:` block. PyYAML resolves the bare key `on` to the boolean True (YAML 1.1)."""
    triggers = document.get("on", document.get(True))
    assert isinstance(triggers, dict), "The workflow declares no triggers."
    return triggers


def _run_commands(document: dict[str, Any]) -> list[str]:
    """Every `run:` script in the workflow — the commands GitHub will actually execute.

    Comments and step names are excluded by construction, which is the point: only a real
    command satisfies the assertions below.
    """
    commands: list[str] = []

    for job in document.get("jobs", {}).values():
        for step in job.get("steps", []):
            script = step.get("run")
            if script:
                commands.append(script)

    return commands


def test_runs_on_pull_requests_to_main() -> None:
    """Every pull request against main is checked automatically (FR-008).

    The branch list is read from inside the `pull_request` trigger specifically. Searching the
    whole file would be satisfied by the `push` trigger's identical branch list, and the
    pull-request trigger could be repointed elsewhere without this failing.
    """
    triggers = _triggers(_workflow())

    assert "pull_request" in triggers, "The workflow does not trigger on pull requests."

    branches = (triggers["pull_request"] or {}).get("branches")
    assert branches == ["main"], (
        f"The pull_request trigger targets {branches!r}, not ['main']. "
        "Pull requests against the default branch would go unchecked."
    )


def test_runs_every_check_in_the_contract() -> None:
    """All four checks of contracts/checks.md run in CI as commands, not a subset."""
    scripts = " \n".join(_run_commands(_workflow()))
    checks = {
        "C1 environment install": "uv sync",
        "C2 lint": "ruff check",
        "C3 format": "ruff format --check",
        "C4 tests": "pytest",
    }

    missing = [name for name, command in checks.items() if command not in scripts]

    assert not missing, (
        f"No `run:` step in the workflow executes these checks from contracts/checks.md: "
        f"{missing}. A check that runs only locally is a check that stops running."
    )


def test_install_is_locked() -> None:
    """CI installs from the committed lock file rather than re-resolving (FR-009).

    Without --locked, CI can quietly resolve a different dependency set than a contributor has,
    and a local pass and a CI pass stop meaning the same thing.
    """
    scripts = _run_commands(_workflow())
    syncs = [script for script in scripts if "uv sync" in script]

    assert syncs, "No `run:` step installs the environment with `uv sync`."
    assert all("--locked" in script for script in syncs), (
        f"A `uv sync` step omits --locked: {syncs}. It may re-resolve dependencies instead of "
        "failing when uv.lock disagrees with pyproject.toml."
    )


def test_needs_no_secrets_so_forks_can_run_it() -> None:
    """The workflow reads no secret and asks for no write access (Principle V).

    This is what lets it run unchanged on a pull request from a fork, and it is the property
    most likely to be lost by accident when a later step is added.
    """
    document = _workflow()

    assert "secrets." not in WORKFLOW.read_text(encoding="utf-8"), (
        "The workflow references a repository secret. None of the four checks needs one, "
        "and requiring one stops the workflow running on pull requests from forks."
    )
    assert document.get("permissions") == {"contents": "read"}, (
        f"The workflow declares permissions {document.get('permissions')!r}, "
        "expected {'contents': 'read'}. It only reads the repository; say so rather than "
        "inheriting the default token scope."
    )
