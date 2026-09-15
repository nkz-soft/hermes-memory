"""Provenance (ARCHITECTURE.md §3.3) and the record the enrich stage of §7 produces.

Principle II makes provenance mandatory for every retained item: source, source id, original time,
project, repository when known, and the importer version. It is a separate value rather than a
field on the conversation because §7 puts classification *between* normalization and enrichment —
the parser cannot know the project, and a conversation rewritten later to gain one would be a
mutable value in a pipeline built on immutable ones (research.md R8).

`imported_at` lives here and nowhere else. That is the point: §11 forbids the import date standing
in for the conversation date, and the way to forbid it is to leave `Conversation` no field it could
be written into.
"""

from __future__ import annotations

from pydantic import Field, model_validator

from hermes_memory.normalization.base import FrozenModel, OpaqueIdentifier, Slug, Text, Timestamp
from hermes_memory.normalization.conversation import Conversation, Source
from hermes_memory.normalization.tags import AnyTag, ProjectTag, SourceTag

__all__ = ["EnrichedConversation", "Provenance"]


class Provenance(FrozenModel):
    """Where a conversation came from, when it was imported, and by which importer.

    `project` is required and carries `unknown` when classification did not resolve one (§15) —
    "not determined" is an answer the tag convention has a value for, whereas an absent project is
    an item that cannot be scoped at all.
    """

    source: Source
    source_id: OpaqueIdentifier
    project: Slug
    repository: Text | None = None
    title: Text | None = None
    imported_at: Timestamp
    importer_version: Text = Field(min_length=1)


class EnrichedConversation(FrozenModel):
    """A conversation with its provenance and its tags: the output of §7's enrich stage.

    This is what the raw archive persists and what the memory store receives, so it is the shape
    the boundaries of §8 name. Defining it here is what keeps each of those boundaries from
    describing the same triple in its own way.
    """

    conversation: Conversation
    provenance: Provenance
    # `AnyTag` rather than `Tag`: a field typed as the base would rebuild the base when this comes
    # back from the raw archive, and the base refuses to be built (see `tags.AnyTag`).
    tags: tuple[AnyTag, ...] = ()

    @property
    def document_id(self) -> str:
        """Delegated (§10), so a caller holding this never reaches past it to rebuild the id."""
        return self.conversation.document_id

    def content_hash(self) -> str:
        """Delegated (§17). Neither the provenance nor the tags are part of it: ADR-006 excludes
        importer-produced metadata, which is what keeps a changed importer version from
        re-extracting the whole corpus on an ordinary refresh."""
        return self.conversation.content_hash()

    @model_validator(mode="after")
    def _provenance_describes_this_conversation(self) -> EnrichedConversation:
        """Provenance that names something else is worse than none: it is wrong provenance."""
        if self.provenance.source != self.conversation.source:
            raise ValueError(
                f"provenance source ({self.provenance.source}) does not match the "
                f"conversation's ({self.conversation.source})"
            )
        if self.provenance.source_id != self.conversation.source_id:
            raise ValueError(
                f"provenance source_id ({self.provenance.source_id!r}) does not match the "
                f"conversation's ({self.conversation.source_id!r})"
            )
        return self

    @model_validator(mode="after")
    def _the_tags_agree_with_what_they_scope(self) -> EnrichedConversation:
        """A tag that contradicts the conversation it scopes is worse than a missing one.

        Tags are the only scoping mechanism there is (ADR-002), so a wrong one fails nothing at
        the time and files the conversation where nobody will look for it afterwards. The two that
        can contradict something already known are checked here: `source:` against the
        conversation's own source — which the document id (§10) is built from — and `project:`
        against the project classification resolved into the provenance (§15).

        Every other tag is enrichment's business. This constrains disagreement, not tagging.
        """
        for tag in self.tags:
            if isinstance(tag, SourceTag) and tag.value != self.conversation.source:
                raise ValueError(
                    f"tag {tag} names a source the conversation does not have "
                    f"({self.conversation.source})"
                )
            if isinstance(tag, ProjectTag) and tag.value != self.provenance.project:
                raise ValueError(
                    f"tag {tag} names a project the provenance does not have "
                    f"({self.provenance.project})"
                )
        return self

    @model_validator(mode="after")
    def _no_tag_appears_twice(self) -> EnrichedConversation:
        """Two tags sharing a value across namespaces are not duplicates; the same tag twice is."""
        if len(set(self.tags)) != len(self.tags):
            raise ValueError(f"tags contains duplicates: {[str(tag) for tag in self.tags]}")
        return self
