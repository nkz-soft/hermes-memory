# Feature Specification: Logging and Telemetry Baseline

**Feature Branch**: `003-logging-telemetry-baseline`

**Created**: 2026-09-14

**Status**: Draft

**Input**: GitHub issue #6 — "Establish structured logging and telemetry baseline". Phase 1, wave 2.
Depends on #4.

## User Scenarios & Testing *(mandatory)*

The users of this feature are the contributors and operators who run an import and then have to
find out what it did, and every later component that emits a log line. The value delivered is that
the observability guarantees of ARCHITECTURE.md §18 and Principle V — a complete, machine-readable
record per operation, and no credential or conversation body anywhere in it — hold because the
logging pipeline enforces them, not because each caller remembered them.

### User Story 1 - An operator can tell what an import did, line by line (Priority: P1)

Someone runs an import over a large export and afterwards needs to know which conversations were
imported, which were skipped, which failed and why. They read the output — or feed it to whatever
reads machine-readable logs — and every operation is one record carrying the same named fields,
with no line needing to be correlated by hand against another.

**Why this priority**: this is the record §18 requires, and the reason the issue exists. An import
that reports nothing per conversation cannot be trusted at the scale this project targets, and the
fields have to be fixed before the first component starts inventing its own.

**Independent Test**: emit an ingestion operation through the logging surface, capture the output,
parse it as structured data, and assert every field §18 names is present with the intended value.

**Acceptance Scenarios**:

1. **Given** the logging baseline is configured, **When** an ingestion operation completes
   successfully, **Then** one record is emitted carrying source, source id, project, bank, document
   id, start time, duration, status and error, and it parses as structured data rather than as
   prose.
2. **Given** an ingestion operation, **When** it finishes, **Then** its status is one of the three
   outcomes §18 defines — imported, skipped or failed — and never an ad-hoc value.
3. **Given** an ingestion operation that raises an error, **When** it finishes, **Then** the record
   is still emitted, its status is failed, and the error is recorded in the error field.
4. **Given** an ingestion operation that raises an error, **When** the caller continues, **Then**
   the logging surface has neither swallowed the failure nor aborted the run on the caller's behalf
   — §18's conversation-by-conversation rule stays the caller's to honour, and the record does not
   change it.
5. **Given** an operation has been given its context, **When** any further line is emitted while
   that operation is in progress, **Then** that line carries the same context fields without the
   caller passing them again.
6. **Given** a component that is not part of an ingestion operation, **When** it emits a line,
   **Then** the line is still structured and still carries the shared fields that apply to it,
   without inventing empty values for fields that do not.

---

### User Story 2 - A credential or a conversation body cannot reach the log (Priority: P1)

A contributor debugging a failing import logs the request that failed, the settings it was built
from, and the conversation it was working on. None of the log lines carries the token, the
authorization header, or the text of the conversation. Nobody had to remember to redact anything at
the call site.

**Why this priority**: equal in importance to Story 1 and independently testable. Principle V is
categorical — conversation contents are not logged by default, credentials and tokens never — and
the corpus is years of private engineering history where a leaked token is a live credential. The
protection has to live in the pipeline, because the call sites that could leak it have not been
written yet.

**Independent Test**: emit an event carrying a credential-shaped value and a conversation body,
capture the output, and assert that neither literal appears anywhere in it.

**Acceptance Scenarios**:

1. **Given** an event whose fields include a credential under a name that identifies it as one,
   **When** the event is emitted, **Then** the value does not appear in the output and a marker
   records that something was redacted there.
2. **Given** an event carrying a value held in the project's secret type, **When** the event is
   emitted, **Then** its value does not appear regardless of the field name it was given.
3. **Given** an event carrying an unmistakably credential-shaped value under an innocuous field
   name, **When** the event is emitted, **Then** the value does not appear.
4. **Given** an event carrying a conversation body, **When** the event is emitted with the project
   at its default configuration, **Then** the body does not appear.
