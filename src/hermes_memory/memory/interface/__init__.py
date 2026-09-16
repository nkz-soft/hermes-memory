"""What every other module depends on. Knows nothing of any memory engine.

The memory store boundary of ARCHITECTURE.md §8: `retain` and `recall`, expressed in the
architecture's vocabulary. The Hindsight implementation arrives with #16 and lives in
`memory/hindsight` — the only module permitted to know that Hindsight exists (Principle IV).
"""

from hermes_memory.memory.interface.store import (
    MemoryStore,
    MemoryStoreRejected,
    MemoryStoreUnavailable,
    RecallResult,
)

__all__ = ["MemoryStore", "MemoryStoreRejected", "MemoryStoreUnavailable", "RecallResult"]
