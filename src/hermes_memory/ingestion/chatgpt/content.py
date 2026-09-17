"""One ChatGPT message as a turn of the normalized model (research R5, R6).

Whatever a message carries, it has an outcome here: it becomes text, a non-text marker, or an
omission with a reason. Nothing is dropped without one of the three.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from hermes_memory.ingestion.chatgpt.thread import UnreadableRecord
from hermes_memory.normalization import Message, Role

__all__ = ["ReadMessage", "read_message"]

_ROLES = {role.value: role for role in Role}


@dataclass(frozen=True, slots=True)
class ReadMessage:
    """A message's outcome: a turn, or the reason it was omitted."""

    turn: Message | None
    omitted: str | None = None


def _role(body: Mapping[str, Any]) -> Role:
    author = body.get("author")
    role = author.get("role") if isinstance(author, Mapping) else None
    if role not in _ROLES:
        raise UnreadableRecord("a message has no recognized author role")
    return _ROLES[role]


def _strings(parts: Any) -> list[str]:
    if not isinstance(parts, list):
        return []
    return [part for part in parts if isinstance(part, str)]


def export_time(value: Any) -> datetime | None:
    """An export's seconds-since-the-epoch as a UTC instant, or None where the export has none.

    Never a clock (§11). A value that is present but is not a usable time fails the conversation
    rather than being read as absent: an absent time and a corrupt one are different facts.
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise UnreadableRecord("a time is not a finite number of seconds")
    try:
        return datetime.fromtimestamp(value, UTC)
    except (OverflowError, OSError, ValueError) as out_of_range:
        raise UnreadableRecord("a time is outside the representable range") from out_of_range


def read_message(body: Mapping[str, Any]) -> ReadMessage:
    content = body.get("content")
    if not isinstance(content, Mapping):
        content = {}
    text = "\n".join(_strings(content.get("parts")))
    return ReadMessage(
        turn=Message(role=_role(body), text=text, sent_at=export_time(body.get("create_time")))
    )