5. **Given** a nested structure — a mapping inside a list inside a mapping — with a credential at
   the bottom of it, **When** the event is emitted, **Then** the credential does not appear.
6. **Given** an exception that carries a credential in its message or its arguments, **When** it is
   logged, **Then** the credential does not appear in the rendered traceback or message.
7. **Given** any emitted record, **When** it is inspected, **Then** the redaction is visible as a
   marker rather than as a silently missing field, so a reader can tell redaction from absence.

---

### User Story 3 - Conversation content can be turned on deliberately, for one debugging session (Priority: P2)

Someone chasing a parser defect needs to see the conversation the parser choked on. They set one
explicit flag, run the import again, and the content is there. Nothing else in the project changes,
the flag is off again the moment they stop setting it, and credentials stay redacted regardless.

**Why this priority**: valuable but derivative — Stories 1 and 2 already deliver a usable, safe
log. This one keeps the safe default from being worked around by a contributor commenting out the
redactor, which is what happens when the escape hatch does not exist.

**Independent Test**: emit a conversation body with the flag unset and observe it absent; set the
flag, emit the same body, and observe it present.

**Acceptance Scenarios**:

1. **Given** the explicit content flag is not set, **When** a conversation body is logged, **Then**
   it is absent from the output — this is the default with no configuration at all.
2. **Given** the explicit content flag is set, **When** a conversation body is logged, **Then** it
   appears in the output.
3. **Given** the explicit content flag is set, **When** an event carrying a credential is logged,
   **Then** the credential is still redacted — the flag governs conversation content only and can
   never expose a credential.
4. **Given** the project's committed configuration example, **When** it is inspected, **Then** the
   flag is documented as off, with its consequence stated.

---

### User Story 4 - A later span has somewhere to attach (Priority: P2)

The feature that calls `retain` wants to time it and record its outcome as a span. It finds a
tracer already configured, asks for a span, and the log lines emitted inside that span can be
correlated with it. Nothing had to be bootstrapped first, and an operator who has no trace
collector running is not forced to run one.

**Why this priority**: the issue asks for the attachment point rather than for tracing coverage.
It is genuinely useful only once something is traced, so it ranks below the logging guarantees —
but establishing it now is what keeps the next feature from inventing its own.

**Independent Test**: request a span from the configured tracer, emit a log line inside it, and
assert the line carries identifiers that tie it to that span.

**Acceptance Scenarios**:

1. **Given** the project at its default configuration, **When** the observability baseline is
   initialised, **Then** a tracer is available to every component and requesting a span from it
   succeeds.
2. **Given** no trace collector is configured, **When** a span is started and ended, **Then**
   nothing is exported, nothing fails, and no connection is attempted.
3. **Given** a log line emitted while a span is active, **When** the record is inspected, **Then**
   it carries the identifiers that tie it to that span, so logs and traces can be correlated.
4. **Given** a log line emitted while no span is active, **When** the record is inspected, **Then**
   it is emitted normally, without correlation identifiers and without error.

---

### Edge Cases

- A component emits a line before the baseline has been initialised — the line must still be
  structured and still redacted, because an unconfigured default that leaks is the failure this
  feature exists to prevent.
- The baseline is initialised twice, in the same process — the second call must not duplicate
  output or stack a second copy of the pipeline.
- A field value cannot be rendered as structured data at all — a custom object, a cyclic structure
  — the line must be emitted with a fallback rendering rather than the logging call raising into
  the caller.
- The redactor itself fails on a malformed value — the record must fail closed, withholding the
  value, never emitting it because inspection errored.
- A credential appears as a substring of a longer string, such as inside a URL with credentials in
  it or an authorization header rendered into prose.
- A field carries an extremely large conversation body — the record must not become unbounded
  output when content logging is deliberately enabled.
- Two operations are in progress on the same thread in sequence — the context of the first must not
  leak into the records of the second.
