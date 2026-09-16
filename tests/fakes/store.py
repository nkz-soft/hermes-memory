"""Two in-memory memory stores, and the reason there are two.

ADR-001 accepts a deliberate dependency on Hindsight and pays for it with an exit: the archive and
the normalized model are independent of the engine, so the backend can be replaced. That claim is
either demonstrated or merely asserted, and one implementation demonstrates nothing.

So there are two, with genuinely different internals — one scans, one keeps a tag index — and the
pipeline test runs over both. If replacing the store took more than the line that chooses it, the
interface would be wrong (SC-006).

Neither performs I/O, and neither knows what a bank is.
"""

from __future__ import annotations

from collections import defaultdict

from hermes_memory.memory.interface import (
    MemoryStoreRejected,
    MemoryStoreUnavailable,
    RecallResult,
)
from hermes_memory.normalization import AnyTag, EnrichedConversation


def _content(enriched: EnrichedConversation) -> str:
    """One logical document, as §7 requires — not one item per message."""
    return "\n".join(message.text for message in enriched.conversation.messages if message.text)


class InMemoryMemoryStore:
    """Keeps documents in a dictionary and scans them on recall."""

    def __init__(self, *, rejects: bool = False, unavailable: bool = False) -> None:
        self._documents: dict[str, EnrichedConversation] = {}
        self._rejects = rejects
        self._unavailable = unavailable

    @property
    def retained(self) -> tuple[str, ...]:
        """Which documents are held, for a pipeline test — not part of the boundary."""
        return tuple(self._documents)

    def retain(self, enriched: EnrichedConversation) -> None:
        self._refuse_if_broken(enriched.document_id)
        # Assignment rather than append: one logical document, replaced (§9's `update_mode`).
        self._documents[enriched.document_id] = enriched

    def recall(
        self,
        query: str,
        tags: tuple[AnyTag, ...] = (),
        limit: int | None = None,
    ) -> tuple[RecallResult, ...]:
        self._refuse_if_broken(None)
        matches = [
            enriched
            for enriched in self._documents.values()
            if query.lower() in _content(enriched).lower()
            and all(tag in enriched.tags for tag in tags)
        ]
        results = tuple(
            RecallResult(content=_content(enriched), provenance=enriched.provenance)
            for enriched in matches
        )
        return results[:limit] if limit is not None else results

    def _refuse_if_broken(self, subject: str | None) -> None:
        if self._rejects:
            raise MemoryStoreRejected("the engine refused the call", subject=subject)
        if self._unavailable:
            raise MemoryStoreUnavailable("the engine could not be reached", subject=subject)


class TagIndexedMemoryStore:
    """The same contract, kept differently: a tag index consulted before anything is read.

    Exists to be swapped in for `InMemoryMemoryStore` in the pipeline test. Its recall narrows by
    tag first and scans only the candidates, so a caller that depended on the scanning store's
    ordering or on its incidental behaviour would notice — which is the point.
    """

    def __init__(self) -> None:
        self._documents: dict[str, EnrichedConversation] = {}
        self._by_tag: dict[str, set[str]] = defaultdict(set)

    @property
    def retained(self) -> tuple[str, ...]:
        return tuple(self._documents)

    def retain(self, enriched: EnrichedConversation) -> None:
        document_id = enriched.document_id
        for holders in self._by_tag.values():
            holders.discard(document_id)

        self._documents[document_id] = enriched
        for tag in enriched.tags:
            self._by_tag[str(tag)].add(document_id)

    def recall(
        self,
        query: str,
        tags: tuple[AnyTag, ...] = (),
        limit: int | None = None,
    ) -> tuple[RecallResult, ...]:
        if tags:
            candidates: set[str] = set(self._documents)
            for tag in tags:
                candidates &= self._by_tag.get(str(tag), set())
        else:
            candidates = set(self._documents)

        results = tuple(
            RecallResult(
                content=_content(self._documents[document_id]),
                provenance=self._documents[document_id].provenance,
                score=1.0,
            )
            for document_id in sorted(candidates)
            if query.lower() in _content(self._documents[document_id]).lower()
        )
        return results[:limit] if limit is not None else results
