# Contract — the six boundary interfaces

**Feature**: [spec.md](../spec.md) | **Plan**: [plan.md](../plan.md) |
**Types**: [data-model.md](../data-model.md) | **Errors**: [errors.md](./errors.md)

The six rows of ARCHITECTURE.md §8, one protocol each, in the vocabulary of #8 (FR-001, FR-002).
Signatures are shown as they will be declared; the rules beneath each are what
[contract-suites.md](./contract-suites.md) holds every implementation to.

Every protocol is `typing.Protocol` — structural, never inherited from (R1). Every method is
synchronous (R17).

---

## 1. `ConversationSource` — `ingestion/source.py`

> §8: read one source format, yield normalized conversations.

```python
class SourceConversation(FrozenModel):
    conversation: Conversation
    original: OriginalPayload


class ConversationSource(Protocol):
    source: Source

    def read(self) -> Iterator[SourceConversation]: ...
```

* Yields each conversation **together with the bytes it was read from**. Principle I asks the
  archive for both forms and only the source has the original — by the time a conversation is
  normalized, the slice of the export it came from is gone unless somebody kept it. Added during
  implementation: the pipeline harness (PL-1) could not be written until the source and the archive
  agreed about this, which is the discovery US3 exists to make before either is real.
* Yields one conversation at a time, so a caller can fail on one without abandoning the export or
  holding it in memory (FR-003, §18).
* Every conversation it yields carries `source == self.source`.
* An export with no conversations yields nothing. Emptiness is not an error (FR-017).
* A conversation that cannot be read raises `SourceFormatError` from the iterator, and **the
  iterator stays usable** for the remaining conversations — which rules out a generator, since an
  exception raised inside one closes it for good (found while writing the fake); the export being unreachable raises
  `SourceUnavailable`.
* Reading twice yields equal conversations: a source is a reader, not a cursor that consumes.

## 2. `SecretSanitizer` — `sanitization/sanitizer.py`

> §8: redact secrets, report what was redacted.

```python
class SecretSanitizer(Protocol):
    def sanitize(self, conversation: Conversation) -> tuple[Conversation, RedactionReport]: ...
```

* Returns a new conversation; the argument is unchanged (#8's values are frozen, and Principle V's
  failure mode is a half-redacted object escaping after an exception).
* Identity is preserved: `source`, `source_id`, `document_id` and message count and order are the
  same as the input's.
* The report counts what was redacted, by §13 category, and carries no redacted value (FR-004, R6).
* Nothing to redact returns the conversation and an empty report — never `None`.
* Redaction preserves the surrounding text (§13): the returned message text is not the empty string
  where the input was non-empty, and a message is never dropped.
* A conversation it cannot rewrite raises `SanitizationError`. It never returns the input unchanged
  to signal failure.

## 3. `ProjectClassifier` — `classification/classifier.py`

> §8: determine the project for a conversation.

```python
class ProjectClassifier(Protocol):
    def classify(self, conversation: Conversation) -> ProjectTag: ...
```

* Always returns a tag. No rule matching returns `UNKNOWN_PROJECT` — `project:unknown` (§15, FR-005,
  R7).
* Deterministic: the same conversation classifies the same way within a run and between runs.
* Declares no error (FR-017): §15 makes the unresolved case ordinary, and the classifier reads a
  conversation it was handed — there is nothing to be unavailable.
* Pure: it performs no I/O and leaves the conversation unchanged.

## 4. `RawArchive` — `archive/interface.py`

> §8: persist originals and normalized forms.

```python
class RawArchive(Protocol):
    def store(self, enriched: EnrichedConversation, original: OriginalPayload) -> None: ...

    def load(self, document_id: str) -> EnrichedConversation: ...

    def load_original(self, document_id: str) -> OriginalPayload: ...
```

* Stores both forms together (Principle I, §14, R8). A partial store — one form without the other —
  is a contract violation.
