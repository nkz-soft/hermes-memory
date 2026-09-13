"""Repository-level invariants of the configuration boundary.

Two claims that are about the repository rather than about the settings object, and that would
each go quietly untrue: version control must ignore a filled-in `.env` and track `.env.example`
(FR-011), and nothing outside the settings module may read the environment (FR-001, SC-008).

Both are asserted against the committed tree — `git` is asked what it does rather than
`.gitignore` being read for what it appears to say, and the sources are parsed rather than
grepped.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = REPO_ROOT / "src" / "hermes_memory"
SETTINGS_MODULE = PACKAGE_ROOT / "settings.py"

ENVIRONMENT_READERS = {"getenv", "environ", "environb"}
"""Names through which a module could reach the process environment."""


def _git(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_local_env_file_is_ignored() -> None:
    """FR-011 — the file an operator fills in with real credentials is never committable.

    Asked of git rather than read out of `.gitignore`, because a later negation pattern could
    un-ignore it while the line this would have matched still sits in the file.
    """
    result = _git("check-ignore", "-q", ".env")

    assert result.returncode == 0, (
        "git does not ignore .env. That file holds real credentials, and this repository is public."
    )


def test_the_example_file_is_tracked() -> None:
    """FR-011 — the credential-free roster is committed, and stays committed."""
    result = _git("ls-files", "--error-unmatch", ".env.example")

    assert result.returncode == 0, (
        ".env.example is not tracked by git. It is the only configuration documentation an "
        "operator has."
    )


def test_no_env_file_was_committed_by_accident() -> None:
    """The inverse of the above, and the one that would matter most if it ever failed."""
    tracked = _git("ls-files", ".env", ".env.*").stdout.split()
    unexpected = [name for name in tracked if name != ".env.example"]

    assert not unexpected, (
        f"These environment files are tracked by git: {unexpected}. If any holds a real "
        "credential, treat it as leaked and rotate it."
    )


def _environment_readers(source: Path) -> list[str]:
    """Every reference in a module that reaches the process environment.

    Parsed rather than grepped: a comment mentioning `os.environ`, or the string in an error
    message, is not a read, and a check that cannot tell the difference is one people learn to
    work around.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"))
    found: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in ENVIRONMENT_READERS:
            found.append(f"{ast.unparse(node)} (line {node.lineno})")
        elif isinstance(node, ast.ImportFrom) and node.module == "os":
            found.extend(
                f"from os import {alias.name} (line {node.lineno})"
                for alias in node.names
                if alias.name in ENVIRONMENT_READERS
            )

    return found


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(path, id=path.relative_to(PACKAGE_ROOT).as_posix())
        for path in sorted(PACKAGE_ROOT.rglob("*.py"))
        if path != SETTINGS_MODULE
    ],
)
def test_no_module_outside_settings_reads_the_environment(source: Path) -> None:
    """FR-001, SC-008 — one source of configuration, enforced rather than agreed.

    The moment a second module reads `os.environ`, the settings object stops being the single
    place a value comes from, and `.env.example` stops describing what the project reads — which
    is the drift this whole feature exists to prevent.
    """
    readers = _environment_readers(source)

    assert not readers, (
        f"{source.relative_to(REPO_ROOT).as_posix()} reads the environment: {readers}. "
        "Configuration comes from hermes_memory.settings, and from nowhere else."
    )


def test_the_invariant_check_would_catch_a_violation(tmp_path: Path) -> None:
    """The parametrized check above passes on a tree with nothing in it — prove it can fail."""
    offender = tmp_path / "offender.py"
    offender.write_text(
        '"""A module that helps itself to the environment."""\n'
        "import os\n\n"
        "VALUE = os.environ['HERMES_HINDSIGHT__TOKEN']\n",
        encoding="utf-8",
    )

    assert _environment_readers(offender)


def test_a_comment_is_not_a_read(tmp_path: Path) -> None:
    """And prove it does not fire on text that merely mentions the environment."""
    innocent = tmp_path / "innocent.py"
    innocent.write_text(
        '"""Reads nothing. Configuration comes from os.environ via the settings module."""\n'
        "MESSAGE = 'set os.environ yourself and this will not notice'\n",
        encoding="utf-8",
    )

    assert not _environment_readers(innocent)


def test_the_settings_module_is_the_one_that_does_read_it() -> None:
    """The exemption above is not vacuous — the settings module really is the reader.

    If this ever fails, either the loading moved somewhere else or `pydantic-settings` stopped
    being what reads the environment. Both are worth noticing.
    """
    assert SETTINGS_MODULE.exists()
    assert "pydantic_settings" in SETTINGS_MODULE.read_text(encoding="utf-8")
