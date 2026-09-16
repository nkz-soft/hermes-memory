"""An in-memory raw archive: both forms, keyed by document id.

This is the fake most likely to be mistaken for a real implementation, which is exactly why it
lives here and not in `src/` (research.md R12, FR-027). It is thirty lines and it loses everything
on exit — the opposite of what Principle I asks the archive to be. #13 writes the real one.
"""

from __future__ import annotations

from hermes_memory.archive import (
    ArchiveDocumentNotFound,
    ArchiveRejected,
    ArchiveUnavailable,
    OriginalPayload,
)
from hermes_memory.normalization import EnrichedConversation


class InMemoryRawArchive:
    """Holds both forms in a dictionary, last write wins."""

    def __init__(self, *, unavailable: bool = False, rejects: bool = False) -> None:
        self._documents: dict[str, tuple[EnrichedConversation, OriginalPayload]] = {}
        self._unavailable = unavailable
        self._rejects = rejects

    @property
    def document_ids(self) -> frozenset[str]:
        """What is held, for a pipeline test to assert against — not part of the boundary."""
        return frozenset(self._documents)

    def store(self, enriched: EnrichedConversation, original: OriginalPayload) -> None:
        if self._unavailable:
            raise ArchiveUnavailable(
                "the archive could not be reached", subject=enriched.document_id
            )
        if self._rejects:
            raise ArchiveRejected("the archive refused this document", subject=enriched.document_id)

        self._documents[enriched.document_id] = (enriched, original)

    def load(self, document_id: str) -> EnrichedConversation:
        if self._unavailable:
            raise ArchiveUnavailable("the archive could not be reached", subject=document_id)
        if document_id not in self._documents:
            raise ArchiveDocumentNotFound(document_id)
        return self._documents[document_id][0]

    def load_original(self, document_id: str) -> OriginalPayload:
        if self._unavailable:
            raise ArchiveUnavailable("the archive could not be reached", subject=document_id)
        if document_id not in self._documents:
            raise ArchiveDocumentNotFound(document_id)
        return self._documents[document_id][1]
