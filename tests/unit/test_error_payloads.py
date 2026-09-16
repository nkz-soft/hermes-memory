"""What a boundary error may never carry (contracts/errors.md E5, FR-016, §19, Principle V).

An error is the object that gets logged and reported. §18 requires every failure to be recorded
with its source id, its error and its time; §19 and Principle V forbid conversation content,
credentials, tokens and authorization headers anywhere near a log. The two meet on this type, so
the constraint belongs here rather than on each call site that formats one.

The sharp edge is the chained cause, and it has its own test below: an HTTP client's exception can
carry a URL with a token in it, so the memory store's errors say in their own documentation that
the chain is not safe to render.
"""

from __future__ import annotations

import inspect

import pytest

from hermes_memory.archive import ArchiveDocumentNotFound, ArchiveRejected, ArchiveUnavailable
from hermes_memory.errors import BoundaryError
from hermes_memory.ingestion import (
    ImportStateCorrupt,
    ImportStateUnavailable,
    SourceFormatError,
    SourceUnavailable,
)
from hermes_memory.memory.interface import MemoryStoreRejected, MemoryStoreUnavailable
from hermes_memory.sanitization import SanitizationError

SECRET = "hunter2"
CONTENT = "We moved the saga to Wolverine in March."

EVERY_ERROR = (
    SourceFormatError("the conversation could not be parsed", subject="chatgpt:abc123"),
    SourceUnavailable("the export could not be reached"),
    SanitizationError("the conversation could not be rewritten", subject="chatgpt:abc123"),
    ArchiveDocumentNotFound("chatgpt:abc123"),
    ArchiveRejected("the archive refused this document", subject="chatgpt:abc123"),
    ArchiveUnavailable("the archive could not be reached"),
    MemoryStoreRejected("the engine refused the call", subject="chatgpt:abc123"),
    MemoryStoreUnavailable("the engine could not be reached"),
    ImportStateCorrupt("the import state could not be read"),
    ImportStateUnavailable("the import state could not be reached"),
)


@pytest.mark.parametrize("error", EVERY_ERROR, ids=lambda error: type(error).__name__)
def test_every_error_carries_only_the_three_fields_the_report_needs(error: BoundaryError) -> None:
    """E4 — and E5 by consequence: a field that does not exist cannot hold a secret."""
    assert set(vars(error)) == {"boundary", "subject", "message"}


@pytest.mark.parametrize("error", EVERY_ERROR, ids=lambda error: type(error).__name__)
def test_every_error_names_its_boundary(error: BoundaryError) -> None:
    """§18's report says where a failure happened, and it reads it from here."""
    assert error.boundary
    assert error.boundary in {
        "conversation source",
        "secret sanitizer",
        "raw archive",
        "memory store",
        "import state",
    }


@pytest.mark.parametrize("error", EVERY_ERROR, ids=lambda error: type(error).__name__)
def test_every_error_answers_whether_a_retry_could_succeed(error: BoundaryError) -> None:
    """E2 — read as a property, never parsed out of a message (§18, what #20 consumes)."""
    assert isinstance(error.retryable, bool)


def test_rendering_an_error_cannot_leak_content_or_a_credential() -> None:
    """E5 — whatever a caller logs, it logs the message it was given and nothing else."""
    error = MemoryStoreRejected("the engine refused the call", subject="chatgpt:abc123")

    rendered = f"{error} {error!r} {vars(error)}"

    assert SECRET not in rendered
    assert CONTENT not in rendered


def test_the_memory_stores_errors_warn_that_the_chained_cause_is_not_safe_to_render() -> None:
    """E5's sharp edge, documented where the person catching it will be looking.

    An `httpx` exception can carry a URL, a header or a body holding a credential. §18's failure
    report renders the boundary error alone — and the only way a future implementer knows that is
    if the type they are chaining from says so.
    """
    for error in (MemoryStoreRejected, MemoryStoreUnavailable):
        documentation = inspect.getdoc(error) or ""
        assert "not safe to render" in documentation, (
            f"{error.__name__} does not warn that its chained cause is unsafe to render. "
            "The warning belongs on the type, not in a specification nobody re-reads."
        )


def test_an_error_stays_useful_when_it_concerns_no_single_conversation() -> None:
    """An unreachable export fails no conversation in particular, and must still be reportable."""
    error = SourceUnavailable("the export could not be reached")

    assert error.subject is None
    assert error.message
    assert error.boundary == "conversation source"
