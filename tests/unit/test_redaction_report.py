"""The report: truthful about counts, and incapable of carrying a value.

The failure this file guards against is the well-meaning one. A sanitizer that reports what it
found, rather than what it replaced, over-counts every overlap; one that reports the value or its
offset hands back the secret through the mechanism meant to audit its removal — and with the
archived original of §14 beside it, an offset is the secret (#9's research R6).

FR-008, SC-004, SC-005 and rule RR-8.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from hermes_memory.normalization import Conversation, Message, Role, Source
from hermes_memory.sanitization import PatternSecretSanitizer, RedactionCategory, RedactionReport
from tests.synthetic.secrets import sample_for

STARTED_AT = datetime(2026, 3, 4, 9, 30, tzinfo=UTC)

GITLAB = sample_for(RedactionCategory.GITLAB_TOKEN)
GITHUB = sample_for(RedactionCategory.GITHUB_TOKEN)


@pytest.fixture
def sanitizer() -> PatternSecretSanitizer:
    return PatternSecretSanitizer()


def conversation(*texts: str) -> Conversation:
    return Conversation(
        source=Source.CHATGPT,
        source_id="counted1",
        started_at=STARTED_AT,
        messages=tuple(
            Message(role=Role.ASSISTANT, text=text, sent_at=STARTED_AT) for text in texts
        ),
    )


def test_counts_are_per_category_and_sum_to_the_replacements_made(
    sanitizer: PatternSecretSanitizer,
) -> None:
    original = conversation(
        f"first {GITLAB.value}",
        f"second {GITLAB.value} and {GITHUB.value}",
    )

    sanitized, report = sanitizer.sanitize(original)

    assert report.counts == {
        RedactionCategory.GITLAB_TOKEN: 2,
        RedactionCategory.GITHUB_TOKEN: 1,
    }
    assert report.total == 3
    assert sanitized.model_dump_json().count("[REDACTED]") == 3


def test_a_category_with_nothing_redacted_is_absent_rather_than_zero(
    sanitizer: PatternSecretSanitizer,
) -> None:
    """A zero would claim the category was searched for, which the report cannot know (#9)."""
    _, report = sanitizer.sanitize(conversation(f"only {GITLAB.value}"))

    assert set(report.counts) == {RedactionCategory.GITLAB_TOKEN}


def test_a_clean_conversation_gives_an_empty_report_not_none(
    sanitizer: PatternSecretSanitizer,
) -> None:
    """SS-6: nothing found is a value, not an absence."""
    sanitized, report = sanitizer.sanitize(conversation("We moved the saga to Wolverine."))

    assert isinstance(report, RedactionReport)
    assert report.is_empty
    assert report.total == 0
    assert sanitized == conversation("We moved the saga to Wolverine.")


def test_a_conversation_with_no_messages_gives_an_empty_report(
    sanitizer: PatternSecretSanitizer,
) -> None:
    empty = Conversation(source=Source.CHATGPT, source_id="empty1", started_at=STARTED_AT)

    sanitized, report = sanitizer.sanitize(empty)

    assert sanitized == empty
    assert report.is_empty


def test_the_report_rendered_in_full_quotes_no_value(sanitizer: PatternSecretSanitizer) -> None:
    """SS-7, against the whole rendering rather than one field."""
    _, report = sanitizer.sanitize(conversation(f"token {GITLAB.value} and {GITHUB.value}"))

    rendered = f"{report.model_dump()!r} {report.model_dump_json()} {report!r}"

    assert GITLAB.value not in rendered
    assert GITHUB.value not in rendered
    assert set(type(report).model_fields) == {"counts"}


def test_sanitizing_twice_changes_nothing_and_reports_nothing(
    sanitizer: PatternSecretSanitizer,
) -> None:
    """RR-8. A conversation replayed from the archive (§14) is re-sanitized on the way through."""
    once, first = sanitizer.sanitize(conversation(f"token {GITLAB.value} expired"))
    twice, second = sanitizer.sanitize(once)

    assert first.total == 1
    assert twice == once
    assert second.is_empty
