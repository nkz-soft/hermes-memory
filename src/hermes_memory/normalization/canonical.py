"""The canonical form of a conversation, and the content hash of ARCHITECTURE.md §17.

The §17 skip rests entirely on this value: a conversation whose source id and hash are unchanged is
skipped before any call is made, which is what keeps a re-import from paying for extraction twice
(Principle II). ADR-006 decision 4 fixes what the hash covers — the messages, their order and their
timestamps — and what it excludes — the title and any metadata the importer produces.

Two properties are load-bearing, and both are asserted in a separate process by
`tests/unit/test_canonical.py`:

* **Determinism.** Two structurally identical conversations hash equal in any process, in any run,
  under any hash seed. A hash that varies turns every refresh into a full re-extraction.
* **Coverage.** The included fields are written out by name below. They are never derived from a
  dump of the model, because then every field a later feature adds would join the hash silently —
  and a field joining the hash silently is every stored hash invalidated, discovered months later
  as a mass re-extraction (research.md R1).

The full contract is
`specs/006-normalized-conversation-model/contracts/canonical-form.md`.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from hermes_memory.normalization.conversation import Conversation, Message

__all__ = ["CANONICAL_VERSION", "canonical_bytes", "canonical_form", "content_hash"]

CANONICAL_VERSION = 1
"""The version of this representation, carried inside the payload.

It exists so that a future change to what the hash covers is a value a stored hash can be compared
against, rather than a silent divergence. Changing the coverage means incrementing this, in a
commit that states what re-extracts as a result.
"""


def _format(moment: datetime) -> str:
    """Render a UTC datetime, without asking the platform how to do it.

    `strftime("%Y")` is the one remaining platform dependency in a function whose whole purpose is
    platform independence: below year 1000 it zero-pads on some C libraries and not on others. No
    real export reaches that, and a determinism routine that is deterministic only for plausible
    inputs is not what §17 needs.
    """
    return (
        f"{moment.year:04d}-{moment.month:02d}-{moment.day:02d}"
        f"T{moment.hour:02d}:{moment.minute:02d}:{moment.second:02d}"
        f".{moment.microsecond:06d}Z"
    )


def _render(moment: datetime | None) -> str | None:
    """A timestamp as UTC at fixed precision, or `None` rendered as itself.

    Converting first is what makes an export taken in Moscow hash equal to the same conversation
    exported in UTC — the same instant, two offsets. The fixed `%f` matters for the same reason at
    a smaller scale: `isoformat` omits zero microseconds, so a timestamp landing on a whole second
    would otherwise render in a different shape from one that does not (research.md R4).

    A missing time stays missing. §11 forbids substituting the import time or the current clock,
    and the canonical form renders the absence as itself.
    """
    if moment is None:
        return None
    return _format(moment.astimezone(UTC))


def _message_form(message: Message) -> dict[str, Any]:
    """One message, reduced to the fields ADR-006 decision 4 covers.

    Tool activity and non-text parts are included because they are part of the message rather than
    metadata about it: §7 exists partly to preserve the chain command → error → investigation →
    solution, so a tool result that changed is content that changed (research.md R11).
    """
    return {
        "role": message.role.value,
        "text": message.text,
        "sent_at": _render(message.sent_at),
        "tool_activity": [
            {"name": activity.name, "request": activity.request, "result": activity.result}
            for activity in message.tool_activity
        ],
        "non_text_parts": [
            {"kind": part.kind.value, "name": part.name} for part in message.non_text_parts
        ],
    }


def canonical_form(conversation: Conversation) -> dict[str, Any]:
    """The deterministic representation of a conversation's content.

    Holds plain JSON types only — no model, no enum instance, no datetime — so the bytes below are
    produced without a custom encoder. A value needing one would be a value whose rendering nobody
    decided.

    The title is absent because ADR-006 decision 4 excludes it. The source and the native id are
    absent because they are the key this hash is filed under in the import state, not part of what
    is being compared.

    The conversation's own `started_at` and `last_activity_at` are absent too, and that one is this
    feature's decision rather than the ADR's — it names the *messages'* timestamps. They are
    excluded because a start time is a property of the conversation rather than of what was said,
    and because including them would re-extract the whole corpus the day a parser learns to fill in
    `last_activity_at`. The consequence — a corrected start time goes stale in the bank exactly as
    a rename does — is written down in `contracts/canonical-form.md`, where changing the trade is
    named as an amendment to ADR-006 rather than an edit here.
    """
    return {
        "version": CANONICAL_VERSION,
        "messages": [_message_form(message) for message in conversation.messages],
    }


def canonical_bytes(conversation: Conversation) -> bytes:
    """The canonical form as the exact bytes that are hashed.

    Every degree of freedom JSON leaves is closed here. `sort_keys` makes key order independent of
    construction order; `separators` removes whitespace; `ensure_ascii=False` keeps the text as
    text, which matters because this corpus is substantially non-ASCII and escaping would make the
    bytes depend on something the content does not control (research.md R2).

    Text is hashed as it stands: no Unicode normalization, no trimming, no case folding. Two
    byte-different strings are two different contents, and this module does not decide otherwise on
    the parser's behalf.
    """
    payload = canonical_form(conversation)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def content_hash(conversation: Conversation) -> str:
    """The value §17 stores in the import state and compares on the next run.

    SHA-256 because this is an identity check that will be stored and compared for years, and the
    recognizable choice costs nothing here — the expensive part of an import is extraction, by
    orders of magnitude (research.md R3).
    """
    return hashlib.sha256(canonical_bytes(conversation)).hexdigest()
