"""The contract every secret sanitizer must satisfy (ARCHITECTURE.md §8, row 2).

Rules SS-1 to SS-8 of specs/007-boundary-interfaces/contracts/contract-suites.md.

A generic suite cannot know which strings a given sanitizer recognizes — #11's patterns are #11's.
So the implementation supplies one: `secret_sample` returns a string it must redact and the §13
category it reports for it. The suite then holds it to what §13 requires of any sanitizer: the
value gone, the surrounding words kept, the report counting without quoting.
"""

from __future__ import annotations

import pytest

from hermes_memory.normalization import Conversation, Message, Role, Source
from hermes_memory.sanitization import (
    RedactionCategory,
    RedactionReport,
    SanitizationError,
    SecretSanitizer,
)
from tests.contracts import conversations


class SecretSanitizerContract:
    """Subclass this and implement `make_sanitizer` and `secret_sample`."""

    # --- what a subclass supplies ---------------------------------------------------------------

    def make_sanitizer(self) -> SecretSanitizer:
        raise NotImplementedError

    def secret_sample(self) -> tuple[str, RedactionCategory]:
        """A value this sanitizer must redact, and the category it reports for it."""
        raise NotImplementedError

    def make_failing_sanitizer(self) -> SecretSanitizer | None:
        """Return a sanitizer that cannot rewrite the conversation it is given, or `None`."""
        return None

    # --- helpers ---------------------------------------------------------------------------------

    def _conversation_containing(self, secret: str) -> Conversation:
        return Conversation(
            source=Source.CHATGPT,
            source_id="leaky1",
            title="A failing GitLab call",
            started_at=conversations.STARTED_AT,
            messages=(
                Message(
                    role=Role.ASSISTANT,
                    text=f"GitLab request using token {secret} returned HTTP 401 Unauthorized.",
                    sent_at=conversations.STARTED_AT,
                ),
            ),
        )

    # --- the contract ---------------------------------------------------------------------------

    def test_ss1_the_input_conversation_is_left_alone(self) -> None:
        """Principle V's failure mode is a half-redacted object escaping after an exception."""
        secret, _ = self.secret_sample()
        original = self._conversation_containing(secret)
        before = original.model_copy(deep=True)

        self.make_sanitizer().sanitize(original)

        assert original == before

    def test_ss2_identity_and_message_order_survive(self) -> None:
        secret, _ = self.secret_sample()
        original = self._conversation_containing(secret)

        sanitized, _ = self.make_sanitizer().sanitize(original)

        assert sanitized.source == original.source
        assert sanitized.source_id == original.source_id
        assert sanitized.document_id == original.document_id
        assert len(sanitized.messages) == len(original.messages)
        assert [m.role for m in sanitized.messages] == [m.role for m in original.messages]

    def test_ss3_the_secret_is_gone_from_every_message(self) -> None:
        secret, _ = self.secret_sample()

        sanitized, _ = self.make_sanitizer().sanitize(self._conversation_containing(secret))

        assert all(secret not in message.text for message in sanitized.messages)

    def test_ss4_the_surrounding_context_is_preserved(self) -> None:
        """§13: the context is usually the knowledge worth keeping; dropping the line is wrong."""
        secret, _ = self.secret_sample()
        original = self._conversation_containing(secret)

        sanitized, _ = self.make_sanitizer().sanitize(original)

        assert len(sanitized.messages) == len(original.messages)
        for before, after in zip(original.messages, sanitized.messages, strict=True):
            if before.text:
                assert after.text, "a message that carried text must still carry text"
        assert "401 Unauthorized" in sanitized.messages[0].text

    def test_ss5_the_report_counts_what_was_redacted_by_category(self) -> None:
        secret, category = self.secret_sample()

        _, report = self.make_sanitizer().sanitize(self._conversation_containing(secret))

        assert isinstance(report, RedactionReport)
        assert report.counts.get(category, 0) >= 1
        assert report.total >= 1

    def test_ss6_nothing_to_redact_returns_an_empty_report_not_none(self) -> None:
        clean = conversations.conversation()

        sanitized, report = self.make_sanitizer().sanitize(clean)

        assert report is not None
        assert report.is_empty
        assert sanitized == clean

    def test_ss7_the_report_quotes_neither_the_value_nor_its_position(self) -> None:
        """Principle V — an offset plus the archived original reconstructs the secret (R6)."""
        secret, _ = self.secret_sample()

        _, report = self.make_sanitizer().sanitize(self._conversation_containing(secret))

        rendered = repr(report.model_dump())
        assert secret not in rendered
        assert set(type(report).model_fields) == {"counts"}

    def test_ss8_a_failure_is_raised_rather_than_signalled_by_returning_the_input(self) -> None:
        sanitizer = self.make_failing_sanitizer()
        if sanitizer is None:
            pytest.skip("this implementation cannot be made to fail")
        secret, _ = self.secret_sample()
        original = self._conversation_containing(secret)

        with pytest.raises(SanitizationError) as raised:
            sanitizer.sanitize(original)

        assert raised.value.retryable is False
