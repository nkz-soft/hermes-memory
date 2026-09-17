"""Streaming the conversation array one record at a time, keeping exact text (research R3)."""

from __future__ import annotations

import io
import json

import pytest

from hermes_memory.ingestion import SourceFormatError
from hermes_memory.ingestion.chatgpt.records import RecordScanner
from tests.synthetic import chatgpt_export as synth

TRICKY = [
    {"conversation_id": "a", "title": "Привет, мир 🚀", "text": "braces } ] [ { and , commas"},
    {"conversation_id": "b", "title": 'escaped "quotes" and \\ backslash \n newline'},
    {"conversation_id": "c", "nested": {"list": [1, 2.5, None, True, {"x": "]"}]}},
]


def _scan(text: str, chunk_size: int = 64 * 1024) -> list[tuple[str, object]]:
    return [(one.raw, one.value) for one in RecordScanner(io.StringIO(text), chunk_size=chunk_size)]


@pytest.mark.parametrize("chunk_size", [1, 7, 64 * 1024])
def test_each_record_comes_with_its_exact_text(chunk_size: int) -> None:
    text = synth.export_text(TRICKY)

    scanned = _scan(text, chunk_size)

    assert [raw for raw, _ in scanned] == [synth.serialize(one) for one in TRICKY]
    assert [value for _, value in scanned] == TRICKY


def test_ascii_escapes_are_kept_as_written() -> None:
    raw = json.dumps({"conversation_id": "a", "title": "Привет"}, ensure_ascii=True)

    assert _scan(f"[{raw}]", 3) == [(raw, {"conversation_id": "a", "title": "Привет"})]


def test_whitespace_and_a_byte_order_mark_are_tolerated() -> None:
    raw = synth.serialize(TRICKY[0])

    assert _scan(f"﻿ \n[\n  {raw} ,\n\n]\n", 5) == [(raw, TRICKY[0])]


@pytest.mark.parametrize("text", ["[]", "  [ \n ] ", "﻿[]"])
def test_an_empty_array_yields_nothing(text: str) -> None:
    assert _scan(text) == []


def _scan_until_failure(text: str, chunk_size: int = 4) -> tuple[list[object], SourceFormatError]:
    values: list[object] = []
    scanner = RecordScanner(io.StringIO(text), chunk_size=chunk_size)
    with pytest.raises(SourceFormatError) as raised:
        for one in scanner:
            values.append(one.value)
    assert raised.value.subject is None
    assert next(scanner, None) is None
    return values, raised.value


@pytest.mark.parametrize("text", ['{"conversation_id": "a"}', '"text"', "", "   "])
def test_a_top_level_that_is_not_an_array_is_an_export_failure(text: str) -> None:
    values, _ = _scan_until_failure(text)

    assert values == []


@pytest.mark.parametrize(
    "tail",
    [', {"conversation_id": "b", "title": "unterminated', ', {"broken": }]', " {}]", ", {"],
)
def test_invalid_json_ends_the_read_after_the_records_before_it(tail: str) -> None:
    text = "[" + synth.serialize(TRICKY[0]) + tail

    values, _ = _scan_until_failure(text)

    assert values == [TRICKY[0]]


def test_a_number_split_across_chunks_is_not_cut_short() -> None:
    """`raw_decode` accepts `4` from a buffer holding `4` of `42`; the scanner must not."""
    text = "[" + ", ".join(["12345678"] * 5) + "]"

    assert [value for _, value in _scan(text, 3)] == [12345678] * 5


def test_the_failure_message_carries_no_record_text() -> None:
    secret = "a-unique-marker-7f3a"
    _, failure = _scan_until_failure('[{"title": "' + secret + '" oops}]')

    assert secret not in str(failure)
    assert secret not in failure.message


MIXED = [
    {"conversation_id": "f", "create_time": 1772616600.123456, "weight": 1.5e3, "neg": -2.5e-7},
    {"conversation_id": "g", "text": "crlf\r\nlineé ✓ 🚀 \\u escapes \t"},
    {"conversation_id": "h", "n": [0, -0.0, 12345678901234567890, 1e300, True, False, None]},
]


@pytest.mark.parametrize("chunk_size", range(1, 17))
def test_every_chunk_size_reads_the_same(chunk_size: int) -> None:
    text = synth.export_text(MIXED).replace(", ", ",\r\n  ")
    top_level_numbers = "[1500.0, 1.5e3, -2e-2, 7]"

    assert [value for _, value in _scan(text, chunk_size)] == MIXED
    assert [value for _, value in _scan(top_level_numbers, chunk_size)] == [1500.0, 1.5e3, -2e-2, 7]


@pytest.mark.parametrize(
    "text",
    [
        "[" + "9" * 5000 + "]",
        "[" + "[" * 200_000 + "]" * 200_000 + "]",
        "[{}] trailing",
        "[{}] [{}]",
    ],
    ids=["huge integer", "deep nesting", "trailing text", "two arrays"],
)
def test_malformed_exports_fail_as_boundary_errors(text: str) -> None:
    _scan_until_failure(text, chunk_size=64 * 1024)


class _CountingStream(io.StringIO):
    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.consumed = 0

    def read(self, size: int | None = -1) -> str:
        chunk = super().read(size)
        self.consumed += len(chunk)
        return chunk


def test_garbage_fails_without_reading_the_rest_of_the_file() -> None:
    stream = _CountingStream("[" + "x" * (8 * 1024 * 1024) + "]")

    with pytest.raises(SourceFormatError):
        list(RecordScanner(stream, chunk_size=64 * 1024))

    assert stream.consumed < 256 * 1024


def test_a_large_record_costs_logarithmically_many_decode_attempts() -> None:
    attempts = 0
    decoder = json.JSONDecoder()

    def counting(text: str, index: int):
        nonlocal attempts
        attempts += 1
        return decoder.raw_decode(text, index)

    big = [{"conversation_id": str(i), "text": "x" * (1024 * 1024)} for i in range(2)]
    scanner = RecordScanner(
        io.StringIO(synth.export_text(big)), chunk_size=64 * 1024, raw_decode=counting
    )

    assert [one.value for one in scanner] == big
    assert attempts < 30
