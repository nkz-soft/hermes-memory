"""The contract every raw archive must satisfy (ARCHITECTURE.md §8, row 4).

Rules RA-1 to RA-9 of specs/007-boundary-interfaces/contracts/contract-suites.md.

Principle I makes this the source of truth, so the rules that look pedantic are the ones that
matter: what goes in comes back *equal*, with an equal content hash, and the original bytes come
back byte-identical. A field quietly dropped here parses fine and replays wrong, years later, out
of the archive that was supposed to be the thing that could not be lost.
"""

from __future__ import annotations

import pytest

from hermes_memory.archive import (
    ArchiveDocumentNotFound,
    ArchiveRejected,
    ArchiveUnavailable,
    OriginalPayload,
    RawArchive,
)
from hermes_memory.errors import BoundaryError
from tests.contracts import conversations

PAYLOAD = OriginalPayload(content=b'{"conversation": "as exported"}', media_type="application/json")
SECOND_PAYLOAD = OriginalPayload(
    content=b'{"conversation": "re-exported"}', media_type="application/json"
)


class RawArchiveContract:
    """Subclass this and implement `make_archive`."""

    # --- what a subclass supplies ---------------------------------------------------------------

    def make_archive(self) -> RawArchive:
        raise NotImplementedError

    def make_unavailable_archive(self) -> RawArchive | None:
        """Return an archive that cannot be reached, or `None`."""
        return None

    def make_rejecting_archive(self) -> RawArchive | None:
        """Return an archive that refuses what it is given, or `None`."""
        return None

    def reopen(self, archive: RawArchive) -> RawArchive | None:
        """Return a *new* archive over the same storage as this one, or `None`.

        The way RA-9 tells "stored" from "remembered by this object": #13 on local storage returns
        a fresh instance over the same directory. An implementation that cannot be reopened says so,
        and RA-9 is skipped rather than passed on the strength of an in-memory cache.
        """
        return None

    # --- the contract ---------------------------------------------------------------------------

    def test_ra1_the_normalized_form_comes_back_equal(self) -> None:
        archive = self.make_archive()
        enriched = conversations.enrich(conversations.conversation())

        archive.store(enriched, PAYLOAD)
        loaded = archive.load(enriched.document_id)

        assert loaded == enriched
        assert loaded.content_hash() == enriched.content_hash()

    def test_ra2_the_original_comes_back_byte_identical(self) -> None:
        archive = self.make_archive()
        enriched = conversations.enrich(conversations.conversation())

        archive.store(enriched, PAYLOAD)
        loaded = archive.load_original(enriched.document_id)

        assert loaded.content == PAYLOAD.content
        assert loaded.media_type == PAYLOAD.media_type

    def test_ra3_storing_twice_leaves_one_document_and_the_second_wins(self) -> None:
        """A re-run after a crash must not multiply the source of truth — either form of it."""
        archive = self.make_archive()
        first = conversations.enrich(conversations.conversation(text="The first answer."))
        second = conversations.enrich(conversations.conversation(text="The corrected answer."))
        assert first.document_id == second.document_id

        archive.store(first, PAYLOAD)
        archive.store(second, SECOND_PAYLOAD)

        assert archive.load(second.document_id) == second
        assert archive.load_original(second.document_id).content == SECOND_PAYLOAD.content

    def test_ra4_loading_an_unknown_document_is_a_declared_permanent_failure(self) -> None:
        with pytest.raises(ArchiveDocumentNotFound) as raised:
            self.make_archive().load("chatgpt:never-stored")

        assert raised.value.retryable is False

    def test_ra5_loading_an_unknown_original_is_the_same_failure(self) -> None:
        with pytest.raises(ArchiveDocumentNotFound):
            self.make_archive().load_original("chatgpt:never-stored")

    def test_ra6_a_conversation_using_every_field_round_trips_unchanged(self) -> None:
        archive = self.make_archive()
        enriched = conversations.enrich(conversations.conversation_using_every_field())

        archive.store(enriched, PAYLOAD)

        assert archive.load(enriched.document_id) == enriched

    def test_ra7_an_unreachable_archive_is_retryable_and_a_refusal_is_not(self) -> None:
        enriched = conversations.enrich(conversations.conversation())

        unavailable = self.make_unavailable_archive()
        if unavailable is not None:
            with pytest.raises(ArchiveUnavailable) as raised:
                unavailable.store(enriched, PAYLOAD)
            assert raised.value.retryable is True

        rejecting = self.make_rejecting_archive()
        if rejecting is not None:
            with pytest.raises(ArchiveRejected) as refused:
                rejecting.store(enriched, PAYLOAD)
            assert refused.value.retryable is False

        if unavailable is None and rejecting is None:
            pytest.skip("this implementation cannot be made to fail")

    def test_ra8_no_library_exception_crosses_the_boundary(self) -> None:
        enriched = conversations.enrich(conversations.conversation())

        for archive in (self.make_unavailable_archive(), self.make_rejecting_archive()):
            if archive is None:
                continue
            try:
                archive.store(enriched, PAYLOAD)
            except BoundaryError:
                pass
            except Exception as leaked:
                pytest.fail(f"a non-boundary exception crossed the boundary: {leaked!r}")

    def test_ra9_a_stored_document_survives_reopening_the_archive(self) -> None:
        """Principle I — durable once `store` returns, not merely remembered by the object.

        §7 archives before retaining, so an archive that held the document only in memory when the
        process died would leave the derived memory ahead of the source of truth.
        """
        archive = self.make_archive()
        enriched = conversations.enrich(conversations.conversation_using_every_field())
        archive.store(enriched, PAYLOAD)

        reopened = self.reopen(archive)
        if reopened is None:
            pytest.skip("this implementation cannot be reopened over the same storage")
        assert reopened is not archive, "reopen must return a new instance, not the same object"

        assert reopened.load(enriched.document_id) == enriched
        assert reopened.load_original(enriched.document_id).content == PAYLOAD.content
