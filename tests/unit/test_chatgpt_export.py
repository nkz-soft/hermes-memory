"""Locating and opening the conversation files of a ChatGPT export (research R2, R10)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_memory.ingestion import SourceFormatError, SourceUnavailable
from hermes_memory.ingestion.chatgpt.export import Export
from tests.synthetic import chatgpt_export as synth

RECORDS = [synth.linear_record(f"c{i}", synth.message("user", f"question {i}")) for i in range(3)]


def _read_all(export: Export) -> list[str]:
    texts = []
    for name in export.names:
        with export.open(name) as stream:
            texts.append(stream.read())
    return texts


def test_a_directory_is_opened(tmp_path: Path) -> None:
    synth.write_directory(tmp_path / "export", RECORDS)

    with Export(tmp_path / "export") as export:
        assert export.names == ("conversations.json",)
        assert _read_all(export) == [synth.export_text(RECORDS)]


def test_an_archive_is_opened_in_place(tmp_path: Path) -> None:
    synth.write_zip(tmp_path / "export.zip", RECORDS)

    with Export(tmp_path / "export.zip") as export:
        assert export.names == ("conversations.json",)
        assert _read_all(export) == [synth.export_text(RECORDS)]


def test_the_conversations_file_itself_is_opened(tmp_path: Path) -> None:
    synth.write_directory(tmp_path / "export", RECORDS)

    with Export(tmp_path / "export" / "conversations.json") as export:
        assert _read_all(export) == [synth.export_text(RECORDS)]


@pytest.mark.parametrize("writer", [synth.write_directory, synth.write_zip])
def test_a_split_export_is_read_in_numeric_order(tmp_path: Path, writer) -> None:
    records = [synth.linear_record(f"c{i}", synth.message("user", "hi")) for i in range(11)]
    target = tmp_path / ("export.zip" if writer is synth.write_zip else "export")
    writer(target, records, split=1)

    with Export(target) as export:
        assert export.names[:3] == (
            "conversations-000.json",
            "conversations-001.json",
            "conversations-002.json",
        )
        assert export.names[-1] == "conversations-010.json"


def test_a_missing_path_is_retryable(tmp_path: Path) -> None:
    with pytest.raises(SourceUnavailable) as raised:
        Export(tmp_path / "nowhere.zip")

    assert raised.value.retryable is True
    assert raised.value.__cause__ is not None


def _format_failure(target: Path) -> SourceFormatError:
    with pytest.raises(SourceFormatError) as raised:
        Export(target)
    assert raised.value.subject is None
    assert raised.value.retryable is False
    return raised.value


def test_a_corrupt_archive_is_permanent(tmp_path: Path) -> None:
    (tmp_path / "export.zip").write_bytes(b"this is not a zip archive")

    assert _format_failure(tmp_path / "export.zip").__cause__ is not None


def test_a_file_that_is_neither_archive_nor_json_is_permanent(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("hello", encoding="utf-8")

    _format_failure(tmp_path / "notes.txt")


def test_an_export_without_a_conversation_file_is_permanent(tmp_path: Path) -> None:
    (tmp_path / "export").mkdir()
    (tmp_path / "export" / "chat.html").write_text("<html/>", encoding="utf-8")

    _format_failure(tmp_path / "export")


def test_both_the_single_and_the_split_form_is_ambiguous(tmp_path: Path) -> None:
    synth.write_directory(tmp_path / "export", RECORDS)
    synth.write_directory(tmp_path / "export", RECORDS, split=2)

    _format_failure(tmp_path / "export")
