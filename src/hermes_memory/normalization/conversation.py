"""The conversation as the pipeline sees it, independent of the format it arrived in.

ARCHITECTURE.md §7 puts a normalize stage between the parser and everything downstream so that the
sanitizer, the classifier, the archive and the memory store speak one vocabulary rather than one
per source. This module is that vocabulary.

Two rules from the architecture are enforced here rather than remembered:

* **§11** — the times are the source's own. No field defaults to a clock, so the import date cannot
  drift into the place of the conversation date, and temporal retrieval keeps working.
* **§10** — `document_id` is derived, never supplied, so a re-import cannot mint a new identity for
  a conversation that already has one (Principle II).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from hermes_memory.normalization.base import FrozenModel, OpaqueIdentifier, Timestamp

__all__ = [
    "Conversation",
    "Message",
    "NonTextKind",
    "NonTextPart",
    "Role",
    "Source",
    "ToolActivity",
]


class Source(StrEnum):
    """The history sources the architecture names (ARCHITECTURE.md §6 and §10).

    Closed on purpose: each new source is separate work with its own specification and decision
    record (§2), so a source arrives by amending this enum in that work — not by a caller passing
    a string nobody planned for.

    Only `CHATGPT` is parsed in Phase 1. The others are here because the document-id scheme and the
    tag convention already name them, and a vocabulary that disagreed with those would be the
    defect.
    """

    CHATGPT = "chatgpt"
    CLAUDE_CHAT = "claude-chat"
    CLAUDE_CODE = "claude-code"
    CODEX = "codex"
    HERMES = "hermes"


class Role(StrEnum):
    """Who produced a turn.

    `TOOL` is a role rather than a flag because §7 keeps the chain command → error → investigation
    → solution inside the conversation, and a tool result is part of that chain.
    """

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class NonTextKind(StrEnum):
    """What kind of non-text part a source carried."""

    IMAGE = "image"
    FILE = "file"
    AUDIO = "audio"
    OTHER = "other"


class NonTextPart(FrozenModel):
    """A marker that the source carried something this model does not represent.

    No bytes, no path, no URL — only that it existed, and what the source called it. The MVP
    extracts text; recording the rest is what keeps a replay from the raw archive (Principle I)
    from silently omitting content nobody knows about.

    Storing the content itself is the archive's question (§14), not this model's.
    """

    kind: NonTextKind
    name: str | None = None


class ToolActivity(FrozenModel):
    """What a source records about a tool the assistant used.

    Modelled at the level a ChatGPT export carries. Claude Code and Codex record substantially
    richer structure and arrive with their own specification and decision record (§2, Phase 2);
    extending this then is expected, and building for it now would be inventing a shape with no
    consumer.

    `result` is absent for a call that errored or never completed, which is what a real history
    contains.
    """

    name: str = Field(min_length=1)
    request: str | None = None
    result: str | None = None


class Message(FrozenModel):
    """One turn in a conversation.

    `text` may be empty: a turn that carried only an image is still a turn, and dropping it would
    break the order the conversation depends on.

    `sent_at` may be absent, because ChatGPT exports omit it on some messages — and it has no
    default, because §11 forbids substituting any other time for a missing one.
    """

    role: Role
    text: str
    sent_at: Timestamp | None = None
    tool_activity: tuple[ToolActivity, ...] = ()
    non_text_parts: tuple[NonTextPart, ...] = ()


class Conversation(FrozenModel):
    """One conversation from one source, in the vocabulary every stage of §7 speaks.

    The messages are a tuple, and their order is that tuple's order. It is never re-derived from
    the timestamps: an export omits some of them, and two messages can share one, so a sort would
    reorder a conversation on the strength of a value that was never an ordering.
    """

    source: Source
    source_id: OpaqueIdentifier
    title: str | None = None
    started_at: Timestamp
    last_activity_at: Timestamp | None = None
    messages: tuple[Message, ...] = ()

    @model_validator(mode="after")
    def _activity_does_not_precede_the_start(self) -> Conversation:
        """A conversation that ended before it began is a parser bug, caught at the boundary.

        Compared as instants: 09:00Z and 12:00+03:00 are one moment, and a timezone must not be
        able to forge an ordering that the source does not contain.
        """
        if self.last_activity_at is not None and self.last_activity_at < self.started_at:
            raise ValueError(
                f"last_activity_at ({self.last_activity_at.isoformat()}) precedes "
                f"started_at ({self.started_at.isoformat()})"
            )
        return self
