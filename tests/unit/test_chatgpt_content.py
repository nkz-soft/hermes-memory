"""Turning one ChatGPT message into a turn of the normalized model (research R5, R6)."""

from __future__ import annotations

import pytest

from hermes_memory.ingestion.chatgpt.content import fold_tool_calls, read_message
from hermes_memory.normalization import NonTextKind, NonTextPart, Role, ToolActivity
from tests.synthetic import chatgpt_export as synth


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("user", Role.USER),
        ("assistant", Role.ASSISTANT),
        ("system", Role.SYSTEM),
        ("tool", Role.TOOL),
    ],
)
def test_roles_map(role: str, expected: Role) -> None:
    assert read_message(synth.message(role, "hello")).turn.role is expected


def test_text_parts_are_joined_with_a_newline() -> None:
    body = synth.message("user", content={"content_type": "text", "parts": ["one", "two"]})

    assert read_message(body).turn.text == "one\ntwo"


def test_text_is_carried_unaltered() -> None:
    text = "  leading spaces, trailing newline\n\ttab, Привет 🚀  "

    assert read_message(synth.message("user", text)).turn.text == text


def test_an_empty_message_is_kept() -> None:
    read = read_message(synth.message("assistant", ""))

    assert read.turn.text == ""
    assert read.omitted is None


# --- every content type has an outcome (User Story 3, research R5) --------------------------------


def _read(role: str = "assistant", **content):
    return read_message(synth.message(role, content=content))


def test_multimodal_text_keeps_text_and_marks_every_other_part() -> None:
    read = _read(
        "user",
        content_type="multimodal_text",
        parts=[
            "look at this",
            {"content_type": "image_asset_pointer", "asset_pointer": "file-service://a"},
            {"content_type": "audio_asset_pointer", "asset_pointer": "file-service://b"},
            {"content_type": "real_time_user_audio_video_asset_pointer"},
            {"content_type": "audio_transcription", "text": "spoken words"},
            {"content_type": "hologram"},
        ],
    )

    assert read.turn.text == "look at this\nspoken words"
    assert read.turn.non_text_parts == (
        NonTextPart(kind=NonTextKind.IMAGE),
        NonTextPart(kind=NonTextKind.AUDIO),
        NonTextPart(kind=NonTextKind.AUDIO),
        NonTextPart(kind=NonTextKind.OTHER, name="hologram"),
    )
    assert read.unrecognized == ("hologram",)


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ({"content_type": "code", "language": "python", "text": "print(1)"}, "print(1)"),
        ({"content_type": "execution_output", "text": "1"}, "1"),
        (
            {
                "content_type": "tether_quote",
                "url": "https://example.invalid/page",
                "title": "A page",
                "text": "quoted passage",
            },
            "A page\nhttps://example.invalid/page\nquoted passage",
        ),
        ({"content_type": "tether_quote", "text": "only text"}, "only text"),
        (
            {"content_type": "tether_browsing_display", "result": "L0: a result", "summary": "sum"},
            "L0: a result\nsum",
        ),
        (
            {"content_type": "system_error", "name": "Timeout", "text": "took too long"},
            "Timeout: took too long",
        ),
        (
            {
                "content_type": "user_editable_context",
                "user_profile": "profile words",
                "user_instructions": "instruction words",
            },
            "instruction words\nprofile words",
        ),
    ],
)
def test_textual_content_types_become_text(content: dict, expected: str) -> None:
    read = read_message(synth.message("assistant", content=content))

    assert read.turn.text == expected
    assert read.turn.non_text_parts == ()
    assert read.unrecognized == ()


@pytest.mark.parametrize("content_type", ["thoughts", "reasoning_recap"])
def test_hidden_reasoning_is_omitted(content_type: str) -> None:
    read = _read(
        content_type=content_type, thoughts=[{"summary": "s", "content": "c"}], content="c"
    )

    assert read.turn is None
    assert read.omitted == "hidden_reasoning"


@pytest.mark.parametrize(
    "content",
    [
        {"content_type": "text", "parts": ["system context"]},
        {"content_type": "user_editable_context", "user_profile": "p"},
    ],
)
def test_a_hidden_node_is_omitted_whatever_its_type(content: dict) -> None:
    read = read_message(synth.message("system", content=content, hidden=True))

    assert read.turn is None
    assert read.omitted == "hidden"


def test_an_unknown_content_type_keeps_the_message_and_names_the_type() -> None:
    read = _read(content_type="quantum_entanglement", payload="whatever")

    assert read.turn.text == ""
    assert read.turn.non_text_parts == (
        NonTextPart(kind=NonTextKind.OTHER, name="quantum_entanglement"),
    )
    assert read.unrecognized == ("quantum_entanglement",)


def test_attachments_become_file_markers() -> None:
    read = read_message(synth.message("user", "see files", attachments=["app.log", "trace.txt"]))

    assert read.turn.text == "see files"
    assert read.turn.non_text_parts == (
        NonTextPart(kind=NonTextKind.FILE, name="app.log"),
        NonTextPart(kind=NonTextKind.FILE, name="trace.txt"),
    )


# --- tool calls fold with their results (research R6) ---------------------------------------------


def _code(text: str, recipient: str) -> dict:
    return synth.message(
        "assistant", content={"content_type": "code", "text": text}, recipient=recipient
    )


def _output(text: str, name: str) -> dict:
    return synth.message(
        "tool", content={"content_type": "execution_output", "text": text}, author_name=name
    )


def _fold(*bodies: dict):
    return fold_tool_calls([(body, read_message(body).turn) for body in bodies])


def test_a_call_and_its_result_become_one_activity() -> None:
    turns, folded = _fold(
        synth.message("user", "compute"), _code("1 + 1", "python"), _output("2", "python")
    )

    assert folded == 1
    assert [turn.role for turn in turns] == [Role.USER, Role.ASSISTANT]
    assert turns[1].text == ""
    assert turns[1].tool_activity == (ToolActivity(name="python", request="1 + 1", result="2"),)


def test_a_call_without_a_result_keeps_no_result() -> None:
    turns, folded = _fold(_code("search terms", "browser"), synth.message("assistant", "done"))

    assert folded == 0
    assert turns[0].tool_activity == (ToolActivity(name="browser", request="search terms"),)
    assert turns[1].text == "done"


def test_a_result_from_another_tool_is_not_folded() -> None:
    turns, folded = _fold(_code("x", "python"), _output("from elsewhere", "browser"))

    assert folded == 0
    assert turns[0].tool_activity[0].result is None
    assert turns[1].role is Role.TOOL
    assert turns[1].text == "from elsewhere"


def test_a_lone_tool_message_stays_a_turn() -> None:
    turns, folded = _fold(_output("unprompted", "dalle.text2im"))

    assert folded == 0
    assert [(turn.role, turn.text) for turn in turns] == [(Role.TOOL, "unprompted")]


def test_a_folded_result_keeps_its_non_text_parts() -> None:
    image = synth.message(
        "tool",
        content={
            "content_type": "multimodal_text",
            "parts": [{"content_type": "image_asset_pointer", "asset_pointer": "file-service://i"}],
        },
        author_name="dalle.text2im",
    )

    turns, folded = _fold(_code("a lighthouse", "dalle.text2im"), image)

    assert folded == 1
    assert turns[0].non_text_parts == (NonTextPart(kind=NonTextKind.IMAGE),)
