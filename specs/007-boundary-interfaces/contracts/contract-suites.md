# Contract — the six suites

**Feature**: [spec.md](../spec.md) | **Interfaces**: [interfaces.md](./interfaces.md) |
**Errors**: [errors.md](./errors.md)

Passing a boundary's suite is what "implements this boundary" means (FR-018, FR-019). Each suite is
a base class in `tests/contracts/`; an implementation's test module subclasses it and supplies the
implementation through one factory method (R11):

```python
class TestInMemoryRawArchive(RawArchiveContract):
    def make_archive(self) -> RawArchive:
        return InMemoryRawArchive()
```

Nothing in a suite may name a file, a URL, a table, a fixture or an implementation (FR-018). Where
a suite needs a conversation it builds a synthesized one (CLAUDE.md), and where it needs a failure
it asks the implementation for one through the factory's optional hooks — an implementation that
cannot be made to fail transiently declares so, and the suite skips that case rather than asserting
a lie.

Every rule below has an id, and every id has exactly one test.

---

## `ConversationSourceContract`

| Id | Rule |
|---|---|
| CS-1 | Every yielded value is a `Conversation`, and its `source` equals the source's declared `source`. |
| CS-2 | Reading yields conversations one at a time — the return value is an iterator, not a materialized sequence. |
| CS-3 | An empty export yields nothing and raises nothing. |
| CS-4 | Reading twice yields equal conversations. |
| CS-5 | A conversation that cannot be read raises `SourceFormatError`, and the remaining conversations are still yielded. |
| CS-6 | An unreachable export raises `SourceUnavailable`, which is retryable. |
| CS-7 | No exception belonging to a library crosses the boundary (E1). |

## `SecretSanitizerContract`

| Id | Rule |
|---|---|
| SS-1 | The input conversation is unchanged after the call. |
| SS-2 | The returned conversation preserves `source`, `source_id`, `document_id`, message count and message order. |
| SS-3 | A conversation carrying a known secret returns with that value absent from every message. |
| SS-4 | The surrounding text survives: a message that was non-empty is non-empty afterwards, and no message is dropped (§13). |
| SS-5 | The report counts what was redacted, by §13 category. |
| SS-6 | Nothing to redact returns an empty report, not `None`, and the conversation unchanged. |
| SS-7 | No redacted value, and no offset into the content, appears anywhere in the report (Principle V). |
| SS-8 | A conversation that cannot be rewritten raises `SanitizationError`; the failure is never signalled by returning the input. |

## `ProjectClassifierContract`

| Id | Rule |
|---|---|
| PC-1 | Every call returns a `ProjectTag`. |
| PC-2 | A conversation matching no rule returns `UNKNOWN_PROJECT` (`project:unknown`), and does not raise. |
| PC-3 | The same conversation classifies identically on repeated calls. |
| PC-4 | The conversation is unchanged after the call. |
| PC-5 | Classification raises no `BoundaryError` for any conversation the suite offers it (E8). |

## `RawArchiveContract`

| Id | Rule |
|---|---|
| RA-1 | A stored enriched conversation loads back equal, with an equal content hash. |
| RA-2 | The original payload loads back byte-identical, with its media type. |
| RA-3 | Storing the same document id twice leaves one document, and the second store wins. |
| RA-4 | `load` for an unknown document id raises `ArchiveDocumentNotFound`, which is not retryable. |
| RA-5 | `load_original` for an unknown document id raises `ArchiveDocumentNotFound`. |
| RA-6 | A conversation exercising every optional field of #8's model round-trips unchanged. |
| RA-7 | An unavailable store raises `ArchiveUnavailable`, which is retryable; refused input raises `ArchiveRejected`, which is not. |
| RA-8 | No exception belonging to a library crosses the boundary (E1). |
| RA-9 | After `store` returns, the document is loadable — no deferred write the caller cannot see (Principle I). |

## `MemoryStoreContract`

| Id | Rule |
|---|---|
| MS-1 | A retained conversation is recallable by a query matching its content. |
| MS-2 | Retaining the same enriched conversation twice yields no duplicate in recall results (FR-010). |
| MS-3 | Re-retaining a changed conversation under the same document id replaces rather than adds. |
| MS-4 | `recall` matching nothing returns an empty tuple. |
| MS-5 | Results carry the provenance the item was retained with. |
| MS-6 | `tags` narrow results: an item whose tags do not include the requested ones is not returned. |
| MS-7 | `limit` bounds the number of results. |
| MS-8 | A rejected, unauthorized or invalid call raises `MemoryStoreRejected`, which is not retryable. |
| MS-9 | A timeout, reset or 429/502/503/504 raises `MemoryStoreUnavailable`, which is retryable (§18). |
| MS-10 | No exception belonging to a library crosses the boundary, and no public name in the interface is a Hindsight term (FR-009). |
| MS-11 | A conversation large enough to be delivered in parts is recalled as one document; the caller cannot observe the split (§9). |

## `ImportStateContract`

| Id | Rule |
|---|---|
| IS-1 | `find` for a conversation never recorded returns `None`. |
| IS-2 | A recorded conversation is returned by `find` with every field equal to what was written. |
| IS-3 | Recording the same `(source, source_id)` twice leaves the later record. |
| IS-4 | A `failed` record is retrievable and distinguishable from no record (§18). |
| IS-5 | Records for different sources with the same native id do not collide. |
| IS-6 | `may_skip` is true only for an `imported` record whose content hash matches; false for `None`, for `failed`, for `skipped`, and for a changed hash. |
| IS-7 | An unavailable store raises `ImportStateUnavailable`, which is retryable; unreadable state raises `ImportStateCorrupt`, which is not. |
| IS-8 | No exception belonging to a library crosses the boundary (E1). |

---

## Every suite is shown to fail (FR-020, SC-003)

For each boundary, a deliberately broken fake violates exactly one rule, and a test asserts the
suite catches that rule and names it:

| Boundary | The breakage | Rule that must fail |
|---|---|---|
| Conversation source | stops iterating at the first unreadable conversation | CS-5 |
| Secret sanitizer | reports a redaction it did not perform | SS-3 |
| Project classifier | raises instead of answering `project:unknown` | PC-2 |
| Raw archive | drops the message timestamps on store | RA-1 |
| Memory store | appends on re-retain instead of replacing | MS-2 |
| Import state | records only successes | IS-4 |

A suite that passed one of these would be a suite that lets an implementation ship broken — which
is the failure mode contract suites exist to have, and the reason the repository already insists a
guard be watched failing (`test_the_behaviour_guard_still_bites`, R13).

## The pipeline harness (SC-004, SC-005)

Not a contract suite: one integration test that composes the six fakes into §7's order.

| Id | Rule |
|---|---|
| PL-1 | One synthesized conversation is sanitized, classified, enriched, archived, retained and recorded. |
| PL-2 | A second run over unchanged content reaches neither the archive nor the memory store, and the import state is what decided it (§17). |
| PL-3 | A run over changed content reaches both, under the same `document_id` (§10). |
| PL-4 | A conversation that fails one stage does not stop the run; the others are imported and the failure is reported with its source id (§18). |
| PL-5 | The whole run performs no network call and no filesystem write, blocked rather than merely unobserved (R14). |
| PL-6 | Replacing the memory store fake with a differently-implemented one changes only the composition line, and PL-1 to PL-5 pass unchanged (SC-006). |
