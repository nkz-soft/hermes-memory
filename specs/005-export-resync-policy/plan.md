# Implementation Plan: Export resynchronization policy (ADR-006)

**Branch**: `005-export-resync-policy` | **Date**: 2026-09-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-export-resync-policy/spec.md`

## Summary

Add ADR-006 to ARCHITECTURE.md §23 and point §17 at it. The record settles four questions the
architecture left open about what happens after the first ChatGPT export: the refresh model, a
conversation that continued, a conversation that disappeared, and what the content hash covers.
It unblocks #8, #14 and #21, each of which would otherwise answer one of those questions
implicitly in code.

The technical approach is editorial: two edits to one file, in the register and shape the file
already uses. There is no code to write, no dependency to add, and nothing to run.

## Technical Context

**Language/Version**: N/A — Markdown prose. No executable artefact is produced.

**Primary Dependencies**: None added. The change is confined to ARCHITECTURE.md.

**Storage**: N/A

**Testing**: No automated test, and none is available to borrow: CI runs `ruff`, `pytest`, the
secret scan and the image build, and not one of them inspects Markdown — there is no documentation
linter or link checker in this repository today. Verification is therefore a review against the
spec's acceptance scenarios, plus the manual checks in [quickstart.md](./quickstart.md). CI still
runs unchanged and must stay green, which for this diff means it proves only that nothing was
broken elsewhere.

**Target Platform**: N/A — repository documentation.

**Project Type**: Documentation change to the architecture of a modular monolith.

**Performance Goals**: N/A

**Constraints**: The added text matches the surrounding document — English, the same wrapping
width, the same register — and touches §17 and §23 only.

**Scale/Scope**: One decision record of roughly the length of ADR-002 through ADR-005, plus a
one-sentence cross-reference in §17.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design — see below.*

### Principle I — Raw Archive Is the Source of Truth

**Complies, and reinforces.** Decision 3 is Principle I applied to a case the principle implies but
does not spell out: if absence from an export could remove a conversation, the source service would
retain the power to empty an archive whose entire purpose is independence from it. The record makes
the implication normative. Nothing here weakens the requirement that ingestion be re-runnable from
the archive alone — decision 2 exists partly to preserve it, since tail-appending would make a
replay from the archive duplicate content.

### Principle II — Provenance and Stable Identity

**Complies.** `document_id` remains derived from source and native identifier (§10), unchanged.
Decision 2 keeps re-import on the upsert path rather than inventing a second write mode, which is
what the principle's no-duplicates requirement rests on. Decision 4 refines §17's content hash by
saying what the canonical representation covers; it narrows an ambiguity rather than altering the
identity scheme, and the real conversation timestamp is untouched.

### Principle III — Test-First (NON-NEGOTIABLE)

**No implementation, therefore nothing to bind — stated, not assumed.** The principle governs code:
a test is written first, fails, and then code makes it pass. This feature adds prose to
ARCHITECTURE.md and no executable behaviour, so there is no unit under test and a test written here
would assert the presence of a sentence, which is review's job rather than pytest's.

This is deliberately not an exemption claimed for convenience, and two things keep it honest:

1. The behavioural test named in issue #39 — import an export from which a previously imported
   conversation is missing, assert it survives in the archive and the bank — is real and is
   **required**, but cannot exist yet: there is no importer, no archive and no memory store to run
   it against. It is inherited by #14, which delivers the import state, and the specification
   records that inheritance in its Assumptions so it cannot be quietly dropped.
2. Every downstream issue that implements a consequence of this record is bound by Principle III in
   the ordinary way. The record makes those tests *possible to write correctly*; it does not
   substitute for them.

### Principle IV — Replaceable Boundaries

**Complies.** No boundary is added, removed or redefined — §8 is untouched. Decision 1 keeps the
acquisition of the export outside the decision, which protects the boundary set rather than
extending it: automating acquisition later (#40, with its own ADR-007) changes none of the four
decisions, precisely because the record does not bind them to how the file arrives.

### Principle V — Secrets Never Reach the Memory Engine

**Complies, and leaves the remedy path open.** Nothing in sanitization changes. Decision 3's second
half names deliberate forgetting — a human-initiated operation on a named `document_id` — as the
answer to a secret the sanitizer missed, while keeping it out of every import path and out of the
MVP. Recording that it is not built is the honest position: today the only remedy for a leaked
value already extracted is rebuilding the bank, and the record says where the better one belongs.

### Technology Stack

Unchanged. No entry in the stack table is altered and no dependency is introduced, so no decision
record beyond ADR-006 itself is owed.

### Governance

The issue's Governance impact ticks "None of the above", and that holds: the Hindsight contract
(§9), the bank strategy (ADR-002), the tag convention (§6) and the document-id scheme (§10) are all
untouched. The change is itself a decision record, which is the form the constitution requires for
a decision of this kind, added rather than amending an existing one.

**Gate result: PASS.** No violations, so Complexity Tracking below stays empty.

## Project Structure

### Documentation (this feature)

```text
specs/005-export-resync-policy/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output — the four decisions and what was weighed
├── quickstart.md        # Phase 1 output — how a reviewer verifies the change
├── checklists/
│   └── requirements.md  # Specification quality checklist
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

