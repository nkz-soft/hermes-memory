"""The tag convention of ARCHITECTURE.md §6, as a type rather than as a string.

Tags are the only scoping mechanism the architecture has (ADR-002: one shared bank, projects
separated by tags). A malformed tag does not fail anything — it files a conversation where nobody
will look for it, which is why the convention is validated at construction rather than checked at
the point of sending.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from hermes_memory.normalization import (
    ConversationType,
    ProjectTag,
    Source,
    SourceTag,
    TagNamespace,
    TypeTag,
    UserTag,
)


def test_the_namespaces_are_the_four_the_architecture_names() -> None:
    assert {namespace.value for namespace in TagNamespace} == {
        "source",
        "project",
        "type",
        "user",
    }


def test_the_conversation_types_are_closed() -> None:
    """§6 fixes these four. Choosing between them for a given conversation is nobody's job yet."""
    assert {kind.value for kind in ConversationType} == {
        "conversation",
        "coding-session",
        "decision",
        "troubleshooting",
    }


@pytest.mark.parametrize(
    ("tag", "rendered"),
    [
        pytest.param(SourceTag(value=Source.CHATGPT), "source:chatgpt", id="source"),
        pytest.param(ProjectTag(value="miratorg"), "project:miratorg", id="project"),
        pytest.param(ProjectTag(value="unknown"), "project:unknown", id="the §15 fallback"),
        pytest.param(
            TypeTag(value=ConversationType.TROUBLESHOOTING), "type:troubleshooting", id="type"
        ),
        pytest.param(UserTag(value="nkz"), "user:nkz", id="user"),
    ],
)
def test_a_tag_renders_to_the_string_the_convention_defines(tag: object, rendered: str) -> None:
    """One method produces the string form, so the memory store never builds one by hand."""
    assert str(tag) == rendered


def test_the_namespace_is_carried_as_a_value_not_inferred_from_the_string() -> None:
    """A function that needs the project tag can then say so in its signature (research R9)."""
    assert ProjectTag(value="miratorg").namespace is TagNamespace.PROJECT
    assert SourceTag(value=Source.CHATGPT).namespace is TagNamespace.SOURCE


def test_the_namespace_cannot_be_overridden() -> None:
    """A project tag claiming the source namespace would scope memory to nothing at all."""
    with pytest.raises(ValidationError):
        ProjectTag(value="miratorg", namespace=TagNamespace.SOURCE)


def test_the_base_tag_cannot_be_constructed_directly() -> None:
    """Otherwise the base is a hole in the convention it exists to describe.

    `Tag` is the supertype a signature names when it accepts any tag. Constructing one directly
    would pair a namespace with an unvalidated value, which is exactly the free string §6 is
    written against.
    """
    from hermes_memory.normalization import Tag

    with pytest.raises(ValidationError):
        Tag(namespace=TagNamespace.PROJECT, value="Not A Slug")


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("", id="empty"),
        pytest.param("Miratorg", id="uppercase"),
        pytest.param("two words", id="space"),
        pytest.param("mira:torg", id="colon forging a namespace"),
        pytest.param("-leading", id="leading hyphen"),
    ],
)
def test_a_malformed_project_value_is_refused(value: str) -> None:
    with pytest.raises(ValidationError):
        ProjectTag(value=value)


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("", id="empty"),
        pytest.param("NKZ", id="uppercase"),
        pytest.param("two words", id="space"),
    ],
)
def test_a_malformed_user_value_is_refused(value: str) -> None:
    with pytest.raises(ValidationError):
        UserTag(value=value)


def test_a_source_value_outside_the_vocabulary_is_refused() -> None:
    """`source:` takes a Source, so the tag and the document id cannot disagree about a name."""
    with pytest.raises(ValidationError):
        SourceTag(value="gpt")


def test_a_type_value_outside_the_vocabulary_is_refused() -> None:
    with pytest.raises(ValidationError):
        TypeTag(value="rambling")


def test_a_tag_is_immutable() -> None:
    with pytest.raises(ValidationError):
        ProjectTag(value="miratorg").value = "other"  # type: ignore[misc]


def test_tags_with_the_same_namespace_and_value_are_the_same_tag() -> None:
    """Equality and hashing by value, so a set of tags de-duplicates as a reader expects."""
    assert ProjectTag(value="miratorg") == ProjectTag(value="miratorg")
    assert len({ProjectTag(value="miratorg"), ProjectTag(value="miratorg")}) == 1


def test_tags_in_different_namespaces_are_different_tags() -> None:
    """`project:nkz` and `user:nkz` scope different things and must never collapse."""
    assert ProjectTag(value="nkz") != UserTag(value="nkz")
    assert len({ProjectTag(value="nkz"), UserTag(value="nkz")}) == 2
