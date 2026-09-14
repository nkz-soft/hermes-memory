"""Withholding credentials, and conversation content, from every record.

This module is the reason the logging pipeline exists as a boundary rather than as a convention.
Principle V is categorical — credentials, tokens and authorization headers are never logged — and
the call sites that could break it have not been written yet, so the protection has to live here,
where every record passes, rather than in the discipline of each future caller.

Three rules, in the order they are applied to a value:

1. the field's **name** says it is a credential (`SENSITIVE_SEGMENTS`, `SENSITIVE_PAIRS`);
2. the value's **type** says so — anything Pydantic holds as a secret;
3. the value's **shape** says so (`CREDENTIAL_SHAPES`), whatever it was called.

Rule 3 is the last line of defence for a log line and **not** a secret scanner. Scanning
conversation content for secrets is ARCHITECTURE.md §13's sanitizer, which is separate work with
its own specification, operating on content bound for the memory engine where a missed secret is
replicated into facts and the graph. Nothing may treat this module as a substitute for it
(specs/003-logging-telemetry-baseline/research.md R7).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from itertools import pairwise
from typing import Any

from pydantic import SecretBytes, SecretStr

__all__ = [
    "CONTENT_REDACTED",
    "CREDENTIAL_SHAPES",
    "MAX_DEPTH",
    "REDACTED",
    "SENSITIVE_PAIRS",
    "SENSITIVE_SEGMENTS",
    "TRUNCATED_SUFFIX",
    "ConversationContent",
    "redacting_processor",
]

REDACTED = "[redacted]"
"""What a withheld value is replaced by. A replacement rather than a removal, so that a reader can
tell a redacted field from an absent one (FR-013)."""

CONTENT_REDACTED = "[redacted:content]"
"""What a conversation body is replaced by while the content flag is off."""

TRUNCATED_SUFFIX = "…[truncated]"

CONTENT_CAP = 4000
"""How much of a conversation body is emitted when the flag is deliberately on. A 2 MB
conversation on one line helps nobody, and an unbounded record is its own hazard."""

MAX_DEPTH = 6
"""How far into nested structures the walk descends before it withholds rather than inspects.

Deeper than any record this project plausibly emits, and finite — which is also what makes a
cyclic structure terminate without a separate visited-set (research.md R9).
"""

SENSITIVE_SEGMENTS = frozenset(
    {
        "token",
        "secret",
        "password",
        "passwd",
        "credential",
        "credentials",
        "authorization",
        "cookie",
        "cookies",
        "jwt",
        "bearer",
        "apikey",
    }
)
"""Name segments whose field is always withheld.

Matched against the field name lowercased and split on runs of non-alphanumeric characters —
never as substrings. `auth` as a substring redacts `author`, and this project's domain is
conversations that have authors; a redactor that eats real fields is one contributors route
around (research.md R6). For the same reason `key` is absent: `idempotency_key`, `sort_key` and
`bank_key` are all ordinary here, so `key` matches only in a pair below.
"""

SENSITIVE_PAIRS = frozenset(
    {
        ("api", "key"),
        ("access", "key"),
        ("private", "key"),
        ("secret", "key"),
        ("auth", "header"),
        ("auth", "token"),
    }
)
"""Adjacent segment pairs whose field is always withheld."""

CREDENTIAL_SHAPES: tuple[re.Pattern[str], ...] = (
    # An Authorization-style prefix and its token.
    re.compile(r"\b(?:Bearer|Basic|Token)\s+[A-Za-z0-9._\-+/=]{8,}", re.IGNORECASE),
    # A JSON web token: three base64url segments, the first announcing a JSON header.
    re.compile(r"\beyJ[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}"),
    # A conventionally prefixed API key.
    re.compile(r"\b(?:sk|pk|rk)-(?:[A-Za-z0-9]+-)?[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}"),
    # Credentials in a URL's userinfo.
    re.compile(r"(?<=://)[^\s/:@]+:[^\s/@]+(?=@)"),
)
"""Value shapes withheld whatever the field is named.