`data-model.md` and `contracts/` are **not** produced, and their absence is a decision rather than
an omission. This feature introduces no entity, no stored field and no interface: it changes prose
in an architecture document. A data model describing "an ADR has a title and three sections", or a
contract directory holding no contract, would be template compliance pretending to be design work.

### Source Code (repository root)

No source file is added or modified. The repository layout established in #4 is untouched:

```text
ARCHITECTURE.md          # modified: §17 gains a reference, §23 gains ADR-006
src/                     # unchanged
tests/                   # unchanged
```

**Structure Decision**: Documentation-only. The entire diff outside `specs/005-export-resync-policy/`
is two edits to `ARCHITECTURE.md` — a cross-reference sentence at the end of §17, and a new
`### ADR-006` subsection appended to §23 after ADR-005.

## Phase 0 — Research

See [research.md](./research.md). For this feature, "research" is the record of what was weighed
before each of the four decisions and what was rejected — the material that belongs in the ADR's
Rationale and Consequences, worked out before the record is written rather than invented while
writing it. No NEEDS CLARIFICATION markers survived the specification, so no question is carried
into this phase.

## Phase 1 — Design

The design of a decision record is its placement, its shape and its normative language:

* **Placement.** §23, after ADR-005, keeping the numbering contiguous. The cross-reference goes at
  the end of §17, where a reader asking about idempotency is already standing.
* **Shape.** Decision / Rationale / Consequences, matching ADR-001 through ADR-005. The four
  decisions are stated inside the Decision section as a numbered list, because they are one policy
  answering one question — how history stays current — not four records that happen to share a
  date.
* **Normative language.** The deletion rule is written with MUST NOT, quotable as a single
  sentence, because SC-005 requires a reviewer to cite it verbatim. The remaining decisions are
  declarative; the architecture uses normative language sparingly and this preserves that.
* **Consequences stated, not softened.** The three that cost something: extraction is paid again
  for a grown conversation; a renamed conversation keeps a stale title in the bank until some other
  change re-imports it; a conversation deleted in the source lives on in memory, by design.

See [quickstart.md](./quickstart.md) for how a reviewer verifies the result.

### Constitution re-check after design

Re-evaluated against all five principles once the design above was fixed: **PASS, unchanged**. The
design added no boundary, no entity, no dependency and no executable path, so no gate moved. The
one thing the design phase sharpened is Principle III's position — the verification is enumerated
in quickstart.md as six concrete checks rather than left as "a reviewer reads it", and the test
this feature cannot write is named there again, with its owner.

## Complexity Tracking

No constitution violations, so this table is empty.
