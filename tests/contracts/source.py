"""The contract every conversation source must satisfy (ARCHITECTURE.md §8, row 1).

Rules CS-1 to CS-7 of specs/007-boundary-interfaces/contracts/contract-suites.md.

An implementation is run against this by subclassing it and supplying itself through
`make_source`. The three optional hooks describe failures; an implementation that cannot be made to
fail that way returns `None` and the rule is skipped rather than asserted falsely.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from hermes_memory.errors import BoundaryError
from hermes_memory.ingestion import ConversationSource, SourceFormatError, SourceUnavailable
from hermes_memory.normalization import Conversation
from tests.contracts import conversations


class ConversationSourceContract:
    """Subclass this and implement `make_source` to have an implementation tested."""

    # --- what a subclass supplies ---------------------------------------------------------------

    def make_source(self, conversations: tuple[Conversation, ...]) -> ConversationSource:
        """Return a source that reads exactly these conversations."""
        raise NotImplementedError

    def make_source_with_one_unreadable(
        self, conversations: tuple[Conversation, ...]
    ) -> ConversationSource | None:
        """Return a source where the *second* conversation cannot be read, or `None`."""
        return None

    def make_unreachable_source(self) -> ConversationSource | None:
        """Return a source whose export cannot be reached at all, or `None`."""
        return None

    # --- the contract ---------------------------------------------------------------------------

    def test_cs1_every_conversation_carries_the_declared_source(self) -> None:
        source = self.make_source(
            (conversations.conversation("a"), conversations.conversation("b"))
        )

        read = tuple(source.read())

        assert len(read) == 2
        assert all(isinstance(one, Conversation) for one in read)
        assert all(one.source == source.source for one in read)

    def test_cs2_reading_yields_one_conversation_at_a_time(self) -> None:
        """An iterator: a year of history is not held in memory to sanitize one item of it."""
        read = self.make_source((conversations.conversation(),)).read()

        assert isinstance(read, Iterator)

    def test_cs3_an_empty_export_yields_nothing_and_raises_nothing(self) -> None:
        assert tuple(self.make_source(()).read()) == ()

    def test_cs4_reading_twice_yields_equal_conversations(self) -> None:
        """A source is a reader over an export, not a cursor that consumes it."""
        source = self.make_source(
            (conversations.conversation("a"), conversations.conversation("b"))
        )

        assert tuple(source.read()) == tuple(source.read())

    def test_cs5_one_unreadable_conversation_does_not_end_the_iteration(self) -> None:
        """§18 — one failure must not abort a run; a malformed conversation is ordinary."""
        wanted = (
            conversations.conversation("a"),
            conversations.conversation("b"),
            conversations.conversation("c"),
        )
        source = self.make_source_with_one_unreadable(wanted)
        if source is None:
            pytest.skip("this implementation cannot be made to fail on a single conversation")

        read: list[Conversation] = []
        failures: list[SourceFormatError] = []
        iterator = source.read()
        while True:
            try:
                read.append(next(iterator))
            except StopIteration:
                break
            except SourceFormatError as failure:
                failures.append(failure)

        assert len(failures) == 1
        assert [one.source_id for one in read] == ["a", "c"]

    def test_cs6_an_unreachable_export_is_a_retryable_failure(self) -> None:
        source = self.make_unreachable_source()
        if source is None:
            pytest.skip("this implementation cannot be made unreachable")

        with pytest.raises(SourceUnavailable) as raised:
            tuple(source.read())

        assert raised.value.retryable is True

    def test_cs7_no_library_exception_crosses_the_boundary(self) -> None:
        """E1 — a caller must never import the backend's dependency to handle its failures."""
        pair = (conversations.conversation("a"), conversations.conversation("b"))
        for source in (self.make_source_with_one_unreadable(pair), self.make_unreachable_source()):
            if source is None:
                continue
            try:
                tuple(source.read())
            except BoundaryError:
                pass
            except Exception as leaked:
                pytest.fail(f"a non-boundary exception crossed the boundary: {leaked!r}")
