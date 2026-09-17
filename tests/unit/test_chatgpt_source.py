"""`ChatGPTExportSource` end to end over synthesized exports (contracts/chatgpt-source.md)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_memory.ingestion import SourceConversation
from hermes_memory.ingestion.chatgpt import ChatGPTExportSource
from hermes_memory.normalization import Source
from tests.synthetic import chatgpt_export as synth

say = synth.message


def _records(count: int = 3) -> list[synth.Record]:
    return [
        synth.linear_record(
            f"conv-{i}", say("user", f"question {i}"), say("assistant", f"answer {i}")
        )
        for i in range(count)
    ]


def test_the_constructor_does_no_io(tmp_path: Path) -> None:
    source = ChatGPTExportSource(tmp_path / "does-not-exist.zip")

    assert source.source is Source.CHATGPT


@pytest.mark.parametrize(
    ("writer", "name"), [(synth.write_directory, "export"), (synth.write_zip, "export.zip")]
)
def test_conversations_are_yielded_in_export_order(tmp_path: Path, writer, name: str) -> None:
    writer(tmp_path / name, _records())

    read = list(ChatGPTExportSource(tmp_path / name).read())

    assert all(isinstance(one, SourceConversation) for one in read)
    assert [one.conversation.source_id for one in read] == ["conv-0", "conv-1", "conv-2"]
    assert [turn.text for turn in read[1].conversation.messages] == ["question 1", "answer 1"]


def test_a_split_export_reads_as_one(tmp_path: Path) -> None:
    synth.write_directory(tmp_path / "export", _records(5), split=2)

    read = list(ChatGPTExportSource(tmp_path / "export").read())

    assert [one.conversation.source_id for one in read] == [f"conv-{i}" for i in range(5)]


def test_reading_twice_yields_equal_results(tmp_path: Path) -> None:
    synth.write_zip(tmp_path / "export.zip", _records())
    source = ChatGPTExportSource(tmp_path / "export.zip")

    assert list(source.read()) == list(source.read())
