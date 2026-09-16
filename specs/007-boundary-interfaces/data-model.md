# Phase 1 — Data model: the types the boundaries own

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Research**:
[research.md](./research.md)

#8 defined the conversation, the message, tool activity, provenance, the enriched conversation and
the tags, and SC-001 of that feature reserved exactly this space: a boundary may own a type the
model deliberately does not define, as long as it does not invent a second way to describe a
conversation. Seven such types are defined here — six planned, and `SourceConversation`, which implementation
showed was missing — and nothing else.

Every value is a `FrozenModel` from `hermes_memory.normalization.base` — immutable, extra fields
forbidden, validated on construction — except the errors, which are exceptions (R16, R4).

---

## `OriginalPayload` — `archive/interface.py`

What the source was read from, kept beside the normalized form so that a replay can re-run a fixed
parser over the original bytes (Principle I, §14, R8).

| Field | Type | Required | Rule |
|---|---|---|---|
| `content` | `bytes` | yes | the source's own bytes, unmodified |
| `media_type` | `Text` | yes | non-empty, e.g. `application/json` |

The archive does not interpret either field. The on-disk layout is #13's (§20).

## `SourceConversation` — `ingestion/source.py`

One conversation as a source reads it, with the bytes it came from. Added during implementation,
when composing the boundaries showed the archive needs an original that only the source holds
([interfaces.md §1](./contracts/interfaces.md#1-conversationsource--ingestionsourcepy)).

| Field | Type | Required | Rule |
|---|---|---|---|
| `conversation` | `Conversation` | yes | #8's normalized conversation |
| `original` | `OriginalPayload` | yes | the bytes it was parsed from |

## `RedactionReport` and `RedactionCategory` — `sanitization/sanitizer.py`

What the sanitizer redacted, by category and count — never the values (Principle V, FR-004, R6).

`RedactionCategory` is a `StrEnum` seeded with §13's minimum categories: `api-key`, `bearer-token`,
`jwt`, `github-token`, `gitlab-token`, `anthropic-key`, `openai-key`, `aws-access-key`,
`private-key`, `password`, `connection-string`, `dotenv-value`, `kubernetes-secret`. #11 may add a
category; it may not turn the field into a free string.

| Field | Type | Required | Rule |
|---|---|---|---|
| `counts` | `Mapping[RedactionCategory, int]` | yes | every count ≥ 1; a category with none redacted is absent, not zero; held read-only |

Derived: `total` → the sum of the counts. `is_empty` → no counts at all.

Invariants:

* A report carries no text from the conversation, no redacted value and no offset into the content
  (R6 — an offset plus the archived original reconstructs the secret).
* An empty report is an ordinary value. A boundary returning `None` instead is a contract violation.

## `ImportRecord`, `ImportStatus` and the skip rule — `ingestion/state.py`

The §17 record, and §18's outcome vocabulary.

`ImportStatus` is a `StrEnum`: `imported`, `skipped`, `failed`.

| Field | Type | Required | Rule |
|---|---|---|---|
| `source` | `Source` | yes | closed vocabulary, from #8 |
| `source_id` | `OpaqueIdentifier` | yes | the source's native id |
| `content_hash` | `Text` | yes | #8's hash of the conversation **as read, before sanitization** — what the source yields next time; the hash of the redacted form would never match once anything was redacted |
| `document_id` | `Text` | yes | §10 shape, derived by #8 |
| `recorded_at` | `Timestamp` | yes | when the importer wrote this record — the import clock, never the conversation's (§11) |
| `status` | `ImportStatus` | yes | `imported` or `failed`; **`skipped` is refused** — it is the run's report, and a stored skip would overwrite the record it was decided from |
| `error` | `Text \| None` | for `failed` | required for `failed`, refused otherwise; carries no conversation content and no credential (R5) |

The skip decision is one function, defined here and not in any store (R10, FR-012):

```text
may_skip(record: ImportRecord | None, content_hash: str) -> bool
```

It is true when a record exists, its status is `imported`, and its content hash equals the one
offered. It is false for no record, for a `failed` record, and for a changed hash.

## `RecallResult` — `memory/interface/store.py`

One match returned by a recall, expressed without naming the engine that produced it (FR-009, R9).

| Field | Type | Required | Rule |
|---|---|---|---|
| `content` | `Text` | yes | what was recalled |
| `provenance` | `Provenance` | yes | the §3.3 record the item was retained with |
| `score` | `float \| None` | no | whatever the implementation means by relevance; comparable only within one result set, never across calls or implementations |

No field names a bank, an item, a document version or an update mode.

## The errors — `errors.py` and the boundary modules

`errors.py` holds the taxonomy (R3, R4); each boundary declares its own leaves.

```text
BoundaryError                 retryable: ClassVar[bool]
├── TransientBoundaryError    retryable = True
└── PermanentBoundaryError    retryable = False
```

| Attribute | Type | Rule |
|---|---|---|
| `boundary` | `str` | which §8 boundary raised it |
| `subject` | `str \| None` | the source id or document id it concerned, when there is one |
| `message` | `str` | human-readable; no conversation content, no credential, no token, no authorization header (R5, §19) |

`retryable` is a class attribute, readable on any instance and settable on none: §18's
never-retryable conditions must not be expressible as retryable (FR-014, R4). No error timestamps
itself — the time belongs to the report that records it (§18, §11).

The leaves each boundary declares:

| Boundary | Permanent | Transient |
|---|---|---|
| Conversation source | `SourceFormatError` — this conversation cannot be read | `SourceUnavailable` — the export itself could not be reached |
| Secret sanitizer | `SanitizationError` — the conversation could not be rewritten | — |
| Project classifier | — (an unresolved project is `project:unknown`, not a failure) | — |
| Raw archive | `ArchiveDocumentNotFound`, `ArchiveRejected` | `ArchiveUnavailable` |
| Memory store | `MemoryStoreRejected` — refused, unauthorized or invalid input | `MemoryStoreUnavailable` — timeout, reset, 429, 502, 503, 504 |
| Import state | `ImportStateCorrupt` | `ImportStateUnavailable` |

The classifier declares no error deliberately (FR-017, §15, R7): the case a classifier fails on is
the case §15 says is ordinary.

---

## What is *not* defined here

* **No second conversation shape.** Everything crossing a boundary is #8's `Conversation`,
  `EnrichedConversation`, `Provenance` or `Tag` (FR-002).
* **No archive layout, no state schema, no wire format.** §20 leaves them to the features that need
  them — #13 and #14.
* **No retry policy and no backoff values.** #20 (R17).
* **No redaction patterns.** #11 supplies them; this feature supplies the vocabulary they report in.
