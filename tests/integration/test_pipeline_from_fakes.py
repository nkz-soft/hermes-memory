"""§7's pipeline, assembled entirely from fakes, before any of its parts exists (PL-1 to PL-6).

This is issue #9's own statement of how we would know it works: a pipeline made of fakes that runs
a conversation end to end with no real I/O. It is also the cheapest possible discovery that two
boundaries do not fit together — before either is real, and while changing one is free.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from hermes_memory.ingestion import ImportStatus, SourceConversation
from hermes_memory.memory.interface import MemoryStore
from hermes_memory.normalization import ProjectTag, Source
from tests.contracts import conversations
from tests.fakes.archive import InMemoryRawArchive
from tests.fakes.classifier import InMemoryProjectClassifier
from tests.fakes.sanitizer import InMemorySecretSanitizer
from tests.fakes.source import InMemoryConversationSource
from tests.fakes.state import InMemoryImportState
from tests.fakes.store import InMemoryMemoryStore, TagIndexedMemoryStore
from tests.integration.pipeline import Pipeline

NOW = datetime(2026, 9, 16, 10, 0, tzinfo=UTC)
read = conversations.as_read


def assemble(
    *,
    conversations_read: tuple[SourceConversation, ...],
    store: MemoryStore | None = None,
    archive: InMemoryRawArchive | None = None,
    state: InMemoryImportState | None = None,
    unreadable: frozenset[str] = frozenset(),
) -> Pipeline:
    return Pipeline(
        source=InMemoryConversationSource(conversations_read, unreadable=unreadable),
        sanitizer=InMemorySecretSanitizer(conversations.FAKE_SECRET),
        classifier=InMemoryProjectClassifier({"wolverine": "hermes-memory"}),
        archive=archive or InMemoryRawArchive(),
        store=store or InMemoryMemoryStore(),
        state=state or InMemoryImportState(),
    )


def test_pl1_one_conversation_goes_all_the_way_through(no_io: None) -> None:
    """Sanitized, classified, enriched, archived, retained and recorded — §7 end to end."""
    archive = InMemoryRawArchive()
    store = InMemoryMemoryStore()
    state = InMemoryImportState()
    pipeline = assemble(
        conversations_read=read(conversations.conversation_with_a_secret("leaky1")),
        archive=archive,
        store=store,
        state=state,
    )

    outcome = pipeline.run(now=NOW)

    assert outcome.imported == ["leaky1"]
    assert outcome.failed == []

    assert archive.document_ids == {"chatgpt:leaky1"}
    archived = archive.load("chatgpt:leaky1")
    assert conversations.FAKE_SECRET not in archived.conversation.messages[0].text
    assert "401 Unauthorized" in archived.conversation.messages[0].text
    assert archived.provenance.imported_at == NOW
    assert ProjectTag(value="unknown") in archived.tags

    assert store.retained == ("chatgpt:leaky1",)
    assert archive.load_original("chatgpt:leaky1").content == conversations.PAYLOAD.content

    remembered = state.find(Source.CHATGPT, "leaky1")
    assert remembered is not None
    assert remembered.status is ImportStatus.IMPORTED
    assert remembered.document_id == "chatgpt:leaky1"
    assert remembered.content_hash == archived.content_hash()


def test_pl1_the_redaction_report_reaches_the_run(no_io: None) -> None:
    """Principle V — what was redacted is reported, and counted, and never quoted."""
    pipeline = assemble(conversations_read=read(conversations.conversation_with_a_secret()))

    outcome = pipeline.run(now=NOW)

    assert outcome.redactions.total == 1
    assert conversations.FAKE_SECRET not in repr(outcome.redactions.model_dump())


def test_pl2_a_second_run_over_unchanged_content_touches_nothing(no_io: None) -> None:
    """§17 — the skip that keeps a refresh from paying for extraction a second time."""
    archive = InMemoryRawArchive()
    store = InMemoryMemoryStore()
    state = InMemoryImportState()
    read_once = read(conversations.conversation("abc123"))

    first = assemble(conversations_read=read_once, archive=archive, store=store, state=state)
    first.run(now=NOW)

    quiet_archive = InMemoryRawArchive(unavailable=True)
    quiet_store = InMemoryMemoryStore(unavailable=True)
    second = assemble(
        conversations_read=read_once, archive=quiet_archive, store=quiet_store, state=state
    )
    outcome = second.run(now=NOW)

    assert outcome.skipped == ["abc123"]
    assert outcome.imported == []
    assert outcome.failed == []
    assert quiet_store.retained == ()
    assert quiet_archive.document_ids == frozenset()


def test_pl2_a_skip_does_not_overwrite_what_the_state_knew(no_io: None) -> None:
    """A third run must skip too. Recording the skip would re-import the conversation forever."""
    state = InMemoryImportState()
    read_once = read(conversations.conversation("abc123"))

    assemble(conversations_read=read_once, state=state).run(now=NOW)
    assemble(conversations_read=read_once, state=state).run(now=NOW)
    outcome = assemble(conversations_read=read_once, state=state).run(now=NOW)

    assert outcome.skipped == ["abc123"]
    remembered = state.find(Source.CHATGPT, "abc123")
    assert remembered is not None
    assert remembered.status is ImportStatus.IMPORTED


def test_pl3_changed_content_is_imported_again_under_the_same_document_id(no_io: None) -> None:
    """ADR-006 — a refreshed export brings new messages, and §10 keeps the identity stable."""
    archive = InMemoryRawArchive()
    store = InMemoryMemoryStore()
    state = InMemoryImportState()

    assemble(
        conversations_read=read(conversations.conversation("abc123", text="We chose Wolverine.")),
        archive=archive,
        store=store,
        state=state,
    ).run(now=NOW)

    outcome = assemble(
        conversations_read=read(
            conversations.conversation("abc123", text="We chose Wolverine, then Rebus.")
        ),
        archive=archive,
        store=store,
        state=state,
    ).run(now=NOW)

    assert outcome.imported == ["abc123"]
    assert archive.document_ids == {"chatgpt:abc123"}
    assert store.retained == ("chatgpt:abc123",)
    assert "Rebus" in archive.load("chatgpt:abc123").conversation.messages[1].text


def test_pl5_the_run_reaches_neither_the_network_nor_the_filesystem(no_io: None) -> None:
    """SC-004 — blocked for the duration, not merely unobserved (research R14)."""
    outcome = assemble(
        conversations_read=read(
            conversations.conversation("a"), conversations.conversation_using_every_field("b")
        )
    ).run(now=NOW)

    assert outcome.imported == ["a", "b"]


def test_pl5_the_guard_itself_bites(no_io: None) -> None:
    """A guard nobody has watched fail is a guard nobody knows is working."""
    from tests.integration.conftest import ForbiddenIO

    with pytest.raises(ForbiddenIO):
        open("would-have-been-written.txt", "w")  # noqa: SIM115 - the call is the assertion


@pytest.mark.parametrize("store_class", [InMemoryMemoryStore, TagIndexedMemoryStore])
def test_pl6_the_memory_store_is_replaceable(store_class, no_io: None) -> None:
    """SC-006 — ADR-001's exit strategy, exercised rather than asserted.

    Only the line that chooses the store differs between the two runs of this test. If a second
    implementation needed anything else to change, the interface would be the thing that is wrong.
    """
    store = store_class()
    pipeline = assemble(conversations_read=read(conversations.conversation("abc123")), store=store)

    outcome = pipeline.run(now=NOW)

    assert outcome.imported == ["abc123"]
    recalled = store.recall("Wolverine")
    assert len(recalled) == 1
    assert recalled[0].provenance.source_id == "abc123"


def test_pl4_one_conversation_fails_and_the_run_continues(no_io: None) -> None:
    """§18 — import proceeds conversation by conversation; one failure must not abort the run."""
    state = InMemoryImportState()
    store = InMemoryMemoryStore()
    pipeline = assemble(
        conversations_read=read(
            conversations.conversation("a"),
            conversations.conversation("b"),
            conversations.conversation("c"),
        ),
        store=store,
        state=state,
        unreadable=frozenset({"b"}),
    )

    outcome = pipeline.run(now=NOW)

    assert outcome.imported == ["a", "c"]
    assert store.retained == ("chatgpt:a", "chatgpt:c")

    assert len(outcome.failed) == 1
    assert outcome.failed[0].source_id == "b"
    assert outcome.failed[0].retryable is False


def test_pl4_a_transient_failure_is_told_apart_from_a_permanent_one(no_io: None) -> None:
    """What #20 reads: whether repeating the identical call could succeed (§18, E2)."""
    unreachable_store = InMemoryMemoryStore(unavailable=True)
    outcome = assemble(
        conversations_read=read(conversations.conversation("a")), store=unreachable_store
    ).run(now=NOW)

    assert [failure.source_id for failure in outcome.failed] == ["a"]
    assert outcome.failed[0].retryable is True

    refusing_store = InMemoryMemoryStore(rejects=True)
    refused = assemble(
        conversations_read=read(conversations.conversation("a")), store=refusing_store
    ).run(now=NOW)

    assert refused.failed[0].retryable is False


def test_pl4_a_failure_is_recorded_and_is_not_the_same_as_never_attempted(no_io: None) -> None:
    """§17 with §18: the next run must retry it, and must be able to see that it broke."""
    state = InMemoryImportState()
    assemble(
        conversations_read=read(conversations.conversation("a")),
        store=InMemoryMemoryStore(unavailable=True),
        state=state,
    ).run(now=NOW)

    recorded = state.find(Source.CHATGPT, "a")
    assert recorded is not None
    assert recorded.status is ImportStatus.FAILED
    assert recorded.error
    assert conversations.FAKE_SECRET not in (recorded.error or "")

    retried = assemble(conversations_read=read(conversations.conversation("a")), state=state).run(
        now=NOW
    )

    assert retried.imported == ["a"]
    assert retried.skipped == []
