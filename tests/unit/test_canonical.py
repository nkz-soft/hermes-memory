"""The canonical form and the content hash of ARCHITECTURE.md §17, as ADR-006 decision 4 fixes it.

This is the value the import state stores and compares, and the whole §17 skip rests on it: a hash
that varies between runs turns every refresh into a full re-extraction, and a hash that covers the
title turns a rename into one.

Each test names the guarantee it holds to from
`specs/006-normalized-conversation-model/contracts/canonical-form.md`.

The determinism guarantees (C1, C6, C9) are also asserted **in a separate process**, under a
different `PYTHONHASHSEED`. A determinism claim checked once inside one interpreter is not a
determinism claim.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta, timezone

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
    ToolActivity,
    canonical_bytes,
    canonical_form,
    content_hash,
)

STARTED = datetime(2026, 1, 1, 9, tzinfo=UTC)
IMPORTED = datetime(2026, 9, 14, 10, tzinfo=UTC)


def a_message(**overrides: object) -> Message:
    fields: dict[str, object] = {
        "role": Role.USER,
        "text": "why does retain fail here?",
        "sent_at": STARTED,
    }
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


def a_provenance(**overrides: object) -> Provenance:
    fields: dict[str, object] = {
        "source": Source.CHATGPT,
        "source_id": "conversation-id",
        "project": "miratorg",
        "imported_at": IMPORTED,
        "importer_version": "1",
    }
    return Provenance(**(fields | overrides))  # type: ignore[arg-type]


def hash_in_a_separate_process(seed: str) -> str:
    """Build the same conversation in a fresh interpreter and return its content hash.

    The conversation is rebuilt from source rather than pickled, so what is compared is the
    canonical form's determinism and not a serializer's.
    """
    script = """
from datetime import UTC, datetime
from hermes_memory.normalization import Conversation, Message, Role, Source, content_hash

