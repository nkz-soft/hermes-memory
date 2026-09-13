"""The README still documents the commands a first-time contributor needs (FR-010).

Verified by hand on a clean clone, which is the real proof — but a README drifts silently, and
"the setup command is written down somewhere" is exactly the kind of claim that stops being true
without anyone noticing. These assertions keep the documented commands and
`specs/001-project-skeleton/contracts/checks.md` from parting company.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
README = REPO_ROOT / "README.md"


def test_readme_documents_setup_test_and_lint_commands() -> None:
    """The three commands of FR-010 appear in the README, verbatim."""
    text = README.read_text(encoding="utf-8")
    commands = {
        "setup (C1)": "uv sync",
        "tests (C4)": "uv run pytest",
        "lint (C2)": "uv run ruff check .",
        "format (C3)": "uv run ruff format --check .",
    }

    missing = [name for name, command in commands.items() if command not in text]

    assert not missing, (
        f"README.md no longer documents: {missing}. A first-time contributor reads the README; "
        "a command that is only in contracts/checks.md is a command nobody runs."
    )


def test_readme_states_the_required_python_version() -> None:
    """The runtime the project pins is stated where someone will look for it."""
    text = README.read_text(encoding="utf-8")

    assert "3.13" in text, (
        "README.md does not name the required Python version. The pin lives in "
        ".python-version, but a contributor should not have to find it there."
    )
