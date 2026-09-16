"""The one domain rule this feature owns: when a conversation may be skipped (§17).

`may_skip` is a function rather than a method on `ImportState` deliberately (research.md R10). If
each store answered the question its own way, #14's SQLite store and a later PostgreSQL one could
disagree about what "unchanged" means — and both would pass a suite that let them define it. The
disagreement would surface as an extraction bill, which is the thing Principle II exists to
prevent.
"""

from __future__ import annotations

from datetime import UTC, datetime

from hermes_memory.ingestion import ImportRecord, ImportStatus, may_skip
from hermes_memory.normalization import Source

HASH = "a" * 64
OTHER_HASH = "b" * 64
NOW = datetime(2026, 9, 16, 10, 0, tzinfo=UTC)


def record(status: ImportStatus, content_hash: str = HASH) -> ImportRecord:
    return ImportRecord(
        source=Source.CHATGPT,
        source_id="abc123",
        content_hash=content_hash,
        document_id="chatgpt:abc123",
        recorded_at=NOW,
        status=status,
        error="the gateway timed out" if status is ImportStatus.FAILED else None,
    )


def test_an_imported_conversation_whose_content_has_not_moved_is_skipped() -> None:
    """§17 — the skip that keeps a refresh from paying for extraction twice."""
    assert may_skip(record(ImportStatus.IMPORTED), HASH) is True


def test_a_conversation_never_seen_is_not_skipped() -> None:
    """IS-1 — the state of everything on the first run."""
    assert may_skip(None, HASH) is False


def test_a_changed_conversation_is_not_skipped() -> None:
    """ADR-006: a refreshed export brings new messages, and they are the point of the refresh."""
    assert may_skip(record(ImportStatus.IMPORTED, content_hash=OTHER_HASH), HASH) is False


def test_a_failed_import_is_retried_rather_than_skipped() -> None:
    """§18 — and the reason a failure is recorded at all rather than omitted (research R10)."""
    assert may_skip(record(ImportStatus.FAILED), HASH) is False
