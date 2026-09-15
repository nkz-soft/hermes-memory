"""The tag convention of ARCHITECTURE.md §6, expressed as types.

Tags are the only scoping mechanism the architecture has: there is one shared bank and projects are
separated by tags (ADR-002). That makes a malformed tag quiet rather than loud — nothing fails, the
conversation is simply filed where nobody will look for it. So the namespace is a closed
vocabulary, the value is validated, and the string form is produced in exactly one place.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from hermes_memory.normalization.base import FrozenModel, Slug
from hermes_memory.normalization.conversation import Source

__all__ = [
    "AnyTag",
    "ConversationType",
    "ProjectTag",
    "SourceTag",
    "Tag",
    "TagNamespace",
    "TypeTag",
    "UserTag",
]


class TagNamespace(StrEnum):
    """The four namespaces §6 defines. Adding a fifth is an amendment, not a call site."""

    SOURCE = "source"
    PROJECT = "project"
    TYPE = "type"
    USER = "user"


class ConversationType(StrEnum):
    """The `type:` vocabulary of §6.

    Typed here because §6 fixes it. Choosing between these for a given conversation is nobody's job
    yet: classification determines the project (§15), and the type is decided by whichever feature
    first needs to tell a troubleshooting thread from a decision.
    """

    CONVERSATION = "conversation"
    CODING_SESSION = "coding-session"
    DECISION = "decision"
    TROUBLESHOOTING = "troubleshooting"


class Tag(FrozenModel):
    """A scoping tag: a namespace and a value, rendering to `namespace:value`.

    This is the supertype a signature names when it accepts any tag. It cannot be constructed
    directly — one of the four concrete forms below must be, because each of those is what
    validates the value against its namespace. A constructible base would be a hole in the
    convention it exists to describe.
    """

    namespace: TagNamespace
    value: str

    @model_validator(mode="after")
    def _only_a_concrete_namespace_may_be_built(self) -> Tag:
        if type(self) is Tag:
            raise ValueError(
                "Tag is the supertype of the four namespaces; construct SourceTag, ProjectTag, "
                "TypeTag or UserTag, each of which validates its own value"
            )
        return self

    def __str__(self) -> str:
        """The exact string form §6 defines, produced here and nowhere else."""
        return f"{self.namespace.value}:{self.value}"


class SourceTag(Tag):
    """`source:<source>` — takes a `Source`, so the tag and the document id cannot disagree."""

    namespace: Literal[TagNamespace.SOURCE] = TagNamespace.SOURCE
    value: Source


class ProjectTag(Tag):
    """`project:<slug>` — the scoping ADR-002 rests on.

    `project:unknown` is an ordinary value: §15 expects a substantial share of conversations to
    resolve to no project, and they are still imported and still retrievable.
    """

    namespace: Literal[TagNamespace.PROJECT] = TagNamespace.PROJECT
    value: Slug


class TypeTag(Tag):
    """`type:<kind>` — the closed vocabulary above."""

    namespace: Literal[TagNamespace.TYPE] = TagNamespace.TYPE
    value: ConversationType


class UserTag(Tag):
    """`user:<slug>`."""

    namespace: Literal[TagNamespace.USER] = TagNamespace.USER
    value: Slug


AnyTag = Annotated[SourceTag | ProjectTag | TypeTag | UserTag, Field(discriminator="namespace")]
"""One of the four concrete tags, told apart by its namespace.

This is what a *field* holding tags is annotated with, while `Tag` is what a function signature
names when it merely accepts one. The distinction is not cosmetic: a field typed as the base would
rebuild the base when a record comes back from the raw archive — and the base refuses to be built,
because building it would pair a namespace with an unvalidated value.

That failure is real rather than theoretical; `tests/unit/test_serialization.py` caught it on the
first round trip of an enriched conversation.
"""
