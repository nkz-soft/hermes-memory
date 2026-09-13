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
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue

        commented = stripped.startswith("#")
        declaration = _as_declaration(stripped.lstrip("#").strip())

        if declaration is None:
            # Prose in a comment is what most of this file is, and it is fine. An *uncommented*
            # line that is not an assignment is not: skipping what it does not recognise is how a
            # parser misses the thing it exists to find.
            if commented:
                continue
            raise ExampleFileError(
                f"{path} line {number} is neither a comment, a blank, nor NAME=value: {line!r}. "
                "A check that quietly skips a line it cannot read is a check that a committed "
                "credential walks straight past."
            )

        name, value = declaration
        variables[name] = value

    if not variables:
        raise ExampleFileError(
            f"{path} parsed to no variables at all. Either the file is empty or the parser is "
            "wrong — both must fail loudly rather than comparing empty sets."
        )

    return variables


def _as_declaration(text: str) -> tuple[str, str] | None:
    """`NAME=value` split into its halves, or `None` if this is not a declaration at all.

    `export NAME=value` counts. It is live dotenv syntax — `_reject_malformed` in the settings
    module blesses the prefix, and python-dotenv reads such a line as a real assignment — so a
    parser that did not recognise it would skip it, and skipping is how a committed token stays
    invisible with the suite green.
    """
    name, separator, value = text.removeprefix("export ").strip().partition("=")
    name = name.strip()

    if not separator or not name.isupper() or not name.isidentifier():
        return None
    return name, value.strip()


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


def test_an_export_line_cannot_smuggle_a_credential_past_the_check(tmp_path: Path) -> None:
    """`export NAME=value` is live dotenv syntax, so the check must see it.

    `_reject_malformed` in the settings module explicitly blesses the `export ` prefix, and
    python-dotenv reads such a line as a real assignment. A parser here that skipped it would let
    a committed token sit in the file with the whole suite green — and this check is the only
    thing standing between a public repository and that token, because Gitleaks is deferred.
    """
    path = tmp_path / ".env.example"
    path.write_text(
        "HERMES_HINDSIGHT__TOKEN=\nexport HERMES_HINDSIGHT__TOKEN=sk-a-real-looking-token\n",
        encoding="utf-8",
    )

    assert parse_example(path)["HERMES_HINDSIGHT__TOKEN"] == "sk-a-real-looking-token"


def test_a_line_the_parser_cannot_classify_fails_rather_than_being_skipped(
    tmp_path: Path,
) -> None:
    """Everywhere else in this feature an unreadable line is a failure; here too.

    Silently skipping is the wrong default for a check whose job is to notice what is in a file.
    """
    path = tmp_path / ".env.example"
    path.write_text(
        "HERMES_HINDSIGHT__TOKEN=\nnot a variable assignment at all\n", encoding="utf-8"
    )

    with pytest.raises(ExampleFileError):
        parse_example(path)
