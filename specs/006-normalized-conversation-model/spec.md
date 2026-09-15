# Feature Specification: Normalized conversation model

**Feature Branch**: `006-normalized-conversation-model`

**Created**: 2026-09-14

**Status**: Draft

**Input**: Issue #8 — "Define the normalized conversation model"

## User Scenarios & Testing *(mandatory)*

This feature delivers a vocabulary, not behaviour. Its users are the authors of the stages and
boundaries that must speak it — the parser, the sanitizer, the classifier, the archive, the memory
store and the import state — and the reviewer who must be able to reject a change that leaks
Hindsight into the domain. Each story is testable by writing code against the model alone, with no
source export, no network and no storage in reach.

### User Story 1 - The boundary author declares six interfaces in one vocabulary (Priority: P1)

Issue #9 declares the six boundaries of §8 as interfaces with their signatures and error semantics.
Every one of them takes or returns a conversation: the source yields them, the sanitizer rewrites
them, the classifier reads them, the archive persists them, the memory store sends them and the
import state remembers them. Without the model, each signature would invent its own shape, and the
first implementation written against one of them would fix that shape by accident.

**Why this priority**: This is the reason the issue is in wave 2 rather than later. Six issues
depend on #9 and #9 depends on this; a shape settled here is settled once, and a shape settled by
the first parser is settled in the wrong place and against Principle IV.

**Independent Test**: Write the six signatures against the model, in a scratch module, using only
the entities this feature defines. No boundary needs a type it has to invent, and none needs a
dictionary or a free-form string to carry something the architecture requires.

**Acceptance Scenarios**:

1. **Given** the model, **When** a conversation source's signature is written, **Then** its return
   type is the normalized conversation and nothing source-specific appears in it.
2. **Given** the model, **When** the memory store's signature is written, **Then** what it accepts
   is the conversation with its provenance and tags, and none of its parameters names a Hindsight
   concept.
3. **Given** the model, **When** the import state's signature is written, **Then** the key it stores
   is the source id and the content hash the model itself computes, not a hash the caller invents.

---

### User Story 2 - The importer skips an unchanged conversation without paying for it (Priority: P1)

A second import runs over a fresh export (ADR-006). For every conversation already imported, the
importer must decide — before any call is made — whether anything changed. That decision is a
comparison of the content hash this model produces, and it is only sound if the hash is
deterministic across processes and runs, and if it covers exactly what ADR-006 decision 4 says it
covers.

**Why this priority**: Principle II forbids paying for extraction twice, and the whole skip rests on
this one value. A hash that varies between runs turns every refresh into a full re-extraction; a
hash that covers the title turns a rename into one.

**Independent Test**: Build two structurally identical conversations in two separate processes and
compare their hashes. Change a message, then change only the title, and observe which hash moves.

**Acceptance Scenarios**:

1. **Given** two conversations with identical messages, order and message timestamps, **When** their
   content hashes are computed in separate processes, **Then** the two values are equal.
2. **Given** a conversation, **When** any message's text, role, order or timestamp changes, **Then**
   the content hash changes.
3. **Given** a conversation, **When** only its title changes, **Then** the content hash is unchanged.
4. **Given** a conversation, **When** its `document_id` is derived, **Then** it is
   `<source>:<native id>` and the same conversation yields the same value on every run.

---

### User Story 3 - The archive round-trips a conversation years later (Priority: P2)

Principle I makes the raw archive the source of truth and requires ingestion to be re-runnable from
it alone. The normalized form persisted there must therefore come back out as exactly what went in
— after the parser, the sanitizer, the extraction policy or Hindsight itself has changed.

**Why this priority**: The archive is written in #13, so nothing breaks today if this is wrong.
But a lossy serialization is discovered only when a replay is attempted, by which time the archive
holding years of history is already the lossy one.

**Independent Test**: Serialize a conversation exercising every field — tool activity, a message
with no timestamp, an empty title — re-parse it, and compare against the original.

**Acceptance Scenarios**:

1. **Given** a conversation using every field the model defines, **When** it is serialized and
   re-parsed, **Then** the result equals the original and its content hash is unchanged.
2. **Given** a serialized conversation, **When** a field the model requires is missing or malformed,
   **Then** re-parsing fails with an error naming the field, rather than yielding a partial object.

---

### User Story 4 - The reviewer rejects a Hindsight leak by pointing at a test (Priority: P2)

Principle IV confines Hindsight to `memory/hindsight`, and the constitution's merge gate obliges a
reviewer to reject a Hindsight reference outside the memory store. The reviewer needs a failing
test, not an argument.

**Why this priority**: The boundary is cheap to hold now and expensive to restore once three
modules import through it. It ranks below P1 only because violating it breaks no behaviour on the
day it happens.

**Independent Test**: Add an import of `memory/hindsight` — or of an HTTP or storage library — to
the normalization module and observe the suite fail.

**Acceptance Scenarios**:

