"""Map a parsed source into the source-independent conversation model.

This is the vocabulary every stage of the ingestion pipeline speaks (ARCHITECTURE.md §7) and what
crosses every boundary of §8 — the conversation source yields it, the sanitizer rewrites it, the
classifier reads it, the archive persists it, the memory store sends it, and the import state
remembers its hash.

**Nothing here may reach Hindsight, HTTP or storage**, directly or transitively (Principle IV,
ADR-001's exit strategy). No name below is a Hindsight term either: replacing the memory engine
must touch `memory/hindsight` and nothing in this module.
`tests/structure/test_normalization_boundary.py` enforces both.
"""

from hermes_memory.normalization.conversation import (
    Conversation,
    Message,
    NonTextKind,
    NonTextPart,
    Role,
    Source,
    ToolActivity,
)
from hermes_memory.normalization.provenance import EnrichedConversation, Provenance
from hermes_memory.normalization.tags import (
    ConversationType,
    ProjectTag,
    SourceTag,
    Tag,
    TagNamespace,
    TypeTag,
    UserTag,
)

__all__ = [
    "Conversation",
    "ConversationType",
    "EnrichedConversation",
    "Message",
    "NonTextKind",
    "NonTextPart",
    "ProjectTag",
    "Provenance",
    "Role",
    "Source",
    "SourceTag",
    "Tag",
    "TagNamespace",
    "ToolActivity",
    "TypeTag",
    "UserTag",
]
