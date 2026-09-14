# Implementation Plan: Normalized conversation model

**Branch**: `006-normalized-conversation-model` | **Date**: 2026-09-14 | **Spec**:
[spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-normalized-conversation-model/spec.md`

## Summary

Fill `src/hermes_memory/normalization/` with the source-independent vocabulary the rest of the
pipeline speaks: a conversation and its ordered messages, the §3.3 provenance record, the §6 tag
convention as typed values, and the canonical form and content hash §17 depends on. Nothing else —
no parser, no archive format, no boundary protocol.

The technical approach is frozen Pydantic v2 models with closed vocabularies, a canonical form
assembled by naming the fields it covers rather than dumping the model, SHA-256 over its UTF-8 JSON
bytes, and two tests that make Principle IV's boundary fail rather than be argued. No dependency is
added: Pydantic is already in the stack table and already installed, and `hashlib` and `json` are
standard library.

This unblocks #9, which declares the six boundaries of §8 against these types.

## Technical Context

**Language/Version**: Python 3.13 (`requires-python = "==3.13.*"`).

**Primary Dependencies**: `pydantic>=2`, already declared for the "Models and contracts" row of the
stack table. Nothing is added — see the Technology Stack gate below.

**Storage**: None. The module persists nothing and reads nothing; the archive that will store its
output is #13 (§14).

**Testing**: `pytest`, already configured. Unit tests under `tests/unit/`, the Principle IV boundary
checks under `tests/structure/` alongside the existing repository-shape checks. Two determinism
assertions run in a subprocess, because a claim about behaviour across processes cannot be made from
inside one.

**Target Platform**: In-process library code inside the modular monolith. Imported by every
ingestion stage; imports nothing of theirs.

**Project Type**: Domain model — a single module of a Python monolith, with no I/O surface.

**Performance Goals**: None stated, and none needed. The hash runs once per conversation per import
over a few kilobytes of text; the cost of an import is extraction, by orders of magnitude (ADR-006).

**Constraints**: No import of Hindsight, HTTP or storage, direct or transitive (Principle IV). No
configuration read at import time (FR-018). Deterministic canonical bytes across processes and runs
(FR-011). No default that substitutes a clock for a missing timestamp (§11, FR-007).

**Scale/Scope**: Four source files and their tests. Nine entities, five closed vocabularies, one
canonical form. Roughly the size of the settings module delivered by #35.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design — see below.*

### Principle I — Raw Archive Is the Source of Truth

**Complies, and is a precondition for it.** The archive stores the normalized form alongside the
original, so the round-trip of FR-014 is what makes Principle I's promise — ingestion re-runnable
from the archive alone — mechanically true rather than aspirational. That is why the round-trip is
specified as equality *and* equal content hash, not as "parses without raising": a serialization
that loses a message timestamp would still parse, and would still replay, wrong.

The immutability of R7 serves the same principle from a different side: a pipeline stage that
mutated a conversation in place could leave the archive holding something the parser never produced.

### Principle II — Provenance and Stable Identity

**Complies, and is where the principle is enforced in code.** `document_id` is derived from source
and native id in the §10 shape and has no setter, so "a freshly generated identifier per import run"
is not a rule to remember but a thing the type will not do (FR-006, R10). Provenance carries every
§3.3 field as a typed value rather than a dictionary (FR-009). `imported_at` exists on `Provenance`
and nowhere else, so the §11 mistake — importing time standing in for conversation time — has no
field to hide in (FR-007).

The content hash is the other half of the principle: the §17 skip that keeps a re-import from paying
for extraction twice is a comparison of this value, and ADR-006 decision 4 is transcribed into
[contracts/canonical-form.md](./contracts/canonical-form.md) rather than paraphrased.

### Principle III — Test-First (NON-NEGOTIABLE)

**Complies, and the ordering is enforceable here in a way it was not for #39.** Every rule in the
specification that a test can assert has one (NFR-002), each is written first and observed to fail,
and `tasks.md` orders them that way. The suite includes the constitution's stated minimum that
applies at this layer — there is no parser and no sanitizer yet, so the parser and sanitizer tests
belong to #10 and #12, and the end-to-end test to the feature that first has an end to end.

Two specifics worth naming, because they are where a test-first claim usually goes soft:

* The determinism guarantees (C1, C6, C9) are asserted **in a subprocess**. A same-process assertion
  would pass on an implementation that is only accidentally stable.
* The boundary guard is itself tested to bite (R12, quickstart step 5), following the precedent
  `test_the_behaviour_guard_still_bites` already set in this repository. A guard nobody has watched
  fail is a guard nobody knows is working.

### Principle IV — Replaceable Boundaries

**Complies, and this feature is the principle's foundation rather than merely consistent with it.**
The whole point of the module is that what crosses a boundary is typed and source-independent, so
the six interfaces of #9 can be written against it and any implementation replaced behind them. The
rule is enforced by test, twice (R12, [contracts/module-boundary.md](./contracts/module-boundary.md)):
statically over the module's own imports, and at runtime over the true transitive closure.

FR-017 extends this past imports to vocabulary: no public name may be a Hindsight term. A model
called `RetainItem` would satisfy every import check and still bind the domain to the engine, which
is exactly what ADR-001's exit strategy is written against.

### Principle V — Secrets Never Reach the Memory Engine

**Complies; nothing here weakens it, and one choice supports it.** This module performs no I/O,
logs nothing and holds no credential. Sanitization is #12 and runs over these types — and the
immutability of R7 is what lets the sanitizer return a redacted conversation instead of editing one
in place, which is the failure mode where a half-redacted object escapes after an exception.

Test fixtures are synthesized conversations, never real history, per CLAUDE.md. Nothing in this
feature reads `data/`.

### Technology Stack

**Unchanged; no dependency added.** Pydantic v2 is the "Models and contracts" row of the stack
table and is already declared in `pyproject.toml`. `hashlib` and `json` are standard library. The
one tool that would have been a natural addition — `import-linter` for the Principle IV guard — was
weighed and rejected in research R12 in favour of thirty lines of `ast` and `subprocess`, precisely
so that no record is owed.

### Governance

The issue's Governance impact ticks "None of the above", and that holds. No principle is amended.
The Hindsight contract (§9) is untouched — this module is forbidden to know it exists. The bank
strategy (ADR-002), the tag convention (§6) and the document-id scheme (§10) are **implemented**
here, not changed: §6's four namespaces and §10's shape are transcribed, and a divergence would be
a defect in this feature rather than a decision.

One consequence is worth stating rather than leaving to be discovered: the `version` constant in the
canonical payload (contract rule 1) means a future change to what the hash covers is a versioned,
visible change with a stated re-extraction cost — not a silent one. That is a mechanism this feature
adds, within ADR-006 rather than beyond it.

**Gate result: PASS.** No violations, so Complexity Tracking below stays empty.

## Project Structure

### Documentation (this feature)

```text
specs/006-normalized-conversation-model/
├── spec.md                      # Feature specification
├── plan.md                      # This file
├── research.md                  # Phase 0 — the fifteen design decisions and what was weighed
├── data-model.md                # Phase 1 — entities, fields, validation rules
├── contracts/
│   ├── canonical-form.md        # the §17 hash: what it covers, its bytes, its guarantees
│   └── module-boundary.md       # the public surface, and what the module may not import
├── quickstart.md                # Phase 1 — how a reviewer verifies the result
├── checklists/
│   └── requirements.md          # Specification quality checklist
└── tasks.md                     # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
src/hermes_memory/normalization/
├── __init__.py                  # the public surface; re-exports, __all__
├── conversation.py              # Conversation, Message, ToolActivity, NonTextPart, Role, Source
├── provenance.py                # Provenance, EnrichedConversation
├── tags.py                      # Tag and its four namespaces
└── canonical.py                 # canonical_form, content_hash

tests/unit/
├── test_conversation.py         # construction, validation, ordering, immutability
├── test_provenance.py           # §3.3 fields, the conversation/provenance pairing
├── test_tags.py                 # the §6 convention, rendering, rejection of malformed values
├── test_canonical.py            # contracts C1–C9, including the subprocess determinism checks
└── test_serialization.py        # round-trip (FR-014) and parse failures (FR-015)

tests/structure/
├── test_normalization_boundary.py   # Principle IV: static and runtime import checks
└── test_module_layout.py            # modified: FILLED_BOUNDARIES gains "normalization"
```

**Structure Decision**: The module split follows the axes along which these things change (research
R14) — a new source touches `conversation.py`, a new tag namespace touches `tags.py`, and ADR-006
governs `canonical.py` alone, so a reviewer checking the hash against the ADR has one file to read.
Tests mirror the split, and follow the existing convention where `tests/structure/` holds checks
about the shape of the repository and `tests/unit/` holds checks about behaviour.

The one file touched outside the feature is `tests/structure/test_module_layout.py`: its
`FILLED_BOUNDARIES` set holds every recorded boundary to a bare docstring until a feature fills it,
and its own docstring requires the filling commit to make that edit deliberately (research R13).

## Phase 0 — Research

See [research.md](./research.md). Fifteen decisions, from the canonical form's construction to what
is deliberately not built. No `[NEEDS CLARIFICATION]` marker survived the specification, so no
question is carried into this phase; what is here is the design the specification deferred.

Four claims were checked by running them rather than reasoning about them — that naive datetimes are
rejected, that a frozen model with tuple fields round-trips equal, that two offsets of one instant
compare equal, and that the package imports cleanly in a subprocess. Their results are quoted in
R3, R5, R7 and R12.

## Phase 1 — Design

See [data-model.md](./data-model.md) for the entities and their validation rules, and `contracts/`
for the two contracts this module owes its consumers:

* **[canonical-form.md](./contracts/canonical-form.md)** — what the hash covers, the exact payload
  and bytes, and nine guarantees (C1–C9) the tests hold to. This is where ADR-006 decision 4 becomes
  executable.
* **[module-boundary.md](./contracts/module-boundary.md)** — the public surface, seven behavioural
  guarantees (B1–B7), and the allowlist the import checks enforce.

[quickstart.md](./quickstart.md) is how a reviewer verifies all of it, including the step that makes
the Principle IV guard visibly fail before trusting it.

### Constitution re-check after design

Re-evaluated against all five principles with the design fixed: **PASS, unchanged.** No boundary was
added or moved, no dependency introduced, no I/O path opened, and no Hindsight term entered the
vocabulary.

Two things the design phase sharpened rather than left implied:

1. **Principle III's ordering is now concrete.** The determinism guarantees are subprocess
   assertions and the boundary guard is itself proven to bite, so "tests first" has a failing state
   that is observable for the parts most likely to be waved through.
2. **Principle II gained a mechanism, not just a rule.** The canonical payload's `version` constant
   makes a future change to the hash's coverage a visible, costed change. Without it, the honest
   position would have been that ADR-006 decision 4 is enforced by whoever remembers it.

## Complexity Tracking

No constitution violations, so this table is empty.
