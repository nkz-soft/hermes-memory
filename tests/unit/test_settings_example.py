"""`.env.example` and the settings object name the same variables (US4).

Neither side is a re-typed list. The expected names come from the settings class itself and the
actual names are parsed out of the file, so this proves the two agree rather than proving that two
copies of one list match each other — the same reasoning that has
`tests/structure/test_module_layout.py` parse the constitution instead of quoting it
(specs/002-environment-configuration/research.md R5).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_memory.settings import (
    PROJECT_ROOT,
    environment_variable_names,
    secret_variable_names,
)

EXAMPLE_FILE = PROJECT_ROOT / ".env.example"


class ExampleFileError(AssertionError):
    """The example file could not be located or read.

    Deliberately an `AssertionError`: a file the parser cannot read must fail the suite, never let
    it pass by comparing two empty sets. A check that cannot find what it checks against is worse
    than no check.
    """


def parse_example(path: Path = EXAMPLE_FILE) -> dict[str, str]:
    """Variable names to assigned values, including the ones commented out.

    A defaulted setting is documented as `#HERMES_ARCHIVE_ROOT=` so an operator can see it exists
    without being asked to set it. Those count as declared: FR-009 wants every setting listed, not
    every setting mandatory.
    """
    if not path.exists():
        raise ExampleFileError(f"The example environment file is missing at {path}.")

    variables: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip().lstrip("#").strip()
        if "=" not in stripped:
            continue
        name, _, value = stripped.partition("=")
        name = name.strip()
        if name.isupper() and name.isidentifier():
            variables[name] = value.strip()

    if not variables:
        raise ExampleFileError(
            f"{path} parsed to no variables at all. Either the file is empty or the parser is "
            "wrong — both must fail loudly rather than comparing empty sets."
        )

    return variables


def test_the_parser_fails_loudly_on_an_unreadable_record(tmp_path: Path) -> None:
    """The failure mode that matters: an empty parse would make every check below vacuous."""
    with pytest.raises(ExampleFileError):
        parse_example(tmp_path / "gone")

    empty = tmp_path / "empty"
    empty.write_text("# only a comment\n", encoding="utf-8")
    with pytest.raises(ExampleFileError):
        parse_example(empty)


def test_every_declared_setting_appears_in_the_example_file() -> None:
    """FR-010, SC-004 — an operator configuring from this file misses nothing."""
    missing = sorted(environment_variable_names() - set(parse_example()))

    assert not missing, (
        f"Declared by the settings but absent from .env.example: {missing}. An operator "
        "configuring from that file would still get a startup failure."
    )


def test_the_example_file_names_nothing_the_project_does_not_read() -> None:
    """FR-010, SC-004 — the other direction, which is what catches a removed setting."""
    surplus = sorted(set(parse_example()) - environment_variable_names())

    assert not surplus, (
        f"Named in .env.example but read by nothing: {surplus}. Either the setting was removed "
        "and the file was not, or the name is a typo that will never take effect."
    )


def test_no_secret_in_the_example_file_carries_a_usable_value() -> None:
    """SC-006 — this file is committed to a public repository.

    Every credential variable must be present but unassigned. A placeholder that looks like a real
    token is how a fake secret becomes a real one after somebody edits the wrong copy.
    """
    example = parse_example()
    filled = {name: value for name in secret_variable_names() if (value := example.get(name, ""))}

    assert not filled, (
        f"These credential variables carry a value in .env.example: {sorted(filled)}. "
        "The file holds names and explanations only."
    )


def test_the_required_settings_are_not_commented_out() -> None:
    """A required setting shown as `#NAME=` reads as optional, and the operator skips it."""
    text = EXAMPLE_FILE.read_text(encoding="utf-8")
    required = ("HERMES_HINDSIGHT__BASE_URL", "HERMES_LLM__BASE_URL")

    commented = [name for name in required if f"#{name}" in text]

    assert not commented, (
        f"These required settings are commented out in .env.example: {commented}. "
        "A required setting must read as required."
    )
