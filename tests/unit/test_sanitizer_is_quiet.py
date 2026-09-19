"""The sanitizer emits no log event at all.

Principle V forbids logging conversation content, and the surest way for this boundary not to log
content is for it not to log (specs/009-secret-sanitizer/research.md R8). The report is the audit
trail; what the run records from it is #19's decision.

Asserted against what the pipeline actually rendered, never against an event dictionary a caller
built — see the `rendered` fixture's own warning in `conftest.py`.
"""

from __future__ import annotations

import re
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any, cast

from hermes_memory.normalization import (
    Conversation,
    Message,
    NonTextKind,
    NonTextPart,
    Role,
    Source,
    ToolActivity,
)
from hermes_memory.observability import get_logger
from hermes_memory.sanitization import (
    PatternSecretSanitizer,
    RedactionCategory,
    SanitizationError,
)
from hermes_memory.sanitization.patterns import Pattern
from tests.synthetic.secrets import SAMPLES

from .conftest import Rendered

STARTED_AT = datetime(2026, 3, 4, 9, 30, tzinfo=UTC)


def a_conversation_full_of_secrets() -> Conversation:
    return Conversation(
        source=Source.CHATGPT,
        source_id="loud1",
        title=f"everything at once: {SAMPLES[4].value}",
        started_at=STARTED_AT,
        messages=tuple(
            Message(
                role=Role.ASSISTANT,
                text=sample.sentence,
                sent_at=STARTED_AT,
                tool_activity=(ToolActivity(name="http", request=sample.sentence, result="401"),),
                non_text_parts=(NonTextPart(kind=NonTextKind.FILE, name="config.env"),),
            )
            for sample in SAMPLES
        ),
    )


def test_sanitizing_emits_nothing(rendered: Rendered) -> None:
    """Nothing here configures logging: the default pipeline already writes, which is the point —
    a log line from this boundary would reach the output whether anyone configured it or not."""
    PatternSecretSanitizer().sanitize(a_conversation_full_of_secrets())

    assert rendered.text() == ""


def test_a_failure_emits_nothing_either(rendered: Rendered) -> None:
    """A boundary that logged its own failure would log the subject it failed on."""
    broken = PatternSecretSanitizer(patterns=_a_pattern_that_cannot_be_applied())

    with suppress(SanitizationError):
        broken.sanitize(a_conversation_full_of_secrets())

    assert rendered.text() == ""


def test_the_capture_would_notice_a_log_line(rendered: Rendered) -> None:
    """Without this, an empty buffer could mean the fixture captured nothing at all."""
    get_logger(__name__).info("a deliberate line")

    assert rendered.text() != ""


class _ExplodingExpression:
    """A pattern that fails while scanning, which is the one failure this boundary has."""

    def finditer(self, text: str) -> Any:
        raise re.error("the pattern could not be applied")


def _a_pattern_that_cannot_be_applied() -> tuple[Pattern, ...]:
    return (
        Pattern(
            category=RedactionCategory.API_KEY,
            expression=cast(re.Pattern[str], _ExplodingExpression()),
        ),
    )
