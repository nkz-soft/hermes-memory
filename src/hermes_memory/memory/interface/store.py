"""The memory store boundary (ARCHITECTURE.md §8, row 5).

> `retain` / `recall` — the only component aware of Hindsight.

This is the module ADR-001's exit strategy rests on. The dependency on Hindsight is deliberate and
not permanent, and the architecture survives it only while the dependency stays in one place: the
*implementation* in `memory/hindsight` (#16). Nothing here may name a Hindsight concept — no bank,
no item, no retain mission, no update mode, no operation id, no endpoint. `retain` and `recall` are
§16's words, and they stay because they are the architecture's, not the engine's.

The temptation this module is written against is small and specific: an inspection method. Proving
"retaining twice creates no duplicate" is easiest if the store can be asked how many documents it
holds — and no memory engine owes us that. A count would be a Hindsight-shaped hole in the
abstraction, so the promise is tested through `recall`, which every implementation has
(specs/007-boundary-interfaces/research.md R9).

Contract: specs/007-boundary-interfaces/contracts/interfaces.md, rules MS-1 to MS-11.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from hermes_memory.errors import PermanentBoundaryError, TransientBoundaryError
from hermes_memory.normalization import AnyTag, EnrichedConversation, Provenance
from hermes_memory.normalization.base import FrozenModel, Text

__all__ = ["MemoryStore", "MemoryStoreRejected", "MemoryStoreUnavailable", "RecallResult"]

BOUNDARY = "memory store"


class RecallResult(FrozenModel):
    """One match from a recall.

    Carries the provenance the item was retained with (Principle II), so a caller can say where a
    recalled fact came from without asking the engine a second question.
    """

    content: Text
    provenance: Provenance
    score: float | None = None
    """Whatever the implementation means by relevance.

    Comparable within one result set and nowhere else — not across calls, not across
    implementations, and never a number to threshold on. Declared because every retrieval system
    ranks and #23 and #31 will want the order; promising more would be promising something about
    Hindsight.
    """


class MemoryStoreRejected(PermanentBoundaryError):
    """The engine refused the call: rejected, unauthorized, or invalid input.

    §18's never-retry list, which is why this is permanent and cannot be made to look otherwise.

    The chained cause is **not safe to render**: an HTTP client's exception can carry a URL, a
    header or a body holding a credential. §18's failure report shows this error, never the chain
    (contracts/errors.md E5).
    """

    def __init__(self, message: str, *, subject: str | None = None) -> None:
        super().__init__(BOUNDARY, message, subject=subject)


class MemoryStoreUnavailable(TransientBoundaryError):
    """The engine could not be reached, or asked us back later: timeout, reset, 429, 502, 503, 504.

    §18's retry list. #20 repeats exactly this branch, with backoff and jitter.

    The chained cause is **not safe to render**, for the same reason as `MemoryStoreRejected`.
    """

    def __init__(self, message: str, *, subject: str | None = None) -> None:
        super().__init__(BOUNDARY, message, subject=subject)


@runtime_checkable
class MemoryStore(Protocol):
    """Retains conversations as memory, and recalls against them."""

    def retain(self, enriched: EnrichedConversation) -> None:
        """Send one conversation as one logical document.

        One document, not one item per message (§7): extraction must see the whole context.

        Retaining the same conversation twice leaves one logical document (MS-2) — promised to the
        caller here, achieved however the implementation likes. #16 will lean on `document_id`
        upsert and an idempotency key (§9); another engine may do something else entirely, and no
        caller can tell.

        A conversation too large for a single call is the implementation's problem, and a caller
        cannot observe whether it was delivered in parts (MS-11).

        Raises:
            MemoryStoreRejected: refused, unauthorized or invalid input.
            MemoryStoreUnavailable: timeout, reset or a retryable status.
        """
        ...

    def recall(
        self,
        query: str,
        tags: tuple[AnyTag, ...] = (),
        limit: int | None = None,
    ) -> tuple[RecallResult, ...]:
        """Return what the store has that answers this query.

        `tags` narrow the search — the `project:` scoping of ADR-002 is one of these, not a
        separate store. `limit` bounds the results. Matching nothing returns an empty tuple, which
        is an answer and not a failure (MS-4).

        §16's `reflect` is deliberately absent: it is used by #31 over accumulated memory, and a
        method with no caller is a contract nobody has tested (research.md R9).

        Raises:
            MemoryStoreRejected: refused, unauthorized or invalid input.
            MemoryStoreUnavailable: timeout, reset or a retryable status.
        """
        ...
