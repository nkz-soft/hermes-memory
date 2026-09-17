"""One export record as a normalized conversation (research R4 to R7).

The conversation comes with an account of the record it was read from: how many nodes became
turns, how many were folded into a tool call, and how many were left out and why. The account is
what makes "skip nothing without recording that it was skipped" checkable — its counts must add up
to every node in the graph, or it refuses to exist.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from hermes_memory.ingestion.chatgpt.content import (
    HIDDEN,
    HIDDEN_REASONING,
    export_time,
    fold_tool_calls,
    read_message,
)
from hermes_memory.ingestion.chatgpt.thread import UnreadableRecord, reconstruct
from hermes_memory.normalization import Conversation, Message, Source

__all__ = ["ReadConversation", "ThreadAccount", "parse_record"]


@dataclass(frozen=True, slots=True)
class ThreadAccount:
    """What reading one conversation did with every node of its graph. Never content (R9)."""

    source_id: str
    nodes: int = 0
    turns: int = 0
    folded_tool_results: int = 0
    structural: int = 0
    hidden: int = 0
    hidden_reasoning: int = 0
    abandoned_branch: int = 0
    fallback_branch: bool = False
    start_from_messages: bool = False
    inconsistent_times: bool = False
    unrecognized_content_types: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        counts = (
            self.turns,
            self.folded_tool_results,
            self.structural,
            self.hidden,
            self.hidden_reasoning,
            self.abandoned_branch,
        )
        if any(count < 0 for count in counts):
            raise ValueError("an account count is negative")
        if sum(counts) != self.nodes:
            raise ValueError(f"the account accounts for {sum(counts)} of {self.nodes} nodes")
        if list(self.unrecognized_content_types) != sorted(set(self.unrecognized_content_types)):
            raise ValueError("unrecognized content types are not sorted and distinct")

    def as_fields(self) -> dict[str, Any]:
        """The account as log fields; the type list is left out when empty."""
        fields = asdict(self)
        types = fields.pop("unrecognized_content_types")
        if types:
            fields["unrecognized_content_types"] = list(types)
        return fields


@dataclass(frozen=True, slots=True)
class ReadConversation:
    conversation: Conversation
    account: ThreadAccount


def _source_id(record: Mapping[str, Any]) -> str:
    for field in ("conversation_id", "id"):
        value = record.get(field)
        if isinstance(value, str) and value:
            return value
    raise UnreadableRecord("a conversation record has no identifier")


def parse_record(value: object) -> ReadConversation:
    if not isinstance(value, Mapping):
        raise UnreadableRecord("a conversation record is not a JSON object")
    source_id = _source_id(value)
    mapping = value.get("mapping")
    thread = reconstruct(mapping, value.get("current_node"))
    assert isinstance(mapping, Mapping)

    items: list[tuple[Mapping[str, Any], Message]] = []
    omitted = {HIDDEN: 0, HIDDEN_REASONING: 0}
    structural = 0
    unrecognized: set[str] = set()
    for node_id in thread.node_ids:
        body = mapping[node_id].get("message")
        if body is None:
            structural += 1
            continue
        if not isinstance(body, Mapping):
            raise UnreadableRecord("a node's message is not a JSON object")
        read = read_message(body)
        unrecognized.update(read.unrecognized)
        if read.turn is None:
            assert read.omitted is not None
            omitted[read.omitted] += 1
        else:
            items.append((body, read.turn))
    turns, folded = fold_tool_calls(items)

    # §11: the start is the export's creation time, or failing that the earliest time a turn of
    # the conversation carries. Never the import's.
    started_at = export_time(value.get("create_time"))
    start_from_messages = started_at is None
    if started_at is None:
        started_at = min((t.sent_at for t in turns if t.sent_at is not None), default=None)
    if started_at is None:
        raise UnreadableRecord("a conversation has no creation time and no message time")

    last_activity_at: datetime | None = export_time(value.get("update_time"))
    inconsistent_times = last_activity_at is not None and last_activity_at < started_at
    if inconsistent_times:
        last_activity_at = None

    title = value.get("title")
    return ReadConversation(
        conversation=Conversation(
            source=Source.CHATGPT,
            source_id=source_id,
            title=title if isinstance(title, str) else None,
            started_at=started_at,
            last_activity_at=last_activity_at,
            messages=turns,
        ),
        account=ThreadAccount(
            source_id=source_id,
            nodes=len(mapping),
            turns=len(turns),
            folded_tool_results=folded,
            structural=structural,
            hidden=omitted[HIDDEN],
            hidden_reasoning=omitted[HIDDEN_REASONING],
            abandoned_branch=thread.abandoned,
            fallback_branch=thread.fallback_branch,
            start_from_messages=start_from_messages,
            inconsistent_times=inconsistent_times,
            unrecognized_content_types=tuple(sorted(unrecognized)),
        ),
    )
