"""Conversation bodies: absent by default, present only when someone asks (User Story 3).

Checks 19-24 of specs/003-logging-telemetry-baseline/contracts/observability.md.

The flag exists so that the safe default is not worked around. Someone chasing a parser defect
needs to see the conversation the parser choked on; without a supported way to get it, the way
they get it is by commenting out the redactor, and then it stays commented out.

What the flag must never do is expose a credential. That is check 22, and it is the assertion that
keeps the escape hatch from becoming the leak.
"""

from __future__ import annotations

import pytest

from hermes_memory.observability import REDACTED, ConversationContent, configure, get_logger
from hermes_memory.observability.redaction import CONTENT_CAP, CONTENT_REDACTED, TRUNCATED_SUFFIX
from hermes_memory.settings import load_settings

from .conftest import Rendered

A_BODY = "the private text of a conversation about a production incident"
A_TOKEN = "ghp_AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"


@pytest.fixture
def content_enabled(complete_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure the process the way an operator chasing a parser defect would."""
    monkeypatch.setenv("HERMES_LOGGING__INCLUDE_CONVERSATION_CONTENT", "true")
    configure(load_settings(env_file=None))


def test_content_is_absent_with_no_configuration_at_all(rendered: Rendered) -> None:
    """Check 19 — nothing is configured here, and that is the point (FR-014).

    The default an operator gets by doing nothing has to be the safe one, because doing nothing is
    what an operator who has never read `.env.example` does.
    """
    get_logger().info("parsed a conversation", body=ConversationContent(A_BODY))

    assert A_BODY not in rendered.text()
    assert rendered.one()["body"] == CONTENT_REDACTED


def test_content_is_absent_with_the_flag_explicitly_off(
    rendered: Rendered, complete_environment: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Check 20 — the configured default agrees with the unconfigured one."""
    monkeypatch.setenv("HERMES_LOGGING__INCLUDE_CONVERSATION_CONTENT", "false")
    configure(load_settings(env_file=None))

    get_logger().info("parsed a conversation", body=ConversationContent(A_BODY))

    assert A_BODY not in rendered.text()


def test_content_appears_when_the_flag_is_on(rendered: Rendered, content_enabled: None) -> None:
    """Check 21 — the escape hatch actually opens, or nobody will use the supported route."""
    get_logger().info("parsed a conversation", body=ConversationContent(A_BODY))

    assert rendered.one()["body"] == A_BODY


def test_a_credential_is_still_withheld_when_content_is_on(
    rendered: Rendered, content_enabled: None
) -> None:
    """Check 22 — the assertion that keeps the escape hatch from becoming the leak (FR-015)."""
    get_logger().info(
        "parsed a conversation",
        body=ConversationContent(A_BODY),
        hindsight_token=A_TOKEN,
    )

    record = rendered.one()

    assert record["body"] == A_BODY
    assert record["hindsight_token"] == REDACTED
    assert A_TOKEN not in rendered.text()


def test_a_credential_inside_the_content_is_still_withheld(
    rendered: Rendered, content_enabled: None
) -> None:
    """The flag consents to conversation text, not to a token that happens to sit in it.

    This is defence in depth rather than a substitute for ARCHITECTURE.md §13's sanitizer: the
    shape roster catches the unmistakable shapes and nothing more.
    """
    get_logger().info(
        "parsed a conversation",
        body=ConversationContent(f"I ran it with {A_TOKEN} and it still failed"),
    )

    body = rendered.one()["body"]

    assert A_TOKEN not in body
    assert "and it still failed" in body


def test_content_beyond_the_cap_is_truncated_and_marked(
    rendered: Rendered, content_enabled: None
) -> None:
    """Check 23 — an enabled flag must not turn a 2 MB conversation into one log line."""
    get_logger().info("parsed a conversation", body=ConversationContent("x" * (CONTENT_CAP * 2)))

    body = rendered.one()["body"]

    assert body.endswith(TRUNCATED_SUFFIX)
    assert len(body) < CONTENT_CAP * 2


def test_content_within_the_cap_is_not_marked(rendered: Rendered, content_enabled: None) -> None:
    """A marker on an untruncated body would make every record look truncated."""
    get_logger().info("parsed a conversation", body=ConversationContent(A_BODY))

    assert not rendered.one()["body"].endswith(TRUNCATED_SUFFIX)


def test_the_wrapper_withholds_the_text_from_its_own_rendering() -> None:
    """Check 24 — the same defence in depth `SecretStr` gives a credential (research.md R8).

    A call site that interpolates a body outside the logging path — into an exception message, a
    print, an f-string — reveals nothing.
    """
    content = ConversationContent(A_BODY)

    assert A_BODY not in repr(content)
    assert A_BODY not in str(content)
    assert A_BODY not in f"{content}"
    assert content.reveal() == A_BODY


def test_the_wrapper_is_immutable() -> None:
    """Nothing may swap the text after a caller handed it over."""
    content = ConversationContent(A_BODY)

    with pytest.raises(AttributeError):
        content._text = "something else"  # type: ignore[misc]
