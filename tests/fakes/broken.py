"""Six implementations that each break exactly one rule.

They exist so that every contract suite can be watched failing (FR-020). A suite that asserts
nothing passes quietly — and then certifies six implementations as correct, which is the expensive
version of the mistake this repository already guards against elsewhere
(``test_the_behaviour_guard_still_bites``).

Each breakage is a plausible mistake rather than an absurd one. That is deliberate: a suite that
only catches nonsense catches nothing worth catching.
"""

from __future__ import annotations

from collections.abc import Iterator

from hermes_memory.archive import ArchiveDocumentNotFound, OriginalPayload
from hermes_memory.classification import ProjectClassifier
from hermes_memory.errors import PermanentBoundaryError
from hermes_memory.ingestion import (
    ImportRecord,
    ImportStatus,
    SourceConversation,
    SourceFormatError,
)
from hermes_memory.memory.interface import RecallResult
from hermes_memory.normalization import (
    AnyTag,
    Conversation,
    EnrichedConversation,
    ProjectTag,
    Source,
)
from hermes_memory.sanitization import RedactionCategory, RedactionReport


class SourceThatStopsAtTheFirstBadConversation:
    """Breaks CS-5: a generator, so the first `SourceFormatError` ends the iteration for good.

    The most likely way to write this boundary, and the reason CS-5 is a rule.
    """

    def __init__(
        self, conversations: tuple[SourceConversation, ...], unreadable: frozenset[str]
    ) -> None:
        self.source = Source.CHATGPT
        self._conversations = conversations
        self._unreadable = unreadable

    def read(self) -> Iterator[SourceConversation]:
        for read in self._conversations:
            if read.conversation.source_id in self._unreadable:
                raise SourceFormatError("unparsable", subject=read.conversation.source_id)
            yield read


class SanitizerThatReportsWhatItDidNotDo:
    """Breaks SS-3: counts a redaction it never performed, and passes the secret through.

    The failure Principle V is written against, wearing the appearance of compliance: the report
    looks right, the logs look right, and the credential is in the bank.
    """

    def __init__(self, category: RedactionCategory = RedactionCategory.PASSWORD) -> None:
        self._category = category

    def sanitize(self, conversation: Conversation) -> tuple[Conversation, RedactionReport]:
        return conversation, RedactionReport(counts={self._category: 1})


class ClassifierThatRaisesInsteadOfAnsweringUnknown:
    """Breaks PC-2 and PC-5: treats §15's ordinary case as a failure."""

    def classify(self, conversation: Conversation) -> ProjectTag:
        raise PermanentBoundaryError(
            "project classifier", "no rule matched", subject=conversation.document_id
        )


class ArchiveThatDropsMessageTimestamps:
    """Breaks RA-1: stores a conversation that parses fine and replays wrong.

    The loss is invisible until someone re-runs ingestion from the archive, at which point the
    archive holding years of history is the lossy one (Principle I).
    """

    def __init__(self) -> None:
        self._documents: dict[str, tuple[EnrichedConversation, OriginalPayload]] = {}

    def store(self, enriched: EnrichedConversation, original: OriginalPayload) -> None:
        stripped = enriched.conversation.model_copy(
            update={
                "messages": tuple(
                    message.model_copy(update={"sent_at": None})
                    for message in enriched.conversation.messages
                )
            }
        )
        self._documents[enriched.document_id] = (
            enriched.model_copy(update={"conversation": stripped}),
            original,
        )

    def load(self, document_id: str) -> EnrichedConversation:
        if document_id not in self._documents:
            raise ArchiveDocumentNotFound(document_id)
        return self._documents[document_id][0]

    def load_original(self, document_id: str) -> OriginalPayload:
        if document_id not in self._documents:
            raise ArchiveDocumentNotFound(document_id)
        return self._documents[document_id][1]


class StoreThatAppendsOnEveryRetain:
    """Breaks MS-2: a second import of unchanged content duplicates the document.

    What Principle II costs when it is missed: the bank fills with the same conversation, and every
    recall answers with it twice.
    """

    def __init__(self) -> None:
        self._documents: list[EnrichedConversation] = []

    def retain(self, enriched: EnrichedConversation) -> None:
        self._documents.append(enriched)

    def recall(
        self,
        query: str,
        tags: tuple[AnyTag, ...] = (),
        limit: int | None = None,
    ) -> tuple[RecallResult, ...]:
        results = tuple(
            RecallResult(
                content="\n".join(message.text for message in enriched.conversation.messages),
                provenance=enriched.provenance,
            )
            for enriched in self._documents
            if query.lower()
            in "\n".join(message.text for message in enriched.conversation.messages).lower()
            and all(tag in enriched.tags for tag in tags)
        )
        return results[:limit] if limit is not None else results


class StateThatRemembersOnlySuccesses:
    """Breaks IS-4: a failed import looks exactly like one that was never attempted.

    §18 requires the outcome of every conversation to be recorded. Without the failures, a resume
    cannot tell a conversation it never reached from one that broke after the archive write.
    """

    def __init__(self) -> None:
        self._records: dict[tuple[Source, str], ImportRecord] = {}

    def record(self, record: ImportRecord) -> None:
        if record.status is ImportStatus.FAILED:
            return
        self._records[(record.source, record.source_id)] = record

    def find(self, source: Source, source_id: str) -> ImportRecord | None:
        return self._records.get((source, source_id))


BROKEN_CLASSIFIER: ProjectClassifier = ClassifierThatRaisesInsteadOfAnsweringUnknown()
