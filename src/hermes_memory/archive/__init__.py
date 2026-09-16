"""Persist originals and normalized forms, independently of any memory engine.

The raw archive boundary of ARCHITECTURE.md §8 — the source of truth Principle I requires. The
local store behind it, and its on-disk layout, arrive with #13.

**This package re-exports the interface and nothing else.** `ingestion/source.py` names
`OriginalPayload`, so every consumer of the source interface initializes this package — Python runs
a package's `__init__` before any module inside it, whichever module was asked for. An
implementation re-exported from here would be loaded, filesystem and all, into code that only
wanted to read a conversation. Implementations are imported from their own module.
"""

from hermes_memory.archive.interface import (
    ArchiveDocumentNotFound,
    ArchiveRejected,
    ArchiveUnavailable,
    OriginalPayload,
    RawArchive,
)

__all__ = [
    "ArchiveDocumentNotFound",
    "ArchiveRejected",
    "ArchiveUnavailable",
    "OriginalPayload",
    "RawArchive",
]
