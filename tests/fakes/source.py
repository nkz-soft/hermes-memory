"""An in-memory conversation source: the first proof #10's interface is implementable.

It reads a tuple it was handed. What makes it worth having is not the reading but the failures: it
can be told to fail on one conversation (§18's ordinary case) or to be unreachable, so the pipeline
tests can exercise a run that survives a failure without a malformed export on disk.

**It is not a generator, and that is the point.** CS-5 requires that a `SourceFormatError` for one
conversation leaves the iterator usable for the rest — §18's "one failure must not abort a run" —
and an exception raised inside a generator closes it for good. An explicit iterator is what makes
the rule implementable, and writing the fake is how that was discovered rather than left for #10.
"""

from __future__ import annotations

from collections.abc import Iterator

from hermes_memory.ingestion import SourceConversation, SourceFormatError, SourceUnavailable
from hermes_memory.normalization import Source


class _ResumableReader(Iterator[SourceConversation]):
    """Yields conversations, raising for the unreadable ones without ending the iteration."""

    def __init__(
        self, conversations: tuple[SourceConversation, ...], unreadable: frozenset[str]
    ) -> None:
        self._conversations = conversations
        self._unreadable = unreadable
        self._position = 0

    def __next__(self) -> SourceConversation:
        while self._position < len(self._conversations):
            read = self._conversations[self._position]
            self._position += 1
            if read.conversation.source_id in self._unreadable:
                raise SourceFormatError(
                    "this conversation could not be parsed",
                    subject=read.conversation.source_id,
                )
            return read
        raise StopIteration


class InMemoryConversationSource:
    """Yields the conversations it was constructed with.

    `unreadable` names the source ids this source cannot parse; reaching one raises
    `SourceFormatError` and the next call continues with the following conversation.
    """

    def __init__(
        self,
        conversations: tuple[SourceConversation, ...] = (),
        *,
        source: Source = Source.CHATGPT,
        unreadable: frozenset[str] = frozenset(),
        unreachable: bool = False,
    ) -> None:
        self.source = source
        self._conversations = conversations
        self._unreadable = unreadable
        self._unreachable = unreachable

    def read(self) -> Iterator[SourceConversation]:
        if self._unreachable:
            raise SourceUnavailable("the export could not be reached")
        return _ResumableReader(self._conversations, self._unreadable)
