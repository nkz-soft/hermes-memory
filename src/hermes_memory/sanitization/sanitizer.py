"""The secret sanitizer boundary (ARCHITECTURE.md §8, row 2).

> Redact secrets, report what was redacted.

Principle V: sanitization runs before any content leaves the process for the memory engine, the
minimum categories of §13 are covered, and a redaction replaces the value while **preserving the
surrounding context** — because the context is usually the knowledge worth keeping. §13's own
example is the standard this boundary is held to:

```text
Bad:   drop the entire tool output
Good:  GitLab request using token [REDACTED] returned HTTP 401 Unauthorized
```

The patterns are #11's. What lives here is the shape of the answer, including the part that is
easy to get wrong: the report says *what kind* of secret was redacted and *how many times*, and
never the value. A report carrying the secret defeats Principle V by way of the mechanism that
serves it, and an offset into the text plus the archived original (§14) reconstructs it just as
well — so neither exists as a field (research.md R6).

Contract: specs/007-boundary-interfaces/contracts/interfaces.md, rules SS-1 to SS-8.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import field_validator

from hermes_memory.errors import PermanentBoundaryError
from hermes_memory.normalization import Conversation
from hermes_memory.normalization.base import FrozenModel

__all__ = ["RedactionCategory", "RedactionReport", "SanitizationError", "SecretSanitizer"]

BOUNDARY = "secret sanitizer"


class RedactionCategory(StrEnum):
    """The minimum categories §13 requires a sanitizer to cover.

    A closed vocabulary rather than free strings, so that a report is comparable across runs: free
    strings give `aws_key`, `aws-key` and `AWS key` for one thing, and the report exists to be read
    by a human deciding whether redaction is working.

    §13 fixes this list, so it is architecture rather than a guess about what #11 will find. #11
    adds *patterns*, and a pattern for a category named here is not a vocabulary change; adding a
    category is expected and is an ordinary edit.
    """

    API_KEY = "api-key"
    BEARER_TOKEN = "bearer-token"
    JWT = "jwt"
    GITHUB_TOKEN = "github-token"
    GITLAB_TOKEN = "gitlab-token"
    ANTHROPIC_KEY = "anthropic-key"
    OPENAI_KEY = "openai-key"
    AWS_ACCESS_KEY = "aws-access-key"
    PRIVATE_KEY = "private-key"
    PASSWORD = "password"
    CONNECTION_STRING = "connection-string"
    DOTENV_VALUE = "dotenv-value"
    KUBERNETES_SECRET = "kubernetes-secret"


class RedactionReport(FrozenModel):
    """What was redacted, by category and count — and nothing else (Principle V, SS-7).

    There is deliberately no field for the value, no field for its position and no field for the
    text around it. The report is what gets logged and shown; the fields it does not have are the
    ones it cannot leak.
    """

    counts: Mapping[RedactionCategory, int] = {}

    @field_validator("counts")
    @classmethod
    def _a_category_with_nothing_redacted_is_absent(
        cls, counts: Mapping[RedactionCategory, int]
    ) -> Mapping[RedactionCategory, int]:
        """A zero would claim the category was searched for, which the report cannot know."""
        for category, count in counts.items():
            if count < 1:
                raise ValueError(
                    f"a count must be at least 1, got {count} for {category}; a category with "
                    "nothing redacted is left out"
                )
        return counts

    @property
    def total(self) -> int:
        """How many redactions were made in all."""
        return sum(self.counts.values())

    @property
    def is_empty(self) -> bool:
        """Whether nothing was redacted.

        An ordinary answer, and a value rather than an absence: a sanitizer returning `None` to
        mean "nothing found" makes every caller handle a case that is not a case (SS-6).
        """
        return not self.counts


class SanitizationError(PermanentBoundaryError):
    """The conversation could not be rewritten.

    Permanent: the same text sanitizes the same way. It exists so that a sanitizer never signals
    failure by returning its input unchanged — which would send the secret onwards (SS-8).
    """

    def __init__(self, message: str, *, subject: str | None = None) -> None:
        super().__init__(BOUNDARY, message, subject=subject)


@runtime_checkable
class SecretSanitizer(Protocol):
    """Rewrites a conversation with its secrets redacted, and reports what it redacted."""

    def sanitize(self, conversation: Conversation) -> tuple[Conversation, RedactionReport]:
        """Return the redacted conversation and the report of what was removed.

        A new conversation: #8's values are frozen, and the failure mode Principle V is written
        against is a half-redacted object escaping after an exception (SS-1).

        Identity survives — source, native id, document id, message count and message order are
        the input's (SS-2) — and so does the surrounding text: a message that carried words around
        a token still carries them (SS-4, §13).

        Nothing to redact returns the conversation and an empty report (SS-6).

        Raises:
            SanitizationError: the conversation could not be rewritten.
        """
        ...
