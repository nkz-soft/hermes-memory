"""The six fakes, held to the six contracts (SC-002).

This is the feature's own proof that each interface is implementable by something other than the
eventual real thing — the claim #9 makes and #8 could only assert. It is also the template #10
through #16 follow: subclass the suite, return your implementation, and passing is what implementing
the boundary means.

The seventh subclass is `TestTagIndexedMemoryStore`: a second memory store with different internals,
held to the same contract, because ADR-001's exit strategy is a claim about the second
implementation and not the first.
"""

from __future__ import annotations

from hermes_memory.archive import RawArchive
from hermes_memory.classification import ProjectClassifier
from hermes_memory.ingestion import ConversationSource, ImportState
from hermes_memory.memory.interface import MemoryStore
from hermes_memory.normalization import Conversation
from hermes_memory.sanitization import RedactionCategory, SecretSanitizer
from tests.contracts import conversations
from tests.contracts.archive import RawArchiveContract
from tests.contracts.classifier import ProjectClassifierContract
from tests.contracts.sanitizer import SecretSanitizerContract
from tests.contracts.source import ConversationSourceContract
from tests.contracts.state import ImportStateContract
from tests.contracts.store import MemoryStoreContract
from tests.fakes.archive import InMemoryRawArchive
from tests.fakes.classifier import InMemoryProjectClassifier
from tests.fakes.sanitizer import InMemorySecretSanitizer
from tests.fakes.source import InMemoryConversationSource
from tests.fakes.state import InMemoryImportState
from tests.fakes.store import InMemoryMemoryStore, TagIndexedMemoryStore


class TestInMemoryConversationSource(ConversationSourceContract):
    def make_source(self, conversations: tuple[Conversation, ...]) -> ConversationSource:
        return InMemoryConversationSource(conversations)

    def make_source_with_one_unreadable(
        self, conversations: tuple[Conversation, ...]
    ) -> ConversationSource | None:
        return InMemoryConversationSource(
            conversations, unreadable=frozenset({conversations[1].source_id})
        )

    def make_unreachable_source(self) -> ConversationSource | None:
        return InMemoryConversationSource(unreachable=True)


class TestInMemorySecretSanitizer(SecretSanitizerContract):
    def make_sanitizer(self) -> SecretSanitizer:
        return InMemorySecretSanitizer()

    def secret_sample(self) -> tuple[str, RedactionCategory]:
        return conversations.FAKE_SECRET, RedactionCategory.PASSWORD

    def make_failing_sanitizer(self) -> SecretSanitizer | None:
        return InMemorySecretSanitizer(fails=True)


class TestInMemoryProjectClassifier(ProjectClassifierContract):
    def make_classifier(self) -> ProjectClassifier:
        return InMemoryProjectClassifier({"wolverine": "hermes-memory"})


class TestInMemoryRawArchive(RawArchiveContract):
    def make_archive(self) -> RawArchive:
        return InMemoryRawArchive()

    def make_unavailable_archive(self) -> RawArchive | None:
        return InMemoryRawArchive(unavailable=True)

    def make_rejecting_archive(self) -> RawArchive | None:
        return InMemoryRawArchive(rejects=True)


class TestInMemoryMemoryStore(MemoryStoreContract):
    def make_store(self) -> MemoryStore:
        return InMemoryMemoryStore()

    def make_rejecting_store(self) -> MemoryStore | None:
        return InMemoryMemoryStore(rejects=True)

    def make_unavailable_store(self) -> MemoryStore | None:
        return InMemoryMemoryStore(unavailable=True)


class TestTagIndexedMemoryStore(MemoryStoreContract):
    """A second implementation, written against the interface rather than against the first."""

    def make_store(self) -> MemoryStore:
        return TagIndexedMemoryStore()


class TestInMemoryImportState(ImportStateContract):
    def make_state(self) -> ImportState:
        return InMemoryImportState()

    def make_unavailable_state(self) -> ImportState | None:
        return InMemoryImportState(unavailable=True)

    def make_corrupt_state(self) -> ImportState | None:
        return InMemoryImportState(corrupt=True)