1. **Given** the normalization module, **When** its transitive import graph is inspected, **Then**
   it reaches neither `memory/hindsight`, nor an HTTP client, nor any storage library.
2. **Given** the model's public names, **When** they are read, **Then** none of them is a Hindsight
   term — no bank, retain, recall, item or update mode.

---

### Edge Cases

- **A message with no timestamp.** ChatGPT exports omit the time on some messages. The message must
  remain representable, must keep its position, and the canonical form must render the absence
  identically on every run rather than substituting the import time (§11) or the current clock.
- **Two messages with the same timestamp.** Order is the message's position in the conversation,
  never a sort by time; the canonical form must preserve that position.
- **A naive timestamp.** A time without an offset is ambiguous, and an ambiguous time in the
  canonical form is a hash that depends on where it ran. It is rejected at construction.
- **A conversation with no messages.** Representable — an export can carry one — and its hash is
  defined rather than an error, so the importer can skip it like any other.
- **A conversation whose title is absent or empty.** Titles are outside the hash (ADR-006), so both
  must be representable and must hash identically to each other.
- **A message carrying non-text content** — an image, an attachment, a rendered chart. The MVP
  extracts text, but a message must be able to record that non-text parts existed, so that a replay
  from the archive is not silently missing something nobody knows was there.
- **Tool activity without a result** — a call that errored or was never completed. Representable;
  the absence is not an error.
- **A source id containing a colon.** `document_id` is `<source>:<native id>` (§10); the derivation
  must stay unambiguous and must not depend on splitting the result back apart.
- **A project that could not be determined.** `project:unknown` (§15) is an ordinary value of the
  project tag, not a missing one.
- **A conversation large enough to exceed a single retain request.** That is a §9 concern belonging
  to the memory store; nothing in the model may carve out a case for it.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The normalization module MUST define a normalized conversation carrying its source,
  the source's native identifier, an optional title, the conversation's real timestamps, and its
  messages in order.
- **FR-002**: The model MUST define a message carrying its role, its content, its time when the
  source provides one, and any tool activity the source carries.
- **FR-003**: Message order MUST be explicit and preserved as the sequence given at construction.
  Ordering MUST NOT be derived from timestamps, which may be absent or equal.
- **FR-004**: The source MUST be a closed vocabulary matching §6 and §10 — `chatgpt`,
  `claude-chat`, `claude-code`, `codex`, `hermes` — and a value outside it MUST be rejected rather
  than carried as a string.
- **FR-005**: The message role MUST be a closed vocabulary, and a value outside it MUST be rejected.
- **FR-006**: `document_id` MUST be derived deterministically from the source and the native
  identifier in the shape of §10, MUST be stable across runs and processes, and the model MUST offer
  no way to supply a generated one (Principle II).
- **FR-007**: Timestamps carried by the conversation and its messages MUST be the source's real
  times. The model MUST NOT provide any default that substitutes the import time or the current
  clock for a missing one (§11).
- **FR-008**: All timestamps MUST be timezone-aware; a naive value MUST be rejected at construction.
- **FR-009**: The model MUST define provenance as a typed structure carrying every field of §3.3 —
  source, source id, project, repository when known, title, import time and importer version — as a
  value distinct from the conversation, so that the project, which classification determines after
  normalization, is attached without rewriting the normalized conversation.
- **FR-010**: The model MUST express the tag vocabulary of §6 as typed values — `source:`,
  `project:`, `type:`, `user:` — that render to exactly the strings §6 defines, and MUST reject a
  value that would render a malformed tag. `project:unknown` MUST be an ordinary value.
- **FR-011**: The model MUST define a canonical representation of a conversation that is
  deterministic — identical for two structurally identical conversations, in any process, in any
  run, under any hash seed or key ordering.
- **FR-012**: The canonical representation MUST cover the messages, their order and their
  timestamps, and MUST exclude the title and any metadata the importer itself produces (ADR-006,
  decision 4).
- **FR-013**: The model MUST compute a content hash over that canonical representation, as the
  value §17 requires the import state to store and compare.
- **FR-014**: A conversation MUST serialize and re-parse without loss: the re-parsed value equals
  the original and hashes to the same content hash.
- **FR-015**: Parsing a serialized conversation that is missing a required field, or carries a value
  outside a closed vocabulary, MUST fail with an error naming what was wrong, rather than producing
  a partial object.
- **FR-016**: The module MUST NOT import Hindsight, its client, any HTTP library or any storage
  library, directly or transitively, and a test MUST assert this over the import graph (Principle
  IV, §8).
- **FR-017**: No public name in the module may be a Hindsight term; the vocabulary is the
  architecture's, so that replacing the memory engine touches no domain code (ADR-001 exit
  strategy).
- **FR-018**: The module MUST NOT perform input or output, read configuration, or require any
  environment to be importable and usable.
- **FR-019**: A message MUST be able to record that the source carried non-text parts alongside its
  text, so that a replay from the archive does not silently omit content nobody knows existed.
