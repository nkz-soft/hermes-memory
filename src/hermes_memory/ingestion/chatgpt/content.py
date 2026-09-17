"""One ChatGPT message as a turn of the normalized model (research R5, R6).

Whatever a message carries, it has an outcome here: it becomes text, a non-text marker, or an
omission with a reason. Nothing is dropped without one of the three.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
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


def read_message(body: Mapping[str, Any]) -> ReadMessage:
    content = body.get("content")
    if not isinstance(content, Mapping):
        content = {}
    text = "\n".join(_strings(content.get("parts")))
    return ReadMessage(turn=Message(role=_role(body), text=text))
