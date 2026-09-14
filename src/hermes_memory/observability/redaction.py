"""Withholding credentials, and conversation content, from every record.

Placeholder. The slot exists in the chain from the start so that its position — immediately before
the renderer, after `format_exc_info` — is fixed by the pipeline rather than negotiated later; the
rosters and the walker arrive with User Story 2, against tests written first.
"""

from __future__ import annotations

from typing import Any

__all__ = ["redacting_processor"]


def redacting_processor(*, include_conversation_content: bool) -> Any:
    """Return the processor that withholds what must not be emitted."""

    def redact(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        return event_dict

    return redact