- The output stream is not a terminal, or is a terminal — the machine-readable format is the one
  the guarantees are stated over and must not silently change with the destination.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The project MUST expose a single logging surface that every component uses; no
  component may configure its own logging output or write log lines directly to a stream.
- **FR-002**: Every emitted record MUST be machine-readable structured data with named fields, not
  a formatted human sentence.
- **FR-003**: The project MUST define the ingestion operation record of §18 as a fixed field set —
  source, source id, project, bank, document id, start time, duration, status, error — and MUST
  emit exactly one such record per ingestion operation.
- **FR-004**: The status field MUST be constrained to the outcomes §18 defines: imported, skipped,
  failed.
- **FR-005**: The duration MUST be measured by the logging surface rather than supplied by the
  caller, so that it cannot be forgotten or misreported.
- **FR-006**: An operation that ends in an error MUST still produce its record, with status failed
  and the error recorded, and MUST let that error continue to propagate to the caller unchanged.
- **FR-007**: Context bound once for an operation MUST appear on every record emitted during that
  operation without being passed again, and MUST NOT outlive the operation it was bound for.
- **FR-008**: A redaction step MUST run inside the logging pipeline, on every record, after the
  caller has assembled it and before it is rendered — never as a discipline at the call site.
- **FR-009**: The redaction step MUST withhold the value of any field whose name identifies it as a
  credential, token, secret, password or authorization header, matched case-insensitively against a
  documented roster.
- **FR-010**: The redaction step MUST withhold the value of any field held in the project's secret
  type, whatever the field is named.
- **FR-011**: The redaction step MUST withhold values matching a documented roster of unmistakable
  credential shapes, whatever the field is named, as the last line of defence for values that reach
  a log under an innocuous name.
- **FR-012**: The redaction step MUST descend into nested mappings and sequences to a documented
  depth, and MUST withhold the value at a depth it declines to descend past rather than emitting it
  unexamined.
- **FR-013**: A withheld value MUST be replaced by a marker that preserves the field, so that a
  reader can distinguish a redacted field from an absent one.
- **FR-014**: Conversation content MUST NOT be emitted unless an explicit configuration flag is
  set; the flag MUST default to off, and absent configuration MUST behave as off.
- **FR-015**: The content flag MUST NOT affect credential redaction: with it set, FR-009 through
  FR-013 still hold.
- **FR-016**: Exception information rendered into a record — message, arguments, traceback — MUST
  pass through the same redaction as any other field.
- **FR-017**: A record whose value cannot be inspected or rendered MUST fail closed: the value is
  withheld, the record is still emitted, and the logging call does not raise into the caller.
- **FR-018**: The project MUST expose a tracer that any component can request a span from,
  initialised as part of the same observability baseline.
- **FR-019**: With no trace collector configured, starting and ending a span MUST succeed, export
  nothing, and attempt no network connection.
- **FR-020**: A record emitted while a span is active MUST carry the identifiers that correlate it
  with that span; one emitted with no span active MUST be emitted normally without them.
- **FR-021**: All configuration this feature reads — output level, the content flag, any trace
  destination — MUST come through the project's existing settings object, and this feature MUST NOT
  read the environment itself.
- **FR-022**: Every setting this feature adds MUST appear in the committed example environment
  file, which the existing automated check compares against the declared settings.
- **FR-023**: Initialising the baseline MUST be idempotent: a second initialisation in the same
  process MUST NOT duplicate output or stack a second pipeline.
- **FR-024**: A record emitted before the baseline is initialised MUST still be structured and
  still be redacted.
- **FR-025**: This feature MUST NOT parse, normalize, sanitize, archive or retain anything; it
  provides the record and the tracer that those features will use.

### Key Entities

- **Logging surface**: the single entry point a component obtains to emit records, already wired to
  the pipeline the guarantees live in.
- **Record**: one structured event — named fields and their values — as emitted after redaction and
  rendering.
