"""Synthesized conversations the contract suites build on.

Never real history: this repository is public and the data it processes is private engineering
history (CLAUDE.md). Everything here is invented, including the fake secret — which is the string
`hunter2`, chosen because it is a joke rather than a credential.
"""

from __future__ import annotations

from datetime import UTC, datetime

from hermes_memory.archive import OriginalPayload
from hermes_memory.ingestion import SourceConversation
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
)

STARTED_AT = datetime(2026, 3, 4, 9, 30, tzinfo=UTC)
IMPORTED_AT = datetime(2026, 9, 16, 10, 0, tzinfo=UTC)
IMPORTER_VERSION = "1"

FAKE_SECRET = "hunter2"
"""A stand-in for a credential. A sanitizer under test must remove it; it is not a real secret."""


def conversation(
    source_id: str = "abc123",
    *,
    source: Source = Source.CHATGPT,
    title: str | None = "Wolverine saga error handling",
    text: str = "We moved the saga to Wolverine in March.",
) -> Conversation:
    """The minimal conversation most rules need: two turns, one distinctive phrase."""
    return Conversation(
        source=source,
        source_id=source_id,
        title=title,
        started_at=STARTED_AT,
        messages=(
            Message(
                role=Role.USER,
                text="How should the saga handle a failed step?",
                sent_at=STARTED_AT,
            ),
            Message(role=Role.ASSISTANT, text=text, sent_at=STARTED_AT),
        ),
    )


def conversation_with_a_secret(source_id: str = "leaky1") -> Conversation:
    """A conversation whose text surrounds a fake credential, for SS-3 and SS-4.

    The surrounding words are the point: §13 requires the context to survive the redaction, because
    the context is usually the knowledge worth keeping.
    """
    return Conversation(
        source=Source.CHATGPT,
        source_id=source_id,
        title="A failing GitLab call",
        started_at=STARTED_AT,
        messages=(
            Message(
                role=Role.ASSISTANT,
                text=f"GitLab request using token {FAKE_SECRET} returned HTTP 401 Unauthorized.",
                sent_at=STARTED_AT,
            ),
        ),
    )


def conversation_using_every_field(source_id: str = "rich1") -> Conversation:
    """Exercises every optional field of #8's model, for the archive round-trip (RA-6)."""
    return Conversation(
        source=Source.CHATGPT,
        source_id=source_id,
        title="A session with tools and attachments",
        started_at=STARTED_AT,
        last_activity_at=datetime(2026, 3, 4, 11, 45, tzinfo=UTC),
        messages=(
            Message(role=Role.SYSTEM, text="You are a helpful assistant."),
            Message(
                role=Role.USER,
                text="Here is the failing log.",
                sent_at=STARTED_AT,
                non_text_parts=(NonTextPart(kind=NonTextKind.FILE, name="app.log"),),
            ),
            Message(
                role=Role.ASSISTANT,
                text="",
                sent_at=STARTED_AT,
                tool_activity=(
                    ToolActivity(name="search", request="wolverine saga retry", result="3 hits"),
                    ToolActivity(name="fetch", request="https://example.invalid/doc"),
                ),
                non_text_parts=(NonTextPart(kind=NonTextKind.IMAGE),),
            ),
            Message(role=Role.TOOL, text="3 hits", sent_at=STARTED_AT),
        ),
    )


def enrich(source: Conversation, *, project: str = "hermes-memory") -> EnrichedConversation:
    """Attach the provenance and tags §7's enrich stage would, so a boundary gets what it wants."""
    return EnrichedConversation(
        conversation=source,
        provenance=Provenance(
            source=source.source,
            source_id=source.source_id,
            project=project,
            title=source.title,
            imported_at=IMPORTED_AT,
            importer_version=IMPORTER_VERSION,
        ),
        tags=(SourceTag(value=source.source), ProjectTag(value=project)),
    )


PAYLOAD = OriginalPayload(content=b'{"as": "exported"}', media_type="application/json")
"""Stand-in for the bytes a conversation was parsed from. The archive keeps these (Principle I)."""


def as_read(*of: Conversation) -> tuple[SourceConversation, ...]:
    """Pair conversations with their originals, the way a source yields them."""
    return tuple(SourceConversation(conversation=one, original=PAYLOAD) for one in of)
