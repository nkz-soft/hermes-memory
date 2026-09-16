# Contract — boundary errors

**Feature**: [spec.md](../spec.md) | **Interfaces**: [interfaces.md](./interfaces.md) |
**Suites**: [contract-suites.md](./contract-suites.md)

ARCHITECTURE.md §18 requires a run to survive one conversation's failure, to retry transient
failures only, and to report each failure with its source id, its error and its time. That is a
contract on the boundaries: a caller that cannot tell a timeout from a rejected request either
retries forever or gives up on a call that would have worked.

## E1 — Every boundary failure is one of ours

An implementation raises only errors declared in `errors.py` or in its own boundary module. A
caller must never have to catch `httpx.HTTPError`, `sqlite3.DatabaseError`, `OSError`,
`json.JSONDecodeError` or any other library's exception to handle a boundary failure (FR-013,
Principle IV).

The underlying exception is chained (`raise … from …`) so a developer can see it; the chain is for
reading, not for catching.

## E2 — Retryability is answered by type, not by text

```text
BoundaryError            retryable: ClassVar[bool]
├── TransientBoundaryError   retryable = True
└── PermanentBoundaryError   retryable = False
```

A caller answers "could the identical call succeed?" with `except TransientBoundaryError` or by
reading `error.retryable`. It never parses a message and never matches a status code (FR-014, §18).

## E3 — The never-retryable conditions cannot claim to be retryable

§18 names them: a rejected request, an unauthorized one, invalid input. Each is a
`PermanentBoundaryError`, `retryable` is a class attribute, and no constructor accepts a retryable
flag — so the mistake is not available rather than merely discouraged (FR-014, R4).

## E4 — An error carries what §18 needs to report it, and nothing more

`boundary`, `subject` — the source id or document id, when there is one — and a message. Nothing
else (FR-015).

## E5 — An error never carries a secret

No conversation content, no credential, no token, no authorization header, no request or response
body (FR-016, §19, Principle V).

The chained cause is the sharp edge: an HTTP client's exception can carry a URL with a token in it.
The memory store's errors say so in their own documentation, and §18's failure report renders the
boundary error alone, never the chain.

## E6 — An error does not timestamp itself

§18's report records the time; §11 forbids a captured clock standing in for a real one. An error
that stamped itself would be one more place for the wrong time to come from.

## E7 — Ordinary answers are not failures

No boundary raises for: an export with no conversations, nothing to redact, an unresolved project,
a document the archive has never held *when the caller asked whether it holds one*, an empty
recall, or a conversation the import state has not seen (FR-017).

The one deliberate exception is `RawArchive.load`, which raises `ArchiveDocumentNotFound` rather
than returning `None`: `load` is a demand for a document the caller believes exists, and a `None`
that flows on silently is how a replay loses history. It is a `PermanentBoundaryError`, and it is
distinguishable from `ArchiveUnavailable` — the first is an ordinary answer during a resume, the
second is a defect (FR-007).

## E8 — The classifier declares no error at all

§15 makes the unresolved project ordinary and `project:unknown` is its value. A classifier reads a
conversation it was handed: there is no store to be unavailable and no input to be rejected. An
error type here would be an invitation to make the common case exceptional (R7).

---

## The declared leaves

| Boundary | Permanent | Transient |
|---|---|---|
| Conversation source | `SourceFormatError` | `SourceUnavailable` |
| Secret sanitizer | `SanitizationError` | — |
| Project classifier | — | — |
| Raw archive | `ArchiveDocumentNotFound`, `ArchiveRejected` | `ArchiveUnavailable` |
| Memory store | `MemoryStoreRejected` | `MemoryStoreUnavailable` |
| Import state | `ImportStateCorrupt` | `ImportStateUnavailable` |

#20 reads exactly one thing from this table: which side of it an error sits on.
