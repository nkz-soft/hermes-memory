"""Provenance (ARCHITECTURE.md §3.3) and the record the enrich stage of §7 produces.

Principle II makes provenance mandatory for every retained item. What is pinned here is that each
of its fields has exactly one typed place — and that `imported_at` has no way of standing in for a
conversation's real time, which is the §11 mistake this model exists to make impossible.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from hermes_memory.normalization import (
    Conversation,
    EnrichedConversation,
    Message,
    ProjectTag,
    Provenance,
    Role,
    Source,
    SourceTag,
    UserTag,
)

STARTED = datetime(2026, 1, 1, 9, tzinfo=UTC)
IMPORTED = datetime(2026, 9, 14, 10, tzinfo=UTC)


def a_conversation(**overrides: object) -> Conversation:
    fields: dict[str, object] = {
        "source": Source.CHATGPT,
        "source_id": "conversation-id",
        "title": "Wolverine Saga Error Handling",
        "started_at": STARTED,
        "messages": (Message(role=Role.USER, text="why does retain fail here?"),),
    }
    return Conversation(**(fields | overrides))  # type: ignore[arg-type]


def a_provenance(**overrides: object) -> Provenance:
    fields: dict[str, object] = {
        "source": Source.CHATGPT,
        "source_id": "conversation-id",
        "project": "miratorg",
        "title": "Wolverine Saga Error Handling",
        "imported_at": IMPORTED,
        "importer_version": "1",
    }
    return Provenance(**(fields | overrides))  # type: ignore[arg-type]


# --- the §3.3 fields ---------------------------------------------------------------------------


def test_provenance_carries_every_field_the_architecture_requires() -> None:
    """Source, source id, project, repository, title, import time and importer version (§3.3)."""
    provenance = a_provenance(repository="nkz-soft/hermes-memory")

    assert provenance.source is Source.CHATGPT
    assert provenance.source_id == "conversation-id"
    assert provenance.project == "miratorg"
    assert provenance.repository == "nkz-soft/hermes-memory"
    assert provenance.title == "Wolverine Saga Error Handling"
    assert provenance.imported_at == IMPORTED
    assert provenance.importer_version == "1"


def test_a_repository_is_optional() -> None:
    """ChatGPT exports carry no repository, so §15's level 1 does not apply to the MVP source."""
    assert a_provenance().repository is None


def test_the_project_may_be_unknown() -> None:
    """§15: a conversation that resolves to no project is still imported and still retrievable."""
    assert a_provenance(project="unknown").project == "unknown"


def test_a_malformed_project_is_refused() -> None:
    """The value becomes a `project:` tag, and a malformed tag scopes memory to nowhere."""
    with pytest.raises(ValidationError) as failure:
        a_provenance(project="Mira Torg")

    assert "project" in str(failure.value)


def test_the_project_is_required() -> None:
    """`unknown` is the answer for "not determined"; an absent value is not an answer at all."""
    with pytest.raises(ValidationError) as failure:
        Provenance(
            source=Source.CHATGPT,
            source_id="conversation-id",
            imported_at=IMPORTED,
            importer_version="1",
        )

    assert "project" in str(failure.value)


def test_an_empty_importer_version_is_refused() -> None:
    """Provenance that cannot say which importer produced it is not provenance (Principle II)."""
    with pytest.raises(ValidationError) as failure:
        a_provenance(importer_version="")

    assert "importer_version" in str(failure.value)


def test_a_naive_import_time_is_refused() -> None:
    with pytest.raises(ValidationError) as failure:
        a_provenance(imported_at=datetime(2026, 9, 14, 10))

    assert "imported_at" in str(failure.value)


def test_the_import_time_lives_on_provenance_and_nowhere_else() -> None:
    """§11's failure mode has no field to hide in: the conversation has no import-time slot.

    This is the one test in the suite that asserts the *absence* of a field, deliberately. The
    mistake §11 is written against — the import date standing in for the conversation date — is
    made impossible by there being nowhere on `Conversation` to put it.
    """
    assert "imported_at" not in Conversation.model_fields
    assert "imported_at" in Provenance.model_fields


# --- the enrich-stage pairing ------------------------------------------------------------------


