"""The conversation-level rewrite: every text-bearing field, and nothing else.

Rules RR-3 and RR-4 of specs/009-secret-sanitizer/contracts/redaction-rules.md. The failure this
file is written against is the one that passes every string-level test: a sanitizer that rewrites
message text and leaves the title — which travels to the memory store as provenance — or the tool
result, which is §13's own example.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from hermes_memory.normalization import (
    Conversation,
    Message,
    NonTextKind,
    NonTextPart,
    Role,
    Source,
    ToolActivity,
)
from hermes_memory.sanitization import PatternSecretSanitizer, RedactionCategory
from hermes_memory.sanitization.scanner import REDACTED
from tests.synthetic.secrets import CONTRACT_SAMPLE

STARTED_AT = datetime(2026, 3, 4, 9, 30, tzinfo=UTC)
SECRET = CONTRACT_SAMPLE.value


def conversation_with_the_secret_everywhere() -> Conversation:
    return Conversation(
        source=Source.CHATGPT,
        source_id="leaky1",
        title=f"Why does token {SECRET} return 401?",
        started_at=STARTED_AT,
        last_activity_at=STARTED_AT,
        messages=(
            Message(role=Role.USER, text="What is wrong with this call?", sent_at=STARTED_AT),
            Message(
                role=Role.ASSISTANT,
                text=f"GitLab request using token {SECRET} returned HTTP 401 Unauthorized.",
                sent_at=STARTED_AT,
                tool_activity=(
                    ToolActivity(
                        name=f"http-{SECRET}",
                        request=f"GET /api/v4/projects PRIVATE-TOKEN: {SECRET}",
                        result=f"401 Unauthorized for token {SECRET}",
                    ),
                ),
                non_text_parts=(NonTextPart(kind=NonTextKind.FILE, name=f"{SECRET}.env"),),
            ),
        ),
    )


@pytest.fixture
def sanitizer() -> PatternSecretSanitizer:
    return PatternSecretSanitizer()


def test_the_secret_is_gone_from_every_field_that_can_carry_text(
    sanitizer: PatternSecretSanitizer,
) -> None:
    """RR-3. Asserted field by field, so a failure names the field that leaked."""
    sanitized, _ = sanitizer.sanitize(conversation_with_the_secret_everywhere())
    message = sanitized.messages[1]

    assert SECRET not in (sanitized.title or "")
    assert SECRET not in message.text
    assert SECRET not in message.tool_activity[0].name
    assert SECRET not in (message.tool_activity[0].request or "")
    assert SECRET not in (message.tool_activity[0].result or "")
    assert SECRET not in (message.non_text_parts[0].name or "")


def test_identity_is_copied_rather_than_scanned(sanitizer: PatternSecretSanitizer) -> None:
    """RR-4: a pattern that could reach `source_id` could move `document_id` (Principle II)."""
    original = conversation_with_the_secret_everywhere()

    sanitized, _ = sanitizer.sanitize(original)

    assert sanitized.source == original.source
    assert sanitized.source_id == original.source_id
    assert sanitized.document_id == original.document_id
    assert sanitized.started_at == original.started_at
    assert sanitized.last_activity_at == original.last_activity_at
    assert [m.role for m in sanitized.messages] == [m.role for m in original.messages]
    assert [m.sent_at for m in sanitized.messages] == [m.sent_at for m in original.messages]
    assert sanitized.messages[1].non_text_parts[0].kind is NonTextKind.FILE


def test_a_credential_shaped_source_id_is_left_alone(sanitizer: PatternSecretSanitizer) -> None:
    """The deliberate trade of research R1, asserted so that it cannot be reversed by accident."""
    original = Conversation(
        source=Source.CHATGPT,
        source_id=SECRET,
        started_at=STARTED_AT,
        messages=(Message(role=Role.USER, text="hello", sent_at=STARTED_AT),),
    )

    sanitized, report = sanitizer.sanitize(original)

    assert sanitized.source_id == SECRET
    assert sanitized.document_id == original.document_id
    assert report.is_empty


def test_the_input_is_not_mutated(sanitizer: PatternSecretSanitizer) -> None:
    """SS-1: the failure mode Principle V is written against is a half-redacted object escaping."""
    original = conversation_with_the_secret_everywhere()
    before = original.model_copy(deep=True)

    sanitizer.sanitize(original)

    assert original == before


def test_an_absent_field_stays_absent(sanitizer: PatternSecretSanitizer) -> None:
    """A sanitizer does not invent an empty string where the source had nothing."""
    original = Conversation(
        source=Source.CHATGPT,
        source_id="plain1",
        title=None,
        started_at=STARTED_AT,
        messages=(
            Message(
                role=Role.ASSISTANT,
                text=f"token {SECRET}",
                sent_at=STARTED_AT,
                tool_activity=(ToolActivity(name="http", request=None, result=None),),
                non_text_parts=(NonTextPart(kind=NonTextKind.IMAGE, name=None),),
            ),
        ),
    )

    sanitized, _ = sanitizer.sanitize(original)

    assert sanitized.title is None
    assert sanitized.messages[0].tool_activity[0].request is None
    assert sanitized.messages[0].tool_activity[0].result is None
    assert sanitized.messages[0].non_text_parts[0].name is None


def test_a_message_that_was_only_a_secret_keeps_its_place(
    sanitizer: PatternSecretSanitizer,
) -> None:
    """The order is the conversation (#8); an emptied turn is still a turn."""
    original = Conversation(
        source=Source.CHATGPT,
        source_id="only1",
        started_at=STARTED_AT,
        messages=(
            Message(role=Role.USER, text="here it is", sent_at=STARTED_AT),
            Message(role=Role.ASSISTANT, text=SECRET, sent_at=STARTED_AT),
            Message(role=Role.USER, text="thanks", sent_at=STARTED_AT),
        ),
    )

    sanitized, _ = sanitizer.sanitize(original)

    assert len(sanitized.messages) == 3
    assert sanitized.messages[1].text == REDACTED
    assert sanitized.messages[2].text == "thanks"


def test_a_clean_conversation_comes_back_equal(sanitizer: PatternSecretSanitizer) -> None:
    """SS-6: nothing to redact is an ordinary answer, not a special case."""
    original = Conversation(
        source=Source.CHATGPT,
        source_id="clean1",
        title="Wolverine saga error handling",
        started_at=STARTED_AT,
        messages=(
            Message(
                role=Role.ASSISTANT,
                text="We moved the saga to Wolverine in March.",
                sent_at=STARTED_AT,
            ),
        ),
    )

    sanitized, report = sanitizer.sanitize(original)

    assert sanitized == original
    assert report.is_empty


def test_the_report_counts_every_field_it_redacted_in(
    sanitizer: PatternSecretSanitizer,
) -> None:
    """Five occurrences across five fields, plus the message text: the report is of the whole."""
    _, report = sanitizer.sanitize(conversation_with_the_secret_everywhere())

    assert report.counts[RedactionCategory.GITLAB_TOKEN] == 6
    assert report.total == 6


def test_redact_text_is_the_one_string_case(sanitizer: PatternSecretSanitizer) -> None:
    """The convenience on the implementation, not part of the boundary (data-model.md)."""
    redacted, report = sanitizer.redact_text(f"token {SECRET} expired")

    assert redacted == f"token {REDACTED} expired"
    assert report.counts == {RedactionCategory.GITLAB_TOKEN: 1}
