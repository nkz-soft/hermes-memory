"""The contract every memory store must satisfy (ARCHITECTURE.md §8, row 5).

Rules MS-1 to MS-11 of specs/007-boundary-interfaces/contracts/contract-suites.md.

Two things this suite deliberately does not do, because doing them would leak the engine into the
contract:

* **It never counts documents.** MS-2 proves "retaining twice creates no duplicate" by recalling
  before and after the second retain and comparing what comes back. An inspection method would be
  easier and would demand something no memory engine owes us (research.md R9).
* **It never asserts a score's value.** `score` is comparable within one result set and nowhere
  else; a threshold here would be a promise about Hindsight's ranking.
"""

from __future__ import annotations

import pytest

from hermes_memory.errors import BoundaryError
from hermes_memory.memory.interface import (
    MemoryStore,
    MemoryStoreRejected,
    MemoryStoreUnavailable,
    RecallResult,
)
from hermes_memory.normalization import ProjectTag
from tests.contracts import conversations

PHRASE = "Wolverine"
"""A distinctive word planted in the conversation and used as the recall query."""


class MemoryStoreContract:
    """Subclass this and implement `make_store`."""

    # --- what a subclass supplies ---------------------------------------------------------------

    def make_store(self) -> MemoryStore:
        raise NotImplementedError

    def make_rejecting_store(self) -> MemoryStore | None:
        """Return a store that refuses the call — rejected, unauthorized, invalid — or `None`."""
        return None

    def make_unavailable_store(self) -> MemoryStore | None:
        """Return a store that cannot be reached, or `None`."""
        return None

    # --- the contract ---------------------------------------------------------------------------

    def test_ms1_what_was_retained_can_be_recalled(self) -> None:
        store = self.make_store()
        enriched = conversations.enrich(conversations.conversation())

        store.retain(enriched)
        results = store.recall(PHRASE)

        assert results
        assert all(isinstance(result, RecallResult) for result in results)

    def test_ms2_retaining_the_same_conversation_twice_creates_no_duplicate(self) -> None:
        """Principle II — proved through the interface's own read side, never a document count."""
        store = self.make_store()
        enriched = conversations.enrich(conversations.conversation())

        store.retain(enriched)
        after_one = store.recall(PHRASE)
        store.retain(enriched)
        after_two = store.recall(PHRASE)

        assert len(after_two) == len(after_one)

    def test_ms3_re_retaining_changed_content_replaces_rather_than_adds(self) -> None:
        """§9's `update_mode: replace`: one logical document, whatever it said last time."""
        store = self.make_store()
        first = conversations.enrich(
            conversations.conversation(text="We moved the saga to Wolverine in March.")
        )
        second = conversations.enrich(
            conversations.conversation(text="We moved the saga to Rebus in April.")
        )
        assert first.document_id == second.document_id

        store.retain(first)
        store.retain(second)

        assert store.recall(PHRASE) == ()
        assert store.recall("Rebus")

    def test_ms4_recalling_nothing_is_an_empty_result_not_a_failure(self) -> None:
        store = self.make_store()
        store.retain(conversations.enrich(conversations.conversation()))

        assert store.recall("a phrase nobody ever wrote down") == ()

    def test_ms5_results_carry_the_provenance_they_were_retained_with(self) -> None:
        store = self.make_store()
        enriched = conversations.enrich(conversations.conversation())

        store.retain(enriched)

        for result in store.recall(PHRASE):
            assert result.provenance.source == enriched.provenance.source
            assert result.provenance.source_id == enriched.provenance.source_id
            assert result.provenance.project == enriched.provenance.project

    def test_ms6_tags_narrow_the_results(self) -> None:
        """ADR-002 — scoping is by `project:` tags, never by a bank per project."""
        store = self.make_store()
        mine = conversations.enrich(conversations.conversation("mine"), project="hermes-memory")
        theirs = conversations.enrich(conversations.conversation("theirs"), project="miratorg")
        store.retain(mine)
        store.retain(theirs)

        results = store.recall(PHRASE, tags=(ProjectTag(value="miratorg"),))

        assert results
        assert all(result.provenance.project == "miratorg" for result in results)

    def test_ms7_limit_bounds_the_results(self) -> None:
        store = self.make_store()
        for index in range(3):
            store.retain(conversations.enrich(conversations.conversation(f"c{index}")))

        assert len(store.recall(PHRASE, limit=2)) <= 2

    def test_ms8_a_refused_call_is_a_permanent_failure(self) -> None:
        store = self.make_rejecting_store()
        if store is None:
            pytest.skip("this implementation cannot be made to refuse a call")

        with pytest.raises(MemoryStoreRejected) as raised:
            store.retain(conversations.enrich(conversations.conversation()))

        assert raised.value.retryable is False

    def test_ms9_an_unreachable_engine_is_a_transient_failure(self) -> None:
        """§18's retry list: timeout, reset, 429, 502, 503, 504 — what #20 repeats."""
        store = self.make_unavailable_store()
        if store is None:
            pytest.skip("this implementation cannot be made unreachable")

        with pytest.raises(MemoryStoreUnavailable) as raised:
            store.retain(conversations.enrich(conversations.conversation()))

        assert raised.value.retryable is True

    def test_ms10_no_library_exception_crosses_the_boundary(self) -> None:
        for store in (self.make_rejecting_store(), self.make_unavailable_store()):
            if store is None:
                continue
            try:
                store.retain(conversations.enrich(conversations.conversation()))
            except BoundaryError:
                pass
            except Exception as leaked:
                pytest.fail(f"a non-boundary exception crossed the boundary: {leaked!r}")

    def test_ms11_a_large_conversation_is_one_document_to_its_caller(self) -> None:
        """§9 may deliver one document in parts; a caller must not be able to tell (FR-010)."""
        store = self.make_store()
        long_text = " ".join(f"Wolverine handles step {index}." for index in range(500))
        enriched = conversations.enrich(conversations.conversation("large1", text=long_text))

        store.retain(enriched)
        first = store.recall(PHRASE)
        store.retain(enriched)

        assert len(store.recall(PHRASE)) == len(first)
