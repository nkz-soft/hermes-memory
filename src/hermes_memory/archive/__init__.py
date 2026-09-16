"""Persist originals and normalized forms, independently of any memory engine.

The raw archive boundary of ARCHITECTURE.md §8 — the source of truth Principle I requires. The
local store behind it, and its on-disk layout, arrive with #13.
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
