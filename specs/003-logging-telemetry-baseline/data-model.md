# Data Model: Logging and Telemetry Baseline

Phase 1 output for [plan.md](plan.md). Nothing here is persisted — the "data" of this feature is
the shape of a record on its way out of the process, and the objects that shape it. The boundary
callers depend on is [contracts/observability.md](contracts/observability.md).

## The ingestion operation record

The field set of ARCHITECTURE.md §18, emitted exactly once per ingestion operation (FR-003). Every
field is always present; the value may be null where the fact is genuinely unknown, and the columns
below say which.

| Field | Type | Null? | Source |
|---|---|---|---|
| `event` | string | no | fixed: `ingestion.operation` |
| `source` | string | no | caller — the history source, e.g. `chatgpt` |
| `source_id` | string | no | caller — the source's native identifier for the conversation |
| `project` | string | yes | caller — null when classification has not run or found nothing |
| `bank` | string | no | caller, defaulted from the configured bank id |
| `document_id` | string | yes | caller — null when the operation failed before one was derived |
| `start_time` | string | no | measured — ISO 8601, UTC, with offset |
| `duration_ms` | number | no | measured — wall clock, milliseconds, from a monotonic source |
| `status` | string | no | measured — `imported`, `skipped` or `failed` |
| `error` | string | yes | measured — null unless status is `failed` |

Notes that are requirements rather than commentary:

* `duration_ms` and `start_time` are produced by the context manager, never accepted from the
  caller (FR-005). A caller cannot report a duration it did not spend.
* `status` is a closed vocabulary (FR-004), represented as a string enumeration so that a typo is a
  failure at the call site rather than a value in the record.
* `error` holds the exception's type and message after redaction, not a traceback. The traceback is
  the `exception` field the pipeline renders separately, which is subject to the same redaction
  (FR-016).
* Every other field a caller binds to the operation appears alongside these, and these are never
  removed to make room.

### States

The operation has exactly three terminal states and no others:

```text
           ┌──→ imported   the conversation was retained
started ───┼──→ skipped    nothing to do: unchanged since a previous run
           └──→ failed     an exception escaped; error is non-null and it is re-raised
```

There is no `started` record. §18 asks for a record per operation, and one record with a duration
is more useful than two that a reader has to pair up — the start time is a field of the terminal
record, not a second line.

## Operation context

The fields bound once for the duration of one operation and carried by every record emitted inside
it (FR-007). It is held in context variables, so it follows the flow of control rather than being
threaded through call signatures, and it is unbound when the operation ends — a later operation on
the same thread never inherits it (spec, Edge Cases).

## Value markers

Three wrapper or sentinel values with defined rendering. Each exists so that a protection is a
property of the value, not of the call site.

| Marker | What it is | Rendered as |
|---|---|---|
| `REDACTED` | the replacement for a withheld value | `"[redacted]"` |
| `TRUNCATED_SUFFIX` | appended when content exceeded the cap | `"…[truncated]"` |
| `ConversationContent(text)` | a frozen wrapper marking a conversation body | `"[redacted:content]"`, or the text when the content flag is on |

`ConversationContent` withholds its text from its own `__repr__` and `__str__` as well, so a call
site that interpolates it outside the logging path reveals nothing (research.md R8).

`pydantic.SecretStr` needs no wrapper of ours: 002 already made every credential one, and the
redactor treats it as sensitive whatever field it arrives under (FR-010).

## Rosters

Two documented, enumerable sets, reproduced in the contract and asserted item by item in tests
(SC-003).

| Roster | Matched against | Effect |
|---|---|---|
| Sensitive name segments | the field's name, lowercased and split on non-alphanumerics | the whole value becomes `REDACTED` |
| Sensitive name pairs | adjacent segment pairs of the same name | the whole value becomes `REDACTED` |
| Credential shapes | the string value itself, at any key | the matching span becomes `[redacted]`, the rest of the string survives |

## Logging settings

One nested group added to the existing `Settings` object (FR-021, research.md R12). Both fields
have defaults, so a project with no logging configuration at all is correctly configured.

| Field | Environment variable | Type | Default |
|---|---|---|---|
| `level` | `HERMES_LOGGING__LEVEL` | one of `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | `INFO` |
| `include_conversation_content` | `HERMES_LOGGING__INCLUDE_CONVERSATION_CONTENT` | boolean | `false` |

`level` is validated against the closed set and matched case-insensitively; anything else fails at
load time through 002's existing error path, which names the variable and withholds the value.

`include_conversation_content` is the only thing that can ever cause a conversation body to be
emitted, and it can never cause a credential to be (FR-015).

## Tracer resource

The identifying attributes attached to the tracer provider, passed explicitly rather than inherited
from the ambient environment (research.md R11):

| Attribute | Value |
|---|---|
| `service.name` | `hermes-memory` |
| `service.version` | the installed distribution version |

No exporter, no span processor, no sampler beyond the default — nothing is exported, and starting a
span performs no I/O (FR-019).