def test_an_enriched_conversation_carries_the_conversation_its_provenance_and_its_tags() -> None:
    """The output of §7's enrich stage: what the archive persists and the memory store receives."""
    enriched = EnrichedConversation(
        conversation=a_conversation(),
        provenance=a_provenance(),
        tags=(SourceTag(value=Source.CHATGPT), ProjectTag(value="miratorg")),
    )

    assert enriched.conversation.source_id == "conversation-id"
    assert enriched.provenance.project == "miratorg"
    assert [str(tag) for tag in enriched.tags] == ["source:chatgpt", "project:miratorg"]


def test_provenance_naming_another_conversation_is_refused() -> None:
    """Provenance that describes something else is worse than none: it is wrong provenance."""
    with pytest.raises(ValidationError) as failure:
        EnrichedConversation(
            conversation=a_conversation(),
            provenance=a_provenance(source_id="a-different-conversation"),
            tags=(),
        )

    assert "source_id" in str(failure.value)


def test_provenance_naming_another_source_is_refused() -> None:
    with pytest.raises(ValidationError) as failure:
        EnrichedConversation(
            conversation=a_conversation(),
            provenance=a_provenance(source=Source.CODEX),
            tags=(),
        )

    assert "source" in str(failure.value)


def test_a_source_tag_naming_another_source_is_refused() -> None:
    """The same argument as provenance, one field over: a wrong tag is worse than a missing one.

    Tags are the only scoping mechanism there is (ADR-002), and `source:codex` on a ChatGPT
    conversation does not fail anything — it files the conversation where nobody will look, and
    contradicts the document id at the same time.
    """
    with pytest.raises(ValidationError) as failure:
        EnrichedConversation(
            conversation=a_conversation(),
            provenance=a_provenance(),
            tags=(SourceTag(value=Source.CODEX),),
        )

    assert "source" in str(failure.value)


def test_a_project_tag_disagreeing_with_the_provenance_is_refused() -> None:
    """One conversation belongs to one project; two answers to that question is a defect."""
    with pytest.raises(ValidationError) as failure:
        EnrichedConversation(
            conversation=a_conversation(),
            provenance=a_provenance(project="miratorg"),
            tags=(ProjectTag(value="something-else"),),
        )

    assert "project" in str(failure.value)


def test_the_agreeing_tags_are_accepted() -> None:
    """The check constrains disagreement, not tagging: the ordinary case still passes."""
    enriched = EnrichedConversation(
        conversation=a_conversation(),
        provenance=a_provenance(project="miratorg"),
        tags=(SourceTag(value=Source.CHATGPT), ProjectTag(value="miratorg"), UserTag(value="nkz")),
    )

    assert len(enriched.tags) == 3


def test_duplicate_tags_are_refused() -> None:
    """Sending the same tag twice is a parser bug; the boundary is where it is cheap to catch."""
    with pytest.raises(ValidationError) as failure:
        EnrichedConversation(
            conversation=a_conversation(),
            provenance=a_provenance(),
            tags=(ProjectTag(value="miratorg"), ProjectTag(value="miratorg")),
        )

    assert "tags" in str(failure.value)


def test_two_tags_sharing_a_value_across_namespaces_are_not_duplicates() -> None:
    """`project:nkz` and `user:nkz` are different scopes, and both may be present."""
    enriched = EnrichedConversation(
        conversation=a_conversation(),
        # The project deliberately matches the tag: what is under test is that two namespaces
        # sharing a value are not duplicates, not whether the project agrees — which is
        # `test_a_project_tag_disagreeing_with_the_provenance_is_refused` above.
        provenance=a_provenance(project="nkz"),
        tags=(ProjectTag(value="nkz"), UserTag(value="nkz")),
    )

    assert len(enriched.tags) == 2


def test_an_enriched_conversation_may_carry_no_tags_yet() -> None:
    """Enrichment decides the tags; this model says what a tag is, not which ones apply."""
    enriched = EnrichedConversation(
        conversation=a_conversation(), provenance=a_provenance(), tags=()
    )

    assert enriched.tags == ()


def test_an_enriched_conversation_is_immutable() -> None:
    enriched = EnrichedConversation(
        conversation=a_conversation(), provenance=a_provenance(), tags=()
    )

    with pytest.raises(ValidationError):
        enriched.tags = (ProjectTag(value="other"),)  # type: ignore[misc]
