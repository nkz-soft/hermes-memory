"""`ChatGPTExportSource`: the conversation source boundary (§8) for ChatGPT exports.

The reader is a class rather than a generator, and that is required rather than preferred: CS-5
asks that a `SourceFormatError` for one conversation leave the iteration usable for the next, and an
exception raised inside a generator closes it for good (tests/fakes/source.py says the same).

Two kinds of failure, kept apart on purpose. A conversation that cannot be read raises and the
reader moves on. An export that cannot be reached, or cannot be scanned any further, raises and the
reader is finished — there is nothing after it that could be found.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TextIO

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


class _Reader(Iterator[SourceConversation]):
    def __init__(self, path: Path) -> None:
        self._path = path
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
        try:
            read = parse_record(record.value)
        except UnreadableRecord as unreadable:
            raise SourceFormatError(str(unreadable)) from unreadable
        _log.info("chatgpt.conversation.read", **read.account.as_fields())
        return SourceConversation(
            conversation=read.conversation,
            original=OriginalPayload(content=record.raw.encode("utf-8"), media_type=MEDIA_TYPE),
        )

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
