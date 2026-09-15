"""Serialization and re-parsing: what the raw archive of ARCHITECTURE.md §14 depends on.

Principle I makes the archive the source of truth and requires ingestion to be re-runnable from it
alone — after the parser, the sanitizer, the extraction policy or Hindsight itself has changed. The
normalized form written there must therefore come back out as exactly what went in.

The failure this guards against is quiet. A serialization that loses a message timestamp still
parses, and still replays — wrongly, years later, with no record of what was lost. So the
round-trip is asserted as equality *and* as an equal content hash, and a malformed record is
asserted to raise rather than to yield a partial object.

Some of these hold because Pydantic supplies them rather than because this module implements them.
They are pinned anyway: what the module owes its callers is the guarantee, and a guarantee nobody
tests is a property of the current dependency rather than of this boundary.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from hermes_memory.normalization import (
    Conversation,
    EnrichedConversation,
    Message,
    NonTextKind,
    NonTextPart,
    ProjectTag,
    Provenance,
    Role,
    Source,
    SourceTag,
    ToolActivity,
    UserTag,
)

STARTED = datetime(2026, 1, 1, 9, tzinfo=UTC)
IMPORTED = datetime(2026, 9, 14, 10, tzinfo=UTC)


def an_exhaustive_conversation() -> Conversation:
    """A conversation exercising every field the model defines.

    Including the awkward ones: a message with no timestamp, one with no text, an empty title, a
    tool call with no result, a non-text part, a non-ASCII body and a non-UTC offset. A round-trip
    test over a conversation that uses only the easy fields proves nothing about the others.
    """
    return Conversation(
        source=Source.CHATGPT,
        source_id="conversation-id",
        title="",
        started_at=STARTED,
        last_activity_at=datetime(2026, 1, 1, 15, tzinfo=timezone(timedelta(hours=3))),
        messages=(
            Message(role=Role.SYSTEM, text="You are a helpful assistant.", sent_at=STARTED),
            # Non-ASCII on purpose: this corpus is Russian-language engineering history, and a
            # round trip that only ever sees ASCII proves nothing about the one that matters.
            Message(role=Role.USER, text="почему retain падает — 413?"),
            Message(
                role=Role.ASSISTANT,
                text="",
                sent_at=STARTED + timedelta(minutes=2),
                tool_activity=(
                    ToolActivity(name="web.search", request="hindsight retain 413"),
                    ToolActivity(name="repo.read", request="ARCHITECTURE.md", result="§9"),
                ),
                non_text_parts=(
                    NonTextPart(kind=NonTextKind.IMAGE, name="screenshot.png"),
                    NonTextPart(kind=NonTextKind.OTHER),
                ),
            ),
            Message(role=Role.TOOL, text="HTTP 413 Payload Too Large"),
        ),
    )


def an_exhaustive_enriched_conversation() -> EnrichedConversation:
    return EnrichedConversation(
        conversation=an_exhaustive_conversation(),
        provenance=Provenance(
            source=Source.CHATGPT,
            source_id="conversation-id",
            project="miratorg",
            repository="nkz-soft/hermes-memory",
            title="Wolverine Saga Error Handling",
            imported_at=IMPORTED,
            importer_version="1",
        ),
        tags=(SourceTag(value=Source.CHATGPT), ProjectTag(value="miratorg"), UserTag(value="nkz")),
    )


# --- the round trip ----------------------------------------------------------------------------


def test_a_conversation_survives_a_round_trip_unchanged() -> None:
    """FR-014, SC-002. Equality over every field, including the ones that may be absent."""
    original = an_exhaustive_conversation()

    assert Conversation.model_validate_json(original.model_dump_json()) == original


def test_a_round_tripped_conversation_hashes_the_same() -> None:
    """The half that matters to §17: a replay from the archive must skip, not re-extract."""
    original = an_exhaustive_conversation()
    restored = Conversation.model_validate_json(original.model_dump_json())

    assert restored.content_hash() == original.content_hash()
    assert restored.document_id == original.document_id


def test_an_absent_message_time_does_not_become_a_present_one() -> None:
    """The quiet failure this test exists for: a missing time filled in on the way back."""
    original = an_exhaustive_conversation()
    restored = Conversation.model_validate_json(original.model_dump_json())

    assert [message.sent_at for message in restored.messages] == [
        message.sent_at for message in original.messages
    ]
    assert restored.messages[1].sent_at is None


def test_a_utc_offset_survives_the_round_trip() -> None:
    """Equality alone cannot see this: aware datetimes compare by instant, so a value silently
    converted to UTC on the way out would still satisfy every assertion above."""
    original = an_exhaustive_conversation()
    restored = Conversation.model_validate_json(original.model_dump_json())

    assert restored.last_activity_at is not None
    assert restored.last_activity_at.utcoffset() == timedelta(hours=3)


def test_the_message_order_survives_the_round_trip() -> None:
    original = an_exhaustive_conversation()
    restored = Conversation.model_validate_json(original.model_dump_json())

    assert [message.role for message in restored.messages] == [
        Role.SYSTEM,
        Role.USER,
        Role.ASSISTANT,
        Role.TOOL,
    ]


def test_an_empty_title_does_not_become_an_absent_one() -> None:
    """Both are "no title" to the hash, and they must still not be silently interchanged."""
    original = an_exhaustive_conversation()

    assert Conversation.model_validate_json(original.model_dump_json()).title == ""


def test_provenance_survives_a_round_trip_unchanged() -> None:
    original = an_exhaustive_enriched_conversation().provenance

    assert Provenance.model_validate_json(original.model_dump_json()) == original


def test_an_enriched_conversation_survives_a_round_trip_unchanged() -> None:
    """The whole of what the archive persists, including the tags and their namespaces."""
    original = an_exhaustive_enriched_conversation()
    restored = EnrichedConversation.model_validate_json(original.model_dump_json())

    assert restored == original
    assert [str(tag) for tag in restored.tags] == [
        "source:chatgpt",
        "project:miratorg",
        "user:nkz",
    ]


def test_a_round_trip_through_python_objects_is_also_lossless() -> None:
    """`model_dump` / `model_validate`, for an archive that stores structure rather than text."""
    original = an_exhaustive_conversation()

    assert Conversation.model_validate(original.model_dump()) == original


# --- what a malformed record does --------------------------------------------------------------


@pytest.mark.parametrize(
    ("record", "named"),
    [
        pytest.param(
            '{"source": "chatgpt", "source_id": "x"}',
            "started_at",
            id="a missing required field",
        ),
        pytest.param(
            '{"source": "gpt", "source_id": "x", "started_at": "2026-01-01T09:00:00Z"}',
            "source",
            id="a value outside a closed vocabulary",
        ),
        pytest.param(
            '{"source": "chatgpt", "source_id": "x", "started_at": "2026-01-01T09:00:00"}',
            "started_at",
            id="a naive timestamp",
        ),
        pytest.param(
            '{"source": "chatgpt", "source_id": "", "started_at": "2026-01-01T09:00:00Z"}',
            "source_id",
            id="an empty native id",
        ),
        pytest.param(
            '{"source": "chatgpt", "source_id": "x", "started_at": "2026-01-01T09:00:00Z",'
            ' "summary": "a field from a future version"}',
            "summary",
            id="an undeclared field",
        ),
        pytest.param(
            '{"source": "chatgpt", "source_id": "x", "started_at": "2026-01-01T09:00:00Z",'
            ' "messages": [{"role": "narrator", "text": "once upon a time"}]}',
            "role",
            id="a bad value inside a message",
        ),
    ],
)
def test_a_malformed_record_raises_and_names_the_field(record: str, named: str) -> None:
    """B4, FR-015. Never a partial object: in an archive that is the source of truth, a value
    dropped on the way in is a value nobody knows is gone."""
    with pytest.raises(ValidationError) as failure:
        Conversation.model_validate_json(record)

    assert named in str(failure.value)


def test_a_provenance_record_missing_its_importer_version_raises() -> None:
    """Provenance that cannot say which importer produced it is not provenance (Principle II)."""
    with pytest.raises(ValidationError) as failure:
        Provenance.model_validate_json(
            '{"source": "chatgpt", "source_id": "x", "project": "miratorg",'
            ' "imported_at": "2026-09-14T10:00:00Z"}'
        )

    assert "importer_version" in str(failure.value)


def test_an_enriched_record_whose_provenance_names_another_conversation_raises() -> None:
    """The cross-field rule survives the round trip too — it is validation, not construction."""
    original = an_exhaustive_enriched_conversation()
    tampered = original.model_dump()
    tampered["provenance"]["source_id"] = "a-different-conversation"

    with pytest.raises(ValidationError) as failure:
        EnrichedConversation.model_validate(tampered)

    assert "source_id" in str(failure.value)
