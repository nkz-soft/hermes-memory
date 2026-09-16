"""The raw archive boundary (ARCHITECTURE.md §8, row 4).

> Persist originals and normalized forms.

Principle I makes this the source of truth: `retain` is lossy extraction, so the originals must not
live only inside the memory engine, and ingestion must be re-runnable end to end from the archive
alone — without asking ChatGPT for another export.

Both forms, in one call, and that is the decision this module is shaped by. A re-run happens
because the *parser* was fixed, or the redaction rules changed, or the retain mission did; a replay
from the normalized form alone would faithfully reproduce the old parser's mistakes. An interface
that accepted only the normalized conversation would make Principle I unmeetable by construction,
and no later feature could repair it without changing every caller
(specs/007-boundary-interfaces/research.md R8).

What the archive is *on disk* is #13's to settle (§20). This carries bytes and a media type so that
#13 can choose.

Contract: specs/007-boundary-interfaces/contracts/interfaces.md, rules RA-1 to RA-9.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import Field

from hermes_memory.errors import PermanentBoundaryError, TransientBoundaryError
from hermes_memory.normalization import EnrichedConversation
from hermes_memory.normalization.base import FrozenModel, Text

__all__ = [
    "ArchiveDocumentNotFound",
    "ArchiveRejected",
    "ArchiveUnavailable",
    "OriginalPayload",
    "RawArchive",
]

BOUNDARY = "raw archive"


class OriginalPayload(FrozenModel):
    """The bytes a conversation was parsed from, kept so that a fixed parser can be re-run.

    The archive does not interpret either field. Empty content is allowed: an export can carry an
    empty conversation, and refusing it here would lose the fact that it existed.
    """

    content: bytes
    media_type: Text = Field(min_length=1)


class ArchiveDocumentNotFound(PermanentBoundaryError):
    """The archive does not hold this document.

    An ordinary answer during a resume, and an error rather than `None` deliberately: `load` is a
    demand for a document the caller believes exists, and a `None` flowing on silently is how a
    replay loses history (contracts/errors.md E7).

    Distinguishable from `ArchiveUnavailable`, which is a defect (FR-007).
    """

    def __init__(self, document_id: str) -> None:
        super().__init__(
            BOUNDARY, f"the archive holds no document {document_id!r}", subject=document_id
        )


class ArchiveRejected(PermanentBoundaryError):
    """The archive refused what it was given. Repeating the call cannot help."""

    def __init__(self, message: str, *, subject: str | None = None) -> None:
        super().__init__(BOUNDARY, message, subject=subject)


class ArchiveUnavailable(TransientBoundaryError):
    """The archive could not be reached — a locked file, a full disk, a network store away."""

    def __init__(self, message: str, *, subject: str | None = None) -> None:
        super().__init__(BOUNDARY, message, subject=subject)


@runtime_checkable
class RawArchive(Protocol):
    """Holds the originals and the normalized forms, independently of any memory engine."""

    def store(self, enriched: EnrichedConversation, original: OriginalPayload) -> None:
        """Persist both forms of one conversation, together.

        Both or neither: an archive holding a normalized conversation whose original is missing is
        the failure Principle I is about, and nothing downstream would notice until a replay.

        Idempotent by document id — storing twice leaves one document and the second store wins
        (RA-3), because a re-run after a crash must not multiply the source of truth.

        Durable before it returns (RA-9). §7 archives before retaining, so a deferred write that
        had not landed when the retain call failed would leave the derived memory ahead of the
        source of truth.

        Raises:
            ArchiveRejected: the archive refused the input.
            ArchiveUnavailable: the archive could not be reached.
        """
        ...

    def load(self, document_id: str) -> EnrichedConversation:
        """Return the normalized form stored under this document id.

        Equal to what was stored, with an equal content hash (RA-1). A field quietly dropped here
        is the expensive kind of loss: it is discovered on the day of the replay, by which time the
        archive holding years of history is the lossy one.

        Raises:
            ArchiveDocumentNotFound: no such document.
            ArchiveUnavailable: the archive could not be reached.
        """
        ...

    def load_original(self, document_id: str) -> OriginalPayload:
        """Return the original bytes stored under this document id, unchanged (RA-2).

        Raises:
            ArchiveDocumentNotFound: no such document.
            ArchiveUnavailable: the archive could not be reached.
        """
        ...
