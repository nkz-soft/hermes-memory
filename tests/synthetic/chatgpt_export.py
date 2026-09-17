"""Build ChatGPT exports in code, for the parser's tests and for the contract harness.

The shape follows specs/008-chatgpt-export-source/research.md R1: a JSON array of conversation
records, each holding a `mapping` of message nodes and a `current_node`. Only the fields the source
reads are written, plus whatever a test passes explicitly. Every word of text is invented.

Records are serialized one at a time with `serialize`, and an export file is those serializations
joined, so a test knows the exact bytes the source must hand back as a conversation's original.
"""

from __future__ import annotations

import json
import zipfile
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from hermes_memory.normalization import Conversation, Message, NonTextKind

MISSING: Any = object()
"""Leave a field out of the record entirely, rather than writing it as null."""

Record = dict[str, Any]
Node = dict[str, Any]


def epoch(moment: datetime) -> float:
    return moment.timestamp()


def message(
    role: str,
    text: str | None = None,
    *,
    content: Mapping[str, Any] | None = None,
    create_time: float | None = None,
    recipient: str = "all",
    author_name: str | None = None,
    hidden: bool = False,
    attachments: Sequence[str] = (),
    message_id: str = "m",
) -> dict[str, Any]:
    """A message node's `message`. `text` is shorthand for a `text` content with one part."""
    if content is None:
        content = {"content_type": "text", "parts": [text or ""]}
    metadata: dict[str, Any] = {}
    if hidden:
        metadata["is_visually_hidden_from_conversation"] = True
    if attachments:
        metadata["attachments"] = [
            {"id": f"file-{i}", "name": name} for i, name in enumerate(attachments)
        ]
    return {
        "id": message_id,
        "author": {"role": role, "name": author_name, "metadata": {}},
        "create_time": create_time,
        "update_time": None,
        "content": dict(content),
        "status": "finished_successfully",
        "end_turn": True,
        "weight": 1.0,
        "metadata": metadata,
        "recipient": recipient,
    }


def node(
    node_id: str,
    body: dict[str, Any] | None = None,
    *,
    parent: str | None = None,
    children: Sequence[str] = (),
) -> Node:
    return {"id": node_id, "message": body, "parent": parent, "children": list(children)}


def chain(*bodies: dict[str, Any], prefix: str = "n") -> tuple[dict[str, Node], str]:
    """A linear graph: a structural root, then one node per message. Returns (mapping, leaf)."""
    ids = ["root", *(f"{prefix}{i}" for i in range(1, len(bodies) + 1))]
    mapping: dict[str, Node] = {}
    for position, node_id in enumerate(ids):
        body = None if position == 0 else {**bodies[position - 1], "id": node_id}
        mapping[node_id] = node(
            node_id,
            body,
            parent=None if position == 0 else ids[position - 1],
            children=[ids[position + 1]] if position + 1 < len(ids) else [],
        )
    return mapping, ids[-1]


def record(
    conversation_id: str,
    mapping: Mapping[str, Node],
    current_node: str | None,
    *,
    title: Any = "A synthesized conversation",
    create_time: Any = 1772616600.0,
    update_time: Any = 1772620200.0,
    id_field: str = "conversation_id",
) -> Record:
    written: Record = {
        "title": title,
        "create_time": create_time,
        "update_time": update_time,
        "mapping": dict(mapping),
        "moderation_results": [],
        "current_node": current_node,
        "plugin_ids": None,
        id_field: conversation_id,
        "default_model_slug": "synthetic",
    }
    return {key: value for key, value in written.items() if value is not MISSING}


def linear_record(conversation_id: str, *bodies: dict[str, Any], **fields: Any) -> Record:
    mapping, leaf = chain(*bodies)
    return record(conversation_id, mapping, leaf, **fields)


def _bodies_of(turn: Message) -> list[dict[str, Any]]:
    """One model turn rendered as the node bodies ChatGPT would have written for it (R5, R6)."""
    sent = None if turn.sent_at is None else epoch(turn.sent_at)
    bodies: list[dict[str, Any]] = []
    if turn.text or not turn.tool_activity:
        parts: list[Any] = [turn.text]
        for marker in turn.non_text_parts:
            if marker.kind is NonTextKind.IMAGE:
                parts.append(
                    {"content_type": "image_asset_pointer", "asset_pointer": "file-service://x"}
                )
        content = (
            {"content_type": "multimodal_text", "parts": parts}
            if len(parts) > 1
            else {"content_type": "text", "parts": parts}
        )
        files = [m.name or "file" for m in turn.non_text_parts if m.kind is NonTextKind.FILE]
        bodies.append(
            message(turn.role.value, content=content, create_time=sent, attachments=files)
        )
    for activity in turn.tool_activity:
        bodies.append(
            message(
                "assistant",
                content={
                    "content_type": "code",
                    "language": "unknown",
                    "text": activity.request or "",
                },
                create_time=sent,
                recipient=activity.name,
            )
        )
        if activity.result is not None:
            bodies.append(
                message(
                    "tool",
                    content={"content_type": "execution_output", "text": activity.result},
                    create_time=sent,
                    author_name=activity.name,
                )
            )
    return bodies


def from_conversation(conversation: Conversation) -> Record:
    """Render #8's model as the linear ChatGPT record that parses back into it."""
    bodies = [body for turn in conversation.messages for body in _bodies_of(turn)]
    return linear_record(
        conversation.source_id,
        *bodies,
        title=conversation.title,
        create_time=epoch(conversation.started_at),
        update_time=(
            None if conversation.last_activity_at is None else epoch(conversation.last_activity_at)
        ),
    )


def serialize(one: Record) -> str:
    """The exact text a record occupies inside an export file."""
    return json.dumps(one, ensure_ascii=False)


def export_text(records: Iterable[Record]) -> str:
    return "[" + ", ".join(serialize(one) for one in records) + "]"


def _files(records: Sequence[Record], split: int | None) -> dict[str, str]:
    if split is None:
        return {"conversations.json": export_text(records)}
    return {
        f"conversations-{index:03d}.json": export_text(records[start : start + split])
        for index, start in enumerate(range(0, max(len(records), 1), split))
    }


def write_directory(path: Path, records: Sequence[Record], *, split: int | None = None) -> Path:
    """Write an extracted export. `split` is records per file, producing a split export."""
    path.mkdir(parents=True, exist_ok=True)
    for name, text in _files(records, split).items():
        (path / name).write_text(text, encoding="utf-8")
    (path / "chat.html").write_text("<html>not read</html>", encoding="utf-8")
    return path


def write_zip(path: Path, records: Sequence[Record], *, split: int | None = None) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        for name, text in _files(records, split).items():
            archive.writestr(name, text.encode("utf-8"))
        archive.writestr("chat.html", b"<html>not read</html>")
    return path
