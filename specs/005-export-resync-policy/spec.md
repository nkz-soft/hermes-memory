# Feature Specification: Export resynchronization policy (ADR-006)

**Feature Branch**: `005-export-resync-policy`

**Created**: 2026-09-14

**Status**: Draft

**Input**: Issue #39 — "Record ADR-006: how ChatGPT history stays current after the first export"

## User Scenarios & Testing *(mandatory)*

This feature delivers a written decision. Its users are the people and agents who will implement
the importer, refresh the history, and review the pull requests that do either. Each story below
is a separate reader with a separate question, and each is testable by reading the amended
document and finding one unambiguous answer.

### User Story 1 - The importer's author knows what a second export means (Priority: P1)

Someone picks up the import-state work (#14) or the canonical hash (#8) and needs to know how a
re-run treats a conversation that grew, a conversation that vanished, and a conversation that was
renamed. Today ARCHITECTURE.md answers none of the three, so the answers would be invented in
code — differently by each author, and discoverable only by reading the implementation.

**Why this priority**: This is the whole point of the record. Three issues are blocked on it, and
each of the three questions has a plausible wrong answer that is cheaper to write and expensive to
undo once memory has been extracted under it.

**Independent Test**: Read ARCHITECTURE.md alone, without this specification or the issue, and
answer the four questions. Each has exactly one answer, and nothing elsewhere in the document
contradicts it.

**Acceptance Scenarios**:

1. **Given** a reader at §17, **When** they ask what happens on a re-import of a conversation that
   gained messages, **Then** the document states that the conversation is replaced in full, that
   `append` is not used for this, and why paying for extraction again is accepted.
2. **Given** a reader at §17, **When** they ask whether a conversation missing from a newer export
   should be removed, **Then** the document forbids deriving removals from an export in normative
   language, and gives the reason rather than only the rule.
3. **Given** a reader at §17, **When** they ask whether renaming a conversation in the source
   causes re-extraction, **Then** the document states what the content hash covers and what it
   excludes.

---

### User Story 2 - The owner knows how to refresh history and what it costs (Priority: P2)

The person whose history this is wants to bring memory up to date some weeks after the first
import, and needs to know the supported procedure and whether it is expensive.

**Why this priority**: Without it the system works and goes unused, because the refresh path is
folklore. It matters less than P1 only because a wrong answer here wastes time rather than
corrupting the bank.

**Independent Test**: A reader who has never run the importer can state the refresh procedure and
say which conversations will be re-extracted, from the document alone.

**Acceptance Scenarios**:

1. **Given** the amended document, **When** the owner asks how history is refreshed, **Then** it
   describes a fresh full export imported incrementally, and names the manual export request as a
   property of the source rather than a gap in the tooling.
2. **Given** the amended document, **When** the owner asks what a refresh costs, **Then** it states
   that the skip by source id and content hash confines extraction to what is new or changed.

---

### User Story 3 - A reviewer can reject a synchronization that deletes (Priority: P3)

A reviewer sees a pull request that compares the raw archive against the newest export and removes
what is missing. They need a rule to point at, not an argument to win.

**Why this priority**: The constitution's merge gate already rejects a second source of truth for
history; this makes the deletion case explicit, so the rejection cites a line instead of an
interpretation.

**Independent Test**: The rule can be quoted as a single normative sentence naming the prohibited
behaviour.

**Acceptance Scenarios**:

1. **Given** a change that derives removals from an export, **When** it is reviewed against
   ARCHITECTURE.md, **Then** a normative sentence forbids exactly that.

---

### Edge Cases

- **A partial or truncated export.** Indistinguishable from one where conversations were deleted,
  which is the reason the rule is written as an absolute rather than a heuristic. The record must
  state the indistinguishability, not merely the prohibition.
- **A conversation edited in place** — messages removed inside the source. The content hash
  changes, so it takes the replace path along with continued conversations; the earlier form
  survives in the raw archive. The record must not carve out a special case for it.
- **A renamed conversation.** The hash is unchanged, so the conversation is skipped and the title
  held in the bank goes stale until some other change re-imports it. This is a real consequence and
  the record must state it rather than leave it to be discovered.
- **A future source that reports deletions explicitly.** Claude chats, Claude Code and Codex arrive
  with their own decision records (§2). The rule here is scoped to sources whose export cannot
  distinguish absence from deletion, and must not silently bind a source that carries a genuine
  deletion event.
- **A source id that reappears with different content after the archive was cleared.** Handled by
  the same replace path; nothing in the record may depend on the import-state store surviving.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: ARCHITECTURE.md §23 MUST carry a new record, ADR-006, following the shape the other
  records use — Decision, Rationale, Consequences — and named for the model it fixes.
- **FR-002**: ADR-006 MUST state that synchronization is a periodic full re-export imported
  incrementally, that each export carries the account's history in full rather than a delta, and
  that the manual export request is a property of the source recorded as a constraint.
- **FR-003**: ADR-006 MUST state that a conversation whose content changed is replaced in full,
  that `update_mode: "append"` remains reserved for its §9 purpose, and that repeated extraction
  cost is accepted in exchange for idempotent re-import and whole-conversation context.
- **FR-004**: ADR-006 MUST forbid, in normative language, deriving removals from an export or
  diffing the raw archive against one, and MUST give the asymmetry of risk and the independence of
  the archive (Principle I, ADR-001) as the reason.
- **FR-005**: ADR-006 MUST distinguish synchronization, which never removes, from deliberate
  forgetting, which is a human-initiated operation on a named `document_id`, out of scope for the
  MVP and absent from every import path.
- **FR-006**: ADR-006 MUST state what the §17 content hash covers — messages, their order and their
  timestamps — and what it excludes — the title and importer-produced metadata — together with the
  stale-title consequence that follows.
- **FR-007**: ADR-006 MUST place the acquisition of the export outside the decision, as a
  replaceable component whose default implementation in the MVP is manual placement, so that
  automating it later changes none of the four decisions.
- **FR-008**: §17 MUST reference ADR-006, so that a reader arriving at idempotency reaches the
  policy in one hop.
- **FR-009**: The change MUST NOT alter any principle in the constitution, the technology stack of
  ADR-004, the Hindsight contract of §9, the bank strategy of ADR-002, the tag convention of §6, or
  the document-id scheme of §10.
- **FR-010**: The change MUST be confined to ARCHITECTURE.md §17 and §23 plus this feature's own
  specification artefacts; no source code and no test of unimplemented behaviour is added.
- **FR-011**: ADR-006 MUST state the consequence that follows from FR-006 for re-runs: because
  importer-produced metadata is outside the hash, an ordinary refresh after the parser, the
  sanitizer or the extraction policy changed skips everything and does nothing, so the re-application
  §3.1 and Principle I promise is kept by an explicit forced re-import that ignores the skip.
- **FR-012**: ADR-006 MUST resolve the intersection of FR-003 and §9 — a conversation both oversized
  and grown — rather than leaving an implementer to choose between re-sending it and having no legal
  path for it.

### Non-Functional Requirements

- **NFR-001**: The added text MUST match the surrounding document — English, the same wrapping
  width, the same register — so that the record reads as part of ARCHITECTURE.md rather than as an
  import into it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reader given only ARCHITECTURE.md answers all four questions — cadence, continued
  conversations, disappeared conversations, hash scope — with no contradicting statement found
  elsewhere in the document.
- **SC-002**: A reader who starts at §17 reaches the policy in one hop.
- **SC-003**: The three blocked issues — #8, #14, #21 — can each be planned without re-opening any
  of the four questions; every consequence they need is already stated.
- **SC-004**: The committed diff touches ARCHITECTURE.md in §17 and §23 only, and adds no file
  outside `specs/005-export-resync-policy/`.
- **SC-005**: The prohibition on deriving removals is quotable as one normative sentence, so a
  review can cite it verbatim.

## Assumptions

- **Each export carries the account's history in full**, rather than the changes since the last
  one. Not a superset of the previous export: a conversation deleted in the source is absent from
  the next one, which is exactly the case decision 3 governs. This is an observed property of the
  source, not something the project controls; if it ever stops holding, decision 1 is what must be
  revisited, and the record says so.
- **There is no supported programmatic export.** No endpoint yields an account's conversation
  history, so the request step is a human action. Recorded as a constraint of the source; issue #40
  covers automating everything after that step, behind its own boundary.
- **A stale title in the bank is acceptable.** Excluding the title from the hash means a rename
  alone does not re-import, so the title carried as metadata can lag. Titles are metadata rather
  than a retrieval surface, and paying for full re-extraction to correct one is a worse trade.
- **The acceptance test named in issue #39** — importing an export from which a previously imported
  conversation is missing, and asserting it survives in the archive and the bank — **cannot be
  written in this feature.** No importer, archive or memory store exists yet. This feature fixes
  the rule; the test is delivered with the import state in #14, whose specification inherits it.
- **ADR-006 is the next free record number**, following ADR-005 in §23.
- **Documentation-only scope.** The feature adds no executable behaviour, so Principle III has no
  implementation to bind; the plan states this explicitly rather than treating it as a silent
  exemption.

## Dependencies

- Issue #39 is the source of this specification, and blocks #8, #14 and #21.
- Issue #40 depends on decision 1 remaining true when acquisition is automated; it does not block
  this work.
