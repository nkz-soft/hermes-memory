"""Find the secrets in one string, replace each once, and count what was replaced.

The obvious implementation — `re.sub` for every pattern in turn — is wrong here in a way that only
shows up on real history. A JWT arrives inside `Authorization: Bearer …`, and a password arrives
inside a connection string: two patterns match the same region, the second substitution runs over
what the first already wrote, and the report claims two redactions where one value was removed.

So a pass collects *spans* and nothing is rewritten until they are resolved (RR-6). Surviving spans
are disjoint and ordered, the rewrite is a single join, and the count is of replacements actually
made rather than of matches found (RR-5).

A `Span` never leaves this module. It holds a position, and a position plus the archived original of
§14 reconstructs the secret — which is why #9's report has no offset field, and this module must not
become the way one arrives.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from hermes_memory.sanitization.patterns import Pattern, is_placeholder
from hermes_memory.sanitization.sanitizer import RedactionCategory

__all__ = ["REDACTED", "Span", "find_spans", "redact", "resolve"]

REDACTED = "[REDACTED]"
"""§13's replacement, as a literal. Not a mask of the original's length, not a per-category marker:
the marker would name the kind of credential in the text, which the report deliberately does not."""


@dataclass(frozen=True, slots=True, order=True)
class Span:
    """A region of one string that will be replaced. Half-open bounds, as slices are."""

    start: int
    end: int
    category: RedactionCategory
    precedence: int
    """The pattern's position in the table; lower is more specific and wins an overlap."""


def find_spans(text: str, patterns: Sequence[Pattern]) -> list[Span]:
    """Every value any pattern recognizes, as a span, unresolved and possibly overlapping.

    A match whose value is a placeholder or shorter than its pattern allows is dropped here rather
    than later: it is not a redaction that lost, it is not a redaction at all (RR-7).
    """
    spans: list[Span] = []
    for precedence, pattern in enumerate(patterns):
        for match in pattern.expression.finditer(text):
            value = match.group(pattern.value_group)
            if value is None or len(value) < pattern.minimum_length or is_placeholder(value):
                continue
            start, end = match.span(pattern.value_group)
            spans.append(Span(start, end, pattern.category, precedence))
    return spans


def resolve(spans: Iterable[Span]) -> list[Span]:
    """Drop every span that overlaps one already kept, most specific first (RR-6).

    Sorted by precedence before position, so that the winner of an overlap is the more specific
    pattern rather than whichever happened to start first. The result is re-sorted by position,
    because the rewrite walks the string forwards.
    """
    kept: list[Span] = []
    for span in sorted(spans, key=lambda s: (s.precedence, s.start, -s.end)):
        if any(span.start < other.end and other.start < span.end for other in kept):
            continue
        kept.append(span)
    return sorted(kept)


def redact(text: str, patterns: Sequence[Pattern]) -> tuple[str, dict[RedactionCategory, int]]:
    """Return the text with every recognized value replaced, and the counts by category.

    Nothing recognized returns the string that was handed in — the same object, so that a caller
    rebuilding a model can tell "unchanged" without comparing.
    """
    spans = resolve(find_spans(text, patterns))
    if not spans:
        return text, {}

    pieces: list[str] = []
    counts: dict[RedactionCategory, int] = {}
    cursor = 0
    for span in spans:
        pieces.append(text[cursor : span.start])
        pieces.append(REDACTED)
        counts[span.category] = counts.get(span.category, 0) + 1
        cursor = span.end
    pieces.append(text[cursor:])

    return "".join(pieces), counts
