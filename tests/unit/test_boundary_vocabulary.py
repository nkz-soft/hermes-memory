"""User Story 1's independent test, run rather than asserted (SC-001).

The story is that the author of #9 can declare the six boundaries of ARCHITECTURE.md §8 against
this model without inventing a conversation-shaped type. That claim is cheap to make in a
specification and worth nothing until someone writes the six signatures — so they are written here,
against the module and nothing else, and a pipeline assembled from trivial in-memory
implementations is run end to end.

**This is not #9.** The protocols below carry no error semantics, no contract suite and no fakes
worth reusing; #9 defines those, and defines them properly. What this pins is only the vocabulary:
that each boundary can say what it takes and returns in the words this module supplies.

Two boundaries legitimately need a type of their own — the sanitizer's report of what it redacted,
and the import state's record — and both are declared here as the placeholders they are. SC-001
forbids a second way of describing a conversation, not every type a boundary will ever need.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import NamedTuple, Protocol, runtime_checkable

from hermes_memory.normalization import (
    AnyTag,
    Conversation,
    EnrichedConversation,
    Message,
    ProjectTag,
    Provenance,
    Role,
    Source,
    SourceTag,
)

# --- the two types the boundaries own, which this module deliberately does not define -----------


class Redaction(NamedTuple):
    """A placeholder for what the sanitizer reports (§8, #12)."""

    category: str
    count: int


class ImportRecord(NamedTuple):
    """A placeholder for what the import state remembers (§17, #14)."""

    source_id: str
    content_hash: str
    document_id: str


# --- the six boundaries of §8, in this module's vocabulary -------------------------------------


@runtime_checkable
class ConversationSource(Protocol):
    """Read one source format, yield normalized conversations."""

    def read(self) -> Iterable[Conversation]: ...


@runtime_checkable
class SecretSanitizer(Protocol):
    """Redact secrets, report what was redacted."""

    def sanitize(
        self, conversation: Conversation
    ) -> tuple[Conversation, tuple[Redaction, ...]]: ...


@runtime_checkable
class ProjectClassifier(Protocol):
    """Determine the project for a conversation."""

    def classify(self, conversation: Conversation) -> str: ...


@runtime_checkable
class RawArchive(Protocol):
    """Persist originals and normalized forms."""

    def store(self, enriched: EnrichedConversation) -> None: ...

    def load(self, document_id: str) -> EnrichedConversation: ...


@runtime_checkable
class MemoryStore(Protocol):
    """`retain` / `recall` — the only component aware of Hindsight."""

    def retain(self, enriched: EnrichedConversation) -> None: ...

    def recall(self, query: str, tags: tuple[AnyTag, ...]) -> tuple[str, ...]: ...


@runtime_checkable
class ImportState(Protocol):
    """Track what has already been imported."""

    def seen(self, source_id: str, content_hash: str) -> bool: ...

    def record(self, record: ImportRecord) -> None: ...


# --- trivial implementations, and a pipeline made of them --------------------------------------


class InMemorySource:
    def __init__(self, conversations: tuple[Conversation, ...]) -> None:
        self._conversations = conversations

    def read(self) -> Iterable[Conversation]:
        return self._conversations


class ShoutingSanitizer:
    """Stands in for redaction: replaces a known secret, preserving the surrounding text (§13)."""

    def sanitize(self, conversation: Conversation) -> tuple[Conversation, tuple[Redaction, ...]]:
        messages = tuple(
            message.model_copy(update={"text": message.text.replace("hunter2", "[REDACTED]")})
            for message in conversation.messages
        )
        redactions = tuple(
            Redaction(category="password", count=1)
            for message in conversation.messages
            if "hunter2" in message.text
        )
        return conversation.model_copy(update={"messages": messages}), redactions


class FixedClassifier:
    def classify(self, conversation: Conversation) -> str:
        return "miratorg"


class DictArchive:
    def __init__(self) -> None:
        self._stored: dict[str, EnrichedConversation] = {}

    def store(self, enriched: EnrichedConversation) -> None:
        self._stored[enriched.document_id] = enriched

    def load(self, document_id: str) -> EnrichedConversation:
        return self._stored[document_id]


class ListMemoryStore:
    def __init__(self) -> None:
        self.retained: list[EnrichedConversation] = []

    def retain(self, enriched: EnrichedConversation) -> None:
        self.retained.append(enriched)

    def recall(self, query: str, tags: tuple[AnyTag, ...]) -> tuple[str, ...]:
        wanted = {str(tag) for tag in tags}
        return tuple(
            message.text
            for enriched in self.retained
            if wanted <= {str(tag) for tag in enriched.tags}
            for message in enriched.conversation.messages
            if query in message.text
        )


class SetImportState:
    def __init__(self) -> None:
        self._seen: set[tuple[str, str]] = set()

    def seen(self, source_id: str, content_hash: str) -> bool:
        return (source_id, content_hash) in self._seen

    def record(self, record: ImportRecord) -> None:
        self._seen.add((record.source_id, record.content_hash))


def a_conversation(source_id: str = "conversation-id") -> Conversation:
    return Conversation(
        source=Source.CHATGPT,
        source_id=source_id,
        title="Wolverine Saga Error Handling",
        started_at=datetime(2026, 1, 1, 9, tzinfo=UTC),
        messages=(
            Message(
                role=Role.USER,
                text="the database password is hunter2, why does retain fail?",
            ),
            Message(role=Role.ASSISTANT, text="the payload exceeds the limit"),
        ),
    )


def run_the_pipeline(
    source: ConversationSource,
    sanitizer: SecretSanitizer,
    classifier: ProjectClassifier,
    archive: RawArchive,
    memory: MemoryStore,
    state: ImportState,
) -> list[str]:
    """parse → normalize → sanitize → classify → enrich → archive → retain (§7).

    Every parameter is one of the six boundaries, and every value that crosses between them comes
    from `hermes_memory.normalization`. That is the whole of what this test asserts.
    """
    outcomes: list[str] = []

    for conversation in source.read():
        if state.seen(conversation.source_id, conversation.content_hash()):
            outcomes.append("skipped")
            continue

        sanitized, _ = sanitizer.sanitize(conversation)
        project = classifier.classify(sanitized)
        enriched = EnrichedConversation(
            conversation=sanitized,
            provenance=Provenance(
                source=sanitized.source,
                source_id=sanitized.source_id,
                project=project,
                title=sanitized.title,
                imported_at=datetime(2026, 9, 14, 10, tzinfo=UTC),
                importer_version="1",
            ),
            tags=(SourceTag(value=sanitized.source), ProjectTag(value=project)),
        )

        archive.store(enriched)
        memory.retain(enriched)
        state.record(
            ImportRecord(
                source_id=conversation.source_id,
                # The hash recorded is the one the skip above compares — the conversation as it was
                # read, before sanitization. Recording the sanitized hash instead would make the
                # second run import everything again, because the skip runs before the sanitizer
                # has touched anything. §17 puts the skip "before any call is made"; which stage's
                # hash it is comparing is #14's decision, and this test only shows that the two
                # must be the same stage.
                content_hash=conversation.content_hash(),
                document_id=conversation.document_id,
            )
        )
        outcomes.append("imported")

    return outcomes


def test_the_six_boundaries_compose_into_a_pipeline() -> None:
    """SC-001, and User Story 1's independent test: a run assembled entirely from fakes."""
    memory, archive, state = ListMemoryStore(), DictArchive(), SetImportState()

    outcomes = run_the_pipeline(
        source=InMemorySource((a_conversation(),)),
        sanitizer=ShoutingSanitizer(),
        classifier=FixedClassifier(),
        archive=archive,
        memory=memory,
        state=state,
    )

    assert outcomes == ["imported"]
    assert archive.load("chatgpt:conversation-id").provenance.project == "miratorg"
    assert memory.recall("retain", (ProjectTag(value="miratorg"),)) == (
        "the database password is [REDACTED], why does retain fail?",
    )


def test_a_second_run_over_unchanged_history_skips() -> None:
    """The §17 skip, expressed with nothing but this module's content hash."""
    memory, archive, state = ListMemoryStore(), DictArchive(), SetImportState()
    arguments = {
        "sanitizer": ShoutingSanitizer(),
        "classifier": FixedClassifier(),
        "archive": archive,
        "memory": memory,
        "state": state,
    }

    first = run_the_pipeline(source=InMemorySource((a_conversation(),)), **arguments)  # type: ignore[arg-type]
    second = run_the_pipeline(source=InMemorySource((a_conversation(),)), **arguments)  # type: ignore[arg-type]

    assert (first, second) == (["imported"], ["skipped"])
    assert len(memory.retained) == 1


def test_the_boundary_signatures_name_no_type_this_module_lacks() -> None:
    """The conversation-shaped vocabulary is complete: the fakes satisfy the six protocols.

    `isinstance` against a Protocol checks the method names rather than their signatures, so this
    is a weaker check than the ones above — where the pipeline actually calls each method with
    values of these types. It is here for the boundary #9 has not written yet.
    """
    assert isinstance(DictArchive(), RawArchive)
    assert isinstance(ListMemoryStore(), MemoryStore)
    assert isinstance(SetImportState(), ImportState)
    assert isinstance(ShoutingSanitizer(), SecretSanitizer)
    assert isinstance(FixedClassifier(), ProjectClassifier)
    assert isinstance(InMemorySource(()), ConversationSource)
