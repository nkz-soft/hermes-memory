"""An in-memory import state: a dictionary keyed by source and native id.

Keyed by both, deliberately — IS-5. Two sources may mint the same identifier, and a collision would
skip a conversation that was never imported, which is the quietest possible way to lose history.
"""

from __future__ import annotations

from hermes_memory.ingestion import ImportRecord, ImportStateCorrupt, ImportStateUnavailable
from hermes_memory.normalization import Source


class InMemoryImportState:
    """Remembers the latest record per conversation, failures included."""

    def __init__(self, *, unavailable: bool = False, corrupt: bool = False) -> None:
        self._records: dict[tuple[Source, str], ImportRecord] = {}
        self._unavailable = unavailable
        self._corrupt = corrupt

    @property
    def records(self) -> tuple[ImportRecord, ...]:
        """Everything remembered, for a pipeline test to read — not part of the boundary."""
        return tuple(self._records.values())

    def record(self, record: ImportRecord) -> None:
        self._refuse_if_broken(record.source_id)
        self._records[(record.source, record.source_id)] = record

    def find(self, source: Source, source_id: str) -> ImportRecord | None:
        self._refuse_if_broken(source_id)
        return self._records.get((source, source_id))

    def _refuse_if_broken(self, subject: str) -> None:
        if self._unavailable:
            raise ImportStateUnavailable("the import state could not be reached", subject=subject)
        if self._corrupt:
            raise ImportStateCorrupt("the import state could not be read", subject=subject)
