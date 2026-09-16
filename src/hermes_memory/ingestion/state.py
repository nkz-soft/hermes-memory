"""The import state boundary (ARCHITECTURE.md §8, row 6).

> Track what has already been imported.

§17 keeps idempotency in two independent layers: `document_id` gives upsert on the Hindsight side,
and a local record gives the *skip* on ours. Only the second one saves the extraction cost, which
is why it exists at all — a conversation whose source id and content hash are unchanged is skipped
before any call is made.

It lives in `ingestion/` rather than in a module of its own because §17 calls it the importer side
of idempotency, and because the constitution's module tree records no module for it — adding one
would be an amendment (specs/007-boundary-interfaces/research.md R2).

Contract: specs/007-boundary-interfaces/contracts/interfaces.md, rules IS-1 to IS-8.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import Field, model_validator

from hermes_memory.errors import PermanentBoundaryError, TransientBoundaryError
from hermes_memory.normalization import Source
from hermes_memory.normalization.base import FrozenModel, OpaqueIdentifier, Text, Timestamp

__all__ = [
    "ImportRecord",
    "ImportState",
    "ImportStateCorrupt",
    "ImportStateUnavailable",
    "ImportStatus",
    "may_skip",
]

BOUNDARY = "import state"


class ImportStatus(StrEnum):
    """What became of one conversation in one run (§18: imported / skipped / failed)."""

    IMPORTED = "imported"
    SKIPPED = "skipped"
    FAILED = "failed"


class ImportRecord(FrozenModel):
    """What the importer remembers about one conversation (§17).

    `content_hash` and `document_id` are #8's — computed from the conversation and derived from the
    source and its native id respectively. The importer stores them; it never invents them
    (Principle II).
    """

    source: Source
    source_id: OpaqueIdentifier
    content_hash: Text = Field(min_length=1)
    document_id: Text = Field(min_length=1)
    recorded_at: Timestamp
    """When the importer wrote this record.

    The import clock, and the one place it is allowed to be: §11 forbids it standing in for the
    conversation's time, and `Conversation` has no field it could be written into.
    """
    status: ImportStatus
    error: Text | None = None
    """Why it failed, for §18's report. Carries no conversation content and no credential (E5)."""

    @model_validator(mode="after")
    def _only_a_failure_explains_itself(self) -> ImportRecord:
        """An imported conversation carrying an error is a record nobody can act on."""
        if self.error is not None and self.status is not ImportStatus.FAILED:
            raise ValueError(
                f"only a failed record carries an error, got status {self.status} with "
                f"error {self.error!r}"
            )
        return self


def may_skip(record: ImportRecord | None, content_hash: str) -> bool:
    """Whether this conversation can be skipped before any call is made (§17).

    A function rather than a method on `ImportState`, and that is the decision this module exists to
    hold (research.md R10). If each store answered the question itself, #14's SQLite store and a
    later PostgreSQL one could disagree about what "unchanged" means, and both would pass a suite
    that let them define it. Stores answer only "what do you remember about this source id"; the
    rule is here, once.

    True only for a conversation we imported, whose content has not moved since. `None` is the first
    run; a failed record is work to retry (§18); a skipped one records that we did nothing, and
    reading it as success would strand the conversation forever.
    """
    if record is None:
        return False
    return record.status is ImportStatus.IMPORTED and record.content_hash == content_hash


class ImportStateCorrupt(PermanentBoundaryError):
    """The stored state cannot be read as state. Repeating the call cannot help."""

    def __init__(self, message: str, *, subject: str | None = None) -> None:
        super().__init__(BOUNDARY, message, subject=subject)


class ImportStateUnavailable(TransientBoundaryError):
    """The store could not be reached — a locked database, a busy file."""

    def __init__(self, message: str, *, subject: str | None = None) -> None:
        super().__init__(BOUNDARY, message, subject=subject)


@runtime_checkable
class ImportState(Protocol):
    """Remembers what has been imported, so a re-run does not pay for extraction twice."""

    def record(self, record: ImportRecord) -> None:
        """Remember the outcome of one conversation's import.

        Last write wins per `(source, source_id)` (IS-3): a conversation imported, then re-imported
        after a change, has one current record.

        Failures are recorded, not omitted (IS-4, §18). "No record" and "a record saying it failed"
        are different answers, and a resume that cannot tell them apart cannot tell a conversation
        it never reached from one that broke between the archive write and the retain call.

        Raises:
            ImportStateUnavailable: the store could not be reached.
            ImportStateCorrupt: the stored state could not be read.
        """
        ...

    def find(self, source: Source, source_id: str) -> ImportRecord | None:
        """What is remembered about this conversation, or `None` if nothing is (IS-1).

        Keyed by source *and* native id: two sources may mint the same identifier, and a collision
        here would skip a conversation that was never imported (IS-5).

        Answering this contacts no other boundary — that is the whole point of the skip (§17).

        Raises:
            ImportStateUnavailable: the store could not be reached.
            ImportStateCorrupt: the stored state could not be read.
        """
        ...