- **FR-020**: Every entity the model defines MUST validate on construction, so that an invalid
  conversation cannot reach a later stage (ADR-004: contract validation stands in for compile-time
  typing).

### Non-Functional Requirements

- **NFR-001**: The module's public surface MUST be documented in English, and the documentation MUST
  cite the architecture section each rule comes from, so that a later reader changing a field sees
  what it was holding up.
- **NFR-002**: Every rule in this specification that a test can assert MUST have one, written before
  the implementation and observed to fail first (Principle III).

### Key Entities

- **Conversation**: one conversation from one source, independent of that source's format. Carries
  its source, native identifier, optional title, real timestamps and ordered messages. Derives its
  document id, its canonical form and its content hash from itself.
- **Message**: one turn in a conversation — role, content, optional time, optional tool activity,
  and a record of any non-text parts the source carried.
- **Tool activity**: what a source records about a tool the assistant used — its name, what it was
  asked, and what it returned when it returned anything.
- **Source**: the closed set of history sources of §6 and §10. The only source Phase 1 parses is
  ChatGPT; the others exist in the vocabulary because the document id scheme and the tag convention
  already name them.
- **Role**: the closed set of message roles.
- **Provenance**: the §3.3 record of where a conversation came from, when it was imported and by
  which importer version, attached after classification.
- **Tag**: a typed scoping value of §6, rendering to the exact string form the memory store sends.
- **Content hash**: the value derived from the canonical form, on which the §17 skip depends.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All six boundaries of §8 can be declared using only the entities defined here, with no
  *conversation-shaped* type invented and no dictionary or free-form string carrying a field the
  architecture requires. Two boundaries legitimately need a type of their own — the sanitizer's
  report of what it redacted (§8) and the import state's record (§17) — and #9 and #14 define those;
  what this criterion forbids is a second way of describing a conversation, its provenance or its
  tags. Reworded during implementation: as first written it said "no additional type", which those
  two would have breached on the day they are built.
- **SC-002**: Every conversation in the test fixtures survives serialization and re-parsing
  unchanged, including one that exercises every optional field.
- **SC-003**: Two structurally identical conversations produce the same content hash when computed
  in two separate processes; every change to a message, its role, its order or its timestamp changes
  the hash; a change to the title alone does not.
- **SC-004**: The same conversation yields the same `document_id` on every run, and the model offers
  no path to a generated one.
- **SC-005**: The normalization module's transitive import graph contains no Hindsight module, no
  HTTP client and no storage library, asserted by a test that fails when one is added.
- **SC-006**: Every field named by §3.3, §6, §10 and §11 has exactly one place in the model, and a
  reviewer can point at it.
- **SC-007**: The committed change adds no file outside `src/hermes_memory/normalization/`,
  `tests/` and `specs/006-normalized-conversation-model/`, and touches no other module.

## Assumptions

- **Provenance is attached at the enrich stage, not produced at normalize.** §7 puts classification
  between them, and provenance carries the project. The model therefore defines provenance as a
  separate value and defines how it pairs with a conversation; this feature performs no
  classification and no enrichment.
- **Message content is text.** Sources that carry structured content parts flatten them to text when
  they parse, which is the parser's concern (#10). The model records that non-text parts existed
  (FR-019) rather than modelling them, because nothing in Phase 1 consumes them and a shape invented
  without a consumer is a shape invented wrongly.
- **Tool activity is modelled at the level ChatGPT exports carry** — a name, the request and the
  result as text. Claude Code and Codex record substantially richer tool structure, and each arrives
  with its own specification and decision record (§2, Phase 2); extending this entity then is
  expected and is not a reason to over-build it now.
- **A conversation carries a start time and, when the source provides one, a last-activity time.**
  Both are the source's own; neither defaults.
- **The hash algorithm and the exact byte form of the canonical representation are implementation
  choices** settled in `plan.md`, constrained only by FR-011 through FR-013. They are internal: no
  stored hash from a previous run exists to stay compatible with, because no importer has run.
- **Serialization here is the in-process contract, not the archive's on-disk layout.** §14 leaves
  that layout to the feature that builds the archive (#13), which will use this serialization;
  choosing directory structure or file naming is not part of this work.
- **`importer_version` is supplied by the caller** as a non-empty value. What that value is, and how
  it advances, belongs to the importer that sets it.
- **No source-specific mapping is written here.** Parsing a ChatGPT export into this model is #10.
  Fixtures used by this feature's tests are synthesized, never real history (CLAUDE.md).
- **Both dependencies are met**: #4 delivered the module skeleton and the test command, and #39
  delivered ADR-006, which is what makes FR-012 stateable rather than a guess.

## Dependencies

- Depends on #4 (project skeleton, closed) and #39 (ADR-006, closed).
- Blocks #9 (boundary interfaces), and through it #10, #11, #12, #13, #14 and #16.
