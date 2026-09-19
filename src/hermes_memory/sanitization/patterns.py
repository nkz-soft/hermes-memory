"""What a secret looks like, and what only looks like one.

One ordered table, three shapes (specs/009-secret-sanitizer/research.md R3):

* **value-shaped** — a credential recognizable from its own prefix and alphabet. The match *is* the
  value, so `value_group` stays 0.
* **keyed** — the categories with no shape of their own: a password is any string, and an AWS secret
  access key is forty characters of an alphabet that a hash and half the quoted payloads in an
  engineering conversation also use. These are found by the name beside them, and only the named
  `value` group is replaced — `DATABASE_PASSWORD=[REDACTED]` keeps the key, which is usually the
  knowledge worth keeping (§13).
* **delimited block** — a PEM envelope. The body goes, both markers stay.

Order is precedence: a pattern earlier in the table wins an overlap (RR-6), which is why
`sk-ant-` sits above `sk-` and the JWT sits above the bearer header it arrives in.

Every quantifier here is bounded and none is nested, so no input makes the scanner backtrack
indefinitely (research R2). A pattern's `minimum_length` and `is_placeholder` together are the
precision half of the feature: without them the corpus fills with `[REDACTED]` where knowledge used
to be, which is a quieter version of the failure §13 rejects.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from hermes_memory.sanitization.sanitizer import RedactionCategory

__all__ = ["PATTERNS", "Pattern", "is_placeholder"]


@dataclass(frozen=True, slots=True)
class Pattern:
    """One entry in the table.

    `precedence` is not a field: it is the entry's position in the sequence handed to the scanner,
    so the table cannot disagree with itself about which of two patterns is more specific.
    """

    category: RedactionCategory
    expression: re.Pattern[str]
    value_group: int | str = 0
    """Which group holds the value to replace. 0 — the whole match — is the value-shaped case."""

    minimum_length: int = 1
    """Below this, a matched value is treated as a placeholder rather than a credential."""


_PLACEHOLDERS = frozenset(
    {
        "",
        '""',
        "''",
        "...",
        "changeme",
        "change-me",
        "changeit",
        "example",
        "null",
        "none",
        "password",
        "redacted",
        "secret",
        "todo",
        "value",
        "your-key",
        "yourkey",
    }
)
"""Values that are the *name* of a secret rather than one. Compared case-insensitively."""

_REFERENCE = re.compile(
    r"""
    \A(?:
        \$\{?[A-Za-z_][A-Za-z0-9_]{0,63}\}?      # $TOKEN, ${TOKEN}
      | %[A-Za-z_][A-Za-z0-9_]{0,63}%            # %TOKEN%
      | \{\{\s*[^{}]{1,64}\s*\}\}                # {{ token }}, a template
      | <[^<>]{1,64}>                            # <your-api-key>, a documentation placeholder
      | \[REDACTED\]                             # already sanitized — RR-8 falls out of this
      | [xX*.…-]{1,64}                      # xxx, ***, ..., ---
    )\Z
    """,
    re.VERBOSE,
)


def is_placeholder(value: str) -> bool:
    """Whether a matched value is a stand-in rather than a credential (RR-7).

    These shapes are what a README line, an example `curl` and a quoted docker-compose file are made
    of, and the corpus is full of them. Redacting one protects nothing and costs a sentence.

    Quotes are stripped first, because a `.env` line writes its placeholder as `"<your-token>"`.
    """
    stripped = value.strip().strip("\"'")
    return (
        not stripped or stripped.lower() in _PLACEHOLDERS or _REFERENCE.match(stripped) is not None
    )


PATTERNS: tuple[Pattern, ...] = ()
"""The table, most specific first. Filled per §13 category by the tasks of Phase 3."""
