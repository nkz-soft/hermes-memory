"""Settings arrive from the environment and from an optional untracked `.env` (US1).

Covers the precedence and source rows of specs/002-environment-configuration/contracts/settings.md:
FR-003 (two sources), FR-004 (the environment wins) and the edge cases around a `.env` that is
absent, unreadable or malformed.

Every test passes `env_file=` explicitly. Letting the default apply would make the result depend on
whether the developer running the suite happens to have a `.env` in their checkout.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from hermes_memory.settings import Settings, SettingsError, load_settings

COMPLETE_ENV_FILE = """\
HERMES_HINDSIGHT__BASE_URL=http://from-file:8088
HERMES_LLM__BASE_URL=http://from-file:4000/v1
"""


def test_loads_from_the_environment_alone(complete_environment: dict[str, str]) -> None:
    """Every required value in the environment, no file at all (FR-003)."""
    settings = load_settings(env_file=None)

    assert str(settings.hindsight.base_url).rstrip("/") == "http://localhost:8088"
    assert str(settings.llm.base_url).rstrip("/") == "http://localhost:4000/v1"
    assert settings.hindsight.token is not None
    assert settings.hindsight.token.get_secret_value() == "hindsight-token-value"
    assert settings.llm.api_key is not None
    assert settings.llm.api_key.get_secret_value() == "llm-key-value"


def test_loads_from_an_env_file_alone(env_file) -> None:
    """Nothing in the environment, everything in the file (FR-003, US1 scenario 2)."""
    settings = load_settings(env_file=env_file(COMPLETE_ENV_FILE))

    assert str(settings.hindsight.base_url).rstrip("/") == "http://from-file:8088"
    assert str(settings.llm.base_url).rstrip("/") == "http://from-file:4000/v1"


def test_the_environment_beats_the_env_file(complete_environment: dict[str, str], env_file) -> None:
    """A one-off override must not require editing a file (FR-004, US1 scenario 3)."""
    settings = load_settings(env_file=env_file(COMPLETE_ENV_FILE))

    assert str(settings.hindsight.base_url).rstrip("/") == "http://localhost:8088"


def test_the_env_file_beats_a_default(env_file) -> None:
    """A defaulted setting is still settable from the file (FR-003)."""
    contents = COMPLETE_ENV_FILE + "HERMES_HINDSIGHT__BANK_ID=scratch\n"

    assert load_settings(env_file=env_file(contents)).hindsight.bank_id == "scratch"


def test_a_missing_env_file_is_normal(complete_environment: dict[str, str], tmp_path) -> None:
    """The file is optional, not a prerequisite (FR-003, US1 scenario 4)."""
    settings = load_settings(env_file=tmp_path / "nothing-here")

    assert str(settings.hindsight.base_url).rstrip("/") == "http://localhost:8088"


def test_a_malformed_env_file_fails_loudly(complete_environment: dict[str, str], env_file) -> None:
    """A typo in the file must not be indistinguishable from the file being absent.

    The dotenv parser underneath is lenient and skips a line it cannot read, which would let
    ``HERMES_HINDSIGHT__BANK_ID scratch`` — a missing equals sign — silently do nothing.
    """
    contents = COMPLETE_ENV_FILE + "HERMES_HINDSIGHT__BANK_ID scratch\n"

    with pytest.raises(SettingsError) as failure:
        load_settings(env_file=env_file(contents))

    assert "HERMES_HINDSIGHT__BANK_ID scratch" in str(failure.value)


def test_comments_and_blank_lines_in_the_env_file_are_fine(env_file) -> None:
    """Being strict about malformed lines must not make ordinary files malformed."""
    contents = "# a comment\n\n" + COMPLETE_ENV_FILE + "\n   \n# another\n"

    assert load_settings(env_file=env_file(contents)).hindsight.bank_id == "engineering-global"


def test_unrelated_environment_variables_are_ignored(
    complete_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """An environment shared with other tools must not break this one (US2 scenario 5)."""
    monkeypatch.setenv("PATH_TO_SOMETHING_ELSE", "whatever")
    monkeypatch.setenv("HERMES_SOMETHING_WE_DO_NOT_READ", "whatever")

    assert load_settings(env_file=None).hindsight.bank_id == "engineering-global"


def test_defaults_are_the_recorded_ones(complete_environment: dict[str, str]) -> None:
    """The bank id defaults to the single shared bank ADR-002 fixes (research.md R6)."""
    settings = load_settings(env_file=None)

    assert settings.hindsight.bank_id == "engineering-global"
    assert settings.archive_root.name == "archive"
    assert settings.import_state_path.name == "import-state.db"


def test_an_unset_secret_is_none_not_an_empty_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty credential is not a credential — it is an absent one (spec edge case)."""
    monkeypatch.setenv("HERMES_HINDSIGHT__BASE_URL", "http://localhost:8088")
    monkeypatch.setenv("HERMES_LLM__BASE_URL", "http://localhost:4000/v1")
    monkeypatch.setenv("HERMES_HINDSIGHT__TOKEN", "   ")

    settings = load_settings(env_file=None)

    assert settings.hindsight.token is None
    assert settings.llm.api_key is None


def test_the_loaded_object_is_immutable(complete_environment: dict[str, str]) -> None:
    """A run is configured once (contracts/settings.md → what consumers must not do)."""
    settings = load_settings(env_file=None)

    with pytest.raises(ValidationError):
        settings.hindsight.bank_id = "changed"  # type: ignore[misc]


def test_load_settings_returns_a_settings_object(complete_environment: dict[str, str]) -> None:
    """The entry point returns the whole validated object, never a partial one."""
    assert isinstance(load_settings(env_file=None), Settings)
