# Feature Specification: ChatGPT export source

**Feature Branch**: `008-chatgpt-export-source`

**Created**: 2026-09-17

**Status**: Draft

**Input**: Issue #10 — "Parse ChatGPT exports into the normalized model"

## User Scenarios & Testing *(mandatory)*

This feature delivers the first real implementation of a boundary: the conversation source of
ARCHITECTURE.md §8, for the only source the MVP has (§2). Its users are the person whose ChatGPT
history is being imported, the author of the ingestion pipeline (#19) who composes this source with
the other boundaries, and the reviewer whom Principle III obliges to see the parser tested against
realistic fixtures before the stage counts as done.

A ChatGPT export does not store a conversation as a list of turns. It stores a graph of message
nodes, each pointing to its parent and its children, with forks wherever a message was edited or a
response regenerated, and with nodes that are structural or hidden rather than said. Reading it as a
list produces something that looks like a transcript and is not the conversation. The failure is
silent — every test that checks "some messages came out" passes — which is exactly the class of
defect Principle III names.

Every story is testable with synthesized exports only. No real conversation data is used, in a
fixture or anywhere else (CLAUDE.md, "Handling history data").

### User Story 1 - A conversation comes out as the thread the person actually saw (Priority: P1)

The person imports an export. For each conversation in it, they get the sequence of turns that
the ChatGPT interface showed them the last time they looked at it: their messages, the assistant's
answers, in order, with no turn from an abandoned branch mixed in and no visible turn missing.

**Why this priority**: It is the whole of the issue. Every downstream stage — sanitization,
classification, the archive, extraction — works on what this stage produces, and none of them can
recover a turn this stage dropped or detect one it wrongly included.

**Independent Test**: Read a synthesized export containing one linear conversation and one
conversation with an edited message and a regenerated answer, and compare each result with the
thread that was synthesized as the visible one.

**Acceptance Scenarios**:

1. **Given** an export with a conversation whose graph has no forks, **When** it is read, **Then**
   the conversation holds every said turn exactly once, in the graph's order from the root, with
   each turn's role and text.
2. **Given** a conversation in which a user message was edited and an answer regenerated, **When**
   it is read, **Then** the conversation holds only the branch the export marks as current, and no
   turn from the other branches.
3. **Given** a conversation whose export marks no current position, or marks one that does not
   exist in its graph, **When** it is read, **Then** a single deterministic branch is chosen by the
   rule stated in the assumptions, and the fact that the fallback was used is recorded.
4. **Given** a conversation read twice from the same export, **When** the two results are compared,
   **Then** they are equal, including the branch chosen.

---

### User Story 2 - Identity and time survive the parse (Priority: P1)

Re-importing a conversation must upsert rather than duplicate it (§10, §17), and temporal questions
— "what did we use before", "when did we move to X" — depend on the conversation's real time
(§11). Both are decided here: the source is the only stage that sees the export's own identifier
and its own times.

**Why this priority**: A wrong identity duplicates memory on the next refresh (ADR-006), and a wrong
time corrupts temporal retrieval. Neither is visible in a single import, and neither can be repaired
downstream.

**Independent Test**: Read a synthesized conversation with known identifier, title, creation and
update times, and one message without a time, and inspect the result.

**Acceptance Scenarios**:

1. **Given** a conversation with a native identifier, **When** it is read, **Then** its document
   identity is `chatgpt:` followed by that identifier, and reading the same export again yields the
   same identity.
2. **Given** a conversation with a creation time and an update time, **When** it is read, **Then**
   its start is the creation time and its last activity is the update time, both as instants in
   UTC, and neither is the time of the import.
3. **Given** a conversation with no title, **When** it is read, **Then** it is yielded with no
   title, and nothing is invented in its place.
4. **Given** a message with no time, **When** it is read, **Then** the message is kept, in its
   place, with no time — no neighbouring, conversation or import time is substituted.

---

### User Story 3 - Nothing is dropped without a record (Priority: P1)

An export carries more than said text: hidden system context, tool calls and their results, images,
files, and content types this importer does not understand — including ones ChatGPT will introduce
after it is written. Whatever the source does not carry into the normalized conversation, it says so.

**Why this priority**: The issue's own words — "skip nothing without recording that it was
skipped". Principle I promises that a fixed parser can be re-run over the raw archive; that promise
is worth something only if somebody can find out what the previous parser left out.

**Independent Test**: Read a synthesized conversation containing a hidden system node, an abandoned
branch, a tool call with its result, an image, and a content type the importer does not know, and
check each against its expected outcome and its record.

**Acceptance Scenarios**:

1. **Given** a message carrying an image, a file or audio, **When** it is read, **Then** the message
   is kept, and each such part appears as a non-text marker of the matching kind.
2. **Given** an assistant turn that called a tool and a following node carrying the tool's result,
   **When** they are read, **Then** the call and the result are preserved as tool activity rather
   than dropped or flattened into ordinary prose.
3. **Given** a message whose content type is not one the importer recognizes, **When** it is read,
   **Then** the message is kept with a non-text marker naming that type, and the conversation is
   not failed because of it.
4. **Given** a conversation with nodes left out of the thread — abandoned branches, structural
   nodes, nodes the export marks hidden — **When** it is read, **Then** a per-conversation record
   states how many nodes of each kind were left out, and contains no conversation content.

---

### User Story 4 - One bad conversation does not stop the import (Priority: P2)

A year of history is thousands of conversations, and an export produced by a service that changes
its format without notice will sometimes contain one this importer cannot read. The person expects
the others to be imported and the bad one to be named.

**Why this priority**: §18 requires it and the contract suite (CS-5) already tests it. It is P2
only because it concerns the unusual conversation rather than the ordinary one.

**Independent Test**: Read a synthesized export whose second of three conversations is malformed,
and whose file is then made unreachable.

**Acceptance Scenarios**:

1. **Given** an export in which one conversation is malformed, **When** it is read, **Then** that
   conversation raises a permanent, per-conversation failure naming its identifier when one can be
   found, and the remaining conversations are still yielded.
2. **Given** an export that cannot be reached — missing, or not readable at the moment — **When** it
   is read, **Then** a retryable failure concerning the export is raised, and no conversation is
   yielded.
3. **Given** an export that can be reached but whose content is not a ChatGPT export at all,
   **When** it is read, **Then** a permanent failure concerning the export is raised, and it is not
   reported as retryable.
4. **Given** any failure, **When** it crosses the boundary, **Then** it is one of the boundary's own
   error types, and it carries no conversation content.

---

### User Story 5 - The source is proved by the contract it implements (Priority: P2)

The author of the pipeline composes sources without knowing which one they hold. Passing the
conversation-source contract suite from #9 is what makes this source substitutable for the fake the
pipeline was written against.

**Why this priority**: Principle IV. It is P2 because stories 1–4 are what the suite cannot check —
the suite knows nothing of ChatGPT's graph — while the suite is what the stories cannot replace.

**Independent Test**: Run the contract suite against this source, supplying it synthesized exports
built from the suite's conversations.

**Acceptance Scenarios**:

1. **Given** the contract suite CS-1 to CS-7, **When** it is run against this source, **Then** every
   rule passes, and none is skipped.
2. **Given** a conversation yielded by this source, **When** its original is inspected, **Then** it
   is that conversation's own record from the export, and parsing it alone yields an equal
   conversation.

### Edge Cases

- **An empty export.** An export with no conversations yields nothing and raises nothing (CS-3).
- **A conversation with no said turns.** A conversation whose graph holds only structural or hidden
  nodes is yielded with no messages, not skipped and not failed.
- **A message with empty text.** A turn that carried only an image, or whose text is empty, keeps
  its place in the order with empty text.
- **A conversation with no creation time.** Its start is taken from the earliest message time in
  the thread. If no time exists anywhere in it, it fails as unreadable: §11 forbids the import time,
  and the model does not allow a conversation without a start.
- **An update time earlier than the creation time.** The last activity is left absent and the
  inconsistency recorded, rather than failing the conversation or reordering the two times.
- **A cycle or a dangling parent in the graph.** The conversation fails as unreadable, and the rest
  of the export continues.
- **Two conversations with the same identifier in one export.** The first is yielded; the second
  fails as unreadable, naming the identifier, because two different conversations cannot share one
  document identity (§10).
- **Several messages sharing one time, or times out of order along the thread.** The order is the
  graph's, never re-derived from times.
- **A conversation that grew, was renamed, or disappeared since the last export.** Not this
  source's concern: it reads one export as it is. ADR-006 governs what a re-import does with it.

## Requirements *(mandatory)*

### Functional Requirements

**Reading**

- **FR-001**: The source MUST implement the conversation source boundary of #9 and declare ChatGPT
  as its source.
- **FR-002**: The source MUST accept a ChatGPT export in the form in which the person downloads it —
  the archive file, or the directory it was extracted into.
- **FR-003**: The source MUST yield conversations one at a time, and MUST NOT hold more normalized
  conversations than the one being yielded (CS-2).
- **FR-004**: Reading the same export twice MUST yield equal conversations with equal originals
  (CS-4).

**Reconstructing the thread**

- **FR-005**: The conversation's turns MUST be the branch from the graph's root to the node the
  export marks as current, in that order.
- **FR-006**: Where no valid current node is marked, the branch MUST be chosen by the deterministic
  fallback rule in the assumptions, and the use of the fallback MUST be recorded.
- **FR-007**: The order of turns MUST NOT be derived from their times.
- **FR-008**: Nodes that carry no message, and nodes the export marks as hidden from the
  conversation, MUST be left out of the turns and counted in the conversation's record.

**Mapping to the normalized model**

- **FR-009**: The conversation's source identifier MUST be the export's native conversation
  identifier, so that its document identity is `chatgpt:{conversation-id}` (§10).
- **FR-010**: The conversation's start and last activity MUST be the export's creation and update
  times; each message's time MUST be that message's own time or absent. No other time — and never
  the import time — may stand in for a missing one (§11), except the conversation start rule in the
  edge cases.
- **FR-011**: The title MUST be the export's title, or absent when the export has none.
- **FR-012**: Each turn's role MUST be mapped to user, assistant, system or tool.
- **FR-013**: Textual content MUST be carried as the turn's text without alteration beyond joining
  the export's text parts.
- **FR-014**: Tool calls and tool results MUST be preserved as tool activity; a call without a
  result MUST be kept with no result.
- **FR-015**: Images, files, audio and unrecognized content types MUST be kept as non-text markers
  of the matching kind, the unrecognized ones naming the export's type.

**Recording what was left out**

- **FR-016**: For every conversation, the source MUST make available a record of what it left out
  and why — counts per reason (abandoned branch, structural node, hidden node, fallback branch
  choice, inconsistent times) — and this record MUST contain no conversation content.
- **FR-017**: A conversation with nothing left out MUST NOT produce a record claiming otherwise.

**Originals**

- **FR-018**: Every yielded conversation MUST be paired with its original: that conversation's own
  record from the export, sufficient to parse that conversation again on its own (Principle I).

**Failures**

- **FR-019**: A conversation that cannot be read MUST raise a permanent per-conversation failure
  naming its identifier where one is available, and iteration MUST continue with the next
  conversation (CS-5, §18).
- **FR-020**: An export that cannot be reached MUST raise a retryable failure (CS-6).
- **FR-021**: An export that can be reached but is not a ChatGPT export MUST raise a permanent
  failure concerning the export.
- **FR-022**: No exception other than the boundary's own error types MUST cross the boundary
  (CS-7), and no failure MUST carry conversation content (Principle V).

**Testing**

- **FR-023**: Unit tests MUST cover at least: a plain thread, a branched thread, an empty
  conversation, a missing title, a message with no timestamp, a hidden node, a tool call with and
  without a result, a non-text part, an unrecognized content type, and a malformed conversation.
- **FR-024**: The source MUST pass the conversation-source contract suite with no rule skipped.
- **FR-025**: Every fixture MUST be synthesized. No real conversation data may be committed.

**Scope**

- **FR-026**: This feature MUST NOT sanitize, classify, archive, retain, or record import state:
  those are #11, #12, #13, #16 and #14.

### Key Entities

- **ChatGPT export**: What the person downloads — an archive holding the account's conversations as
  JSON, among other files. Read-only input.
- **Conversation record**: One conversation inside the export — its identifier, title, creation and
  update times, a mapping of message nodes and a pointer to the current node.
- **Message node**: A node of the graph — parent, children, and optionally a message with author
  role, content of some content type, time and metadata such as visibility.
- **Thread**: The branch of the graph from the root to the current node; what becomes the
  normalized conversation's turns.
- **Omission record**: Per conversation, what was left out of the thread and for which reason, as
  counts. Never content.
- **Source conversation**: The pair the boundary yields — the normalized conversation (#8) and its
  original.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every synthesized fixture, the conversation read equals the conversation that was
  synthesized as the visible thread — 100% of turns present, 0 turns from abandoned branches.
- **SC-002**: The conversation-source contract suite passes against this source with 7 of 7 rules
  passing and 0 skipped.
- **SC-003**: Reading the same export twice yields identical identities, content and times for
  every conversation.
- **SC-004**: In an export of 3 conversations with the second malformed, 2 conversations are
  yielded and exactly 1 failure is raised, naming the malformed one.
- **SC-005**: For every node present in a fixture's graph, the node either contributes to the
  thread or is counted in the omission record — the two together account for all of them.
- **SC-006**: No time on any yielded conversation or message equals the time the test ran, in a
  test that controls the clock.
- **SC-007**: A synthesized export of 10,000 conversations is read with peak memory bounded by the
  largest single conversation rather than growing with the number of conversations read.

## Assumptions

- **The current branch is what the person saw.** The export's current-node pointer marks the
  position the interface displayed, so the branch from the root to it is the conversation. Other
  branches are regenerations and edits the person moved away from; they are counted, not imported.
  Importing them would put abandoned answers into memory as if they had been accepted.
- **Fallback branch rule.** Where the current node is missing or not in the graph, the thread
  follows, from the root, the last-listed child at every fork — the export appends a regeneration or
  an edit after the child it replaces, so the last-listed child is the latest. This uses no times,
  which may be absent.
- **Hidden nodes are left out.** Nodes the export marks as hidden from the conversation — typically
  system context and custom instructions — were not part of the conversation as displayed. They are
  counted, not imported. Visible system messages are imported with the system role.
- **Hidden model reasoning is left out.** Reasoning content that the interface collapsed rather
  than displayed as the answer is treated as hidden and counted. The answer it led to is imported.
- **Export shape.** The export is the archive ChatGPT emails a download link for, holding the
  conversations as JSON; an archive split into several conversation files is read as one export.
  Other files in it (the rendered HTML page, user and message-feedback files, uploaded assets) are
  not conversations and are not read; asset bytes are the raw archive's question (§14, #13).
- **Times** in the export are seconds since the epoch, and are read as UTC instants.
- **Where the omission record goes.** It is reported through the structured logging baseline (#6)
  as counts per conversation, keyed by source identifier — never content (§18, Principle V). The
  pipeline (#19) may surface it in the run summary; this feature does not build that summary.
- **The original is the conversation's own JSON record**, not the whole export and not the bytes of
  the archive. It is serialized deterministically so that CS-4 holds, and it re-parses on its own to
  an equal conversation.
- **Contract suite harness.** The suite hands `make_source` plain normalized conversations. The
  test harness writes them into a synthesized export and hands that to the real source, which is
  what proves the real parser rather than a pass-through.
- **No new source is added.** ChatGPT is already the MVP source of §2, so no decision record is
  required, and no governance box on the issue is ticked.
- **Dependencies.** #8 (normalized model) and #9 (boundary interfaces and contract suite) are merged
  on `main`. #19 consumes this source.