* Round-trips: what `load` returns equals what was stored, with an equal content hash. A field
  quietly dropped is the failure Principle I is written against.
* Idempotent by document id: storing twice leaves one document, and the second store wins.
* `archive/__init__.py` re-exports the interface and no implementation: the source interface names
  `OriginalPayload`, so every consumer of it initializes this package.
* `load` and `load_original` for a document the archive does not hold raise
  `ArchiveDocumentNotFound`; a store that cannot be reached raises `ArchiveUnavailable`; input the
  archive refuses raises `ArchiveRejected` (FR-007).
* Storing is durable before it returns, because §7 archives before retaining and Principle I says
  the archive is the source of truth.

## 5. `MemoryStore` — `memory/interface/store.py`

> §8: `retain` / `recall` — the only component aware of Hindsight.

```python
class MemoryStore(Protocol):
    def retain(self, enriched: EnrichedConversation) -> None: ...

    def recall(
        self,
        query: str,
        tags: tuple[AnyTag, ...] = (),
        limit: int | None = None,
    ) -> tuple[RecallResult, ...]: ...
```

* No name here is a Hindsight term (FR-009): no bank, item, retain mission, update mode, operation
  id or endpoint. `retain` and `recall` are §16's words.
* Retaining the same enriched conversation twice leaves one logical document — promised to the
  caller, achieved however the implementation likes (FR-010, §9). The suite proves it through
  `recall`, never through an inspection method the interface does not have (R9).
* A conversation too large for one call is the implementation's problem; a caller cannot observe
  whether it was delivered in parts (§9's append mode, spec edge case).
* `recall` matching nothing returns an empty tuple (FR-017). `tags` narrow the results; `limit`
  bounds them.
* Results carry the provenance the item was retained with, so a caller can say where a recalled fact
  came from without asking the engine (Principle II).
* Refused, unauthorized or invalid input raises `MemoryStoreRejected` (never retryable); timeouts,
  resets and 429/502/503/504 raise `MemoryStoreUnavailable` (retryable) — §18, FR-014.

## 6. `ImportState` — `ingestion/state.py`

> §8: track what has already been imported.

```python
class ImportState(Protocol):
    def record(self, record: ImportRecord) -> None: ...

    def find(self, source: Source, source_id: str) -> ImportRecord | None: ...
```

and, in the same module and outside the protocol:

```python
def may_skip(record: ImportRecord | None, content_hash: str) -> bool: ...
```

* `find` for a conversation never seen returns `None` — the state of everything on the first run
  (FR-017).
* `record` is last-write-wins per `(source, source_id)`: a conversation imported, then re-imported
  after a change, has one current record. That is why **a skip is never recorded** — `ImportRecord`
  refuses one — and why the stored hash is of the conversation as read, not as sanitized.
* Outcomes include failures (§18, R10). A `failed` record and no record are different answers, and a
  resume depends on the difference.
* The skip decision is `may_skip`, not a method: one rule for every store, so two implementations
  cannot disagree about what "unchanged" means (R10, FR-012).
* Answering it contacts no other boundary — that is the point of the skip (§17, FR-012).
* Unreachable storage raises `ImportStateUnavailable`; unreadable state raises `ImportStateCorrupt`.

---

## What every interface shares

* **Vocabulary** (FR-002): what crosses is `Conversation`, `EnrichedConversation`, `Provenance`,
  `AnyTag`, a document id, or one of the six types [data-model.md](../data-model.md) defines. No
  dictionaries, no source-specific structures, no free strings standing in for a typed value.
* **Errors** (FR-013): only what [errors.md](./errors.md) declares. No `httpx`, `sqlite3`,
  `OSError` or `json` exception crosses a boundary.
* **No Hindsight** (FR-026): no interface module imports Hindsight, an HTTP client or a storage
  library, directly or transitively — asserted over the import graph.
* **Synchronous, single-writer** (R17): no interface promises concurrency, and none forbids an
  implementation that provides it.
