# Contract: the observability boundary

What every other module may rely on, and what it must not. This is the §8 boundary Principle IV
asks for: components depend on this contract, not on structlog, on OpenTelemetry, or on the shape
of the pipeline behind it.

Every claim below is a test, listed in the Checks section at the end so the task list and the
review have the same roster to work from.

## The surface

Everything a consumer needs is re-exported from `hermes_memory.observability`. Nothing outside that
package configures logging, installs a handler, writes to a stream, or constructs a tracer provider
(FR-001, SC-010).

```python
configure(settings: Settings) -> None
get_logger(name: str | None = None) -> BoundLogger
get_tracer(name: str) -> Tracer
ingestion_operation(*, source, source_id, bank, project=None, document_id=None) -> ContextManager[Operation]
OperationStatus            # imported | skipped | failed
ConversationContent(text)  # the marker wrapper for a conversation body
REDACTED                   # the string a withheld value is replaced by
```

### `configure(settings)`

Applies the level and the content flag from the settings, installs the standard-library bridge, and
constructs the tracer provider.

* Safe to call more than once. A second call replaces the configuration; it does not stack a second
  handler and does not duplicate output (FR-023).
* Reads nothing from the environment itself. Everything it needs arrives on the settings object
  (FR-021).
* Not required before logging. Importing the package already installs a redacting, JSON-rendering
  pipeline at the default level; `configure` refines it (FR-024).
* Performs no network call and opens no file.

### `get_logger(name)`

Returns a bound logger. Keyword arguments become fields of the record. Callers do not format
messages — the first positional argument is an event name, not a sentence with values interpolated
into it (FR-002).

### `ingestion_operation(...)`

A context manager that binds the §18 context, times the body, and emits exactly one record when it
exits (FR-003).

* On a clean exit the status is `imported` unless the body called `skipped()` on the yielded
  operation.
* On an exception the status is `failed`, the error is recorded, the record is still emitted, and
  **the exception continues to propagate** (FR-006). The context manager never swallows; deciding
  that one conversation's failure must not abort the run stays the caller's, which is what §18
  says.
* `start_time` and `duration_ms` come from the manager. There is no way for a caller to supply
  either (FR-005).
* The bound context is removed on exit, whichever way the body left (FR-007).

### `get_tracer(name)`

Returns a tracer from the provider this package owns. Starting and ending a span succeeds, exports
nothing and opens no connection (FR-018, FR-019). Records emitted while a span is active carry
`trace_id` and `span_id`; records emitted with no active span carry neither (FR-020).

## The guarantees

These hold for every record, whatever the caller did, and they are the reason this boundary exists.

1. **Structured.** Every record leaves the process as one JSON object on one line, on standard
   error (FR-002).
2. **No credential.** A value is withheld when its field name matches the name roster below, when
   it is a `SecretStr`, or when the value matches the shape roster below — at any depth up to 6,
   inside mappings and sequences alike (FR-009, FR-010, FR-011, FR-012).
3. **No conversation content by default.** A `ConversationContent` renders as `[redacted:content]`
   unless the content flag is on, and the flag never affects guarantee 2 (FR-014, FR-015).
4. **Exceptions are covered.** The rendered traceback and the exception's message and arguments
   pass through redaction like any other field (FR-016).
5. **Visible redaction.** A withheld value is replaced, never dropped, so a reader can tell a
   redacted field from an absent one (FR-013).
6. **Fail closed.** A value that cannot be inspected or rendered is withheld; the record is still
   emitted; the logging call does not raise into the caller (FR-017).

### Name roster

A field is sensitive when its name — lowercased, split on any run of non-alphanumeric characters —
contains one of these segments:

```text
token  secret  password  passwd  credential  credentials
authorization  cookie  cookies  jwt  bearer  apikey
```

…or contains one of these adjacent pairs:

```text
api+key   access+key   private+key   secret+key   auth+header   auth+token
```

`key` alone is not a segment, and `auth` alone is not: `idempotency_key` and `author` are ordinary
fields in this project and a redactor that eats them gets worked around (research.md R6).

### Shape roster

A string value is redacted, span by span, when it contains:

```text
an Authorization-style prefix and token   Bearer <token>, Basic <token>
a JSON web token                          eyJ<base64url>.<base64url>.<base64url>
a conventionally prefixed API key         sk-…, sk-ant-…, ghp_…, gho_…, ghs_…
credentials in a URL                      scheme://user:password@host
```

Only the matched span is replaced; the surrounding text survives, as Principle V requires of
redaction.

**This roster is not a secret scanner.** ARCHITECTURE.md §13's sanitizer is separate work and is
what protects conversation content on its way to the memory engine. Nothing may treat this boundary
as a substitute for it (research.md R7).

## What this boundary does not do

* It does not decide that a failure should or should not abort a run.
* It does not parse, normalize, sanitize, classify, archive or retain anything (FR-025).
* It does not export traces, and adds no trace-destination setting (research.md R11).
* It does not emit metrics.
* It does not know what Hindsight is. `bank` is a string a caller passes; no Hindsight type,
  endpoint or vocabulary appears anywhere in this package (Principle IV).

## Checks

The roster the task list is built from. Each line is at least one test, written before the code and
observed to fail (Principle III).

**Record shape**

1. An ingestion operation emits exactly one record carrying all ten fields of the §18 set.
2. The record parses as JSON; nothing is emitted as prose.
3. `status` is `imported` on a clean exit, `skipped` when the body says so, `failed` on an
   exception.
4. `duration_ms` is present, numeric, and not supplied by the caller.
5. On an exception, the record is emitted, `error` is non-null, and the exception reaches the
   caller.
6. Context bound for an operation appears on other records emitted inside it, and on none emitted
   after it ends.
7. Two operations in sequence on one thread do not share context.
7a. A failed operation is recorded at error level and survives a raised threshold; the other two
    outcomes are recorded at info.

**Redaction**

8. For **each** segment on the name roster, a value under a field named with it does not appear in
   the output.
9. For **each** pair on the pair roster, the same.
10. `author`, `idempotency_key`, `document_id` and `bank` are **not** redacted — the guard against
    a redactor that eats real fields.
11. A `SecretStr` value is withheld whatever the field is named.
12. For **each** shape on the shape roster, the value does not appear, and the surrounding text
    does.
13. A credential nested inside a mapping inside a list inside a mapping does not appear.
14. A value at depth 7 is withheld rather than emitted unexamined.
15. A credential in an exception's message does not appear in the rendered record.
16. A withheld value is present as the marker, not missing.
17. A value whose inspection raises is withheld, the record is still emitted, and the logging call
    does not raise.
18. A cyclic structure terminates.

**Conversation content**

19. With no configuration at all, a `ConversationContent` does not appear.
20. With the flag off, the same.
21. With the flag on, it appears.
22. With the flag on, a credential in the same record is still withheld.
23. Content beyond the cap is truncated and marked.
24. `ConversationContent`'s own `repr` and `str` do not reveal the text.

**Configuration and lifecycle**

25. Configuring twice and logging once emits one line.
26. A record emitted before `configure` is structured and redacted.
27. `configure` performs no network call and creates no file.
28. An invalid level fails at settings load, naming the variable.
29. `.env.example` lists both new variables — 002's existing check, extended by nothing.

**Tracing**

30. A span can be started and ended; no network call is made.
31. A record emitted inside a span carries `trace_id` and `span_id`.
32. A record emitted outside a span carries neither.

**Repository invariants**

33. No module outside `observability/` configures logging, adds a handler or writes to stderr.
34. The runtime dependency guard names exactly the five permitted distributions.
