"""The secret sanitizer: a conversation in, a redacted conversation and a report out.

It visits the fields that can carry text a person wrote, and copies the rest. The alternative — a
recursive walk redacting every string it meets — is covered for free against a field added later,
and wrong for a specific reason: it would redact `source_id`, and `document_id` is derived from
`source_id`. A native id is an opaque token of exactly the shape several patterns look for, so the
generic walk trades Principle II's stable identity for a hypothetical field
(specs/009-secret-sanitizer/research.md R1).

`SCANNED_FIELDS` and `COPIED_FIELDS` are what buys that trade back. They are declared here and
checked against #8's model by `tests/structure/test_sanitizer_covers_the_model.py`, so a field added
to the model and forgotten here is a red test in the commit that adds it, rather than a leak nobody
sees.

This module does not log. Principle V forbids logging conversation content, and the surest way for
a sanitizer not to log content is for it not to log (research R8). What it produces is the report,
and the caller decides what to record.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from pydantic import ValidationError

from hermes_memory.normalization import Conversation, Message, ToolActivity
from hermes_memory.sanitization.patterns import PATTERNS, Pattern
from hermes_memory.sanitization.sanitizer import (
    RedactionCategory,
    RedactionReport,
    SanitizationError,
)
from hermes_memory.sanitization.scanner import redact

__all__ = ["COPIED_FIELDS", "SCANNED_FIELDS", "PatternSecretSanitizer"]

SCANNED_FIELDS: dict[str, frozenset[str]] = {
    "Conversation": frozenset({"title", "messages"}),
    "Message": frozenset({"text", "tool_activity", "non_text_parts"}),
    "ToolActivity": frozenset({"name", "request", "result"}),
    "NonTextPart": frozenset({"name"}),
}
"""Fields that carry text a person or a tool wrote — or that hold models which do.

`title` is here because it reaches the memory store as provenance, and the tool fields because
§13's own example is a tool output.
"""

COPIED_FIELDS: dict[str, frozenset[str]] = {
    "Conversation": frozenset({"source", "source_id", "started_at", "last_activity_at"}),
    "Message": frozenset({"role", "sent_at"}),
    "ToolActivity": frozenset(),
    "NonTextPart": frozenset({"kind"}),
}
"""Identity, time and closed vocabularies. Never scanned (RR-4)."""


class PatternSecretSanitizer:
    """Redacts the secrets a pattern recognizes, and reports what it redacted.

    The patterns are injectable so that a test can exercise this class with a table of its own; the
    default is the one table `patterns.py` declares, and callers have no reason to pass another.
    """

    def __init__(self, *, patterns: Sequence[Pattern] = PATTERNS) -> None:
        self._patterns = tuple(patterns)

    def sanitize(self, conversation: Conversation) -> tuple[Conversation, RedactionReport]:
        """Return the redacted conversation and the report of what was removed (SS-1 to SS-8)."""
        counts: dict[RedactionCategory, int] = {}
        try:
            title = self._text(conversation.title, counts)
            messages = tuple(self._message(message, counts) for message in conversation.messages)
            sanitized = conversation.model_copy(update={"title": title, "messages": messages})
        except (ValidationError, ValueError, TypeError, RecursionError, re.error) as failure:
            # Never "return the input unchanged": that would send the secret onwards under the
            # appearance of success, which is the failure SS-8 exists to forbid.
            raise SanitizationError(
                "the conversation could not be rewritten", subject=conversation.document_id
            ) from failure

        return sanitized, RedactionReport(counts=counts)

    def redact_text(self, text: str) -> tuple[str, RedactionReport]:
        """The one-string case, for this module's own tests and the quickstart.

        A convenience on the implementation, not part of the boundary: nothing outside
        `sanitization` and its tests may depend on it (data-model.md).
        """
        counts: dict[RedactionCategory, int] = {}
        return self._text(text, counts) or "", RedactionReport(counts=counts)

    def _message(self, message: Message, counts: dict[RedactionCategory, int]) -> Message:
        return message.model_copy(
            update={
                "text": self._text(message.text, counts) or "",
                "tool_activity": tuple(
                    self._tool_activity(activity, counts) for activity in message.tool_activity
                ),
                "non_text_parts": tuple(
                    part.model_copy(update={"name": self._text(part.name, counts)})
                    for part in message.non_text_parts
                ),
            }
        )

    def _tool_activity(
        self, activity: ToolActivity, counts: dict[RedactionCategory, int]
    ) -> ToolActivity:
        return activity.model_copy(
            update={
                "name": self._text(activity.name, counts) or activity.name,
                "request": self._text(activity.request, counts),
                "result": self._text(activity.result, counts),
            }
        )

    def _text(self, text: str | None, counts: dict[RedactionCategory, int]) -> str | None:
        """Redact one field, accumulating its counts. `None` stays `None`, never `""`."""
        if not text:
            return text

        redacted, found = redact(text, self._patterns)
        for category, count in found.items():
            counts[category] = counts.get(category, 0) + count
        return redacted
