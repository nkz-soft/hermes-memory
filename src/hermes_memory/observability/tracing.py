"""The tracer a later span around `retain` attaches to, and log/trace correlation.

Placeholder. The correlation slot sits in the chain before redaction so that the identifiers it
adds pass through redaction like any other field; the provider and the correlation itself arrive
with User Story 4, against tests written first.
"""

from __future__ import annotations

from typing import Any

__all__ = ["add_span_identifiers", "install_tracer_provider"]


def add_span_identifiers(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Add the identifiers tying this record to the active span, when there is one."""
    return event_dict


def install_tracer_provider() -> None:
    """Set the tracer provider this project owns, once per process."""
    return None
