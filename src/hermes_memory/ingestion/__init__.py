"""Conversation sources: read one source format, yield normalized conversations.

Also the importer side of §17's idempotency — the record of what has already been imported, which
§17 places here rather than in a store of its own (`state.py`).

Two of the six boundaries of ARCHITECTURE.md §8 are declared here; their implementations arrive
with #10 (ChatGPT) and #14 (SQLite import state).
"""

from hermes_memory.ingestion.source import (
    ConversationSource,
    SourceConversation,
    SourceFormatError,
    SourceUnavailable,
)
from hermes_memory.ingestion.state import (
    ImportRecord,
    ImportState,
    ImportStateCorrupt,
    ImportStateUnavailable,
    ImportStatus,
    may_skip,
)

__all__ = [
    "ConversationSource",
    "ImportRecord",
    "ImportState",
    "ImportStateCorrupt",
    "ImportStateUnavailable",
    "ImportStatus",
    "SourceConversation",
    "SourceFormatError",
    "SourceUnavailable",
    "may_skip",
]
