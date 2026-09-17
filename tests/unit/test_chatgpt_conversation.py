"""One export record as a normalized conversation (research R4 to R7)."""

from __future__ import annotations

from hermes_memory.ingestion.chatgpt.conversation import parse_record
from hermes_memory.normalization import Message, Role, Source
from tests.synthetic import chatgpt_export as synth

say = synth.message


def test_a_linear_record_becomes_its_turns() -> None:
    record = synth.linear_record(
        "conv-1", say("user", "How do sagas retry?"), say("assistant", "With backoff.")
    )

    conversation = parse_record(record).conversation

    assert conversation.source is Source.CHATGPT
    assert conversation.messages == (
        Message(role=Role.USER, text="How do sagas retry?"),
        Message(role=Role.ASSISTANT, text="With backoff."),
    )


def test_a_branched_record_becomes_the_displayed_thread_only() -> None:
    mapping = {
        "root": synth.node("root", None, children=["u1"]),
        "u1": synth.node("u1", say("user", "question"), parent="root", children=["a1", "a2"]),
        "a1": synth.node("a1", say("assistant", "abandoned answer"), parent="u1"),
        "a2": synth.node("a2", say("assistant", "kept answer"), parent="u1"),
    }

    conversation = parse_record(synth.record("conv-2", mapping, "a2")).conversation

    assert [turn.text for turn in conversation.messages] == ["question", "kept answer"]
