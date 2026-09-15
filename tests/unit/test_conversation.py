"""The conversation tree: what the pipeline of ARCHITECTURE.md §7 passes between its stages.

What is pinned here is the shape every other stage depends on — the closed vocabularies of §6 and
§10, the order of the messages, the absence of any default that would invent a timestamp (§11), and
the immutability that lets a stage return a new conversation instead of editing one.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from hermes_memory.normalization import (
    Conversation,
    Message,
    NonTextKind,
    NonTextPart,
    Role,
    Source,
    ToolActivity,
)

STARTED = datetime(2026, 1, 1, 9, tzinfo=UTC)


def a_message(**overrides: object) -> Message:
    fields: dict[str, object] = {"role": Role.USER, "text": "why does retain fail here?"}
    return Message(**(fields | overrides))  # type: ignore[arg-type]


def a_conversation(**overrides: object) -> Conversation:
    fields: dict[str, object] = {
        "source": Source.CHATGPT,
        "source_id": "conversation-id",
        "title": "Wolverine Saga Error Handling",
        "started_at": STARTED,
        "messages": (a_message(),),
    }
    return Conversation(**(fields | overrides))  # type: ignore[arg-type]


# --- the closed vocabularies -------------------------------------------------------------------


def test_the_sources_are_the_five_the_architecture_names() -> None:
    """§6's tag convention and §10's document-id scheme name the same five (FR-004)."""
    assert {source.value for source in Source} == {
        "chatgpt",
        "claude-chat",
        "claude-code",
        "codex",
        "hermes",
    }


def test_the_roles_are_closed() -> None:
    """A tool turn is a role, not a flag: §7 keeps the tool chain inside the conversation."""
    assert {role.value for role in Role} == {"user", "assistant", "system", "tool"}


def test_the_non_text_kinds_are_closed() -> None:
    assert {kind.value for kind in NonTextKind} == {"image", "file", "audio", "other"}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        pytest.param("source", "gpt", id="source outside the vocabulary"),
        pytest.param("source", "ChatGPT", id="source in the wrong case"),
    ],
)
def test_a_value_outside_a_closed_vocabulary_is_refused(field: str, value: str) -> None:
    """Carried as a typed value rather than a string, so a new source is a decision (§2)."""
    with pytest.raises(ValidationError) as failure:
        a_conversation(**{field: value})

    assert field in str(failure.value)


def test_a_role_outside_the_vocabulary_is_refused() -> None:
    with pytest.raises(ValidationError) as failure:
        a_message(role="narrator")

    assert "role" in str(failure.value)


# --- order -------------------------------------------------------------------------------------


def test_message_order_is_the_order_given() -> None:
    """Order is the sequence at construction, never a sort (FR-003, research.md R6)."""
    first = a_message(text="first", sent_at=datetime(2026, 1, 1, 12, tzinfo=UTC))
    second = a_message(text="second", sent_at=datetime(2026, 1, 1, 10, tzinfo=UTC))

    conversation = a_conversation(messages=(first, second))

    assert [message.text for message in conversation.messages] == ["first", "second"]


def test_messages_with_no_timestamps_keep_their_order() -> None:
    """A ChatGPT export omits some message times; that must not disturb the sequence."""
    conversation = a_conversation(
        messages=(a_message(text="first"), a_message(text="second"), a_message(text="third"))
    )

    assert [message.text for message in conversation.messages] == ["first", "second", "third"]


def test_messages_are_a_tuple_even_when_given_a_list() -> None:
    """The sequence is a value, not a container a caller can go on appending to."""
    assert isinstance(a_conversation(messages=[a_message()]).messages, tuple)


# --- what may be absent ------------------------------------------------------------------------


def test_a_conversation_with_no_messages_is_valid() -> None:
    """An export can carry one, and the importer must be able to skip it like any other."""
    assert a_conversation(messages=()).messages == ()


@pytest.mark.parametrize("title", [None, ""], ids=["absent", "empty"])
def test_a_title_may_be_absent_or_empty(title: str | None) -> None:
    """Titles are outside the content hash (ADR-006), so neither form may be refused."""
    assert a_conversation(title=title).title == title


def test_a_message_may_carry_no_text() -> None:
    """A turn that carried only an image is still a turn."""
    assert a_message(text="", non_text_parts=(NonTextPart(kind=NonTextKind.IMAGE),)).text == ""


def test_a_message_time_is_absent_rather_than_defaulted() -> None:
    """§11: the import time is never used as a conversation time, so nothing may fill this in."""
    assert a_message().sent_at is None


def test_tool_activity_without_a_result_is_valid() -> None:
    """A call that errored or never completed is what a history actually contains."""
    activity = ToolActivity(name="web.search", request="hindsight retain 413")

    assert activity.result is None


def test_a_tool_activity_needs_a_name() -> None:
    with pytest.raises(ValidationError) as failure:
        ToolActivity(name="")

    assert "name" in str(failure.value)


def test_last_activity_may_be_absent() -> None:
    """Not every source carries one, and inventing it would be inventing history."""
    assert a_conversation().last_activity_at is None


def test_last_activity_before_the_start_is_refused() -> None:
    """A conversation that ended before it began is a parser bug, caught at the boundary."""
    with pytest.raises(ValidationError) as failure:
        a_conversation(last_activity_at=STARTED - timedelta(hours=1))

    assert "last_activity_at" in str(failure.value)


def test_last_activity_equal_to_the_start_is_accepted() -> None:
    """A single-message conversation is not an error."""
    assert a_conversation(last_activity_at=STARTED).last_activity_at == STARTED


def test_last_activity_is_compared_as_an_instant_not_as_a_wall_clock() -> None:
    """09:00Z and 12:00+03:00 are the same moment; a timezone must not forge an ordering."""
    moscow_noon = datetime(2026, 1, 1, 12, tzinfo=timezone(timedelta(hours=3)))

    assert a_conversation(last_activity_at=moscow_noon).last_activity_at == STARTED


# --- timestamps --------------------------------------------------------------------------------


def test_a_naive_conversation_timestamp_is_refused() -> None:
    with pytest.raises(ValidationError) as failure:
        a_conversation(started_at=datetime(2026, 1, 1, 9))

    assert "started_at" in str(failure.value)


def test_a_naive_message_timestamp_is_refused() -> None:
    with pytest.raises(ValidationError) as failure:
        a_message(sent_at=datetime(2026, 1, 1, 9))

    assert "sent_at" in str(failure.value)


def test_a_conversation_must_carry_a_start() -> None:
    """§11 makes the real time load-bearing for temporal retrieval; it is not optional."""
    with pytest.raises(ValidationError) as failure:
        Conversation(source=Source.CHATGPT, source_id="conversation-id", messages=())

    assert "started_at" in str(failure.value)


# --- immutability ------------------------------------------------------------------------------


def test_a_conversation_cannot_be_mutated() -> None:
    """So that a sanitizer returns a redacted conversation instead of editing one (research R7)."""
    with pytest.raises(ValidationError):
        a_conversation().title = "Renamed"  # type: ignore[misc]


def test_a_message_cannot_be_mutated() -> None:
    with pytest.raises(ValidationError):
        a_message().text = "[REDACTED]"  # type: ignore[misc]


def test_an_undeclared_field_on_a_conversation_is_refused() -> None:
    with pytest.raises(ValidationError) as failure:
        a_conversation(summary="a field nobody declared")

    assert "summary" in str(failure.value)
