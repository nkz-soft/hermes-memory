"""The value semantics every entity in the normalized model shares.

Three rules live here rather than in each entity, because all of them depend on all three:

* a model is a frozen value that forbids what it does not declare (research.md R7);
* an identifier the model did not mint is opaque, but not unreadable (research.md R10);
* a slug that scopes memory is validated, because a typo in one does not fail — it files a
  conversation where nobody will look for it (research.md R9, ARCHITECTURE.md §6).

The tests exercise them through a throwaway model, so that what is pinned is the shared machinery
and not any one entity's use of it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from hermes_memory.normalization.base import FrozenModel, OpaqueIdentifier, Slug, Timestamp


class Example(FrozenModel):
    """A stand-in for any entity in the model."""

    identifier: OpaqueIdentifier
    slug: Slug
    at: Timestamp


def an_example(**overrides: object) -> Example:
    """An otherwise valid example, so each test varies exactly one thing."""
    fields: dict[str, object] = {
        "identifier": "conversation-id",
        "slug": "miratorg",
        "at": datetime(2026, 1, 1, 9, tzinfo=UTC),
    }
    return Example(**(fields | overrides))  # type: ignore[arg-type]


def test_a_value_cannot_be_mutated_after_construction() -> None:
    """Frozen, so a content hash cannot go stale in the hand of a caller (research.md R7)."""
    example = an_example()

    with pytest.raises(ValidationError):
        example.identifier = "something-else"  # type: ignore[misc]


def test_an_undeclared_field_is_refused() -> None:
    """``extra="forbid"``: a misspelled field in an archived record fails loudly (FR-015).

    Without it, a record written by a future version — or by a typo — parses into an object that
    silently lost the value, which is the failure Principle I cannot afford in the archive.
    """
    with pytest.raises(ValidationError) as failure:
        an_example(nickname="whatever")

    assert "nickname" in str(failure.value)


def test_a_naive_timestamp_is_refused() -> None:
    """A time without an offset is a time whose instant depends on where the code ran.

    The canonical form converts timestamps to UTC before hashing (research.md R4), so an ambiguous
    one is a hash that depends on the machine. It is rejected at construction rather than at the
    point it would have been hashed (FR-008).
    """
    with pytest.raises(ValidationError) as failure:
        an_example(at=datetime(2026, 1, 1, 9))

    assert "at" in str(failure.value)


def test_an_aware_timestamp_at_any_offset_is_accepted() -> None:
    """The rule is about ambiguity, not about UTC. An export taken in Moscow is still valid."""
    moscow = timezone(timedelta(hours=3))
    example = an_example(at=datetime(2026, 1, 1, 12, tzinfo=moscow))

    assert example.at.utcoffset() == timedelta(hours=3)


@pytest.mark.parametrize(
    "identifier",
    [
        pytest.param("", id="empty"),
        pytest.param("   ", id="whitespace only"),
        pytest.param("has a space", id="inner space"),
        pytest.param("trailing ", id="trailing space"),
        pytest.param("line\nbreak", id="newline"),
        pytest.param("bell\x07", id="control character"),
    ],
)
def test_an_unusable_identifier_is_refused(identifier: str) -> None:
    """An identifier must survive a log line and a URL without being trimmed into another one."""
    with pytest.raises(ValidationError) as failure:
        an_example(identifier=identifier)

    assert "identifier" in str(failure.value)


@pytest.mark.parametrize(
    "identifier",
    [
        pytest.param("68f0a1c2-3b4d-4e5f-8a9b-0c1d2e3f4a5b", id="uuid"),
        pytest.param("chatgpt:nested:colons", id="colons"),
        pytest.param("Mixed-Case_1234", id="mixed case"),
        pytest.param("разговор-1", id="non-ascii"),
    ],
)
def test_an_identifier_is_otherwise_opaque(identifier: str) -> None:
    """What a source calls its conversations is the source's business (research.md R10).

    Colons in particular: ``document_id`` is ``<source>:<native id>`` and is never split back
    apart, so a colon inside the native id is harmless and forbidding one would be inventing a
    constraint the source does not owe us.
    """
    assert an_example(identifier=identifier).identifier == identifier


@pytest.mark.parametrize(
    "slug",
    [
        pytest.param("", id="empty"),
        pytest.param("Miratorg", id="uppercase"),
        pytest.param("has space", id="space"),
        pytest.param("-leading-hyphen", id="leading hyphen"),
        pytest.param(".leading-dot", id="leading dot"),
        pytest.param("проект", id="non-ascii"),
        pytest.param("slash/es", id="slash"),
        pytest.param("colon:s", id="colon"),
    ],
)
def test_a_malformed_slug_is_refused(slug: str) -> None:
    """Tags are the only scoping mechanism there is (§6), and a colon would forge a namespace."""
    with pytest.raises(ValidationError) as failure:
        an_example(slug=slug)

    assert "slug" in str(failure.value)


@pytest.mark.parametrize(
    "slug",
    [
        pytest.param("miratorg", id="plain"),
        pytest.param("unknown", id="the §15 fallback"),
        pytest.param("hermes-memory", id="hyphen"),
        pytest.param("team.platform", id="dot"),
        pytest.param("user_42", id="underscore"),
        pytest.param("9lives", id="leading digit"),
    ],
)
def test_a_well_formed_slug_is_accepted(slug: str) -> None:
    """Including ``unknown``, which §15 makes an ordinary project rather than a missing one."""
    assert an_example(slug=slug).slug == slug
