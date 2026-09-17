"""Stream a JSON array one element at a time, keeping each element's exact text (research R3).

A year of ChatGPT history is one JSON array that can exceed a gigabyte, and the standard library has
no incremental parser. `json.JSONDecoder.raw_decode` is enough to build one: it decodes one value
starting at an index and says where the value ended. The scanner keeps a buffer, reads more whenever
a decode fails for want of text, and hands back each element with the slice of text it came from —
which is the conversation's original for the raw archive (Principle I, research R8).

Three rules keep it honest:

* **A decode that more text could change is not trusted** until more text has been read.
  `raw_decode` accepts `4` from a buffer that holds only the first digit of `42`, and `1500` from
  the first half of `1500.0`.
* **The buffer at least doubles between attempts** at one element, so an element of n characters
  costs O(log n) decodes rather than one per chunk.
* **Only an error at the edge of the buffer is read as "not enough text yet".** An error further
  back is the text being wrong, and reading the rest of the file first would buffer all of it.

Text that is not JSON cannot be resynchronized — nothing says where the broken element ends — so it
ends the scan with an export-level `SourceFormatError`. The elements before it have been yielded.
"""

from __future__ import annotations

import json
import zipfile
import zlib
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any, TextIO

from hermes_memory.ingestion.source import SourceFormatError, SourceUnavailable

__all__ = ["ExportRecord", "RecordScanner"]

_WHITESPACE = " \t\r\n"
_BYTE_ORDER_MARK = "﻿"
_DEFAULT_CHUNK = 64 * 1024

_UNSCANNABLE = (ValueError, RecursionError, EOFError, zipfile.BadZipFile, zlib.error)
"""Failures that mean the file cannot be scanned any further, beyond a `JSONDecodeError`.

An integer past the interpreter's digit limit (`ValueError`), nesting past the recursion limit, text
that is not UTF-8 (`UnicodeDecodeError` is a `ValueError`), and a compressed member that fails to
inflate or fails its CRC — which is only checked once the member has been read to its end.
"""

_NUMBER_CONTINUES = frozenset("0123456789.eE+-")

_TRUNCATION_SLACK = 16
"""How close to the end of the buffer a decode error must be to be read as "not enough text yet".

The longest token a buffer can end inside without the decoder calling it unterminated is a literal
or an escape — `false`, a `\\uXXXX` escape — so a small constant is enough.
"""


def _could_be_truncation(invalid: json.JSONDecodeError, buffered: int) -> bool:
    return invalid.msg.startswith("Unterminated string") or (
        invalid.pos >= buffered - _TRUNCATION_SLACK
    )


def _may_continue(value: object, buffer: str, end: int) -> bool:
    """Whether more text could change the value just decoded: a number stops at the buffer's end."""
    if end == len(buffer):
        return True
    is_number = isinstance(value, int | float) and not isinstance(value, bool)
    return is_number and buffer[end] in _NUMBER_CONTINUES


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
        except (StopIteration, SourceFormatError):
            self._state = "done"
            raise
        except OSError as unreadable:
            self._state = "done"
            raise SourceUnavailable("a conversations file could not be read") from unreadable
        except _UNSCANNABLE as unscannable:
            self._state = "done"
            raise SourceFormatError("a conversations file cannot be scanned") from unscannable

    def _advance(self) -> ExportRecord:
        if self._state == "start":
            if self._peek() == _BYTE_ORDER_MARK:
                self._position += 1
            if self._peek() != "[":
                raise SourceFormatError("a conversations file does not hold a JSON array")
            self._position += 1
            self._state = "first"

        next_character = self._peek()
        if next_character is None:
            raise SourceFormatError("a conversations file ends before its array does")
        if next_character == "]":
            self._close_array()
        if self._state == "after":
            if next_character != ",":
                raise SourceFormatError("a conversations file is not valid JSON")
            self._position += 1
            next_character = self._peek()
            if next_character == "]":
                self._close_array()
            if next_character is None:
                raise SourceFormatError("a conversations file ends before its array does")
        return self._decode_one()

    def _close_array(self) -> None:
        """The array ended, so the file must too: text after it means it is not one array."""
        self._position += 1
        if self._peek() is not None:
            raise SourceFormatError("a conversations file continues after its array")
        raise StopIteration

    def _decode_one(self) -> ExportRecord:
        while True:
            try:
                value, end = self._decode(self._buffer, self._position)
            except json.JSONDecodeError as invalid:
                if self._at_end or not _could_be_truncation(invalid, len(self._buffer)):
                    raise SourceFormatError("a conversations file is not valid JSON") from invalid
                self._grow()
                continue
            if not self._at_end and _may_continue(value, self._buffer, end):
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
