"""One export record as a normalized conversation (research R4 to R7)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from hermes_memory.ingestion.chatgpt.conversation import ThreadAccount, parse_record
from hermes_memory.ingestion.chatgpt.thread import UnreadableRecord
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


# --- identity and time (User Story 2) ------------------------------------------------------------

T0 = datetime(2026, 3, 4, 9, 30, tzinfo=UTC)
T1 = datetime(2026, 3, 4, 11, 45, tzinfo=UTC)


def _read(record: synth.Record):
    return parse_record(record)


def test_the_native_id_is_the_identity() -> None:
    conversation = _read(synth.linear_record("6801a0b2-c3d4", say("user", "hi"))).conversation

    assert conversation.source_id == "6801a0b2-c3d4"
    assert conversation.document_id == "chatgpt:6801a0b2-c3d4"


def test_the_id_field_is_used_when_conversation_id_is_absent() -> None:
    record = synth.linear_record("legacy-id", say("user", "hi"), id_field="id")

    assert _read(record).conversation.source_id == "legacy-id"


def test_times_are_the_exports_own_in_utc() -> None:
    record = synth.linear_record(
        "c",
        say("user", "hi", create_time=synth.epoch(T0)),
        create_time=synth.epoch(T0),
        update_time=synth.epoch(T1),
    )

    conversation = _read(record).conversation

    assert conversation.started_at == T0
    assert conversation.started_at.utcoffset() == timedelta(0)
    assert conversation.last_activity_at == T1
    assert conversation.messages[0].sent_at == T0


def test_a_message_without_a_time_keeps_its_place_and_no_time() -> None:
    record = synth.linear_record(
        "c",
        say("user", "first", create_time=synth.epoch(T0)),
        say("assistant", "untimed", create_time=None),
        say("user", "third", create_time=synth.epoch(T1)),
    )

    messages = _read(record).conversation.messages

    assert [m.text for m in messages] == ["first", "untimed", "third"]
    assert messages[1].sent_at is None


@pytest.mark.parametrize("title", [None, synth.MISSING])
def test_a_missing_title_stays_missing(title) -> None:
    record = synth.linear_record("c", say("user", "hi"), title=title)

    assert _read(record).conversation.title is None


@pytest.mark.parametrize("missing", [None, synth.MISSING])
def test_without_a_creation_time_the_earliest_message_time_is_the_start(missing) -> None:
    record = synth.linear_record(
        "c",
        say("user", "a", create_time=synth.epoch(T1)),
        say("assistant", "b", create_time=synth.epoch(T0)),
        create_time=missing,
        update_time=missing,
    )

    read = _read(record)

    assert read.conversation.started_at == T0
    assert read.conversation.last_activity_at is None
    assert read.account.start_from_messages is True


def test_without_any_time_the_conversation_is_unreadable() -> None:
    record = synth.linear_record("c", say("user", "a"), create_time=None, update_time=None)

    with pytest.raises(UnreadableRecord):
        _read(record)


@pytest.mark.parametrize(
    "bad",
    [float("nan"), float("inf"), 1e20, -1e20, 10**400, "yesterday", True],
    ids=["nan", "inf", "far future", "far past", "huge integer", "string", "bool"],
)
def test_an_unusable_time_is_unreadable(bad) -> None:
    record = synth.linear_record("c", say("user", "a"))
    record["create_time"] = bad

    with pytest.raises(UnreadableRecord):
        _read(record)


def test_an_unusable_message_time_is_unreadable() -> None:
    record = synth.linear_record("c", say("user", "a", create_time=float("nan")))

    with pytest.raises(UnreadableRecord):
        _read(record)


def test_an_update_before_the_creation_is_dropped_and_recorded() -> None:
    record = synth.linear_record(
        "c", say("user", "a"), create_time=synth.epoch(T1), update_time=synth.epoch(T0)
    )

    read = _read(record)

    assert read.conversation.started_at == T1
    assert read.conversation.last_activity_at is None
    assert read.account.inconsistent_times is True


def test_an_empty_conversation_is_yielded_with_no_messages() -> None:
    record = synth.record("c", {"root": synth.node("root")}, "root")

    assert _read(record).conversation.messages == ()


def _everything() -> synth.Record:
    """A record exercising every omission reason, a fold, and an unrecognized type.

    root ── sys(hidden) ── u1 ─┬─ a_old (abandoned) ── a_old_tail (abandoned)
                               └─ think ── call ── out ── answer ── odd
    """
    code = {"content_type": "code", "text": "2 + 2"}
    output = {"content_type": "execution_output", "text": "4"}
    order = [
        ("root", None, ["sys"]),
        ("sys", say("system", "custom instructions", hidden=True), ["u1"]),
        ("u1", say("user", "add numbers"), ["a_old", "think"]),
        ("a_old", say("assistant", "abandoned"), ["a_old_tail"]),
        ("a_old_tail", say("user", "abandoned too"), []),
        ("think", say("assistant", content={"content_type": "thoughts", "thoughts": []}), ["call"]),
        ("call", say("assistant", content=code, recipient="python"), ["out"]),
        ("out", say("tool", content=output, author_name="python"), ["answer"]),
        ("answer", say("assistant", "It is 4."), ["odd"]),
        ("odd", say("assistant", content={"content_type": "novel_widget"}), []),
    ]
    parents = {child: parent for parent, _, children in order for child in children}
    mapping = {
        node_id: synth.node(node_id, body, parent=parents.get(node_id), children=children)
        for node_id, body, children in order
    }
    return synth.record("everything", mapping, "odd")


def test_every_node_is_accounted_for() -> None:
    read = _read(_everything())
    account = read.account

    assert account == ThreadAccount(
        source_id="everything",
        nodes=10,
        turns=4,
        folded_tool_results=1,
        structural=1,
        hidden=1,
        hidden_reasoning=1,
        abandoned_branch=2,
        unrecognized_content_types=("novel_widget",),
    )
    assert [turn.role for turn in read.conversation.messages] == [
        Role.USER,
        Role.ASSISTANT,
        Role.ASSISTANT,
        Role.ASSISTANT,
    ]


def test_a_plain_conversation_records_nothing_omitted_but_its_root() -> None:
    account = _read(synth.linear_record("c", say("user", "a"), say("assistant", "b"))).account

    assert (account.hidden, account.hidden_reasoning, account.abandoned_branch) == (0, 0, 0)
    assert account.folded_tool_results == 0
    assert account.structural == 1
    assert not (
        account.fallback_branch or account.start_from_messages or account.inconsistent_times
    )
    assert account.unrecognized_content_types == ()


def test_an_account_that_does_not_add_up_is_refused() -> None:
    with pytest.raises(ValueError, match="accounts for"):
        ThreadAccount(source_id="c", nodes=3, turns=1)


def test_unrecognized_types_are_sorted_and_distinct() -> None:
    record = synth.linear_record(
        "c",
        say("assistant", content={"content_type": "zeta"}),
        say("assistant", content={"content_type": "alpha"}),
        say("assistant", content={"content_type": "zeta"}),
    )

    assert _read(record).account.unrecognized_content_types == ("alpha", "zeta")


def test_no_clock_is_read(monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel = datetime(2099, 1, 1, tzinfo=UTC)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return sentinel

        @classmethod
        def today(cls):
            return sentinel

    for module in ("conversation", "content"):
        monkeypatch.setattr(f"hermes_memory.ingestion.chatgpt.{module}.datetime", Clock)
    record = synth.linear_record(
        "c", say("user", "a", create_time=None), create_time=None, update_time=None
    )
    record["mapping"]["n1"]["message"]["create_time"] = synth.epoch(T0)

    conversation = _read(record).conversation
    times = [conversation.started_at, conversation.last_activity_at]
    times += [m.sent_at for m in conversation.messages]

    assert sentinel not in times
