"""A field whose name says it holds a credential never carries its value out (User Story 2).

Checks 8-10 of specs/003-logging-telemetry-baseline/contracts/observability.md. Every roster entry
is exercised, not a sample of them (SC-003) — a roster with one entry that silently stopped
matching would otherwise go unnoticed until the leak.

Check 10 is the one that looks like it does not belong. It asserts that `author`,
`idempotency_key`, `document_id` and `bank` are *not* redacted, and it is there because the
tempting implementation — matching roster words as substrings anywhere in the key — eats `author`
in a project whose domain is conversations with authors. A redactor that eats real fields is one
contributors route around, and a security control that gets routed around protects nothing
(specs/003-logging-telemetry-baseline/research.md R6).

These assertions are made against rendered output. See the `rendered` fixture before adding one:
`structlog.testing.capture_logs` would make every test in this file pass while proving nothing.
"""

from __future__ import annotations

import pytest

from hermes_memory.observability import REDACTED, get_logger
from hermes_memory.observability.redaction import SENSITIVE_PAIRS, SENSITIVE_SEGMENTS

from .conftest import Rendered

A_SECRET = "hs-live-9f3c2a7e51b04d6f"


@pytest.mark.parametrize("segment", sorted(SENSITIVE_SEGMENTS))
def test_every_sensitive_segment_is_withheld(rendered: Rendered, segment: str) -> None:
    """Check 8 — each of the twelve segments, under a realistic field name (FR-009)."""
    get_logger().info("calling hindsight", **{f"hindsight_{segment}": A_SECRET})

    assert A_SECRET not in rendered.text()
    assert rendered.one()[f"hindsight_{segment}"] == REDACTED


@pytest.mark.parametrize("segment", sorted(SENSITIVE_SEGMENTS))
def test_a_sensitive_segment_is_matched_whatever_the_separator(
    rendered: Rendered, segment: str
) -> None:
    """The same names as an operator or a library would spell them: dots, dashes, upper case."""
    for name in (f"HTTP.{segment.upper()}", f"llm-{segment}", segment):
        get_logger().info("calling hindsight", **{name: A_SECRET})

    assert A_SECRET not in rendered.text()


@pytest.mark.parametrize(("first", "second"), sorted(SENSITIVE_PAIRS))
def test_every_sensitive_pair_is_withheld(rendered: Rendered, first: str, second: str) -> None:
    """Check 9 — `api`+`key` and its four siblings, which single segments must not cover."""
    name = f"{first}_{second}"
    get_logger().info("calling the proxy", **{name: A_SECRET})

    assert A_SECRET not in rendered.text()
    assert rendered.one()[name] == REDACTED


@pytest.mark.parametrize(
    "name",
    ["author", "idempotency_key", "document_id", "bank", "sort_key", "authored_at", "project"],
)
def test_ordinary_fields_survive(rendered: Rendered, name: str) -> None:
    """Check 10 — the guard against a redactor that eats the log it was meant to protect.

    `author` is the one that matters: matching `auth` as a substring would redact it, and this
    project's domain is conversations that have authors.
    """
    get_logger().info("normalized a conversation", **{name: "a perfectly ordinary value"})

    assert rendered.one()[name] == "a perfectly ordinary value"


def test_key_alone_is_not_a_sensitive_segment() -> None:
    """`bank_key` and `sort_key` are not credentials; `key` matches only in a pair (R6)."""
    assert "key" not in SENSITIVE_SEGMENTS
    assert "auth" not in SENSITIVE_SEGMENTS


def test_the_marker_is_visible_rather_than_the_field_being_dropped(rendered: Rendered) -> None:
    """Check 16 — a reader must be able to tell redaction from absence (FR-013)."""
    get_logger().info("calling hindsight", hindsight_token=A_SECRET)

    record = rendered.one()

    assert "hindsight_token" in record, "the field was dropped; it should have been replaced"
    assert record["hindsight_token"] == REDACTED
