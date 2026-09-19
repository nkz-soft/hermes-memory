"""Sanitization stays linear in the text, and no input makes a pattern backtrack indefinitely.

`re` backtracks, and a pattern with nested unbounded quantifiers over hostile text is a way to make
an import hang on one conversation. Every quantifier in the table is bounded and none is nested
(specs/009-secret-sanitizer/research.md R2); this file is the falsifiable version of that claim.

The bounds are generous on purpose. What has to fail here is a pattern that went quadratic or worse,
not a slow machine — a timing test tight enough to catch a 20% regression is a test that fails on
somebody's laptop and gets deleted.
"""

from __future__ import annotations

import time

import pytest

from hermes_memory.sanitization import PatternSecretSanitizer
from hermes_memory.sanitization.patterns import PATTERNS, Pattern
from hermes_memory.sanitization.scanner import redact

HOSTILE = (
    "-----BEGIN OPENSSH " * 400
    # A *complete* marker with no `END` after it, repeated: the shape that makes the block pattern
    # search forward to the end of the text and find nothing, once per marker. Without this the
    # PEM pattern is never stressed, because a match never starts (review of PR for #11).
    + ("-----BEGIN RSA PRIVATE KEY-----\nAAAABBBBCCCC\n" * 400)
    + "sk-" * 2000
    + "eyJ"
    + "a" * 4000
    + "password=" * 2000
    + "a:" * 4000
    + "://" * 2000
)
"""Prefixes and separators the table looks for, repeated, with nothing that completes a match."""


def many_matches(lines: int) -> str:
    """A `.env` file whose every line is a credential — thousands of spans to resolve, not to find.

    The cost of *resolving* spans is invisible to a text with no matches in it, which is what the
    large-manifest case below is. Resolution was quadratic and this suite could not see it.
    """
    return "".join(
        f"SERVICE{index}_TOKEN=abcdefghijklmnopqrstuvwxyz012345\n" for index in range(lines)
    )


LARGE_TOOL_RESULT = "apiVersion: v1\nkind: ConfigMap\ndata:\n" + "".join(
    f"  key-{index}: value-{index}\n" for index in range(8000)
)
"""A dumped manifest of a few hundred kilobytes, which is what a real tool result looks like."""

SECONDS_PER_PATTERN = 2.0
SECONDS_FOR_A_LARGE_FIELD = 5.0


@pytest.mark.parametrize(
    "pattern", PATTERNS, ids=[f"{index}-{p.category.value}" for index, p in enumerate(PATTERNS)]
)
def test_no_pattern_hangs_on_hostile_input(pattern: Pattern) -> None:
    """One pattern at a time, so a failure names the expression that misbehaves."""
    started = time.perf_counter()

    redact(HOSTILE, (pattern,))

    assert time.perf_counter() - started < SECONDS_PER_PATTERN


def test_a_large_tool_result_is_sanitized_promptly() -> None:
    """The whole table over a field far larger than any fixture in the unit suites."""
    started = time.perf_counter()

    redacted, report = PatternSecretSanitizer().redact_text(LARGE_TOOL_RESULT)

    assert time.perf_counter() - started < SECONDS_FOR_A_LARGE_FIELD
    assert redacted == LARGE_TOOL_RESULT
    assert report.is_empty


def test_cost_grows_with_the_text_rather_than_with_its_square() -> None:
    """Ten times the text, not a hundred times the work.

    Measured as a ratio rather than against a clock, so the assertion means the same thing on a fast
    machine and a slow one. The factor of 25 leaves room for timer noise while still failing on a
    quadratic scan, which would cost a hundred.
    """
    small = LARGE_TOOL_RESULT[: len(LARGE_TOOL_RESULT) // 10]
    sanitizer = PatternSecretSanitizer()

    started = time.perf_counter()
    sanitizer.redact_text(small)
    small_cost = time.perf_counter() - started

    started = time.perf_counter()
    sanitizer.redact_text(LARGE_TOOL_RESULT)
    large_cost = time.perf_counter() - started

    assert large_cost < max(small_cost, 0.001) * 25


def test_cost_grows_with_the_number_of_redactions_rather_than_its_square() -> None:
    """The same claim where it was actually false: thousands of spans, all of them kept.

    Eight times the credentials cost sixty-four times the work while `resolve` asked `any(...)`
    over everything it had kept. A field of this size is an ordinary `.env` quoted into a chat.
    """
    sanitizer = PatternSecretSanitizer()

    started = time.perf_counter()
    _, small_report = sanitizer.redact_text(many_matches(1000))
    small_cost = time.perf_counter() - started

    started = time.perf_counter()
    _, large_report = sanitizer.redact_text(many_matches(8000))
    large_cost = time.perf_counter() - started

    assert small_report.total == 1000
    assert large_report.total == 8000
    assert large_cost < max(small_cost, 0.001) * 20
