"""Turning one ChatGPT message into a turn of the normalized model (research R5, R6)."""

from __future__ import annotations

import pytest

from hermes_memory.ingestion.chatgpt.content import read_message
from hermes_memory.normalization import Role
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
