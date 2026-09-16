"""The failures the boundaries of ARCHITECTURE.md §8 are allowed to raise.

§18 requires an import to proceed conversation by conversation, to retry transient failures only —
429, 502, 503, 504, connection resets, timeouts — and never to retry a rejected request, an
unauthorized one or invalid input. That is a contract on the boundaries before it is a policy in
the retry code (#20): a caller that cannot tell a timeout from a rejection either retries what will
never succeed or abandons what would have worked on the second attempt.

Two things follow, and both are mechanisms rather than conventions:

* **Retryability is the class, not a flag.** `TransientBoundaryError` and `PermanentBoundaryError`
  answer the question by existing. No constructor takes a `retryable` argument and no instance can
  rebind the attribute, so §18's never-retryable conditions are not merely discouraged from claiming
  otherwise — they cannot (specs/007-boundary-interfaces/contracts/errors.md, E2 and E3).
* **These errors are ours.** An implementation raises one of these, never the exception its backend
  raised: a caller that had to catch `httpx.HTTPError` or `sqlite3.DatabaseError` would import the
  engine's dependency in order to handle a failure, which is the leak Principle IV exists to
  prevent — and the one easiest to miss, because it passes every import check on the module that
  leaks it. The underlying exception is chained with ``raise ... from``; the chain is for reading,
  not for catching.

This module lives at the package root rather than inside a boundary because all six boundaries and
the retry policy consume it and none of them owns it — the placement `settings.py` already
established here (specs/007-boundary-interfaces/research.md R3).

**Nothing in an error may carry a secret** (E5, §19, Principle V). The error is what gets logged
and reported, so the constraint belongs on the type rather than on each call site that formats one:
no conversation content, no credential, no token, no authorization header, no request or response
body. The chained cause is the sharp edge — an HTTP client's exception can hold a URL with a token
in it — so §18's failure report renders the boundary error alone, never the chain.
"""

from __future__ import annotations

from typing import Any, ClassVar

__all__ = ["BoundaryError", "PermanentBoundaryError", "TransientBoundaryError"]


class BoundaryError(Exception):
    """A failure at one of the six boundaries of §8.

    Never raised directly: a failure is transient or it is permanent, and a caller that cannot tell
    which has learned nothing §18 can use. It exists to be caught — by the reporter that records
    every failure with its source id, its error and its time.
    """

    retryable: ClassVar[bool]
    """Whether retrying the identical call could succeed.

    Declared by the subclass and by nothing else. Reading it on an instance reads the class's value
    (E2); assigning to it raises (E3).
    """

    def __init__(self, boundary: str, message: str, *, subject: str | None = None) -> None:
        """Carry what §18's failure report needs, and nothing more (E4).

        `subject` is the source id or document id the failure concerned, where there is one — an
        export that could not be opened concerns no single conversation.

        No time is recorded here: §18's report owns the time, and §11 is the standing reminder of
        what a captured clock standing in for a real one costs (E6).
        """
        super().__init__(message)
        self.boundary = boundary
        self.subject = subject
        self.message = message

    def __setattr__(self, name: str, value: Any) -> None:
        """Refuse to let retryability be rebound on an instance (E3, FR-014).

        Without this, `error.retryable = True` would shadow the class attribute and a permanent
        failure would be retried forever by code that was reading the right attribute.
        """
        if name == "retryable":
            raise AttributeError(
                "retryable is decided by the error's type, not per instance: raise a "
                "TransientBoundaryError or a PermanentBoundaryError (contracts/errors.md, E3)."
            )
        super().__setattr__(name, value)


class TransientBoundaryError(BoundaryError):
    """The identical call could succeed if repeated.

    §18's list: 429, 502, 503, 504, connection resets and timeouts. #20 retries exactly this branch,
    with backoff and jitter, reusing the same idempotency key.
    """

    retryable: ClassVar[bool] = True


class PermanentBoundaryError(BoundaryError):
    """Repeating the identical call cannot help.

    §18's list: 400, 401, 403 and invalid input — and the ordinary answers a boundary states as a
    failure by design, such as an archive asked to load a document it does not hold.
    """

    retryable: ClassVar[bool] = False
