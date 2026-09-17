"""`ChatGPTExportSource` end to end over synthesized exports (contracts/chatgpt-source.md)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from structlog.testing import capture_logs

from hermes_memory.errors import BoundaryError
from hermes_memory.ingestion import SourceConversation, SourceFormatError, SourceUnavailable
from hermes_memory.ingestion.chatgpt import ChatGPTExportSource
from hermes_memory.ingestion.chatgpt.conversation import parse_record
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


def test_each_original_is_the_records_exact_text(tmp_path: Path) -> None:
    records = _records()
    records[1]["title"] = 'Кириллица, emoji 🚀 and "quotes"'
    synth.write_directory(tmp_path / "export", records)

    read = list(ChatGPTExportSource(tmp_path / "export").read())

    assert [one.original.content for one in read] == [
        synth.serialize(one).encode("utf-8") for one in records
    ]
    assert all(one.original.media_type == "application/json" for one in read)


def test_an_original_alone_parses_to_the_same_conversation(tmp_path: Path) -> None:
    synth.write_zip(tmp_path / "export.zip", _records())

    for one in ChatGPTExportSource(tmp_path / "export.zip").read():
        reparsed = parse_record(json.loads(one.original.content))
        assert reparsed.conversation == one.conversation


MARKER = "zq-unique-marker-4471"


def test_one_content_free_event_is_logged_per_conversation(tmp_path: Path) -> None:
    records = _records(2)
    records[0]["title"] = f"title {MARKER}"
    records[1]["mapping"]["n1"]["message"]["content"] = {"content_type": "novel", "x": MARKER}
    synth.write_directory(tmp_path / "export", records)

    with capture_logs() as events:
        read = list(ChatGPTExportSource(tmp_path / "export").read())

    logged = [event for event in events if event["event"] == "chatgpt.conversation.read"]
    assert len(logged) == len(read) == 2
    assert logged[0] == {
        "event": "chatgpt.conversation.read",
        "log_level": "info",
        "source_id": "conv-0",
        "nodes": 3,
        "turns": 2,
        "folded_tool_results": 0,
        "structural": 1,
        "hidden": 0,
        "hidden_reasoning": 0,
        "abandoned_branch": 0,
        "fallback_branch": False,
        "start_from_messages": False,
        "inconsistent_times": False,
    }
    assert logged[1]["unrecognized_content_types"] == ["novel"]
    assert MARKER not in repr(events)


# --- one bad conversation does not stop the import (User Story 4) ---------------------------------


def _drain(source: ChatGPTExportSource) -> tuple[list[str], list[BoundaryError]]:
    read: list[str] = []
    failures: list[BoundaryError] = []
    iterator = source.read()
    while True:
        try:
            read.append(next(iterator).conversation.source_id)
        except StopIteration:
            return read, failures
        except BoundaryError as failure:
            failures.append(failure)


def _with_marker(record: synth.Record) -> synth.Record:
    record["title"] = f"title {MARKER}"
    for node in record["mapping"].values():
        if node["message"] is not None:
            node["message"]["content"] = {"content_type": "text", "parts": [f"text {MARKER}"]}
    return record


def _break_not_an_object(records):
    records[1] = [MARKER]


def _break_no_identifier(records):
    del records[1]["conversation_id"]


def _break_dangling_parent(records):
    records[1]["mapping"]["n2"]["parent"] = "gone"


def _break_no_time(records):
    records[1]["create_time"] = None
    records[1]["update_time"] = None


BREAKAGES = {
    "not an object": (_break_not_an_object, None),
    "no identifier": (_break_no_identifier, None),
    "dangling parent": (_break_dangling_parent, "conv-1"),
    "no time anywhere": (_break_no_time, "conv-1"),
}


@pytest.mark.parametrize("name", list(BREAKAGES))
def test_one_unreadable_conversation_fails_alone(tmp_path: Path, name: str) -> None:
    breakage, subject = BREAKAGES[name]
    records = [_with_marker(one) for one in _records()]
    breakage(records)
    synth.write_directory(tmp_path / "export", records)

    read, failures = _drain(ChatGPTExportSource(tmp_path / "export"))

    assert read == ["conv-0", "conv-2"]
    assert len(failures) == 1
    assert isinstance(failures[0], SourceFormatError)
    assert failures[0].subject == subject
    assert failures[0].retryable is False
    assert MARKER not in str(failures[0])
    assert MARKER not in failures[0].message


def test_a_value_the_model_refuses_fails_alone_without_echoing_it(tmp_path: Path) -> None:
    records = _records()
    records[1]["mapping"]["n1"]["message"]["content"]["parts"] = [f"{MARKER} SURROGATE"]
    text = synth.export_text(records).replace("SURROGATE", "\\udc00")
    (tmp_path / "export").mkdir()
    (tmp_path / "export" / "conversations.json").write_text(text, encoding="utf-8")

    read, failures = _drain(ChatGPTExportSource(tmp_path / "export"))

    assert read == ["conv-0", "conv-2"]
    assert [failure.subject for failure in failures] == ["conv-1"]
    assert MARKER not in str(failures[0])
    assert "udc00" not in str(failures[0]).lower()


def test_a_duplicate_identifier_fails_the_second_conversation(tmp_path: Path) -> None:
    records = _records()
    records[2]["conversation_id"] = "conv-0"
    synth.write_directory(tmp_path / "export", records)

    read, failures = _drain(ChatGPTExportSource(tmp_path / "export"))

    assert read == ["conv-0", "conv-1"]
    assert [failure.subject for failure in failures] == ["conv-0"]
    assert isinstance(failures[0], SourceFormatError)


def test_invalid_json_ends_the_read_after_what_came_before(tmp_path: Path) -> None:
    records = _records(1)
    (tmp_path / "export").mkdir()
    (tmp_path / "export" / "conversations.json").write_text(
        synth.export_text(records)[:-1] + ', {"broken": }]', encoding="utf-8"
    )

    read, failures = _drain(ChatGPTExportSource(tmp_path / "export"))

    assert read == ["conv-0"]
    assert len(failures) == 1
    assert isinstance(failures[0], SourceFormatError)
    assert failures[0].subject is None


def test_an_unreachable_export_is_retryable(tmp_path: Path) -> None:
    read, failures = _drain(ChatGPTExportSource(tmp_path / "missing.zip"))

    assert read == []
    assert len(failures) == 1
    assert isinstance(failures[0], SourceUnavailable)
    assert failures[0].retryable is True


def test_an_export_level_failure_is_not_repeated(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("hello", encoding="utf-8")

    read, failures = _drain(ChatGPTExportSource(tmp_path / "notes.txt"))

    assert read == []
    assert len(failures) == 1
    assert failures[0].subject is None


def test_reading_twice_yields_equal_results(tmp_path: Path) -> None:
    synth.write_zip(tmp_path / "export.zip", _records())
    source = ChatGPTExportSource(tmp_path / "export.zip")

    assert list(source.read()) == list(source.read())
