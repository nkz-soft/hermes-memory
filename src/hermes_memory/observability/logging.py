"""The processor chain every record in this project passes through.

The guarantees of ARCHITECTURE.md §18 and Principle V are properties of this chain rather than
rules a caller has to remember, and two positions in it carry them
(specs/003-logging-telemetry-baseline/research.md R2):

* `format_exc_info` runs **before** redaction, because structlog renders `exc_info` into a plain
  string and an exception carrying a token in its message is an ordinary thing. After redaction,
  that string would be assembled out of exception arguments and traceback frames with nothing left
  to inspect them.
* redaction runs **immediately before** the renderer, because every other processor has finished
  contributing keys by then. A processor added to this project later goes before it, never after.

A file named `logging.py` inside a package does not shadow the standard library: implicit relative
imports do not exist in Python 3, so the `import logging` below resolves to the standard module.
The name says what the file is rather than dodging a hazard the language removed.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, TextIO

import structlog

from hermes_memory.settings import Settings

__all__ = [
    "configure",
    "get_logger",
    "install_default_pipeline",
    "remove_standard_library_bridge",
]

_HANDLER_MARKER = "_hermes_memory_observability"
"""Identifies the root handler this module owns, so a second `configure()` replaces it instead of
stacking a second copy (research.md R4). A duplicated handler is how structured logs quietly
double-count, and it is invisible to any test that only asserts a line *is* present."""

DEFAULT_LEVEL = "INFO"


def _destination() -> TextIO:
    """Where a record goes: standard error, resolved at write time rather than at configuration.

    structlog's `WriteLogger` and the standard library's `StreamHandler` both capture the stream
    when they are built. Resolving it per write means a process that redirects its standard error
    afterwards — a CLI, a test harness — is honoured rather than writing to a stream nobody is
    reading, and it keeps both paths out of this pipeline pointed at the same place.
    """
    return sys.stderr


class _StandardErrorLogger:
    """structlog's writer for this pipeline, one line per record."""

    def msg(self, message: str) -> None:
        stream = _destination()
        stream.write(message + "\n")
        stream.flush()

    log = debug = info = warn = warning = msg
    err = error = critical = exception = fatal = msg


class _StandardErrorLoggerFactory:
    def __call__(self, *arguments: Any) -> _StandardErrorLogger:
        return _StandardErrorLogger()


class _StructuredHandler(logging.Handler):
    """The standard library's way into the same pipeline, and the same destination.

    A plain `StreamHandler(sys.stderr)` would bind the stream at construction, so a third-party
    record would go somewhere the rest of the pipeline no longer writes.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            stream = _destination()
            stream.write(self.format(record) + "\n")
            stream.flush()
        # A logging handler must never raise into the code that logged.
        except Exception:
            self.handleError(record)


def _shared_processors() -> list[Any]:
    """Everything that shapes a record, in the order the guarantees depend on.

    The correlation and redaction slots are filled by `tracing` and `redaction`; they are looked up
    through those modules at call time so that this module does not need to be reconfigured when
    they are.
    """
    return [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]


def _tail_processors(*, include_conversation_content: bool) -> list[Any]:
    """The last processors: correlation, redaction, renderer. The order is load-bearing."""
    from hermes_memory.observability import redaction, tracing

    return [
        tracing.add_span_identifiers,
        redaction.redacting_processor(include_conversation_content=include_conversation_content),
        structlog.processors.JSONRenderer(),
    ]


def _install(*, level: str, include_conversation_content: bool) -> None:
    """Configure structlog itself. Shared by the import-time default and by `configure`."""
    structlog.configure(
        processors=[
            *_shared_processors(),
            *_tail_processors(include_conversation_content=include_conversation_content),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping()[level],
        ),
        logger_factory=_StandardErrorLoggerFactory(),
        # Deliberately off. Caching freezes the bound logger on first use, so a later `configure()`
        # would be invisible to any logger already obtained — which would make FR-023 untestable
        # and would surprise a CLI that configures again after reading a verbosity flag.
        cache_logger_on_first_use=False,
    )


def install_default_pipeline() -> None:
    """Install the safe default, reading nothing and touching nothing.

    Called at import of `hermes_memory.observability` (research.md R3). structlog's own default
    renders to the console with no redaction, so a component that logs before `configure()` runs —
    an import-time warning, a failure while loading the settings themselves — would emit
    unredacted. The unsafe default only shows itself in the incident.
    """
    _install(level=DEFAULT_LEVEL, include_conversation_content=False)


def configure(settings: Settings) -> None:
    """Apply the configured level and content flag, and bridge the standard library.

    Safe to call repeatedly (FR-023). Reads nothing from the environment itself — everything
    arrives on `settings` (FR-021) — and performs no network call and creates no file.
    """
    level = settings.logging.level
    include_conversation_content = settings.logging.include_conversation_content

    _install(level=level, include_conversation_content=include_conversation_content)
    _bridge_the_standard_library(
        level=level,
        include_conversation_content=include_conversation_content,
    )

    from hermes_memory.observability import tracing

    tracing.install_tracer_provider()


def _bridge_the_standard_library(*, level: str, include_conversation_content: bool) -> None:
    """Route third-party records through the same chain (research.md R5).

    httpx, urllib3 and the OpenTelemetry SDK log through the standard library and will never call
    our surface. Left alone their lines arrive unstructured *and* unredacted, and httpx logging a
    request URL with credentials in it is exactly what Principle V forbids. Sharing the chain makes
    every guarantee cover them; silencing them instead would hide the retry and connection detail
    §18's error reporting needs.
    """
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=_shared_processors(),
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            *_tail_processors(include_conversation_content=include_conversation_content),
        ],
    )

    handler = _StructuredHandler()
    handler.setFormatter(formatter)
    setattr(handler, _HANDLER_MARKER, True)

    remove_standard_library_bridge()

    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.getLevelNamesMapping()[level])


def remove_standard_library_bridge() -> None:
    """Detach the handler this module owns, leaving anything else on the root logger alone.

    Identified by its marker rather than by type, so a handler someone else installed — a test's
    own, a host application's — is never removed on our behalf.
    """
    root = logging.getLogger()
    for existing in list(root.handlers):
        if getattr(existing, _HANDLER_MARKER, False):
            root.removeHandler(existing)


def get_logger(name: str | None = None) -> Any:
    """A bound logger. Keyword arguments become fields; the first argument is an event name.

    Typed as `Any` rather than as a structlog type on purpose: the contract this boundary offers is
    "something you call `.info(event, **fields)` on", and pinning a vendor's generic here would put
    structlog in the signature every other module reads (Principle IV).
    """
    return structlog.get_logger(name)
