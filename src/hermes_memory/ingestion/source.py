"""The conversation source boundary (ARCHITECTURE.md §8, row 1).

> Read one source format, yield normalized conversations.

One implementation per source format — ChatGPT in #10, Claude chats, Claude Code and Codex each
with their own specification and decision record (§2). What they have in common is everything
downstream: a caller of this protocol cannot tell which source it is reading, which is what lets
§7's pipeline be written once.

Contract: specs/007-boundary-interfaces/contracts/interfaces.md, rules CS-1 to CS-7.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol, runtime_checkable

from hermes_memory.archive import OriginalPayload
from hermes_memory.errors import PermanentBoundaryError, TransientBoundaryError
from hermes_memory.normalization import Conversation, Source
from hermes_memory.normalization.base import FrozenModel

__all__ = [
    "ConversationSource",
    "SourceConversation",
    "SourceFormatError",
    "SourceUnavailable",
]

BOUNDARY = "conversation source"


class SourceConversation(FrozenModel):
    """One conversation as read, together with the bytes it was read from.

    The pair exists because Principle I asks the archive for both forms and **only the source knows
    the original**: by the time a conversation has been normalized, the JSON slice it came from is
    gone unless somebody kept it. The alternative designs were worse — a second method on this
    boundary would make every source retain or re-scan its export to answer it, and archiving the
    normalized form alone would mean a replay faithfully reproducing the parser bug that prompted
    the replay.

    Discovered by composing the boundaries rather than by reading them: the pipeline harness of
    #9 could not be written until the source and the archive agreed about this (US3 exists for
    exactly that).
    """

    conversation: Conversation
    original: OriginalPayload


class SourceFormatError(PermanentBoundaryError):
    """One conversation in the export cannot be read.

    Permanent, because the bytes will not improve on a second attempt. It is raised *from the
    iterator*, for one conversation, and iteration continues: §18 requires that one failure cannot
    abort a run, and an export of ten thousand conversations where the four hundredth is malformed
    is the ordinary case, not the exceptional one.
    """

    def __init__(self, message: str, *, subject: str | None = None) -> None:
        super().__init__(BOUNDARY, message, subject=subject)


class SourceUnavailable(TransientBoundaryError):
    """The export itself could not be reached.

    Transient, because the thing that usually causes it — a file locked by another process, a
    download still in flight — passes. Unlike `SourceFormatError` this concerns no single
    conversation, so `subject` is usually absent.
    """

    def __init__(self, message: str, *, subject: str | None = None) -> None:
        super().__init__(BOUNDARY, message, subject=subject)


@runtime_checkable
class ConversationSource(Protocol):
    """Reads one source format and yields normalized conversations.

    `@runtime_checkable` states the intent and is not load-bearing: `isinstance` against a protocol
    checks that the attribute names exist, not that they behave. What decides whether something
    implements this boundary is `tests/contracts/source.py` (research.md R1).
    """

    source: Source
    """Which source this reads. Every conversation it yields carries the same value (CS-1)."""

    def read(self) -> Iterator[SourceConversation]:
        """Yield the export's conversations, one at a time, each with the bytes it came from.

        An iterator rather than a sequence, and deliberately (CS-2): a caller processes and fails
        conversation by conversation (§18), and a year of ChatGPT history is not something to
        materialize in order to sanitize the first item of it.

        Reading twice yields equal conversations (CS-4) — a source is a reader over an export, not
        a cursor that consumes one. An empty export yields nothing and raises nothing (CS-3).

        **The iterator stays usable after a `SourceFormatError`** (CS-5): the caller catches it,
        records the failure and asks for the next conversation. That is what §18's "one failure
        must not abort a run" means at this boundary, and it rules out the obvious implementation —
        an exception raised inside a generator closes the generator for good, so a source yielding
        from one cannot satisfy this. Write an iterator.

        Raises:
            SourceFormatError: for one unreadable conversation; iteration continues afterwards.
            SourceUnavailable: when the export cannot be reached at all.
        """
        ...
