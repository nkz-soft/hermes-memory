"""The logging settings group (FR-021, data-model.md).

Two values and nothing else: how much to emit, and whether conversation bodies may be emitted at
all. Both carry defaults, so a project with no logging configuration is correctly configured — the
safe default has to be the one you get by doing nothing, because that is what an operator who has
never read this file gets.

The level is validated here rather than at `configure()` time on purpose: a typo in a level name
should stop a run at startup with the variable named, not silently become `INFO` and be discovered
when the log a person needed turns out not to exist.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from hermes_memory.settings import SettingsError, load_settings

LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def test_defaults_need_no_configuration(complete_environment: dict[str, str]) -> None:
    """An environment with no `HERMES_LOGGING__*` at all is valid, and safe (FR-014)."""
    settings = load_settings(env_file=None)

    assert settings.logging.level == "INFO"
    assert settings.logging.include_conversation_content is False


@pytest.mark.parametrize("level", LEVELS)
def test_every_standard_level_is_accepted(
    complete_environment: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    level: str,
) -> None:
    """The closed set of data-model.md, each one, not a sample."""
    monkeypatch.setenv("HERMES_LOGGING__LEVEL", level)

    assert load_settings(env_file=None).logging.level == level


@pytest.mark.parametrize("spelling", ["debug", "Debug", "  warning  "])
def test_the_level_is_matched_case_insensitively(
    complete_environment: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    spelling: str,
) -> None:
    """`debug` is what a person types; rejecting it would be pedantry, not validation."""
    monkeypatch.setenv("HERMES_LOGGING__LEVEL", spelling)

    assert load_settings(env_file=None).logging.level == spelling.strip().upper()


def test_an_unknown_level_fails_at_load_naming_the_variable(
    complete_environment: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Check 28 — a typo stops the run at startup rather than becoming a silent default."""
    monkeypatch.setenv("HERMES_LOGGING__LEVEL", "VERBOSE")

    with pytest.raises(SettingsError) as failure:
        load_settings(env_file=None)

    assert "HERMES_LOGGING__LEVEL" in str(failure.value)


def test_an_empty_level_fails_rather_than_defaulting(
    complete_environment: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty value is an unfinished edit, which is how 002 treats every other setting."""
    monkeypatch.setenv("HERMES_LOGGING__LEVEL", "   ")

    with pytest.raises(SettingsError):
        load_settings(env_file=None)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("true", True), ("false", False), ("1", True), ("0", False), ("yes", True), ("no", False)],
)
def test_the_content_flag_parses_the_usual_spellings(
    complete_environment: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    value: str,
    expected: bool,
) -> None:
    """Whatever an operator types for a boolean, the answer must not be "silently off"."""
    monkeypatch.setenv("HERMES_LOGGING__INCLUDE_CONVERSATION_CONTENT", value)

    assert load_settings(env_file=None).logging.include_conversation_content is expected


def test_a_nonsense_content_flag_fails_rather_than_defaulting_to_off(
    complete_environment: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Failing closed is right for the value; failing *loudly* is right for the typo.

    A value of `maybe` silently read as off would look identical to a redactor that works, and the
    person would conclude the flag is broken. FR-015 keeps credentials safe either way, so this is
    about not wasting an afternoon rather than about a leak.
    """
    monkeypatch.setenv("HERMES_LOGGING__INCLUDE_CONVERSATION_CONTENT", "maybe")

    with pytest.raises(SettingsError) as failure:
        load_settings(env_file=None)

    assert "HERMES_LOGGING__INCLUDE_CONVERSATION_CONTENT" in str(failure.value)


def test_the_group_is_frozen(complete_environment: dict[str, str]) -> None:
    """Configuration is read once and does not change under a running process.

    The same `_Frozen` base every other group uses, asserted rather than assumed: a mutable
    settings group would let one component turn the content flag on for the whole process.
    """
    settings = load_settings(env_file=None)

    with pytest.raises(ValidationError):
        settings.logging.level = "DEBUG"  # type: ignore[misc]
