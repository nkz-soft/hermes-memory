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

    requires: re.Pattern[str] | None = None
    """A guard the surrounding text must satisfy before this pattern applies at all.

    It exists for one category: what makes a base64 line a Kubernetes secret is the `kind: Secret`
    above it, and a regular expression cannot look arbitrarily far behind its own match. Without the
    guard the same pattern would empty every ConfigMap quoted in a conversation (research R7).
    """


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


_VALUE = "value"
"""The group name every keyed and block pattern puts the credential in."""

PATTERNS: tuple[Pattern, ...] = (
    # --- delimited block ---------------------------------------------------------------------
    Pattern(
        category=RedactionCategory.PRIVATE_KEY,
        expression=re.compile(
            r"-----BEGIN [A-Z0-9 ]{0,40}PRIVATE KEY-----\r?\n"
            r"(?P<value>[A-Za-z0-9+/=\s:.,@-]{1,20000}?)"
            r"\r?\n-----END [A-Z0-9 ]{0,40}PRIVATE KEY-----"
        ),
        value_group=_VALUE,
        minimum_length=8,
    ),
    # --- value-shaped ------------------------------------------------------------------------
    # Anthropic before OpenAI: `sk-ant-` is a prefix of the `sk-` family, and an overlap goes to
    # whichever pattern comes first (RR-6).
    Pattern(
        category=RedactionCategory.ANTHROPIC_KEY,
        expression=re.compile(r"sk-ant-[A-Za-z0-9_-]{16,200}"),
    ),
    Pattern(
        category=RedactionCategory.OPENAI_KEY,
        expression=re.compile(r"sk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_-]{20,200}"),
    ),
    Pattern(
        category=RedactionCategory.GITHUB_TOKEN,
        expression=re.compile(r"gh[pousr]_[A-Za-z0-9]{36,255}|github_pat_[A-Za-z0-9_]{22,255}"),
    ),
    Pattern(
        category=RedactionCategory.GITLAB_TOKEN,
        expression=re.compile(
            r"gl(?:pat|dt|rt|ptt|soat|cbt|ft|agent|imt|oas)-[A-Za-z0-9_-]{20,64}"
        ),
    ),
    Pattern(
        category=RedactionCategory.AWS_ACCESS_KEY,
        expression=re.compile(r"\b(?:AKIA|ASIA|AGPA|AIDA|AROA|ANPA|ANVA|AIPA)[A-Z0-9]{16}\b"),
    ),
    # A JWT sits above the bearer header it usually arrives in, so the report names the more
    # specific of the two (RR-6).
    Pattern(
        category=RedactionCategory.JWT,
        expression=re.compile(
            r"eyJ[A-Za-z0-9_-]{5,2000}\.[A-Za-z0-9_-]{5,4000}\.[A-Za-z0-9_-]{5,2000}"
        ),
    ),
    # --- keyed ---------------------------------------------------------------------------------
    # What makes a base64 line a secret is the manifest around it, so the manifest is the guard.
    # The value alphabet excludes `-`, which is what keeps `name: hermes-importer` out of it, and
    # the minimum length is what keeps `kind: Secret` itself out (research R7).
    Pattern(
        category=RedactionCategory.KUBERNETES_SECRET,
        expression=re.compile(
            r"^[ \t]{1,16}[A-Za-z0-9._-]{1,64}:[ \t]{0,8}(?P<value>[A-Za-z0-9+/=]{12,4096})[ \t]*$",
            re.MULTILINE,
        ),
        value_group=_VALUE,
        minimum_length=12,
        requires=re.compile(r"kind:[ \t]{0,8}Secret\b"),
    ),
    Pattern(
        category=RedactionCategory.KUBERNETES_SECRET,
        expression=re.compile(
            r"--from-literal=[A-Za-z0-9._-]{1,64}=(?P<value>[^\s'\"]{4,512})",
        ),
        value_group=_VALUE,
        minimum_length=4,
    ),
    # Only the password component goes: a connection string without it still says which database
    # was involved, which is the knowledge (RC-11).
    Pattern(
        category=RedactionCategory.CONNECTION_STRING,
        expression=re.compile(
            r"[a-z][a-z0-9+.-]{1,31}://[^\s:/@]{1,64}:(?P<value>[^\s:/@]{1,256})@",
        ),
        value_group=_VALUE,
        minimum_length=3,
    ),
    Pattern(
        category=RedactionCategory.BEARER_TOKEN,
        expression=re.compile(
            r"(?i:authorization)[ \t]*:[ \t]*(?i:bearer)[ \t]+(?P<value>[A-Za-z0-9._~+/=-]{8,4096})"
        ),
        value_group=_VALUE,
        minimum_length=8,
    ),
    Pattern(
        category=RedactionCategory.BEARER_TOKEN,
        expression=re.compile(
            r"(?i:private-token)[ \t]*:[ \t]*(?P<value>[A-Za-z0-9._~+/=-]{8,4096})"
        ),
        value_group=_VALUE,
        minimum_length=8,
    ),
    Pattern(
        category=RedactionCategory.API_KEY,
        expression=re.compile(
            r"(?i:api[_-]?key|apikey|api[_-]?secret)[\"']?[ \t]*[:=][ \t]*"
            r"[\"']?(?P<value>[^\s\"',;&]{8,512})"
        ),
        value_group=_VALUE,
        minimum_length=8,
    ),
    # The id has a shape; the secret does not, so it is found beside its name or not at all
    # (research R6). Both report under the one category §13 names.
    Pattern(
        category=RedactionCategory.AWS_ACCESS_KEY,
        expression=re.compile(
            r"(?i:aws[_-]?secret[_-]?access[_-]?key|--secret-access-key)[\"']?"
            r"(?:[ \t]*[:=][ \t]*|[ \t]+)[\"']?(?P<value>[A-Za-z0-9+/=]{16,128})"
        ),
        value_group=_VALUE,
        minimum_length=16,
    ),
    Pattern(
        category=RedactionCategory.PASSWORD,
        expression=re.compile(
            r"(?i:password|passwd|pwd)[\"']?[ \t]*[:=][ \t]*[\"']?(?P<value>[^\s\"',;]{4,256})"
        ),
        value_group=_VALUE,
        minimum_length=4,
    ),
    Pattern(
        category=RedactionCategory.PASSWORD,
        expression=re.compile(r"--password(?:[ \t]+|=)[\"']?(?P<value>[^\s\"',;]{4,256})"),
        value_group=_VALUE,
        minimum_length=4,
    ),
    # Last, because a key named `DATABASE_PASSWORD` is a password first and a `.env` line second.
    Pattern(
        category=RedactionCategory.DOTENV_VALUE,
        expression=re.compile(
            r"^[ \t]{0,8}(?:export[ \t]+)?"
            r"[A-Z][A-Z0-9_]{0,63}(?:_TOKEN|_SECRET|_KEY|_PASSWORD|_PASS|_CREDENTIALS)"
            r"[ \t]*=[ \t]*[\"']?(?P<value>[^\s\"']{6,512})",
            re.MULTILINE,
        ),
        value_group=_VALUE,
        minimum_length=6,
    ),
)
"""The table, most specific first. Order is precedence (RR-6)."""
