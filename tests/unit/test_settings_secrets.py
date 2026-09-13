"""A credential's value is absent from every rendering a program produces by default (US3).

FR-007 names four surfaces and SC-003 wants the value in none of them. The fourth — the text of a
load failure — is the one research.md R3 could not settle from documentation, and it is the one
that was not covered for free: a raw Pydantic `ValidationError` renders `input_value=...` into its
own message, so a credential of the wrong shape is echoed by the validation machinery itself. That
is why `load_settings` raises `SettingsError` built from the field location and message only, and
why it raises it outside the `except` block so the original does not survive on `__context__`.

These tests are the regression for both halves. `SecretStr` covers the first three; the fourth is
ours, and would break silently without this file.
"""

from __future__ import annotations

import json

import pytest
from pydantic import SecretStr

from hermes_memory.settings import (
    HindsightSettings,
    LlmSettings,
    Settings,
    SettingsError,
    load_settings,
)

HINDSIGHT_TOKEN = "hindsight-token-value"
LLM_KEY = "llm-key-value"


@pytest.fixture
def settings(complete_environment: dict[str, str]) -> Settings:
    return load_settings(env_file=None)


def _renderings(settings: Settings) -> dict[str, str]:
    """Every way a program renders an object without being asked to reveal anything."""
    return {
        "repr(settings)": repr(settings),
        "str(settings)": str(settings),
        "format(settings)": f"{settings}",
        "repr(settings.hindsight)": repr(settings.hindsight),
        "str(settings.hindsight)": str(settings.hindsight),
        "repr(field)": repr(settings.hindsight.token),
        "str(field)": str(settings.hindsight.token),
        "model_dump()": repr(settings.model_dump()),
        "model_dump_json()": settings.model_dump_json(),
        "json.dumps(model_dump(mode='json'))": json.dumps(settings.model_dump(mode="json")),
    }


@pytest.mark.parametrize("secret", [HINDSIGHT_TOKEN, LLM_KEY])
def test_no_default_rendering_contains_a_secret(settings: Settings, secret: str) -> None:
    """FR-007, SC-003 — surfaces one to three."""
    leaked = [name for name, text in _renderings(settings).items() if secret in text]

    assert not leaked, (
        f"The credential appears in: {leaked}. A value that renders itself is a value that ends "
        "up in a log, and this corpus is private engineering history."
    )


def test_a_load_failure_does_not_contain_the_offending_secret(
    complete_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-007, SC-003 — surface four, the one that is not free.

    A secret is supplied alongside a fault elsewhere, so the load fails while the credential is in
    hand. Neither the message nor the exception chain may carry it.
    """
    monkeypatch.setenv("HERMES_HINDSIGHT__TOKEN", HINDSIGHT_TOKEN)
    monkeypatch.setenv("HERMES_HINDSIGHT__BASE_URL", "not-a-url")

    with pytest.raises(SettingsError) as failure:
        load_settings(env_file=None)

    rendered = "\n".join(
        str(part) for part in (failure.value, failure.value.__cause__, failure.value.__context__)
    )

    assert HINDSIGHT_TOKEN not in rendered
    assert "HERMES_HINDSIGHT__BASE_URL" in str(failure.value)


def test_a_secret_of_the_wrong_shape_is_not_echoed(
    complete_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The credential itself is the invalid value — the worst case for an echoing error."""
    monkeypatch.setenv("HERMES_HINDSIGHT__BANK_ID", "")
    monkeypatch.setenv("HERMES_HINDSIGHT__TOKEN", HINDSIGHT_TOKEN)

    with pytest.raises(SettingsError) as failure:
        load_settings(env_file=None)

    assert HINDSIGHT_TOKEN not in str(failure.value)


def test_the_exception_chain_is_severed(
    complete_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """No `__cause__`, no `__context__` — nothing for a traceback renderer to walk into.

    `raise ... from None` is not enough: it clears `__cause__` and leaves `__context__`, which a
    logger configured to render the chain will happily print.
    """
    monkeypatch.setenv("HERMES_HINDSIGHT__BASE_URL", "not-a-url")

    with pytest.raises(SettingsError) as failure:
        load_settings(env_file=None)

    assert failure.value.__cause__ is None
    assert failure.value.__context__ is None


def test_the_secret_is_obtainable_on_purpose(settings: Settings) -> None:
    """FR-008 — the protection guards accidents, not intended use (US3 scenario 5)."""
    assert settings.hindsight.token is not None
    assert settings.hindsight.token.get_secret_value() == HINDSIGHT_TOKEN
    assert settings.llm.api_key is not None
    assert settings.llm.api_key.get_secret_value() == LLM_KEY


def test_every_credential_field_is_secret_typed() -> None:
    """The guarantee is a property of the type, not of remembering to apply it.

    Named fields, so adding a credential as a plain `str` fails here rather than being noticed in
    a log six months later.
    """
    assert HindsightSettings.model_fields["token"].annotation == SecretStr | None
    assert LlmSettings.model_fields["api_key"].annotation == SecretStr | None


def test_model_dump_json_is_safe_by_default(settings: Settings) -> None:
    """Serialization is the surface a future HTTP or logging feature reaches for first."""
    payload = json.loads(settings.model_dump_json())

    assert payload["hindsight"]["token"] == "**********"
    assert payload["llm"]["api_key"] == "**********"


def test_a_validator_message_cannot_carry_the_value_into_the_failure(
    complete_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`_describe` renders pydantic's `msg`, and a `ValueError` from a validator lands in it.

    Nothing raises `ValueError` on a secret field today, so this locks in the property rather than
    the current accident: the day someone adds `raise ValueError(f"bad token: {value}")`, the
    credential would flow into the message that the rest of this file works to keep it out of.
    """
    from pydantic import ValidationError, field_validator

    from hermes_memory.settings import Settings, _describe

    class Leaky(Settings):
        @field_validator("archive_root", mode="before")
        @classmethod
        def _shout_the_value(cls, value: object) -> object:
            raise ValueError(f"refusing {HINDSIGHT_TOKEN}")

    monkeypatch.setenv("HERMES_ARCHIVE_ROOT", "anything")

    try:
        Leaky(_env_file=None)  # type: ignore[call-arg]
    except ValidationError as error:
        rendered = _describe(error)
    else:  # pragma: no cover - the validator always raises
        raise AssertionError("expected the scratch validator to fail validation")

    assert HINDSIGHT_TOKEN not in rendered, (
        "A validator's own message reached the rendered failure. `_describe` must not pass "
        "`msg` through unfiltered when a validator can interpolate a value into it."
    )
