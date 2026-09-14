"""Logging, tracing and metrics. Conversation contents are not logged by default.

This is the boundary of ARCHITECTURE.md §8 that every other module reaches observability through.
What may be relied on is written down in
`specs/003-logging-telemetry-baseline/contracts/observability.md`; what follows is its surface.

Importing this package installs the pipeline. That is a side effect, and a deliberate one: it
reads no environment, opens no file and makes no network connection, and it is what makes a record
emitted before `configure()` — an import-time warning, or the failure to load the very settings
`configure()` needs — structured and redacted like any other
(specs/003-logging-telemetry-baseline/research.md R3). structlog's own default would render it to
the console with nothing withheld.
"""

from hermes_memory.observability.logging import configure, get_logger, install_default_pipeline
from hermes_memory.observability.operations import (
    Operation,
    OperationStatus,
    ingestion_operation,
)
from hermes_memory.observability.redaction import REDACTED, ConversationContent

__all__ = [
    "REDACTED",
    "ConversationContent",
    "Operation",
    "OperationStatus",
    "configure",
    "get_logger",
    "ingestion_operation",
]

install_default_pipeline()
