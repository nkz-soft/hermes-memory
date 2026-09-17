"""One export record as a normalized conversation (research R4 to R7)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from hermes_memory.ingestion.chatgpt.content import read_message
from hermes_memory.ingestion.chatgpt.thread import UnreadableRecord, reconstruct
from hermes_memory.normalization import Conversation, Source

__all__ = ["ReadConversation", "parse_record"]


@dataclass(frozen=True, slots=True)
class ReadConversation:
    conversation: Conversation


def _time(value: Any) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value, UTC)


def parse_record(value: object) -> ReadConversation:
    if not isinstance(value, Mapping):
        raise UnreadableRecord("a conversation record is not a JSON object")
    mapping = value.get("mapping")
    thread = reconstruct(mapping, value.get("current_node"))
    assert isinstance(mapping, Mapping)

    turns = []
    for node_id in thread.node_ids:
        body = mapping[node_id].get("message")
        if body is None:
            continue
        read = read_message(body)
        if read.turn is not None:
            turns.append(read.turn)

    return ReadConversation(
        conversation=Conversation(
            source=Source.CHATGPT,
            source_id=value.get("conversation_id") or value.get("id"),
            title=value.get("title"),
            started_at=_time(value.get("create_time")),
            last_activity_at=_time(value.get("update_time")),
            messages=tuple(turns),
        )
    )
