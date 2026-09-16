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

from hermes_memory.errors import PermanentBoundaryError, TransientBoundaryError
from hermes_memory.normalization import Conversation, Source

__all__ = ["ConversationSource", "SourceFormatError", "SourceUnavailable"]

BOUNDARY = "conversation source"


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

    def read(self) -> Iterator[Conversation]:
        """Yield the export's conversations, one at a time.

        An iterator rather than a sequence, and deliberately (CS-2): a caller processes and fails
        conversation by conversation (§18), and a year of ChatGPT history is not something to
        materialize in order to sanitize the first item of it.

        Reading twice yields equal conversations (CS-4) — a source is a reader over an export, not
        a cursor that consumes one. An empty export yields nothing and raises nothing (CS-3).

        Raises:
            SourceFormatError: for one unreadable conversation; iteration continues afterwards.
            SourceUnavailable: when the export cannot be reached at all.
        """
        ...
