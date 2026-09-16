"""An in-memory secret sanitizer: one marker, replaced everywhere, counted and reported.

It recognizes one string, which is enough to prove the shape of the answer. The patterns that find
real credentials are #11's, and the categories they report in are §13's, declared in
`hermes_memory.sanitization`.

"Everywhere" is the point worth copying: the title, every message's text, every tool request and
result, and every attachment name. §13's own example is tool output, and the title reaches the
memory store in provenance — a sanitizer that rewrote only message text would leak through both
(SS-3).
"""

from __future__ import annotations

from hermes_memory.normalization import Conversation, Message
from hermes_memory.sanitization import RedactionCategory, RedactionReport, SanitizationError

REDACTED = "[REDACTED]"


class InMemorySecretSanitizer:
    """Replaces a known marker in every text-bearing field, preserving the words around it."""

    def __init__(
        self,
        secret: str = "hunter2",
        category: RedactionCategory = RedactionCategory.PASSWORD,
        *,
        fails: bool = False,
    ) -> None:
        self._secret = secret
        self._category = category
        self._fails = fails

    def sanitize(self, conversation: Conversation) -> tuple[Conversation, RedactionReport]:
        if self._fails:
            raise SanitizationError(
                "the conversation could not be rewritten", subject=conversation.document_id
            )

        redactions = self._count(conversation.title) + sum(
            self._count_in(message) for message in conversation.messages
        )
        if not redactions:
            return conversation, RedactionReport()

        sanitized = conversation.model_copy(
            update={
                "title": self._redact(conversation.title),
                "messages": tuple(
                    self._redact_message(message) for message in conversation.messages
                ),
            }
        )
        return sanitized, RedactionReport(counts={self._category: redactions})

    def _count(self, text: str | None) -> int:
        return text.count(self._secret) if text else 0

    def _count_in(self, message: Message) -> int:
        return (
            self._count(message.text)
            + sum(
                self._count(tool.request) + self._count(tool.result)
                for tool in message.tool_activity
            )
            + sum(self._count(part.name) for part in message.non_text_parts)
        )

    def _redact(self, text: str | None) -> str | None:
        return text.replace(self._secret, REDACTED) if text else text

    def _redact_message(self, message: Message) -> Message:
        return message.model_copy(
            update={
                "text": self._redact(message.text),
                "tool_activity": tuple(
                    tool.model_copy(
                        update={
                            "request": self._redact(tool.request),
                            "result": self._redact(tool.result),
                        }
                    )
                    for tool in message.tool_activity
                ),
                "non_text_parts": tuple(
                    part.model_copy(update={"name": self._redact(part.name)})
                    for part in message.non_text_parts
                ),
            }
        )
