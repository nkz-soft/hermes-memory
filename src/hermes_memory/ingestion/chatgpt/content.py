"""One ChatGPT message as a turn of the normalized model (research R5, R6).

Whatever a message carries, it has an outcome here: it becomes text, a non-text marker, or an
omission with a reason. Nothing is dropped without one of the three — including content types this
module has never heard of, which the service will keep introducing after it was written.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from hermes_memory.ingestion.chatgpt.thread import UnreadableRecord
from hermes_memory.normalization import Message, NonTextKind, NonTextPart, Role, ToolActivity

__all__ = [
    "HIDDEN",
    "HIDDEN_REASONING",
    "ReadMessage",
    "export_time",
    "fold_tool_calls",
    "read_message",
]

HIDDEN = "hidden"
HIDDEN_REASONING = "hidden_reasoning"

_ROLES = {role.value: role for role in Role}
_HIDDEN_REASONING_TYPES = frozenset({"thoughts", "reasoning_recap"})
_AUDIO_PARTS = frozenset({"audio_asset_pointer", "real_time_user_audio_video_asset_pointer"})


@dataclass(frozen=True, slots=True)
class ReadMessage:
    """A message's outcome: a turn, or the reason it was omitted."""

    turn: Message | None
    omitted: str | None = None
    unrecognized: tuple[str, ...] = ()
    """Content or part types this module does not know, each kept as an `OTHER` marker."""


