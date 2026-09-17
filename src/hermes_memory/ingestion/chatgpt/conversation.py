"""One export record as a normalized conversation (research R4 to R7)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from hermes_memory.ingestion.chatgpt.content import export_time, read_message
from hermes_memory.ingestion.chatgpt.thread import UnreadableRecord, reconstruct
from hermes_memory.normalization import Conversation, Source

__all__ = ["ReadConversation", "ThreadAccount", "parse_record"]


@dataclass(frozen=True, slots=True)
class ThreadAccount:
    """What reading one conversation did beyond the turns it produced. Never content."""

    source_id: str
    start_from_messages: bool = False
    inconsistent_times: bool = False


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

    turns = []
    for node_id in thread.node_ids:
        body = mapping[node_id].get("message")
        if body is None:
            continue
        if not isinstance(body, Mapping):
            raise UnreadableRecord("a node's message is not a JSON object")
        read = read_message(body)
        if read.turn is not None:
            turns.append(read.turn)

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
            messages=tuple(turns),
        ),
        account=ThreadAccount(
            source_id=source_id,
            start_from_messages=start_from_messages,
            inconsistent_times=inconsistent_times,
        ),
    )