Deliberately small and unmistakable. High-entropy detection was rejected: it fires on hashes,
base64 payloads and document ids, all of which this project logs by design, and a redactor that
eats real fields gets disabled (research.md R7).
"""


class ConversationContent:
    """A conversation body, marked by its caller as exactly that.

    Wrapped rather than inferred from a field name, because a name roster fails open for the next
    field someone invents. The wrapper also withholds the text from its own `repr` and `str`, so a
    call site that interpolates it outside the logging path reveals nothing — the same defence in
    depth `SecretStr` gives a credential (research.md R8).
    """

    __slots__ = ("_text",)

    def __init__(self, text: str) -> None:
        object.__setattr__(self, "_text", text)

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("ConversationContent is immutable")

    def reveal(self) -> str:
        """The text. Named so that reading it is a deliberate act at the call site."""
        return self._text

    def __repr__(self) -> str:
        return f"ConversationContent({CONTENT_REDACTED})"

    def __str__(self) -> str:
        return CONTENT_REDACTED


def redacting_processor(*, include_conversation_content: bool) -> Any:
    """The processor that withholds what must not be emitted.

    Installed immediately before the renderer and after exception rendering, which is the ordering
    the guarantee depends on (research.md R2). It never raises into the caller: a record that
    cannot be inspected is emitted with the offending value withheld (FR-017).
    """

    def redact(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        return {
            key: _redact_value(
                key,
                value,
                depth=0,
                include_conversation_content=include_conversation_content,
            )
            for key, value in event_dict.items()
        }

    return redact


def _redact_value(
    key: str | None,
    value: Any,
    *,
    depth: int,
    include_conversation_content: bool,
) -> Any:
    """One value, withheld or rendered safe. Never raises (FR-017)."""
    try:
        return _inspect(
            key,
            value,
            depth=depth,
            include_conversation_content=include_conversation_content,
        )
    except Exception:
        # Fail closed. A redactor that raises takes down the caller; one that gives up and emits
        # has leaked. Withholding the value keeps the record — and the rest of its fields.
        return REDACTED


def _inspect(
    key: str | None,
    value: Any,
    *,
    depth: int,
    include_conversation_content: bool,
) -> Any:
    if depth > MAX_DEPTH:
        return REDACTED

    if key is not None and _is_sensitive_name(key):
        return REDACTED

    if isinstance(value, SecretStr | SecretBytes):
        return REDACTED

    if isinstance(value, ConversationContent):
        return _render_content(value, include_conversation_content=include_conversation_content)

    if isinstance(value, str):
        return _redact_shapes(value)

    if isinstance(value, bool | int | float) or value is None:
        return value

    if isinstance(value, Mapping):
        return {
            str(inner_key): _redact_value(
                str(inner_key),
                inner_value,
                depth=depth + 1,
                include_conversation_content=include_conversation_content,
            )
            for inner_key, inner_value in value.items()
        }

    if isinstance(value, Sequence | set | frozenset):
        return [
            _redact_value(
                None,
                item,
                depth=depth + 1,
                include_conversation_content=include_conversation_content,
            )
            for item in value
        ]

    # Anything else: rendered, then treated as the string it became. `repr` is where an object
    # holding a credential would reveal it, which is exactly why the result is shape-scanned
    # rather than handed to the renderer's fallback untouched (research.md R9).
    return _redact_shapes(repr(value))


_SEPARATORS = re.compile(r"[^a-z0-9]+")


def _is_sensitive_name(key: str) -> bool:
    """Whether a field name says its value is a credential (FR-009)."""
    segments = [segment for segment in _SEPARATORS.split(key.lower()) if segment]

    if any(segment in SENSITIVE_SEGMENTS for segment in segments):
        return True

    return any(pair in SENSITIVE_PAIRS for pair in pairwise(segments))


def _redact_shapes(value: str) -> str:
    """Replace every credential-shaped span, leaving the text around it (FR-011).

    Span-wise rather than whole-value because Principle V requires redaction to "replace the secret
    value while preserving the surrounding context rather than dropping the enclosing text" — a log
    line stays readable around the hole.
    """
    for pattern in CREDENTIAL_SHAPES:
        value = pattern.sub(REDACTED, value)
    return value


def _render_content(content: ConversationContent, *, include_conversation_content: bool) -> str:
    """A conversation body: withheld, or emitted and capped (FR-014, FR-015).

    The flag governs this function and nothing else. Every rule above it still applies when the
    flag is on, so consenting to conversation text never consents to a credential.
    """
    if not include_conversation_content:
        return CONTENT_REDACTED

    text = content.reveal()
    if len(text) > CONTENT_CAP:
        text = text[:CONTENT_CAP] + TRUNCATED_SUFFIX
    return _redact_shapes(text)
