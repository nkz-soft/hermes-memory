"""The tracer a later span around `retain` attaches to, and log/trace correlation.

This feature provides the tracer, not the tracing. What it owns is the single place the provider
is constructed, so that the feature with something to time asks for a span rather than
bootstrapping its own telemetry.

**Nothing is exported.** No span processor and no exporter are installed, and no trace-destination
setting exists. Starting and ending a span costs an allocation and makes no connection, which is
FR-019 by construction rather than by configuration. A seam whose only implementation is
unreachable rots, and the feature that actually exports will want to choose its exporter against a
real collector (specs/003-logging-telemetry-baseline/research.md R11).

One thing a reader should not have to discover: the OpenTelemetry SDK reads its own `OTEL_*`
environment variables when it builds a provider. That is the SDK's published contract with
operators, the same kind of thing as httpx honouring `HTTP_PROXY`, and not this project reading
configuration outside `settings.py` — every value *this project* reads still arrives on the
settings object, and the resource attributes below are passed explicitly so they do not depend on
the ambient environment.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

__all__ = ["SERVICE_NAME", "add_span_identifiers", "get_tracer", "install_tracer_provider"]

SERVICE_NAME = "hermes-memory"

_installed = False
"""Whether this process has set its tracer provider.

`trace.set_tracer_provider` ignores a second call and logs a warning, so a repeated `configure()`
would otherwise emit a warning on every call for no reason (FR-023).
"""


def _service_version() -> str:
    try:
        return version("hermes-memory")
    except PackageNotFoundError:
        # Running from a source tree that was never installed. A missing version is not a reason
        # to fail a process that only wanted to log.
        return "unknown"


def install_tracer_provider() -> None:
    """Set the tracer provider this project owns, once per process."""
    global _installed
    if _installed:
        return

    trace.set_tracer_provider(
        TracerProvider(
            resource=Resource.create(
                {
                    "service.name": SERVICE_NAME,
                    "service.version": _service_version(),
                }
            )
        )
    )
    _installed = True


def get_tracer(name: str) -> trace.Tracer:
    """A tracer from the provider this package owns.

    Installs the provider on first use, so that a component asking for a span before `configure()`
    has run gets a real one rather than a no-op whose span context could never be correlated.
    """
    install_tracer_provider()
    return trace.get_tracer(name)


def add_span_identifiers(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Add the identifiers tying this record to the active span, when there is one (FR-020).

    Nothing is added outside a span: empty identifiers on every line would double the noise of a
    log for no information. The identifiers are lowercase hexadecimal of the conventional width,
    which is what every tracing tool expects to join on.

    Runs before redaction, so what it adds passes through redaction like any other field.
    """
    context = trace.get_current_span().get_span_context()

    if context.is_valid:
        event_dict["trace_id"] = trace.format_trace_id(context.trace_id)
        event_dict["span_id"] = trace.format_span_id(context.span_id)

    return event_dict
