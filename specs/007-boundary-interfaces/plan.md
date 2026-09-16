# Implementation Plan: Boundary interfaces and their contract tests

**Branch**: `007-boundary-interfaces` | **Date**: 2026-09-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-boundary-interfaces/spec.md`

## Summary

Declare the six boundaries of ARCHITECTURE.md §8 as protocols written in #8's vocabulary, give each
one a reusable contract suite and an in-memory fake that passes it, and prove the six compose by
running a pipeline built entirely from fakes with the network and the filesystem blocked.

The technical approach: `typing.Protocol` per boundary, each in the module that owns the
responsibility rather than in a new package; a two-branch error taxonomy in a top-level `errors.py`
where retryability is settled by the class a failure derives from, not by a flag someone sets;
contract suites as base classes an implementation's test subclasses; fakes in the test tree, never
in the distribution. Six types the boundaries own are added — the original payload, the redaction
report and its §13 categories, the import record and its status, the recall result — which is the
space #8's SC-001 explicitly reserved. No dependency is added.

This unblocks #10, #11, #12, #13, #14 and #16, and through them #19 and #20.

## Technical Context

**Language/Version**: Python 3.13 (`requires-python = "==3.13.*"`).

**Primary Dependencies**: none added. `typing.Protocol` and `enum.StrEnum` are standard library;
the small immutable values reuse `FrozenModel` from `hermes_memory.normalization.base`, so Pydantic
v2 — already the "Models and contracts" row — carries validation-on-construction here too (R16).

**Storage**: none. This feature declares the interfaces two storage boundaries will be implemented
behind; it opens no file and no database (FR-027).

**Testing**: `pytest`, already configured. Contract suites under `tests/contracts/`, fakes under
`tests/fakes/`, the pipeline harness under `tests/integration/`, the Principle IV guards under
`tests/structure/` alongside the existing repository-shape checks.

**Target Platform**: in-process library code inside the modular monolith. Imported by every
ingestion stage and by the pipeline; imports nothing of theirs.

**Project Type**: contracts and test infrastructure — protocols, small value types, and the suites
that hold implementations to them. No runtime behaviour.

**Performance Goals**: none for the interfaces. One constraint on the suite, from NFR-003: it is
what an implementation author runs continuously, so it must stay a few seconds with no network, no
database and no fixture file.

**Constraints**: no Hindsight, HTTP or storage import in any interface module, direct or transitive
(Principle IV). No Hindsight term in any public name (FR-009). No error borrowed from a backend
library (FR-013). §18's never-retryable conditions not expressible as retryable (FR-014). No new
package under `src/hermes_memory/` — the constitution's module tree is enforced in both directions
by `tests/structure/test_module_layout.py` (R2).

**Scale/Scope**: six protocols across six files, one errors module, six value types, six contract
suites, six fakes plus six deliberately broken ones, one pipeline harness. One test file outside the
feature is edited: `tests/structure/test_module_layout.py`, whose `FILLED_BOUNDARIES` guard this
feature narrows deliberately (R15).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design — see below.*

### Principle I — Raw Archive Is the Source of Truth

**Complies, and this is where the principle becomes enforceable.** The archive interface takes the
original payload *and* the enriched conversation in one call (R8): §8's row says "originals and
normalized forms", and an interface that accepted only the normalized form would make Principle I
unmeetable by construction — a re-run after the parser is fixed needs the original bytes. RA-1, RA-2
and RA-6 hold the round-trip as equality plus equal content hash, because a serialization that loses
a message timestamp still parses and still replays, wrong.

RA-9 — loadable once `store` returns — is the same principle stated against deferred writes: §7
archives before retaining, and an archive that had not yet written when the retain call failed would
leave the source of truth behind the derived memory.

### Principle II — Provenance and Stable Identity

**Complies.** `RecallResult` carries the provenance the item was retained with (MS-5), so a recalled
fact can say where it came from without asking the engine. `ImportRecord` carries the content hash
#8 computes and the `document_id` #8 derives — the importer invents neither (data-model.md).

The skip of §17 is one domain function, `may_skip`, rather than a method each store answers its own
way (R10): two implementations that disagreed about "unchanged" would both pass a suite that let
them define it, and the disagreement would show up as a re-extraction bill. MS-2 and MS-3 hold the
other half — retain twice, no duplicate — and prove it through `recall` rather than through an
inspection method the interface must not have (R9).

### Principle III — Test-First (NON-NEGOTIABLE)

**Complies, and the principle names this feature specifically**: "contract tests for every boundary
in §8" is its stated minimum coverage. Each contract suite is written before the fake that passes
it, each fake is written to make a failing suite pass, and `tasks.md` will order them that way.

Two specifics, because this is where a test-first claim usually goes soft:

* **The suites are watched failing.** Six deliberately broken fakes, one per boundary, each
  violating exactly one rule (R13, contract-suites.md). A contract suite that asserts nothing passes
  quietly and certifies six implementations as correct.
* **"No I/O" is blocked, not observed.** PL-5 monkeypatches the socket and the file-opening paths
  for the duration of the run (R14), and the quickstart states the guard's limits rather than
  implying it is a sandbox.

### Principle IV — Replaceable Boundaries

**Complies; the feature is the principle.** Six interfaces, one responsibility each, mapped one to
one onto §8's rows (FR-001). Protocols rather than base classes mean an implementation does not
import its boundary to satisfy it (R1) — the strongest available statement of the dependency
direction.

Three mechanisms make it checkable rather than asserted:

1. **Vocabulary.** No public name in the memory store interface is a Hindsight term (FR-009,
   MS-10), tested. A method called `retain_items` would satisfy every import check and still bind
   the domain to the engine.
2. **Import graph.** No interface module reaches Hindsight, an HTTP client or a storage library,
   asserted transitively, following the guard #8 already established.
3. **Errors.** No backend exception crosses a boundary (E1): a caller that had to catch
   `httpx.HTTPError` would import the engine's dependency to handle a failure, which is the leak
   Principle IV is written against — and the one that is easiest to miss, because it passes every
   import check on the module that leaks it.

The composability clause is met by the harness: the fakes are composed in §7's order and run
conversation by conversation, with PL-4 asserting one failure does not end the run.

### Principle V — Secrets Never Reach the Memory Engine

**Complies; two choices actively serve it.** The redaction report carries categories and counts and
nothing else (R6, SS-7) — no value, and no offset either, since an offset plus the archived original
reconstructs the secret. And errors carry no content, credential, token or header (E5), with the
chained cause explicitly called out as unsafe to render, because an HTTP client's exception can hold
a URL with a token in it.

This feature writes no redaction pattern — that is #11 — but SS-3 and SS-4 fix what §13 demands of
any sanitizer: the value gone, the surrounding context kept.

Fixtures are synthesized conversations, never real history (CLAUDE.md). Nothing reads `data/`.

### Technology Stack

**Unchanged; no dependency added** (R16). `typing`, `enum` and `hashlib` are standard library;
`FrozenModel` is #8's. No interface declaration library, no mutation-testing tool, no pytest plugin —
each was weighed in research and rejected in favour of what the standard library and the existing
conventions already do.

### Governance

The issue's Governance impact ticks "None of the above", and the design keeps that true — which took
one deliberate decision.

**The module tree is not amended.** A `boundaries/` package would have been the tidy home for six
protocols, and it would have been a constitution amendment: the tree is enforced in both directions,
and "adding a module is an amendment to the constitution first, and a directory second". So each
protocol lives in the module that owns its responsibility, and the import state — which the tree
names no module for — is a *file* inside `ingestion/`, where §17 puts it ("importer side"). R2
records the check that a file inside a recorded package is allowed where a package is not.

The Hindsight contract (§9) is untouched and deliberately unmentioned: MS-11 says a caller cannot
observe whether a large conversation was delivered in parts, which is how §9's append mode stays
the memory store's business. The bank strategy (ADR-002) and the tag convention (§6) are consumed,
not changed.

One consequence worth stating rather than leaving to be discovered: `FILLED_BOUNDARIES` in
`tests/structure/test_module_layout.py` currently matches on a module's first dotted segment, so
filling `memory.interface` by the existing mechanism would exempt `memory/hindsight` from the
behaviour guard — in the very feature whose subject is keeping Hindsight in one place. The guard is
therefore narrowed by dotted prefix instead, and gains a test for the sibling case (R15).

**Gate result: PASS.** No violations, so Complexity Tracking below stays empty.

## Project Structure

### Documentation (this feature)

```text
specs/007-boundary-interfaces/
├── spec.md                       # Feature specification
├── plan.md                       # This file
├── research.md                   # Phase 0 — seventeen decisions and what was weighed
├── data-model.md                 # Phase 1 — the six types the boundaries own
├── contracts/
│   ├── interfaces.md             # the six protocols, their signatures and their rules
│   ├── errors.md                 # the taxonomy, and what an error may never carry
│   └── contract-suites.md        # every rule each suite asserts, by id
├── quickstart.md                 # Phase 1 — how a reviewer verifies the result
├── checklists/
│   └── requirements.md           # Specification quality checklist
└── tasks.md                      # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
src/hermes_memory/
├── errors.py                         # NEW — BoundaryError, Transient…, Permanent…
├── ingestion/
│   ├── source.py                     # NEW — ConversationSource, SourceConversation, source errors
│   └── state.py                      # NEW — ImportState, ImportRecord, ImportStatus, may_skip
├── sanitization/
│   └── sanitizer.py                  # NEW — SecretSanitizer, RedactionReport, RedactionCategory
├── classification/
│   └── classifier.py                 # NEW — ProjectClassifier, UNKNOWN_PROJECT
├── archive/
│   └── interface.py                  # NEW — RawArchive, OriginalPayload, archive errors
└── memory/interface/
    └── store.py                      # NEW — MemoryStore, RecallResult, store errors

