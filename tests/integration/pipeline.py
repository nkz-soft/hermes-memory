"""The smallest arrangement of the six boundaries in §7's order.

**This is not #19's pipeline.** It is a test harness: the fewest lines that put the six interfaces
in contact so that a mistake in one of them shows up as a failure rather than as a discovery made
by whoever implements the fifth. #19 writes the real one, with the logging of §18, the retry of
#20, the dry run of #22 and a command surface.

What it does per conversation, in the order §7 gives:

```text
read → skip? → sanitize → classify → enrich → archive → retain → record
```

Two decisions in here are worth reading rather than skimming, because both are places the obvious
version is wrong:

* **A skip writes no record.** §18's vocabulary — imported, skipped, failed — is the *run's report*.
  The import state answers one question, "may this be skipped next time", and overwriting an
  `imported` record with a `skipped` one would answer it wrongly on the third run: the conversation
  would be re-imported and re-extracted forever. The report says skipped; the state keeps what it
  knew.
* **A failure is recorded and the run continues.** §18 requires both, and the second is what makes
  the first worth having.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime

from hermes_memory.archive import RawArchive
from hermes_memory.classification import ProjectClassifier
from hermes_memory.errors import BoundaryError
from hermes_memory.ingestion import (
    ConversationSource,
    ImportRecord,
    ImportState,
    ImportStatus,
    may_skip,
)
from hermes_memory.memory.interface import MemoryStore
from hermes_memory.normalization import (
    EnrichedConversation,
    ProjectTag,
    Provenance,
    SourceTag,
)
from hermes_memory.sanitization import RedactionReport, SecretSanitizer


@dataclass(frozen=True)
class Failure:
    """§18's failure line: which conversation, what went wrong, and whether a retry could help."""

    source_id: str
    error: BoundaryError

    @property
    def retryable(self) -> bool:
        return self.error.retryable


@dataclass
class ImportOutcome:
    """What a run did, in §18's vocabulary."""

    imported: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[Failure] = field(default_factory=list)
    redactions: RedactionReport = field(default_factory=RedactionReport)


@dataclass(frozen=True)
class Pipeline:
    """The six boundaries, held only as their interfaces."""

    source: ConversationSource
    sanitizer: SecretSanitizer
    classifier: ProjectClassifier
    archive: RawArchive
    store: MemoryStore
    state: ImportState
    importer_version: str = "1"

    def run(self, *, now: datetime) -> ImportOutcome:
        outcome = ImportOutcome()

        for read in self._read_each(outcome):
            conversation = read.conversation
            try:
                remembered = self.state.find(conversation.source, conversation.source_id)
                if may_skip(remembered, conversation.content_hash()):
                    outcome.skipped.append(conversation.source_id)
                    continue

                sanitized, report = self.sanitizer.sanitize(conversation)
                project = self.classifier.classify(sanitized)
                enriched = self._enrich(sanitized, project, now=now)

                self.archive.store(enriched, read.original)
                self.store.retain(enriched)
                self._record(enriched, ImportStatus.IMPORTED, now=now)

                outcome.imported.append(conversation.source_id)
                outcome.redactions = _merge(outcome.redactions, report)
            except BoundaryError as failure:
                outcome.failed.append(Failure(conversation.source_id, failure))
                self._record_failure(conversation, failure, now=now)

        return outcome

    def _read_each(self, outcome: ImportOutcome) -> Iterator:
        """Iterate the source, surviving a conversation it cannot read (CS-5, §18)."""
        try:
            reader = self.source.read()
        except BoundaryError as failure:
            outcome.failed.append(Failure(failure.subject or "", failure))
            return

        while True:
            try:
                yield next(reader)
            except StopIteration:
                return
            except BoundaryError as failure:
                outcome.failed.append(Failure(failure.subject or "", failure))

    def _enrich(self, conversation, project: ProjectTag, *, now: datetime) -> EnrichedConversation:
        return EnrichedConversation(
            conversation=conversation,
            provenance=Provenance(
                source=conversation.source,
                source_id=conversation.source_id,
                project=project.value,
                title=conversation.title,
                imported_at=now,
                importer_version=self.importer_version,
            ),
            tags=(SourceTag(value=conversation.source), project),
        )

    def _record(
        self, enriched: EnrichedConversation, status: ImportStatus, *, now: datetime
    ) -> None:
        self.state.record(
            ImportRecord(
                source=enriched.conversation.source,
                source_id=enriched.conversation.source_id,
                content_hash=enriched.content_hash(),
                document_id=enriched.document_id,
                recorded_at=now,
                status=status,
            )
        )

    def _record_failure(self, conversation, failure: BoundaryError, *, now: datetime) -> None:
        self.state.record(
            ImportRecord(
                source=conversation.source,
                source_id=conversation.source_id,
                content_hash=conversation.content_hash(),
                document_id=conversation.document_id,
                recorded_at=now,
                status=ImportStatus.FAILED,
                # The boundary error, never its chained cause: the cause can carry a credential
                # (contracts/errors.md E5).
                error=failure.message,
            )
        )


def _merge(left: RedactionReport, right: RedactionReport) -> RedactionReport:
    counts = dict(left.counts)
    for category, count in right.counts.items():
        counts[category] = counts.get(category, 0) + count
    return RedactionReport(counts=counts)