- **Operation context**: the §18 field set bound once for the duration of one ingestion operation
  and carried by every record emitted within it.
- **Redaction step**: the stage of the pipeline that withholds credentials and, by default,
  conversation content, and marks where it did so.
- **Sensitive-name roster**: the documented set of field names whose values are always withheld.
- **Credential-shape roster**: the documented set of value shapes that are withheld whatever the
  field name.
- **Content flag**: the explicit, default-off setting that permits conversation bodies in records.
- **Tracer**: the object a later feature requests a span from, and the source of the identifiers
  that correlate records with spans.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the fields §18 names are present on an ingestion operation record, asserted
  against the field set rather than against a sample of it.
- **SC-002**: A record carrying a credential-shaped value and a conversation body yields zero
  occurrences of either literal in the captured output.
- **SC-003**: For each name on the sensitive-name roster, a record carrying a value under that name
  yields zero occurrences of the value — every name, not a sample.
- **SC-004**: With the content flag unset — including with no configuration present at all —
  conversation bodies appear in zero records.
- **SC-005**: With the content flag set, conversation bodies appear and credentials still appear in
  zero records.
- **SC-006**: 100% of emitted records parse as structured data; zero records are emitted as
  unparseable prose.
- **SC-007**: An ingestion operation that raises produces exactly one record, with status failed,
  and the error reaches the caller — verified by a test that asserts both.
- **SC-008**: Starting and ending a span with no collector configured performs zero network calls.
- **SC-009**: 100% of the settings this feature adds appear in the committed example environment
  file, enforced by the check that already exists.
- **SC-010**: Zero components outside the logging surface configure logging output or write log
  lines directly, verified against the committed tree.

## Assumptions

- The technology is not an open question. The constitution's Technology Stack section fixes
  structlog for logging and OpenTelemetry for telemetry, and the issue names both; this
  specification states outcomes so the checks stay verifiable, and the plan states how they are met.
  No decision record is implied.
- Records go to the process's standard error stream in the machine-readable format, in every
  environment, because that is the destination the guarantees above are stated over. A
  human-friendly rendering for interactive use is a later convenience, not part of this baseline.
- The credential-shape roster is a small, documented set of unmistakable shapes — a bearer
  authorization header, a JSON web token, a conventionally prefixed API key — and is deliberately
  not a general secret scanner. Scanning conversation content for secrets is ARCHITECTURE.md §13's
  sanitizer, which is separate work; the roster here is the last line of defence for a log line,
  not a substitute for it.
- The content flag governs fields the caller marks as conversation content. Fields a caller invents
  and does not mark are covered by the name and shape rosters like any other field; the flag is not
  a promise that arbitrary unmarked prose is inspected for conversation text.
- Nothing is exported. The MVP runs on a developer's machine, and requiring a collector in order
  to run an import would be a cost with no return. What this feature owns is the single place the
  tracer is constructed, which is where the feature that has something to export attaches an
  exporter; choosing that exporter against a real collector is that feature's decision, not one to
  pre-empt with a setting nothing exercises.
- Metrics are out of scope. §18 requires logs per operation and this feature adds the tracer the
  issue asks for; a metrics pipeline is neither required by §18 nor useful before something is
  measured.
- Tracing any particular operation is out of scope, including the span around `retain` this
  baseline exists to make possible. That span belongs to the feature that makes the call.
- The ingestion pipeline does not exist yet, so the operation record is exercised against a
  synthesized operation in tests rather than against a real import. The record's shape is fixed
  here; its first real caller arrives with the pipeline.
- This feature adds runtime dependencies. The skeleton's guard test over runtime dependencies
  exists to make that deliberate, and this feature changes it on purpose, in the same commit, for
  entries the stack table already fixes.
- The `observability` module in the constitution's module tree is where this lives. It already
  exists as an empty package; no module is added and no amendment is implied.
