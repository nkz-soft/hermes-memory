"""Stream a JSON array one element at a time, keeping each element's exact text (research R3).

A year of ChatGPT history is one JSON array that can exceed a gigabyte, and the standard library has
no incremental parser. `json.JSONDecoder.raw_decode` is enough to build one: it decodes one value
starting at an index and says where the value ended. The scanner keeps a buffer, reads more whenever
a decode fails for want of text, and hands back each element with the slice of text it came from —
which is the conversation's original for the raw archive (Principle I, research R8).

Two rules keep it honest:

* **A decode that ends at the end of the buffer is not trusted** until the stream is exhausted.
  `raw_decode` accepts `4` from a buffer that holds only the first digit of `42`.
* **The buffer at least doubles between attempts** at one element, so an element of n characters
  costs O(log n) decodes rather than one per chunk.

Text that is not JSON cannot be resynchronized — nothing says where the broken element ends — so it
ends the scan with an export-level `SourceFormatError`. The elements before it have been yielded.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any, TextIO

from hermes_memory.ingestion.source import SourceFormatError, SourceUnavailable

__all__ = ["ExportRecord", "RecordScanner"]

_WHITESPACE = " \t\r\n"
_DEFAULT_CHUNK = 64 * 1024


@dataclass(frozen=True, slots=True)
class ExportRecord:
    """One element of the array: its exact text, and the value that text decodes to."""

    raw: str
    value: object


class RecordScanner(Iterator[ExportRecord]):
    """A resumable iterator over the elements of a JSON array read from a text stream."""

    def __init__(
        self,
        stream: TextIO,
        *,
        chunk_size: int = _DEFAULT_CHUNK,
        raw_decode: Callable[[str, int], tuple[Any, int]] | None = None,
    ) -> None:
        self._stream = stream
        self._chunk_size = chunk_size
        self._decode = raw_decode or json.JSONDecoder().raw_decode
        self._buffer = ""
        self._position = 0
        self._at_end = False
        self._state = "start"

    def __next__(self) -> ExportRecord:
        if self._state == "done":
            raise StopIteration
        try:
            return self._advance()
        except StopIteration:
            self._state = "done"
            raise
        except SourceFormatError:
            self._state = "done"
            raise
        except UnicodeDecodeError as undecodable:
            self._state = "done"
            raise SourceFormatError("a conversations file is not valid UTF-8") from undecodable
        except OSError as unreadable:
            self._state = "done"
            raise SourceUnavailable("a conversations file could not be read") from unreadable

    def _advance(self) -> ExportRecord:
        if self._state == "start":
            if self._peek() == "﻿":
                self._position += 1
            if self._peek() != "[":
                raise SourceFormatError("a conversations file does not hold a JSON array")
            self._position += 1
            self._state = "first"

        next_character = self._peek()
        if next_character is None:
            raise SourceFormatError("a conversations file ends before its array does")
        if next_character == "]":
            raise StopIteration
        if self._state == "after":
            if next_character != ",":
                raise SourceFormatError("a conversations file is not valid JSON")
            self._position += 1
            next_character = self._peek()
            if next_character == "]":
                raise StopIteration
            if next_character is None:
                raise SourceFormatError("a conversations file ends before its array does")
        return self._decode_one()

    def _decode_one(self) -> ExportRecord:
        while True:
            try:
                value, end = self._decode(self._buffer, self._position)
            except json.JSONDecodeError as invalid:
                if self._at_end:
                    raise SourceFormatError("a conversations file is not valid JSON") from invalid
                self._grow()
                continue
            if end == len(self._buffer) and not self._at_end:
                self._grow()
                continue
            break
        raw = self._buffer[self._position : end]
        self._buffer = self._buffer[end:]
        self._position = 0
        self._state = "after"
        return ExportRecord(raw=raw, value=value)

    def _grow(self) -> None:
        """Read at least as much again as the element seen so far, and at least one chunk."""
        self._read(max(self._chunk_size, len(self._buffer) - self._position))

    def _read(self, size: int) -> bool:
        if self._at_end:
            return False
        text = self._stream.read(size)
        if not text:
            self._at_end = True
            return False
        self._buffer += text
        return True

    def _peek(self) -> str | None:
        """The next character that is not whitespace, reading as needed; None at the end."""
        while True:
            if self._position >= len(self._buffer):
                self._buffer = ""
                self._position = 0
                if not self._read(self._chunk_size):
                    return None
                continue
            character = self._buffer[self._position]
            if character in _WHITESPACE:
                self._position += 1
                continue
            return character
