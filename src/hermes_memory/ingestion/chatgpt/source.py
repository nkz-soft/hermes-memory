"""`ChatGPTExportSource`: the conversation source boundary (§8) for ChatGPT exports.

The reader is a class rather than a generator, and that is required rather than preferred: CS-5
asks that a `SourceFormatError` for one conversation leave the iteration usable for the next, and an
exception raised inside a generator closes it for good (tests/fakes/source.py says the same).

Two kinds of failure, kept apart on purpose. A conversation that cannot be read raises and the
reader moves on. An export that cannot be reached, or cannot be scanned any further, raises and the
reader is finished — there is nothing after it that could be found.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import TextIO

from pydantic import ValidationError

from hermes_memory.archive.interface import OriginalPayload
from hermes_memory.ingestion.chatgpt.conversation import parse_record
from hermes_memory.ingestion.chatgpt.export import Export
from hermes_memory.ingestion.chatgpt.records import ExportRecord, RecordScanner
from hermes_memory.ingestion.chatgpt.thread import UnreadableRecord
from hermes_memory.ingestion.source import SourceConversation, SourceFormatError
from hermes_memory.normalization import Source
from hermes_memory.observability import get_logger

__all__ = ["ChatGPTExportSource"]

MEDIA_TYPE = "application/json"

_log = get_logger(__name__)


def _identifier(value: object) -> str | None:
    """The record's identifier for a failure's subject, where one can be found without parsing."""
    if isinstance(value, Mapping):
        for field in ("conversation_id", "id"):
            candidate = value.get(field)
            if isinstance(candidate, str) and candidate:
                return candidate
    return None


def _describe(refused: ValidationError) -> str:
    """Name what the model refused, and where — never the refused value (R10, Principle V).

    Pydantic's own rendering quotes the input, and the input is conversation content.
    """
    problems = sorted(
        {
            f"{error['type']} at {'.'.join(str(part) for part in error['loc'])}"
            for error in refused.errors()
        }
    )
    return "the record does not fit the normalized model: " + "; ".join(problems)


class _Reader(Iterator[SourceConversation]):
    def __init__(self, path: Path) -> None:
        self._path = path
        self._seen: set[str] = set()
        self._export: Export | None = None
        self._names: Iterator[str] = iter(())
        self._stream: TextIO | None = None
        self._scanner: RecordScanner | None = None
        self._done = False

    def __next__(self) -> SourceConversation:
        record = self._next_record()
        return self._convert(record)

    def _next_record(self) -> ExportRecord:
        if self._done:
            raise StopIteration
        try:
            if self._export is None:
                self._export = Export(self._path)
                self._names = iter(self._export.names)
            while True:
                if self._scanner is None:
                    name = next(self._names, None)
                    if name is None:
                        raise StopIteration
                    self._stream = self._export.open(name)
                    self._scanner = RecordScanner(self._stream)
                record = next(self._scanner, None)
                if record is not None:
                    return record
                self._close_stream()
        except BaseException:
            self._finish()
            raise

    def _convert(self, record: ExportRecord) -> SourceConversation:
        subject = _identifier(record.value)
        try:
            read = parse_record(record.value)
        except UnreadableRecord as unreadable:
            raise SourceFormatError(str(unreadable), subject=subject) from unreadable
        except ValidationError as refused:
            raise SourceFormatError(_describe(refused), subject=subject) from refused

        source_id = read.conversation.source_id
        if source_id in self._seen:
            raise SourceFormatError(
                "a conversation identifier appears twice in the export", subject=source_id
            )
        self._seen.add(source_id)
        _log.info("chatgpt.conversation.read", **read.account.as_fields())
        return SourceConversation(
            conversation=read.conversation,
            original=OriginalPayload(content=record.raw.encode("utf-8"), media_type=MEDIA_TYPE),
        )

    def close(self) -> None:
        """Release the export before the iteration is exhausted."""
        self._finish()

    def __del__(self) -> None:
        # A caller that stops early holds the file open until this runs; on Windows an open file
        # cannot be deleted or replaced, which is what a refresh (ADR-006) does to an export.
        self._finish()

    def _close_stream(self) -> None:
        if self._stream is not None:
            self._stream.close()
        self._stream = None
        self._scanner = None

    def _finish(self) -> None:
        self._done = True
        self._close_stream()
        if self._export is not None:
            self._export.close()


class ChatGPTExportSource:
    """Reads a ChatGPT export: a `.zip` archive, its extracted directory, or a conversations file.

    Constructing one touches nothing on disk. Each `read()` opens the export afresh, which is what
    makes reading twice yield equal conversations (CS-4).
    """

    source = Source.CHATGPT

    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    def read(self) -> Iterator[SourceConversation]:
        return _Reader(self._path)