print(
    content_hash(
        Conversation(
            source=Source.CHATGPT,
            source_id="conversation-id",
            title="Wolverine Saga Error Handling",
            started_at=datetime(2026, 1, 1, 9, tzinfo=UTC),
            messages=(
                Message(
                    role=Role.USER,
                    text="why does retain fail here?",
                    sent_at=datetime(2026, 1, 1, 9, tzinfo=UTC),
                ),
            ),
        )
    )
)
"""
    finished = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
        env=os.environ | {"PYTHONHASHSEED": seed},
    )
    return finished.stdout.strip()


# --- C9: the payload and its bytes -------------------------------------------------------------


def test_the_payload_carries_a_version() -> None:
    """C9. A future change to what the hash covers is then a value a stored hash can be compared
    against, rather than a silent divergence discovered as a mass re-extraction."""
    assert canonical_form(a_conversation())["version"] == 1


def test_the_payload_holds_only_the_version_and_the_messages() -> None:
    """C9. Included by name, never by dumping the model and subtracting (research R1)."""
    assert set(canonical_form(a_conversation())) == {"version", "messages"}


def test_a_message_in_the_payload_holds_exactly_the_covered_fields() -> None:
    """C9. Role, text, time, tool activity, non-text parts — and nothing else."""
    [message] = canonical_form(a_conversation())["messages"]

    assert set(message) == {"role", "text", "sent_at", "tool_activity", "non_text_parts"}


def test_the_bytes_are_compact_sorted_and_unescaped() -> None:
    """C9. The exact byte form, pinned. Every degree of freedom JSON leaves is closed here.

    Written out in full rather than re-derived with the same `json.dumps` call the implementation
    uses, which would assert only that the code equals itself.
    """
    conversation = a_conversation(messages=(a_message(text="почему retain падает?"),))

    assert canonical_bytes(conversation) == (
        b'{"messages":[{"non_text_parts":[],"role":"user","sent_at":'
        + b'"2026-01-01T09:00:00.000000Z","text":"'
        + "почему retain падает?".encode()
        + b'","tool_activity":[]}],"version":1}'
    )


def test_an_absent_message_time_renders_as_null() -> None:
    """The absence is rendered as itself: §11 forbids substituting any clock for a missing time."""
    [message] = canonical_form(a_conversation(messages=(a_message(sent_at=None),)))["messages"]

    assert message["sent_at"] is None


def test_a_whole_second_renders_with_the_same_precision_as_a_fraction() -> None:
    """C7. `isoformat` drops zero microseconds; that would make the shape depend on the value."""
    whole = a_conversation(messages=(a_message(sent_at=STARTED),))
    fractional = a_conversation(messages=(a_message(sent_at=STARTED.replace(microsecond=123456)),))

    rendered = [
        canonical_form(conversation)["messages"][0]["sent_at"]
        for conversation in (whole, fractional)
    ]

    assert rendered == ["2026-01-01T09:00:00.000000Z", "2026-01-01T09:00:00.123456Z"]


def test_non_ascii_text_survives_as_text() -> None:
    """The corpus is substantially non-ASCII; escaping would make the bytes depend on nothing."""
    conversation = a_conversation(messages=(a_message(text="почему retain падает?"),))

    assert "почему retain падает?".encode() in canonical_bytes(conversation)


# --- C1: identical conversations hash equal ----------------------------------------------------


def test_structurally_identical_conversations_hash_equal() -> None:
    """C1. The skip of §17 is exactly this comparison."""
    assert content_hash(a_conversation()) == content_hash(a_conversation())


def test_the_hash_is_sixty_four_hex_characters() -> None:
    digest = content_hash(a_conversation())

    assert len(digest) == 64
    assert set(digest) <= set("0123456789abcdef")


def test_the_hash_is_the_same_in_another_process() -> None:
    """C1, C9. Under a different `PYTHONHASHSEED`, in a fresh interpreter."""
    first = hash_in_a_separate_process(seed="0")
    second = hash_in_a_separate_process(seed="12345")

    assert first == second == content_hash(a_conversation())


# --- C2, C3: what moves the hash ---------------------------------------------------------------


def test_changed_text_moves_the_hash() -> None:
    """C2."""
    assert content_hash(a_conversation(messages=(a_message(text="something else"),))) != (
        content_hash(a_conversation())
    )


def test_a_changed_role_moves_the_hash() -> None:
    """C2. The same words from the assistant are not the same conversation."""
    assert content_hash(a_conversation(messages=(a_message(role=Role.ASSISTANT),))) != (
        content_hash(a_conversation())
    )


def test_a_changed_order_moves_the_hash() -> None:
    """C2. Order is content: the same turns in the other order is a different conversation."""
    first, second = a_message(text="first"), a_message(text="second")

    assert content_hash(a_conversation(messages=(first, second))) != content_hash(
        a_conversation(messages=(second, first))
    )


def test_a_changed_message_time_moves_the_hash() -> None:
    """C2. ADR-006 decision 4 names the message timestamps as covered."""
    assert content_hash(
        a_conversation(messages=(a_message(sent_at=STARTED + timedelta(minutes=1)),))
    ) != content_hash(a_conversation())


def test_an_added_message_moves_the_hash() -> None:
    """C2. This is the case ADR-006 decision 2 governs: a conversation that continued."""
    assert content_hash(
        a_conversation(messages=(a_message(), a_message(role=Role.ASSISTANT, text="because…")))
    ) != content_hash(a_conversation())


def test_changed_tool_activity_moves_the_hash() -> None:
    """C3. A tool result is part of the message, not metadata about it (research R11)."""
    with_a_tool = a_conversation(
        messages=(a_message(tool_activity=(ToolActivity(name="web.search", result="404"),)),)
    )
    with_another = a_conversation(
        messages=(a_message(tool_activity=(ToolActivity(name="web.search", result="200"),)),)
    )

    # Three separate comparisons, not a chain: `a != b != c` never compares a with c, so a chained
    # assertion here would pass even if adding a tool call left the hash alone.
    assert content_hash(with_a_tool) != content_hash(with_another)
    assert content_hash(with_a_tool) != content_hash(a_conversation())
    assert content_hash(with_another) != content_hash(a_conversation())


def test_a_changed_non_text_part_moves_the_hash() -> None:
    """C3. That an image was there is content; losing it silently is what FR-019 prevents."""
    with_an_image = a_conversation(
        messages=(a_message(non_text_parts=(NonTextPart(kind=NonTextKind.IMAGE),)),)
    )

    assert content_hash(with_an_image) != content_hash(a_conversation())


# --- C4, C5: what does not move the hash -------------------------------------------------------


def test_a_changed_title_leaves_the_hash_alone() -> None:
    """C4. ADR-006 decision 4, and the stale-title consequence recorded with it: a rename alone
    does not re-import, so the title held in the bank may lag."""
    assert content_hash(a_conversation(title="Renamed")) == content_hash(a_conversation())


def test_an_absent_and_an_empty_title_hash_alike() -> None:
    """C4. Both are "no title", and the hash must not be able to tell them apart."""
    assert content_hash(a_conversation(title=None)) == content_hash(a_conversation(title=""))


def test_the_conversation_timestamps_do_not_move_the_hash() -> None:
    """C4. ADR-006 names the *messages'* timestamps. A parser that learns to fill in
    `last_activity_at` must not thereby re-extract the whole corpus."""
    assert content_hash(
        a_conversation(last_activity_at=STARTED + timedelta(days=1))
    ) == content_hash(a_conversation())


def test_provenance_does_not_move_the_hash() -> None:
    """C5. It is metadata the importer produces, excluded in full by ADR-006 decision 4.

    This is what keeps an ordinary refresh from re-extracting everything the moment the importer
    version changes — and is why ADR-006 also requires a forced re-import for the cases where that
    is exactly what is wanted.
    """
    enriched = EnrichedConversation(conversation=a_conversation(), provenance=a_provenance())
    reimported = EnrichedConversation(
        conversation=a_conversation(),
        provenance=a_provenance(importer_version="2", imported_at=IMPORTED + timedelta(days=30)),
    )

    assert enriched.content_hash() == reimported.content_hash()


def test_tags_do_not_move_the_hash() -> None:
    """C5. Re-classifying into another project does not change the conversation itself."""
    untagged = EnrichedConversation(conversation=a_conversation(), provenance=a_provenance())
    tagged = EnrichedConversation(
        conversation=a_conversation(),
        provenance=a_provenance(),
        tags=(ProjectTag(value="miratorg"),),
    )

    assert untagged.content_hash() == tagged.content_hash()


def test_an_enriched_conversation_delegates_identity_to_its_conversation() -> None:
    """A caller holding the enriched form never reaches past it to recompute either value."""
    conversation = a_conversation()
    enriched = EnrichedConversation(conversation=conversation, provenance=a_provenance())

    assert enriched.document_id == conversation.document_id
    assert enriched.content_hash() == conversation.content_hash()


# --- C6: one instant, two offsets --------------------------------------------------------------


def test_the_same_instant_at_two_offsets_hashes_equal() -> None:
    """C6. An export taken in Moscow and one taken in UTC describe the same conversation."""
    moscow = timezone(timedelta(hours=3))
    in_moscow = a_conversation(
        messages=(a_message(sent_at=datetime(2026, 1, 1, 12, tzinfo=moscow)),)
    )
    in_utc = a_conversation(messages=(a_message(sent_at=datetime(2026, 1, 1, 9, tzinfo=UTC)),))

    assert content_hash(in_moscow) == content_hash(in_utc)


# --- C8: the empty conversation ----------------------------------------------------------------


def test_a_conversation_with_no_messages_has_a_defined_hash() -> None:
    """C8. An export can carry one, and the importer must skip it like any other."""
    empty = a_conversation(messages=())

    assert len(content_hash(empty)) == 64
    assert content_hash(empty) != content_hash(a_conversation())


def test_the_payload_is_json_serializable_as_it_stands() -> None:
    """Nothing in the payload is a model, an enum instance or a datetime — only plain JSON types.

    Pinned because the bytes are produced by `json.dumps` without a custom encoder: a value that
    needed one would be a value whose rendering nobody decided.
    """
    json.dumps(canonical_form(a_conversation()))
