"""The contract every import state must satisfy (ARCHITECTURE.md §8, row 6).

Rules IS-1 to IS-8 of specs/007-boundary-interfaces/contracts/contract-suites.md.

IS-6 tests `may_skip` rather than the store, on purpose: the rule lives in the domain so that
#14's SQLite store and a later PostgreSQL one cannot disagree about what "unchanged" means
(research.md R10). What a store is held to is narrower and more testable — remember what you were
told, including the failures.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from hermes_memory.errors import BoundaryError
from hermes_memory.ingestion import (
    ImportRecord,
    ImportState,
    ImportStateCorrupt,
    ImportStateUnavailable,
    ImportStatus,
    may_skip,
)
from hermes_memory.normalization import Source

HASH = "a" * 64
OTHER_HASH = "b" * 64
RECORDED_AT = datetime(2026, 9, 16, 10, 0, tzinfo=UTC)


def record(
    status: ImportStatus = ImportStatus.IMPORTED,
    *,
    source: Source = Source.CHATGPT,
    source_id: str = "abc123",
    content_hash: str = HASH,
) -> ImportRecord:
    return ImportRecord(
        source=source,
        source_id=source_id,
        content_hash=content_hash,
        document_id=f"{source}:{source_id}",
        recorded_at=RECORDED_AT,
        status=status,
        error="the gateway timed out" if status is ImportStatus.FAILED else None,
    )


class ImportStateContract:
    """Subclass this and implement `make_state`."""

    # --- what a subclass supplies ---------------------------------------------------------------

    def make_state(self) -> ImportState:
        raise NotImplementedError

    def make_unavailable_state(self) -> ImportState | None:
        """Return a state store that cannot be reached, or `None`."""
        return None

    def make_corrupt_state(self) -> ImportState | None:
        """Return a state store whose contents cannot be read as state, or `None`."""
        return None

    # --- the contract ---------------------------------------------------------------------------

    def test_is1_a_conversation_never_recorded_is_unknown(self) -> None:
        """The state of everything on the first run."""
        assert self.make_state().find(Source.CHATGPT, "never-seen") is None

    def test_is2_a_recorded_conversation_comes_back_as_it_was_written(self) -> None:
        state = self.make_state()
        written = record()

        state.record(written)

        assert state.find(Source.CHATGPT, "abc123") == written

    def test_is3_recording_twice_leaves_the_later_record(self) -> None:
        state = self.make_state()
        state.record(record(content_hash=HASH))
        state.record(record(content_hash=OTHER_HASH))

        found = state.find(Source.CHATGPT, "abc123")

        assert found is not None
        assert found.content_hash == OTHER_HASH

    def test_is4_a_failure_is_remembered_and_is_not_the_same_as_nothing(self) -> None:
        """§18 — a resume must tell a conversation it never reached from one that broke."""
        state = self.make_state()
        state.record(record(ImportStatus.FAILED))

        found = state.find(Source.CHATGPT, "abc123")

        assert found is not None
        assert found.status is ImportStatus.FAILED
        assert found.error

    def test_is5_records_are_keyed_by_source_as_well_as_native_id(self) -> None:
        """Two sources may mint one id; a collision would skip a conversation never imported."""
        state = self.make_state()
        state.record(record(source=Source.CHATGPT, source_id="shared"))
        state.record(record(source=Source.CODEX, source_id="shared", content_hash=OTHER_HASH))

        from_chatgpt = state.find(Source.CHATGPT, "shared")
        from_codex = state.find(Source.CODEX, "shared")

        assert from_chatgpt is not None
        assert from_codex is not None
        assert from_chatgpt.content_hash == HASH
        assert from_codex.content_hash == OTHER_HASH

    def test_is6_the_skip_rule_reads_the_record_the_same_way_for_every_store(self) -> None:
        """§17 — one rule, so that two stores cannot disagree about "unchanged" (research R10)."""
        state = self.make_state()
        state.record(record(ImportStatus.IMPORTED))

        assert may_skip(state.find(Source.CHATGPT, "abc123"), HASH) is True
        assert may_skip(state.find(Source.CHATGPT, "abc123"), OTHER_HASH) is False
        assert may_skip(state.find(Source.CHATGPT, "never-seen"), HASH) is False

        state.record(record(ImportStatus.FAILED))
        assert may_skip(state.find(Source.CHATGPT, "abc123"), HASH) is False

    def test_is7_an_unreachable_store_is_retryable_and_corrupt_state_is_not(self) -> None:
        unavailable = self.make_unavailable_state()
        if unavailable is not None:
            with pytest.raises(ImportStateUnavailable) as raised:
                unavailable.find(Source.CHATGPT, "abc123")
            assert raised.value.retryable is True

        corrupt = self.make_corrupt_state()
        if corrupt is not None:
            with pytest.raises(ImportStateCorrupt) as broken:
                corrupt.find(Source.CHATGPT, "abc123")
            assert broken.value.retryable is False

        if unavailable is None and corrupt is None:
            pytest.skip("this implementation cannot be made to fail")

    def test_is8_no_library_exception_crosses_the_boundary(self) -> None:
        for state in (self.make_unavailable_state(), self.make_corrupt_state()):
            if state is None:
                continue
            try:
                state.find(Source.CHATGPT, "abc123")
            except BoundaryError:
                pass
            except Exception as leaked:
                pytest.fail(f"a non-boundary exception crossed the boundary: {leaked!r}")
