# Feature Specification: Boundary interfaces and their contract tests

**Feature Branch**: `007-boundary-interfaces`

**Created**: 2026-09-16

**Status**: Draft

**Input**: Issue #9 — "Define the boundary interfaces and their contract tests"

## User Scenarios & Testing *(mandatory)*

This feature delivers contracts and the tests that hold them, not behaviour a user can observe. Its
users are the authors of the six implementations that follow — #10 the ChatGPT source, #11 the
sanitizer, #12 the classifier, #13 the raw archive, #14 the import state, #16 the Hindsight memory
store — the author of the pipeline (#19) who composes them, and the reviewer whom the
constitution's merge gate obliges to reject a Hindsight reference outside the memory store.

Every story is testable with no export file, no network, no database and no Hindsight instance in
reach: a contract is proved by running it against a fake.

### User Story 1 - Six implementations are written against a declared interface, not against each other (Priority: P1)

Six issues are unblocked by this one, and they will be worked in some order, possibly at the same
time. Each author needs to know exactly what their boundary is handed, what it must return, and
what it is permitted to raise — before anyone has written the first of them. Without that, the
second implementation is written against the shape the first happened to take, and §8's promise
that any single part can be replaced without disturbing the rest is spent before it is tested.

**Why this priority**: It is the whole of the issue's proposal, and the reason ARCHITECTURE.md §8
and Principle IV exist at all. ADR-001's exit strategy — replace Hindsight without re-exporting
anything — is a claim about interfaces, and until the interfaces exist the claim is untested.

**Independent Test**: Write a trivial second implementation of any one boundary against the
declared interface alone, without reading the first one, and have it pass that boundary's contract
suite.

**Acceptance Scenarios**:

1. **Given** the six declared interfaces, **When** an implementation author reads one, **Then** the
   method signatures, what each method returns, and the failures it may raise are stated there,
   and none of them is expressed as a dictionary or a free-form string where the normalized model
   already has a type.
2. **Given** the memory store interface, **When** its declaration is read, **Then** no name in it —
   method, parameter, return type or error — is a Hindsight term, so that the module depending on it
   cannot acquire a Hindsight concept by using it.
3. **Given** any boundary interface, **When** an implementation is substituted for another,
   **Then** no calling code changes, because callers depend on the interface and never on a
   concrete type.

---

### User Story 2 - An implementation is proved by a suite it did not write (Priority: P1)

An implementation that ships with only its own tests is tested against its author's understanding
of the boundary. The contract suite inverts that: the suite belongs to the boundary, the
implementation supplies itself to it, and passing is what "implements this boundary" means.

**Why this priority**: Principle III requires contract tests for every boundary of §8 before a
stage is considered done, and a suite written per implementation cannot be that — it would pass
for six mutually incompatible implementations. It is also what makes the second implementation of a
boundary cheap, which is what replaceability actually costs.

**Independent Test**: Point one boundary's contract suite at its in-memory fake and run it; then
point the same suite at a deliberately broken fake — one that loses a field on store, or reports a
redaction it did not make — and observe the suite fail on exactly that.

**Acceptance Scenarios**:

1. **Given** a contract suite for a boundary, **When** it is pointed at any implementation of that
   boundary, **Then** it runs unchanged, with nothing implementation-specific in it — no file path,
   no URL, no table name, no fixture only one implementation can supply.
2. **Given** an implementation that violates a rule of its boundary, **When** the contract suite is
   run against it, **Then** the suite fails and names the rule that was broken.
3. **Given** the six contract suites, **When** the six in-memory fakes are run against them,
   **Then** all six pass, which is the first proof each interface is implementable by something
   other than the eventual real thing.

---

### User Story 3 - The pipeline is assembled and run before any of its parts exists (Priority: P1)

§7's pipeline — parse, normalize, sanitize, classify, enrich, archive, retain — is composed in #19,
and every stage it composes is unwritten. Assembled from fakes, it must nonetheless run a
conversation end to end: sanitized, classified, enriched, archived, retained, recorded in the
import state, and skipped on a second run because its content hash has not moved.

**Why this priority**: It is the issue's own statement of how we would know it works, and it is the
cheapest possible discovery that two boundaries do not fit together — before either is real. It
ranks with the others at P1 because an interface that composes badly is not discovered by reading
interfaces one at a time.

**Independent Test**: Run a pipeline built entirely from fakes over a synthesized conversation,
with the network and the filesystem unavailable to it, and assert the outcome of each stage.

**Acceptance Scenarios**:

1. **Given** a pipeline assembled from the six fakes, **When** one synthesized conversation is
   imported, **Then** it is archived and retained, and the import state holds its source id,
   content hash and document id.
2. **Given** that same pipeline and the same conversation, **When** the import is run a second
   time, **Then** the conversation is skipped before the memory store is called, and the store
   records no second call (Principle II — extraction is not paid for twice).
3. **Given** that pipeline, **When** the run completes, **Then** no network call and no filesystem
   write has occurred, asserted rather than assumed.
4. **Given** a conversation whose content changed since the last run, **When** it is imported again,
   **Then** it is not skipped, and it reaches the memory store under the same document id.

---

### User Story 4 - One conversation fails and the run continues (Priority: P2)

§18 requires import to proceed conversation by conversation, with one failure unable to abort the
run, and transient failures retried while permanent ones are not. That distinction has to be
expressed at the boundary: a caller that cannot tell a timeout from a rejected request either
retries what will never succeed, or abandons what would have worked on the second attempt.

**Why this priority**: Nothing retries yet — #20 builds that — but the retry policy can only read a
distinction the interfaces already draw. Defining it after the implementations exist means reading
it back out of whichever exceptions the first HTTP client happened to raise, which is precisely the
inversion Principle IV forbids.

**Independent Test**: Have a fake fail transiently for one conversation and permanently for
another, and observe that the run classifies each, continues past both, and reports them as
failures with their source ids.

**Acceptance Scenarios**:

1. **Given** a boundary implementation whose backend fails, **When** the failure surfaces to the
   caller, **Then** it arrives as an error the interface declares, not as an exception belonging to
   the backend's library, so that the caller need not import that library to handle it.
2. **Given** a failure, **When** the caller inspects it, **Then** it can tell whether retrying the
   same call could succeed, without matching on a message string or a status code.
3. **Given** a run over several conversations where one fails, **When** the run finishes, **Then**
   the others were imported and the failure is reported with its source id, its error and its time.

---

### User Story 5 - The memory engine is replaced without touching ingestion (Priority: P2)

ADR-001 accepts a deliberate dependency on Hindsight and pays for it with an exit: the raw archive
and the normalized model are independent of it, so the backend can be replaced. The interface is
where that is either true or merely asserted.

**Why this priority**: Exercising it costs one extra fake and proves the constitution's most
expensive claim. It ranks below P1 because nothing breaks today if it is wrong — the bill arrives
years later, which is exactly why the issue asks for it now.

**Independent Test**: Swap the memory store fake for a second, differently-shaped one, and run the
pipeline tests again with no change to any code outside the line that chooses the store.

**Acceptance Scenarios**:

1. **Given** the memory store interface, **When** a second implementation replaces the first,
   **Then** only the composition point changes and no pipeline, archive, sanitizer, classifier or
   import-state code is edited.
2. **Given** every module this feature adds except the memory store's own implementation module,
   **When** its transitive import graph is inspected, **Then** it reaches neither Hindsight, nor an
   HTTP client, nor any storage library.

---

### Edge Cases

- **A source yields nothing.** An export with no conversations is valid — the run imports zero and
  reports zero, rather than treating emptiness as an error.
- **A source cannot read one conversation.** One malformed conversation inside an otherwise good
  export must not end the iteration; the caller learns which one failed and keeps going (§18).
- **The sanitizer finds nothing to redact.** It returns the conversation and an empty report. An
  empty report and a missing report are not the same thing.
- **The sanitizer's report.** It says what category was redacted and how many times, never the
  value that was redacted — a report carrying the secret defeats Principle V while claiming to
  serve it.
- **The classifier cannot determine a project.** `project:unknown` is an ordinary answer (§15), not
  a failure and not an absent value; a substantial share of ChatGPT conversations will take it.
- **The archive is asked for a document it does not hold.** A declared not-found, distinguishable
  from a storage failure — the first is an ordinary answer during a resume, the second is a defect.
- **The archive is asked to store the same document twice.** Storing again is safe and leaves one
  document, because a re-run after a crash must not multiply the source of truth (Principle I).
- **A conversation too large to retain in one call.** §9 leaves that to the memory store, which may
  deliver one logical document as several parts. The interface must neither require nor forbid it,
  and callers must not be able to observe which happened.
- **`recall` finds nothing.** An empty result, not an error.
- **The import state is asked about a conversation it has never seen.** The answer is "not seen",
  which is the state of every conversation on the first run.
- **An import fails after the archive write but before the memory store call.** The next run must be
  able to tell that the conversation is not imported, so the import state records an outcome rather
  than only successes (§17, §18).
- **Two runs at once over the same import state.** Out of scope for the MVP: the importer is a
  single local command. The interfaces must not, however, promise single-writer semantics that a
  future store would have to break.

## Requirements *(mandatory)*

### Functional Requirements

**The six interfaces**

- **FR-001**: The feature MUST declare exactly one interface for each boundary of §8 —
  conversation source, secret sanitizer, project classifier, raw archive, memory store, import
  state — each with a single responsibility, and MUST NOT merge two of them into one interface or
  split one across two.
- **FR-002**: Every interface MUST be expressed in the vocabulary of the normalized conversation
  model (#8): what crosses a boundary is a conversation, an enriched conversation, provenance, a
  tag or a document id, never a dictionary, a source-specific structure or a free-form string
  standing in for one of those.
- **FR-003**: The conversation source interface MUST yield normalized conversations one at a time,
  so that a caller can process, and can fail on, one conversation without holding the export in
  memory or abandoning the rest of it.
- **FR-004**: The secret sanitizer interface MUST return the rewritten conversation together with a
  report of what was redacted, stated as categories and counts. The report MUST NOT carry the
  redacted values (Principle V), and an empty report MUST be distinguishable from no report.
- **FR-005**: The project classifier interface MUST return the project as the typed project value
  of §6, and MUST return the `unknown` project rather than raising or returning nothing when no
  rule matches (§15).
- **FR-006**: The raw archive interface MUST accept an enriched conversation for storage and MUST
  return one for a document id, so that ingestion is re-runnable from the archive alone
  (Principle I). Storing the same document twice MUST leave one document.
- **FR-007**: The raw archive interface MUST distinguish "this document is not held" from "the
  archive failed", so that a resume can tell an ordinary gap from a defect.
- **FR-008**: The memory store interface MUST offer retain and recall and nothing else, MUST accept
  an enriched conversation for retain, and MUST accept a query with tags for recall, returning
  results carrying at least their content and the provenance the item was retained with.
- **FR-009**: No name in the memory store interface — method, parameter, return type, error or
  documented term — may be a Hindsight term: no bank, retain mission, item, update mode, operation
  id or endpoint. Retain and recall are the architecture's words (§16) and are kept.
- **FR-010**: Retaining the same enriched conversation twice MUST be declared safe at the
  interface: the caller is promised no duplicate document, without being told how the implementation
  achieves it (§9, Principle II).
- **FR-011**: The import state interface MUST answer whether a conversation, identified by its
  source id and content hash, has already been imported, and MUST record the outcome of an import —
  source id, content hash, document id, time and status — including failures (§17, §18).
- **FR-012**: The import state interface MUST make the skip decision answerable without contacting
  any other boundary, because the point of the skip is to avoid paying for extraction (§17).

**Error semantics**

- **FR-013**: Every interface MUST declare which failures it raises, and those errors MUST be
  defined by this feature rather than borrowed from a backend: no caller may have to catch an
  exception belonging to an HTTP client, a database driver or a filesystem to handle a boundary
  failure (Principle IV).
- **FR-014**: Every declared error MUST state whether retrying the identical call could succeed, as
  a property a caller can read rather than a message or a status code it must parse (§18). Values
  §18 names as never retryable — a rejected or unauthorized request, invalid input — MUST NOT be
  expressible as retryable.
- **FR-015**: Every declared error MUST carry enough to satisfy §18's failure report: which
  conversation it concerned, where it happened, and what went wrong.
- **FR-016**: Interface errors MUST NOT carry conversation content, credentials, tokens or
  authorization headers, so that reporting or logging a failure cannot leak what §19 and Principle V
  protect.
- **FR-017**: No interface may declare a failure for a condition the architecture defines as an
  ordinary answer: an unknown project, an empty recall, an unseen conversation and an empty export
  are results, not errors.

**Contract suites and fakes**

- **FR-018**: Each of the six boundaries MUST have a reusable contract suite that any implementation
  can be run against by supplying itself, and that contains nothing specific to one implementation.
- **FR-019**: Each contract suite MUST assert the rules its boundary's requirements state above,
  including the failure semantics, so that "passes the contract suite" means "implements the
  boundary" and not "does not crash".
- **FR-020**: Each contract suite MUST be shown to fail against a deliberately broken implementation
  of its own boundary, so that a suite which asserts nothing cannot pass unnoticed.
- **FR-021**: The feature MUST provide one in-memory fake per boundary, each passing its contract
  suite, performing no input or output, and available to the tests of #10 through #19 rather than
  re-invented by each of them.
- **FR-022**: The fakes MUST be observable enough for a pipeline test to assert what happened — what
  was stored, what was retained, what was skipped, how many times each was called — without that
  observability appearing in the interfaces themselves.
- **FR-023**: A pipeline assembled entirely from the fakes MUST run a conversation end to end, and
  a test MUST assert that the run performed no network call and no filesystem write.
- **FR-024**: The pipeline assembled from fakes MUST demonstrate the §17 skip: a second run over
  unchanged content reaches neither the memory store nor the archive, and a run over changed content
  does, under the same document id.

**Placement and dependencies**

- **FR-025**: The interfaces MUST live where every implementing module can depend on them without
  depending on each other, and the memory store interface MUST sit in the module the constitution
  names for it, separate from any Hindsight implementation.
- **FR-026**: No interface module may import Hindsight, an HTTP client or a storage library,
  directly or transitively, and a test MUST assert this over the import graph (Principle IV, §8).
- **FR-027**: This feature MUST NOT implement any boundary for real: no export is parsed, no secret
  pattern is written, no alias rule is matched, no file is stored, no database is opened and no
  Hindsight call is made. Those are #10 through #16.

### Non-Functional Requirements

- **NFR-001**: Every interface MUST be documented in English, citing the architecture section each
  rule comes from, so that a later reader changing a signature sees what it was holding up.
- **NFR-002**: Every rule in this specification that a test can assert MUST have one, written before
  the implementation and observed to fail first (Principle III).
- **NFR-003**: Running the full suite this feature adds MUST require no network, no Hindsight, no
  database and no fixture file, so that it is the suite an implementation author runs continuously.

### Key Entities

- **Boundary interface**: the declaration of one of §8's six responsibilities — its methods, what
  they accept and return in the normalized model's vocabulary, and the failures they may raise.
- **Conversation source**: reads one source format and yields normalized conversations.
- **Secret sanitizer**: rewrites a conversation with secrets redacted and reports what it redacted.
- **Redaction report**: what the sanitizer redacted, by category and count, never the values.
- **Project classifier**: determines the project for a conversation, `unknown` included.
- **Raw archive**: persists enriched conversations and returns them by document id.
- **Memory store**: retains an enriched conversation and recalls against a query and tags. The only
  boundary whose implementation may know Hindsight.
- **Recall result**: what a recall returns for one match — its content and the provenance it was
  retained with — expressed without naming the engine that produced it.
- **Import state**: remembers what has been imported and answers whether a conversation may be
  skipped.
- **Import record**: the §17 entry — source id, content hash, document id, time and status.
- **Boundary error**: a failure declared by an interface, carrying whether a retry could succeed and
  what §18 needs to report it.
- **Contract suite**: the reusable tests that define what implementing a boundary means.
- **In-memory fake**: an implementation of a boundary that performs no input or output, passes its
  contract suite, and is what the pipeline tests run against.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All six boundaries of §8 have a declared interface, and a reviewer can point at each
  one and at the §8 row it implements.
- **SC-002**: All six boundaries have a contract suite, and the six in-memory fakes pass all six.
- **SC-003**: For each of the six suites, a deliberately broken implementation of that boundary
  fails it, and the failure names the rule that was broken.
- **SC-004**: A pipeline assembled entirely from fakes imports a conversation end to end, and the
  test asserts that no network call and no filesystem write occurred.
- **SC-005**: A second run of that pipeline over unchanged content calls neither the archive nor the
  memory store, and a run over changed content calls both under the same document id.
- **SC-006**: Replacing the memory store fake with a second, differently-implemented one requires
  changing only the line that chooses it, and the pipeline tests pass unchanged.
- **SC-007**: No public name in any interface is a Hindsight term, and the transitive import graph
  of every module this feature adds contains no Hindsight module, no HTTP client and no storage
  library — both asserted by tests that fail when violated.
- **SC-008**: Every failure any interface declares answers "could a retry succeed?" without the
  caller parsing a message or a status code, and no error declared for §18's never-retryable
  conditions can answer yes.
- **SC-009**: The suite this feature adds runs with no network, no Hindsight, no database and no
  fixture file, and its runtime keeps it usable as the suite run on every change.
- **SC-010**: The committed change adds no production behaviour: no export parsing, no redaction
  pattern, no alias rule, no storage, no Hindsight call.

## Assumptions

- **The normalized model is settled and is not reopened here.** #8 delivered the conversation,
  message, tool activity, provenance, enriched conversation, tags, canonical form and content hash.
  This feature consumes them. Where a boundary needs a type the model deliberately does not define —
  the sanitizer's report (§8), the import record (§17), a recall result (§16) — the boundary owns
  it, which SC-001 of #8 explicitly permits.
- **Where the interfaces live is a plan decision**, constrained by the constitution's fixed module
  layout: the memory store interface belongs in `memory/interface`, which the constitution names as
  what every other module depends on. Placing the other five, and in particular the import state,
  which the layout does not name a module for, is settled in `plan.md` with its reasoning, because
  a top-level module the constitution does not list would be a deviation requiring justification.
- **Protocols, not base classes, unless the plan argues otherwise.** ADR-004 chose a stack where
  contract validation sits at the boundaries rather than in a compiler, and structural typing lets
  an implementation satisfy a boundary without inheriting from it. The mechanism is settled in
  `plan.md`.
- **Synchronous interfaces.** The MVP is a local Typer command importing conversation by
  conversation; nothing in Phase 1 needs concurrency, and an asynchronous interface adopted without
  a caller that needs it is a shape invented wrongly. Should throughput later require it, that is a
  change to the interfaces with its own specification.
- **Retry belongs to #20, not here.** This feature declares the distinction a retry policy reads —
  whether a failure is worth repeating — and implements no backoff, no jitter and no policy.
- **The pipeline itself belongs to #19.** What this feature assembles from fakes is a test harness
  proving the interfaces compose, not the production pipeline.
- **`recall` is the only retrieval this feature declares.** §16's `reflect` is used by #31 against
  accumulated memory and is not part of the MVP ingestion path; adding it to the interface now would
  be declaring a method with no caller.
- **The MVP's stores are single-writer.** No interface promises transactional or concurrent
  semantics, and none forbids an implementation that provides them.
- **Fixtures are synthesized.** No real history reaches a test (CLAUDE.md), and the fakes need none.
- **#8 is closed and merged**, so the vocabulary these interfaces are written in exists on `main`.

## Dependencies

- Depends on #8 (normalized conversation model, closed and merged).
- Blocks #10 (ChatGPT source), #11 (sanitizer), #12 (classifier), #13 (raw archive), #14 (import
  state) and #16 (Hindsight memory store), and through them #19 (pipeline) and #20 (retry).
