"""A missing, empty or malformed setting stops the run at startup (US2).

Covers FR-005 and FR-006. The required set is parametrized out of the settings themselves rather
than listed here, so SC-002's "100% of required settings, not a sample" stays true when a setting
is added.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from hermes_memory.settings import (
    SettingsError,
    environment_variable_names,
    load_settings,
)

REQUIRED_VARIABLES = ("HERMES_HINDSIGHT__BASE_URL", "HERMES_LLM__BASE_URL")
"""The settings with no default. Pinned literally because a *test* that derives what it checks
from the thing it checks would pass on a settings object that required nothing at all."""


def test_the_required_set_is_what_the_settings_declare(
    complete_environment: dict[str, str],
) -> None:
    """Every variable in REQUIRED_VARIABLES really is required, and no other one is.

    This is what keeps the parametrized tests below honest: if a default were quietly added to a
    required setting, or removed from a defaulted one, this notices.
    """
    actually_required = set()
    for variable in environment_variable_names():
        environment = {k: v for k, v in complete_environment.items() if k != variable}
        with pytest.MonkeyPatch.context() as patch:
            for name in complete_environment:
                patch.delenv(name, raising=False)
            for name, value in environment.items():
                patch.setenv(name, value)
            try:
                load_settings(env_file=None)
            except SettingsError:
                actually_required.add(variable)

    assert actually_required == set(REQUIRED_VARIABLES)


@pytest.mark.parametrize("variable", REQUIRED_VARIABLES)
def test_a_missing_required_setting_fails_naming_it(
    variable: str, complete_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """One required setting removed; loading fails and says which (FR-005, SC-002)."""
    monkeypatch.delenv(variable)

    with pytest.raises(SettingsError) as failure:
        load_settings(env_file=None)

    assert variable in str(failure.value)


@pytest.mark.parametrize("variable", REQUIRED_VARIABLES)
@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_an_empty_required_setting_fails_like_an_absent_one(
    variable: str,
    blank: str,
    complete_environment: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty credential is not a credential (FR-005, spec edge case)."""
    monkeypatch.setenv(variable, blank)

    with pytest.raises(SettingsError) as failure:
        load_settings(env_file=None)

    assert variable in str(failure.value)


def test_every_missing_setting_is_reported_not_only_the_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fixing configuration one startup failure at a time is the thing to avoid (FR-005)."""
    with pytest.raises(SettingsError) as failure:
        load_settings(env_file=None)

    message = str(failure.value)
    assert all(variable in message for variable in REQUIRED_VARIABLES)
    assert "2 problems" in message


def test_a_missing_group_names_the_leaf_variable_not_the_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`HERMES_HINDSIGHT` is not a variable anyone can set; `..__BASE_URL` is."""
    with pytest.raises(SettingsError) as failure:
        load_settings(env_file=None)

    message = str(failure.value)
    assert "HERMES_HINDSIGHT__BASE_URL" in message
    assert "HERMES_HINDSIGHT:" not in message


@pytest.mark.parametrize("malformed", ["not-a-url", "://missing-scheme", "localhost:8088"])
def test_a_malformed_url_fails_naming_the_setting(
    malformed: str, complete_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A value of the wrong shape fails like a missing one (FR-006)."""
    monkeypatch.setenv("HERMES_HINDSIGHT__BASE_URL", malformed)

    with pytest.raises(SettingsError) as failure:
        load_settings(env_file=None)

    assert "HERMES_HINDSIGHT__BASE_URL" in str(failure.value)


def test_an_empty_bank_id_fails(
    complete_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A defaulted setting set to nothing is an error, not a fallback to the default."""
    monkeypatch.setenv("HERMES_HINDSIGHT__BANK_ID", "   ")

    with pytest.raises(SettingsError) as failure:
        load_settings(env_file=None)

    assert "HERMES_HINDSIGHT__BANK_ID" in str(failure.value)


def test_the_failure_is_settings_error_not_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Callers catch one error type, and it is ours — which is what keeps inputs out of it."""
    with pytest.raises(SettingsError) as failure:
        load_settings(env_file=None)

    assert not isinstance(failure.value, ValidationError)
    assert failure.value.__cause__ is None
    assert failure.value.__context__ is None or not isinstance(
        failure.value.__context__, ValidationError
    )