tests/contracts/                      # NEW — the reusable suites (R11)
├── source.py, sanitizer.py, classifier.py, archive.py, store.py, state.py
├── conversations.py                  # the synthesized conversations every suite builds on
├── test_fakes_pass_the_contracts.py  # the six fakes subclassed into the six suites
└── test_suites_bite.py               # each suite held against a broken fake (FR-020)

tests/fakes/                          # NEW — in-memory implementations and their breakages (R12)
└── source.py, sanitizer.py, classifier.py, archive.py, store.py, state.py, broken.py

tests/integration/                    # NEW
├── conftest.py                       # the `no_io` guard (R14)
├── pipeline.py                       # the harness — not #19's pipeline
└── test_pipeline_from_fakes.py       # PL-1…PL-6, with network and filesystem blocked

tests/unit/
├── test_errors.py                    # the taxonomy: retryability by type, what an error carries
├── test_error_payloads.py            # what no declared error may carry (E5)
├── test_boundary_values.py           # the types the boundaries own, validated on construction
└── test_import_state_rules.py        # may_skip, the one domain rule this feature owns

tests/structure/
├── test_boundary_interfaces.py       # NEW — import graph and vocabulary guards (FR-026, FR-009)
└── test_module_layout.py             # MODIFIED — FILLED_BOUNDARIES narrowed by dotted prefix (R15)
```

**Structure Decision**: each protocol sits in the module that owns its responsibility, which is the
mapping the constitution already draws between §8's rows and the module tree, and which avoids
amending that tree (R2, Governance above). The errors are a top-level module because they are
consumed by all six boundaries and owned by none — the placement `settings.py` already established
in this repository and which the layout guard's own docstring records the reasoning for.

Tests follow the existing convention — `tests/structure/` for checks about the shape of the
repository, `tests/unit/` for behaviour — and add two directories the repository does not yet have:
`tests/contracts/` for the suites, which belong to a boundary rather than to an implementation, and
`tests/fakes/` for the implementations that prove them. `tests/integration/` holds the one test that
is about six things fitting together rather than about any one of them.

## Phase 0 — Research

See [research.md](./research.md). Seventeen decisions, from where an interface lives to what is
deliberately not built. No `[NEEDS CLARIFICATION]` marker survived the specification, so nothing here
answers an open question; what is recorded is the design the specification deferred.

Two claims were checked by running them rather than reasoning about them: that a file placed inside
a recorded package satisfies the layout checks while a package would not (R2 — six passed, one
failed, and the failure is the behaviour guard R15 answers), and that the suite is green at the
branch point (677 passed).

## Phase 1 — Design

See [data-model.md](./data-model.md) for the six types the boundaries own, and `contracts/` for what
this feature owes its six consumers:

* **[interfaces.md](./contracts/interfaces.md)** — the six protocols, their signatures, and the
  rules beneath each.
* **[errors.md](./contracts/errors.md)** — eight rules (E1–E8) covering what a boundary may raise,
  how retryability is answered, and what an error must never carry.
* **[contract-suites.md](./contracts/contract-suites.md)** — every rule each suite asserts, by id,
  plus the six breakages each suite must be watched catching and the six pipeline rules PL-1–PL-6.

[quickstart.md](./quickstart.md) is how a reviewer verifies all of it, including the steps that make
the suites and the layout guard visibly fail before trusting either.

### Constitution re-check after design

Re-evaluated against all five principles with the design fixed: **PASS, unchanged.** No boundary was
added, moved or merged; no dependency introduced; no I/O path opened; no Hindsight term entered the
vocabulary; the module tree is as the constitution records it.

Three things the design phase sharpened rather than left implied:

1. **Principle I gained a field it would otherwise have lost.** Taking the original payload at the
   archive boundary (R8) was not in the specification's first reading of §8's row; without it,
   Principle I would have been unmeetable by construction and #13 could not have fixed it without
   changing every caller.
2. **Principle IV's leak is an exception type, not an import.** E1 is the rule most likely to be
   broken accidentally — `httpx.HTTPError` escaping `memory/hindsight` passes every import check on
   the modules that catch it — so it is a contract rule with a test per boundary rather than a note.
3. **Principle IV's guard nearly deleted itself.** R15: filling `memory.interface` through the
   existing first-segment match would have exempted `memory/hindsight`. Narrowing by dotted prefix,
   with a test for the sibling case, is the difference between a guard and a green tick.

## What implementation changed

Four things the design did not foresee, each found by writing a test or a fake rather than by
reading, and each recorded where it now lives:

1. **A source yields the conversation with the bytes it came from** (`SourceConversation`). The
   archive takes both forms (R8), and only the source holds the original. The pipeline harness could
   not be written until the two agreed — which is what US3 was for. Recorded in
   [interfaces.md §1](./contracts/interfaces.md) and [data-model.md](./data-model.md).
2. **The source's iterator must survive a `SourceFormatError`**, which rules out a generator. Found
   while writing the fake; CS-5 already required it, and the interface's documentation now says so
   plainly because it is the obvious implementation. The broken fake for CS-5 is that generator.
3. **A skip writes no import record.** §18's `skipped` is the run's report; recording it would
   overwrite an `imported` record and re-import the conversation on the third run. Pinned by
   `test_pl2_a_skip_does_not_overwrite_what_the_state_knew`, and #19 inherits it.
4. **The layout guard filters per file, not per walk root.** A recorded parent (`memory`) rglobs
   into its recorded children, so the dotted-prefix match of R15 alone still reported the filled
   `memory/interface`. The sibling test caught it.

None changes a principle, and the constitution re-check above still holds.

## Complexity Tracking

No constitution violations, so this table is empty.
