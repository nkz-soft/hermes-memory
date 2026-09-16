"""An in-memory secret sanitizer: one marker, replaced, counted and reported.

It recognizes one string, which is enough to prove the shape of the answer. The patterns that find
real credentials are #11's, and the categories they report in are §13's, declared in
`hermes_memory.sanitization`.
"""

from __future__ import annotations

from hermes_memory.normalization import Conversation
from hermes_memory.sanitization import RedactionCategory, RedactionReport, SanitizationError

REDACTED = "[REDACTED]"


class InMemorySecretSanitizer:
    """Replaces a known marker, preserving the words around it (§13)."""

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

        redactions = sum(message.text.count(self._secret) for message in conversation.messages)
        if not redactions:
            return conversation, RedactionReport()

        messages = tuple(
            message.model_copy(update={"text": message.text.replace(self._secret, REDACTED)})
            for message in conversation.messages
        )
        return (
            conversation.model_copy(update={"messages": messages}),
            RedactionReport(counts={self._category: redactions}),
        )
