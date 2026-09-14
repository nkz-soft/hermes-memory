"""The ingestion operation record of ARCHITECTURE.md §18.

One record per operation, carrying the fields §18 fixes, with the duration measured here rather
than accepted from the caller. An import that reports nothing per conversation cannot be trusted
at the scale this project targets, and a duration a caller supplies is one a caller can forget.

What this module deliberately does **not** do is decide that a failure should not abort a run.
§18 gives that instruction to the importer; here, a failed operation is recorded and the exception
is re-raised unchanged. A context manager that swallowed it would emit an identical line while the
run carried on believing the conversation had been handled.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

from hermes_memory.observability.logging import get_logger

__all__ = ["EVENT", "Operation", "OperationStatus", "ingestion_operation"]

EVENT = "ingestion.operation"
"""The event name of the terminal record. Fixed, so that a reader can select every ingestion
operation out of a log without matching prose."""


class OperationStatus(Enum):
    """The three outcomes §18 defines, and no others.

    An enumeration rather than a string so that a typo is a failure at the call site rather than a
    value in the record that nothing will ever match (FR-004).
    """

    IMPORTED = "imported"
    SKIPPED = "skipped"
    FAILED = "failed"


class Operation:
    """The handle a body uses to say what happened.

    Only the outcome is settable, and only to `skipped`: `imported` is the default and `failed` is
    decided by an exception rather than claimed.
    """

    def __init__(self) -> None:
        self.status = OperationStatus.IMPORTED

    def skipped(self) -> None:
        """Nothing to do — unchanged since a previous run (ARCHITECTURE.md §17)."""
        self.status = OperationStatus.SKIPPED


@contextmanager
def ingestion_operation(
    *,
    source: str,
    source_id: str,
    bank: str,
    project: str | None = None,
    document_id: str | None = None,
) -> Iterator[Operation]:
    """Bind the §18 context, time the body, and emit exactly one record when it ends.

    Every record emitted inside the body carries the identity of the conversation being worked on,
    without the caller passing it again (FR-007); the binding is removed on every exit path, so the
    next conversation never inherits this one's identity.

    There is no `started` record. §18 asks for a record per operation, and one record carrying a
    duration is more useful to a reader than two that have to be paired up.
    """
    context = {
        "source": source,
        "source_id": source_id,
        "project": project,
        "bank": bank,
        "document_id": document_id,
    }

    operation = Operation()
    start_time = datetime.now(UTC)
    started = time.perf_counter()

    tokens = structlog.contextvars.bind_contextvars(**context)
    try:
        try:
            yield operation
        except BaseException as error:
            _emit(
                context,
                status=OperationStatus.FAILED,
                start_time=start_time,
                started=started,
                error=f"{type(error).__name__}: {error}",
            )
            raise

        _emit(
            context,
            status=operation.status,
            start_time=start_time,
            started=started,
            error=None,
        )
    finally:
        # In `finally` rather than after the emit: an exception leaving this manager must not take
        # the unbinding with it, or the next conversation inherits this one's identity.
        structlog.contextvars.reset_contextvars(**tokens)


def _emit(
    context: dict[str, Any],
    *,
    status: OperationStatus,
    start_time: datetime,
    started: float,
    error: str | None,
) -> None:
    """Write the terminal record.

    The context fields are passed explicitly as well as being bound. Binding alone would be enough
    today, but it would make the completeness of §18's field set depend on a processor staying in
    the chain; passed explicitly, the record carries them because this function says so.

    A failure is recorded at error level so that it survives a raised threshold. An operator who
    quietens a long import must still be told which conversations failed — that is the half of
    §18's report they cannot reconstruct afterwards.
    """
    logger = get_logger()
    emit = logger.error if status is OperationStatus.FAILED else logger.info

    emit(
        EVENT,
        **context,
        start_time=start_time.isoformat(),
        duration_ms=(time.perf_counter() - started) * 1000,
        status=status.value,
        error=error,
    )
