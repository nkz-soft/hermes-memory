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

import re
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
        regions = [(0, len(text))] if pattern.within is None else pattern.within(text)
        for region_start, region_end in regions:
            for match in pattern.expression.finditer(text, region_start, region_end):
                value = match.group(pattern.value_group)
                if value is None or len(value) < pattern.minimum_length or is_placeholder(value):
                    continue
                start, end = match.span(pattern.value_group)
                if pattern.value_group != 0 and _is_a_code_expression(value):
                    continue
                spans.append(Span(start, end, pattern.category, precedence))
    return spans


_CALL_OR_SUBSCRIPT = re.compile(r"\A[A-Za-z_][A-Za-z0-9_.]*[(\[]")
"""A name — possibly dotted — opening a call or a subscript: `os.getenv(`, `getApiKey(`, `env[`."""


def _is_a_code_expression(value: str) -> bool:
    """Whether the value is code rather than a literal.

    `api_key = os.getenv("OPENAI_API_KEY")` and `const apiKey = getApiKey();` are the shapes this
    exists for. Redacting them is worse than an ordinary false positive: the line comes out
    syntactically broken, so the context §13 requires to survive does not.

    Two conditions, because a password may contain brackets and recall wins that trade (research
    R5). The value must *open* with a name applying a call or a subscript, and it must *end* on a
    bracket — which is what an expression truncated at the first quote looks like:

    | value | verdict |
    |---|---|
    | `os.getenv(` | code — a call cut off at its first argument |
    | `getApiKey()` | code |
    | `os.environ[` | code |
    | `P@ssw0rd(1)` | a password; `@` is not part of a name |
    | `Secret[42]xyz` | a password; it does not end on a bracket |
    """
    return _CALL_OR_SUBSCRIPT.match(value) is not None and value[-1] in "()[]"


def resolve(spans: Iterable[Span]) -> list[Span]:
    """Drop every span that overlaps one already kept, most specific first (RR-6).

    Pattern by pattern, in table order, merging each pattern's spans into the ones already kept.
    The merge is what keeps this linear: within one pattern the spans are already disjoint and in
    order — `finditer` yields non-overlapping matches — and the kept list is disjoint and in order
    by construction, so one walk of each settles every overlap between them.

    The obvious version, asking `any(...)` over the kept list per span, is quadratic. It looks
    harmless on a three-line fixture and costs seconds on a `.env` file with a few thousand lines,
    which is a size real history reaches (research R12).
    """
    by_pattern: dict[int, list[Span]] = {}
    for span in spans:
        by_pattern.setdefault(span.precedence, []).append(span)

    kept: list[Span] = []
    for precedence in sorted(by_pattern):
        incoming = sorted(by_pattern[precedence], key=lambda span: (span.start, -span.end))
        kept = _merge(kept, incoming)
    return kept


def _merge(kept: list[Span], incoming: list[Span]) -> list[Span]:
    """Merge one pattern's spans into the kept ones, dropping any that overlap.

    Both lists are sorted by start. `kept` is disjoint by construction; `incoming` is disjoint
    because `finditer` yields non-overlapping matches — but only per region, and a pattern's regions
    come from a caller-supplied `within`. A callable returning two regions that overlap would hand
    this function the same span twice, and the result would be `[REDACTED][REDACTED]` with the count
    doubled. So overlap with what was just emitted is checked too, rather than assumed away.
    """
    merged: list[Span] = []
    index = 0
    for span in incoming:
        while index < len(kept) and kept[index].end <= span.start:
            merged.append(kept[index])
            index += 1
        if index < len(kept) and kept[index].start < span.end:
            continue
        if merged and merged[-1].end > span.start:
            continue
        merged.append(span)
    merged.extend(kept[index:])
    return merged


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
