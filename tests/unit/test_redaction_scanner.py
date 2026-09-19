"""The scanner as a mechanism: find spans, resolve overlaps, rewrite once, count what was replaced.

The table used here is **defined in this file**, not imported. What is under test is the machinery
every category's pattern runs through — that a value group is replaced while its key survives, that
an overlap is redacted once, that a placeholder is not a secret — and a test that reached for the
real table would fail for a reason in a regular expression rather than in the scanner.

Rules RR-1, RR-2, RR-5, RR-6 and RR-7 of specs/009-secret-sanitizer/contracts/redaction-rules.md.
"""

from __future__ import annotations

import re

import pytest

from hermes_memory.sanitization import RedactionCategory
from hermes_memory.sanitization.patterns import Pattern, is_placeholder
from hermes_memory.sanitization.scanner import REDACTED, find_spans, redact, resolve

WHOLE_VALUE = Pattern(
    category=RedactionCategory.GITLAB_TOKEN,
    expression=re.compile(r"glpat-[A-Za-z0-9_-]{20}"),
)
"""Value-shaped: the match is the value."""

KEYED = Pattern(
    category=RedactionCategory.PASSWORD,
    expression=re.compile(r"(?i:password)\s*=\s*(?P<value>\S+)"),
    value_group="value",
)
"""Keyed: only the group named `value` is replaced, so the key survives (RR-2)."""

BLOCK = Pattern(
    category=RedactionCategory.PRIVATE_KEY,
    expression=re.compile(r"BEGIN KEY\n(?P<value>.+?)\nEND KEY", re.DOTALL),
    value_group="value",
)
"""A delimited block whose body spans line breaks."""

LONG_ENOUGH = Pattern(
    category=RedactionCategory.API_KEY,
    expression=re.compile(r"key:(?P<value>\S+)"),
    value_group="value",
    minimum_length=8,
)

SAMPLE = "glpat-" + "0" * 19 + "A"
"""Synthesized, never a real token: twenty characters of the documented shape (CLAUDE.md)."""


def test_a_single_match_is_replaced_and_the_text_either_side_survives() -> None:
    """RR-1 and RR-2, on §13's own example."""
    text = f"GitLab request using token {SAMPLE} returned HTTP 401 Unauthorized"

    redacted, counts = redact(text, (WHOLE_VALUE,))

    assert redacted == "GitLab request using token [REDACTED] returned HTTP 401 Unauthorized"
    assert counts == {RedactionCategory.GITLAB_TOKEN: 1}


def test_the_replacement_does_not_reveal_the_length_of_what_it_replaced() -> None:
    """RR-1: not a mask, not an elision — the same literal whatever was there."""
    short, _ = redact("key:abcdefghij", (LONG_ENOUGH,))
    long, _ = redact(f"key:{'a' * 300}", (LONG_ENOUGH,))

    assert short == long == f"key:{REDACTED}"


def test_the_same_value_twice_is_replaced_twice_and_counted_twice() -> None:
    """RR-5: the count is of replacements, not of distinct values."""
    redacted, counts = redact(f"first {SAMPLE} then {SAMPLE} again", (WHOLE_VALUE,))

    assert redacted == f"first {REDACTED} then {REDACTED} again"
    assert counts == {RedactionCategory.GITLAB_TOKEN: 2}


def test_two_different_secrets_in_one_string_are_both_replaced() -> None:
    redacted, counts = redact(f"{SAMPLE} and password = swordfish!", (WHOLE_VALUE, KEYED))

    assert redacted == f"{REDACTED} and password = {REDACTED}"
    assert counts == {
        RedactionCategory.GITLAB_TOKEN: 1,
        RedactionCategory.PASSWORD: 1,
    }


def test_a_keyed_pattern_keeps_its_key() -> None:
    """RR-2: `DATABASE_PASSWORD=[REDACTED]` is knowledge; a bare `[REDACTED]` is not."""
    redacted, _ = redact("DATABASE_PASSWORD=swordfish!", (KEYED,))

    assert redacted == f"DATABASE_PASSWORD={REDACTED}"


def test_a_block_body_is_one_span_across_its_line_breaks() -> None:
    redacted, counts = redact("BEGIN KEY\nline one\nline two\nEND KEY", (BLOCK,))

    assert redacted == f"BEGIN KEY\n{REDACTED}\nEND KEY"
    assert counts == {RedactionCategory.PRIVATE_KEY: 1}


def test_an_overlap_is_replaced_once_and_counted_once_under_the_earlier_pattern() -> None:
    """RR-6: substituting pattern by pattern would count this twice and could rewrite [REDACTED]."""
    both = (WHOLE_VALUE, Pattern(category=RedactionCategory.API_KEY, expression=re.compile(r"\S+")))

    redacted, counts = redact(SAMPLE, both)

    assert redacted == REDACTED
    assert counts == {RedactionCategory.GITLAB_TOKEN: 1}


def test_resolve_keeps_disjoint_spans_in_order() -> None:
    spans = find_spans(f"{SAMPLE} and {SAMPLE}", (WHOLE_VALUE,))

    kept = resolve(spans)

    assert len(kept) == 2
    assert kept[0].end <= kept[1].start


def test_a_string_with_nothing_to_redact_comes_back_identical() -> None:
    text = "We moved the saga to Wolverine in March."

    redacted, counts = redact(text, (WHOLE_VALUE, KEYED, BLOCK))

    assert redacted == text
    assert counts == {}


@pytest.mark.parametrize(
    "value",
    [
        "$TOKEN",
        "${TOKEN}",
        "%TOKEN%",
        "{{ token }}",
        "{{token}}",
        "<your-api-key>",
        "<your api key>",
        "xxx",
        "XXXXXX",
        "***",
        "changeme",
        "...",
        "[REDACTED]",
        '""',
        "''",
        '"<your-token>"',
        "  ",
    ],
)
def test_a_placeholder_is_recognized(value: str) -> None:
    """RR-7: redacting these replaces knowledge with noise and protects nothing."""
    assert is_placeholder(value)


@pytest.mark.parametrize(
    "value",
    ["$TOKEN", "${TOKEN}", "%TOKEN%", "{{token}}", "<your-api-key>", "xxx", "***", "[REDACTED]"],
)
def test_a_placeholder_is_left_where_it_stands(value: str) -> None:
    """The scanner drops the match rather than redacting it, so the line still reads."""
    redacted, counts = redact(f"password = {value}", (KEYED,))

    assert redacted == f"password = {value}"
    assert counts == {}


@pytest.mark.parametrize("value", ["swordfish!", "AKIA0000000000000000", "a-real-looking-value"])
def test_an_ordinary_value_is_not_mistaken_for_a_placeholder(value: str) -> None:
    """The rejection list is the other half of RR-7: it must not swallow real values."""
    assert not is_placeholder(value)


def test_a_value_shorter_than_the_pattern_allows_is_left_alone() -> None:
    redacted, counts = redact("key:short", (LONG_ENOUGH,))

    assert redacted == "key:short"
    assert counts == {}


def test_redaction_is_idempotent() -> None:
    """RR-8, at the string level: the second pass finds `[REDACTED]`, which is not a secret."""
    once, _ = redact(f"password = swordfish! and {SAMPLE}", (WHOLE_VALUE, KEYED))
    twice, counts = redact(once, (WHOLE_VALUE, KEYED))

    assert twice == once
    assert counts == {}