def export_time(value: Any) -> datetime | None:
    """An export's seconds-since-the-epoch as a UTC instant, or None where the export has none.

    Never a clock (§11). A value that is present but is not a usable time fails the conversation
    rather than being read as absent: an absent time and a corrupt one are different facts.
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise UnreadableRecord("a time is not a number of seconds")
    try:
        if not math.isfinite(value):  # raises OverflowError itself for an integer beyond a float
            raise UnreadableRecord("a time is not a finite number of seconds")
        return datetime.fromtimestamp(value, UTC)
    except (OverflowError, OSError, ValueError) as out_of_range:
        raise UnreadableRecord("a time is outside the representable range") from out_of_range


def _role(body: Mapping[str, Any]) -> Role:
    author = body.get("author")
    role = author.get("role") if isinstance(author, Mapping) else None
    if role not in _ROLES:
        raise UnreadableRecord("a message has no recognized author role")
    return _ROLES[role]


def _string(content: Mapping[str, Any], field: str) -> str | None:
    value = content.get(field)
    return value if isinstance(value, str) and value else None


def _lines(*values: str | None) -> str:
    return "\n".join(value for value in values if value)


@dataclass(slots=True)
class _Parts:
    text: list[str]
    markers: list[NonTextPart]
    unrecognized: list[str]


def _parts(content: Mapping[str, Any], parts: _Parts) -> None:
    """`text` and `multimodal_text`: strings are text; everything else is a marker."""
    raw_parts = content.get("parts")
    for part in raw_parts if isinstance(raw_parts, list) else []:
        if isinstance(part, str):
            parts.text.append(part)
            continue
        part_type = part.get("content_type") if isinstance(part, Mapping) else None
        if part_type == "image_asset_pointer":
            parts.markers.append(NonTextPart(kind=NonTextKind.IMAGE))
        elif part_type in _AUDIO_PARTS:
            parts.markers.append(NonTextPart(kind=NonTextKind.AUDIO))
        elif part_type == "audio_transcription":
            if transcript := _string(part, "text"):
                parts.text.append(transcript)
        else:
            name = part_type if isinstance(part_type, str) and part_type else "unknown"
            parts.markers.append(NonTextPart(kind=NonTextKind.OTHER, name=name))
            parts.unrecognized.append(name)


def _editable_context(content: Mapping[str, Any]) -> str:
    return _lines(
        *(
            value
            for field, value in sorted(content.items())
            if field != "content_type" and isinstance(value, str)
        )
    )


_TEXTUAL: dict[str, Callable[[Mapping[str, Any]], str]] = {
    "code": lambda c: _string(c, "text") or "",
    "execution_output": lambda c: _string(c, "text") or "",
    "tether_quote": lambda c: _lines(_string(c, "title"), _string(c, "url"), _string(c, "text")),
    "tether_browsing_display": lambda c: _lines(_string(c, "result"), _string(c, "summary")),
    "system_error": lambda c: ": ".join(
        value for value in (_string(c, "name"), _string(c, "text")) if value
    ),
    "user_editable_context": _editable_context,
    "model_editable_context": _editable_context,
}


def read_message(body: Mapping[str, Any]) -> ReadMessage:
    role = _role(body)
    metadata = body.get("metadata")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    if metadata.get("is_visually_hidden_from_conversation") is True:
        return ReadMessage(turn=None, omitted=HIDDEN)

    content = body.get("content")
    content = content if isinstance(content, Mapping) else {}
    content_type = content.get("content_type")
    if content_type in _HIDDEN_REASONING_TYPES:
        return ReadMessage(turn=None, omitted=HIDDEN_REASONING)

    parts = _Parts(text=[], markers=[], unrecognized=[])
    if content_type in ("text", "multimodal_text"):
        _parts(content, parts)
    elif isinstance(content_type, str) and content_type in _TEXTUAL:
        parts.text.append(_TEXTUAL[content_type](content))
    else:
        name = content_type if isinstance(content_type, str) and content_type else "unknown"
        parts.markers.append(NonTextPart(kind=NonTextKind.OTHER, name=name))
        parts.unrecognized.append(name)

    attachments = metadata.get("attachments")
    for attachment in attachments if isinstance(attachments, list) else []:
        name = attachment.get("name") if isinstance(attachment, Mapping) else None
        parts.markers.append(
            NonTextPart(kind=NonTextKind.FILE, name=name if isinstance(name, str) else None)
        )

    return ReadMessage(
        turn=Message(
            role=role,
            text="\n".join(parts.text),
            sent_at=export_time(body.get("create_time")),
            non_text_parts=tuple(parts.markers),
        ),
        unrecognized=tuple(parts.unrecognized),
    )


def _tool_call(body: Mapping[str, Any], turn: Message) -> str | None:
    """The tool an assistant message addresses, or None for an ordinary turn."""
    recipient = body.get("recipient")
    if turn.role is Role.ASSISTANT and isinstance(recipient, str) and recipient not in ("", "all"):
        return recipient
    return None


def _tool_name(body: Mapping[str, Any]) -> Any:
    author = body.get("author")
    return author.get("name") if isinstance(author, Mapping) else None


def fold_tool_calls(
    items: Sequence[tuple[Mapping[str, Any], Message]],
) -> tuple[tuple[Message, ...], int]:
    """Turn each tool call into a `ToolActivity`, folding in the result that answers it (R6).

    A result answers a call when it is the very next turn on the thread, has the tool role, and
    names the tool the call addressed. Anything looser would pair a result with the wrong call.
    Returns the turns and the number of tool turns that were folded.
    """
    turns: list[Message] = []
    folded = 0
    position = 0
    while position < len(items):
        body, turn = items[position]
        position += 1
        tool = _tool_call(body, turn)
        if tool is None:
            turns.append(turn)
            continue

        result: str | None = None
        markers = turn.non_text_parts
        if position < len(items):
            next_body, next_turn = items[position]
            if next_turn.role is Role.TOOL and _tool_name(next_body) == tool:
                result = next_turn.text
                markers = markers + next_turn.non_text_parts
                folded += 1
                position += 1

        turns.append(
            turn.model_copy(
                update={
                    "text": "",
                    "tool_activity": (
                        ToolActivity(name=tool, request=turn.text or None, result=result),
                    ),
                    "non_text_parts": markers,
                }
            )
        )
    return tuple(turns), folded
