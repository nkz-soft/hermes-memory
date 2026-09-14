---

description: "Task list for the export resynchronization policy (ADR-006)"
---

# Tasks: Export resynchronization policy (ADR-006)

**Input**: Design documents from `/specs/005-export-resync-policy/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[quickstart.md](./quickstart.md)

**Tests**: None. The feature adds prose to ARCHITECTURE.md and no executable behaviour, so there is
no unit to test — see plan.md, Principle III. The behavioural test named in issue #39 is inherited
by #14, which delivers the import state. Verification here is the six checks in quickstart.md.

**Organization**: Tasks are grouped by user story, with one honest qualification stated up front.

## A note on story independence

The template asks that each user story be an independently deliverable increment. Here they are
not, and pretending otherwise would produce a fictional task list. All three stories are served by
one artefact — a single decision record — and the record is not shippable in thirds: an ADR that
answers two of its four questions is worse than none, because it looks complete.

What the stories do give is an ordering and a check per reader. US1 carries the substance; US2 and
US3 are satisfied by verifying that the record, as written for US1, actually serves their reader,
and by amending it where it does not. That is how their phases below are written.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Documentation-only feature. The single file modified outside this feature directory is
`ARCHITECTURE.md` at the repository root. `src/` and `tests/` are untouched.

---

## Phase 1: Setup

**Purpose**: Fix the insertion points and the house style before writing, so the record reads as
part of the document rather than as an import into it (NFR-001).

- [x] T001 Read `ARCHITECTURE.md` §17 and §23 and record: the exact line ending §17, the exact line
  ending ADR-005, the wrap width in use, and the heading shape of the existing records
  (`### ADR-00N — Title`, then Decision / Rationale / Consequences as bold lead-ins)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The record's frame, into which the four decisions are written.

**⚠️ CRITICAL**: Every story task edits this block, so it exists before any of them begin.

- [x] T002 Append the `### ADR-006 — History is re-exported periodically, imported incrementally`
  heading to `ARCHITECTURE.md` §23 after ADR-005, with **Decision**, **Rationale** and
  **Consequences** paragraphs matching the shape found in T001. The heading is shortened from the
  record's full name so that it sits within the length the other five headings use

**Checkpoint**: The record exists and is empty. Story work can begin.

---

## Phase 3: User Story 1 - The importer's author knows what a second export means (Priority: P1) 🎯 MVP

**Goal**: A reader of ARCHITECTURE.md alone can answer all four questions — cadence, continued
conversations, disappeared conversations, hash scope — with no contradiction elsewhere in the
document.

**Independent Test**: quickstart.md §2 — answer the four questions from the document alone, then
grep for contradicting statements.

Tasks T003–T006 write consecutive paragraphs of the same block and therefore carry no `[P]`.

- [x] T003 [US1] Write decision 1 in `ARCHITECTURE.md` ADR-006 Decision: periodic full re-export
  imported incrementally; the archive is cumulative rather than a delta; the manual export request
  is a property of the source recorded as a constraint; acquisition is explicitly outside this
  decision, a replaceable component whose MVP default is manual placement (FR-002, FR-007)
- [x] T004 [US1] Write decision 2: a conversation whose content changed is replaced in full;
  `update_mode: "append"` stays reserved for its §9 purpose of delivering one oversized document as
  several items in a single operation (FR-003)
- [x] T005 [US1] Write decision 3: the archive is never diffed against an export and removals are
  never derived from one, as a single quotable MUST NOT sentence; an absence may be logged and
  nothing may act on it; deliberate forgetting is a separate human-initiated operation on a named
  `document_id`, out of scope for the MVP and absent from every import path (FR-004, FR-005)
- [x] T006 [US1] Write decision 4: the §17 content hash covers messages, their order and their
  timestamps, and excludes the title and importer-produced metadata (FR-006)
- [x] T007 [US1] Write the **Rationale** paragraph from research.md: the cumulative archive making
  the skip sufficient, idempotency and whole-conversation context outweighing re-extraction cost,
  the indistinguishability of a truncated export from a deliberate deletion, the asymmetry of risk,
  and the archive's independence under Principle I and ADR-001
- [x] T008 [US1] Write the **Consequences** paragraph stating the three costs plainly rather than
  softening them: a grown conversation is re-extracted in full; a renamed conversation keeps a stale
  title until some other change re-imports it; a conversation deleted in the source lives on in
  memory by design
- [x] T009 [US1] Add the cross-reference at the end of `ARCHITECTURE.md` §17 pointing to ADR-006, so
  a reader asking about idempotency reaches the policy in one hop (FR-008, SC-002)

**Checkpoint**: The record is complete and §17 leads to it. quickstart.md §2, §3 and §4 pass.

---

## Phase 4: User Story 2 - The owner knows how to refresh history and what it costs (Priority: P2)

**Goal**: Someone who has never run the importer can state the refresh procedure and say which
conversations will be re-extracted, from the document alone.

**Independent Test**: quickstart.md §2, row 1 — read only what T003 and T008 produced and describe
the refresh and its cost.

- [x] T010 [US2] Re-read decision 1 and the Consequences in `ARCHITECTURE.md` as this reader, and
  amend where the refresh procedure or its cost is implied rather than stated — the skip by source
  id plus content hash must be named as what confines the cost, and #21's `status` as what makes
  the cadence visible

---

## Phase 5: User Story 3 - A reviewer can reject a synchronization that deletes (Priority: P3)

**Goal**: The prohibition can be cited verbatim in a review, without surrounding context.

**Independent Test**: quickstart.md §4 — `grep -n "MUST NOT" ARCHITECTURE.md` returns a sentence
that stands alone.

- [x] T011 [US3] Check the sentence written in T005 in isolation: it must name both prohibited
  behaviours — diffing the archive against an export, and deriving removals from one — and remain
  unambiguous when quoted away from its paragraph. Rewrite it if it depends on its neighbours

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T012 Run quickstart.md §1: `git diff --stat origin/main...HEAD` shows `ARCHITECTURE.md` and
  files under `specs/005-export-resync-policy/` only, and the `ARCHITECTURE.md` diff is two hunks
  (SC-004)
- [x] T013 Run quickstart.md §2's consistency grep over `ARCHITECTURE.md` for `append`, `delete`,
  `deletion`, `remove` and `hash`, confirming every hit is consistent with the record — in
  particular that §9's description of `append` is narrowed, not contradicted (SC-001)
- [x] T014 Confirm FR-009 by inspection: the diff leaves the constitution, the stack table, §6, §9,
  §10 and ADR-002 untouched
- [x] T015 Run `uv run ruff check . && uv run ruff format --check . && uv run pytest` as the guard
  rail that nothing in the codebase was disturbed — noting it cannot verify the record itself,
  since no check in this repository inspects Markdown

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (T001)**: no dependencies
- **Foundational (T002)**: depends on T001, blocks every story task
- **US1 (T003–T009)**: depends on T002; T003–T008 are strictly sequential, T009 edits a different
  section and could run alongside them
- **US2 (T010)**: depends on T003 and T008 — it reviews and amends what they wrote
- **US3 (T011)**: depends on T005 — same relationship
- **Polish (T012–T015)**: depends on everything above

### Parallel Opportunities

Almost none, and that is the nature of the work: fourteen of the fifteen tasks edit one file, and
six of them edit one block of it. T009 is separable from T003–T008 by section. T015 is independent
of the content and can run at any point.

---

## Implementation Strategy

The record lands in one commit. The phases order the writing; they do not describe deliverable
increments, for the reason stated at the top of this file — a decision record answering half its
questions is worse than none, because it reads as settled.

MVP scope is therefore Phases 1–3 (T001–T009) with Phases 4–6 as verification, not a later release.

---

## Notes

- No test task appears anywhere in this list. This is a documented position, not an omission: see
  plan.md under Principle III, and the inheritance of issue #39's behavioural test by #14
- Commit once, after T014, with T015's output quoted in the pull request's verification section
- Stop and ask rather than improvise if T013 finds a statement elsewhere in ARCHITECTURE.md that
  contradicts a decision — a contradiction between the record and the document is a defect in one
  of them, and which one is a decision for a person
