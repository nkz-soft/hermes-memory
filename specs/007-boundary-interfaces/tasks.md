# Tasks: Boundary interfaces and their contract tests

**Input**: Design documents from `/specs/007-boundary-interfaces/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Required, not optional. Principle III is non-negotiable and names this feature's
deliverable specifically — "contract tests for every boundary in §8". Every task below that adds a
rule writes its test first and observes it fail.

**Organization**: by user story, in the priority order of [spec.md](./spec.md). The per-boundary
work is deliberately *not* split across phases boundary by boundary: US1 declares all six
interfaces, US2 proves all six, so that "half the boundaries are declared" is never a state the
branch is in.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel — different files, no dependency on an incomplete task
- **[Story]**: US1–US5 from [spec.md](./spec.md)

## Path Conventions

Single project: `src/hermes_memory/`, `tests/` at repository root, per
[plan.md](./plan.md#source-code-repository-root).

---

## Phase 1: Setup

**Purpose**: the three test packages this feature adds, so that later tasks import rather than
create them.

- [x] T001 [P] Create `tests/contracts/__init__.py` with a docstring stating that the modules here
      belong to the boundary, not to any implementation (research R11)
- [x] T002 [P] Create `tests/fakes/__init__.py` with a docstring stating that nothing here ships in
      `src/` and why (research R12, FR-027)
- [x] T003 [P] Create `tests/integration/__init__.py` with a docstring stating that it holds tests
      about several boundaries fitting together

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the error taxonomy every interface declares against, and the layout guard that
otherwise rejects the first line of code placed in a recorded boundary.

**⚠️ CRITICAL**: no interface can be declared until T005 lands — `tests/structure/test_module_layout.py`
fails on any file with behaviour inside `ingestion/`, `sanitization/`, `classification/`, `archive/`
or `memory/interface/`.

- [x] T004 Write `tests/unit/test_errors.py` first and observe it fail: `TransientBoundaryError.retryable`
      is `True` and `PermanentBoundaryError.retryable` is `False` (E2); `retryable` is a `ClassVar`
      that no constructor accepts and no instance can rebind (E3, FR-014); an error carries
      `boundary`, `subject` and `message` and nothing else (E4, FR-015); no error timestamps itself
      (E6)
- [x] T005 Create `src/hermes_memory/errors.py` with `BoundaryError`, `TransientBoundaryError` and
      `PermanentBoundaryError` per [data-model.md](./data-model.md#the-errors--errorspy-and-the-boundary-modules),
      making T004 pass (research R3, R4)
- [x] T006 Narrow the behaviour guard in `tests/structure/test_module_layout.py`: `FILLED_BOUNDARIES`
      matches a recorded module by dotted prefix instead of first segment, and gains `ingestion`,
      `sanitization`, `classification`, `archive` and `memory.interface` — with the docstring
      recording which feature filled each, as the existing entries do (research R15)
- [x] T007 Add `test_filling_a_submodule_does_not_exempt_its_sibling` to
      `tests/structure/test_module_layout.py`: code placed in `memory/hindsight/` is still caught
      while `memory/interface/` is filled. Watch it fail against the first-segment version before
      T006 is in place (research R15)

**Checkpoint**: `uv run pytest tests/unit/test_errors.py tests/structure/test_module_layout.py` is
green, and a file inside a recorded boundary no longer fails the layout guard.

---

## Phase 3: User Story 1 — Six implementations written against a declared interface (Priority: P1) 🎯 MVP

**Goal**: the six protocols of [contracts/interfaces.md](./contracts/interfaces.md), each in the
module that owns its responsibility, with the six types the boundaries own and the errors each
declares.

**Independent Test**: write a trivial second implementation of any one boundary against the
declaration alone and have it type-check and run — which US2 then does six times over.

### Types and declarations

- [x] T008 [P] [US1] Write `tests/unit/test_import_state_rules.py` first and observe it fail:
      `may_skip` is true only for an `imported` record whose `content_hash` matches, and false for
      `None`, for `failed`, for `skipped` and for a changed hash (IS-6, FR-012, research R10)
- [x] T009 [P] [US1] Write `tests/unit/test_boundary_values.py` first and observe it fail: the six
      owned types validate on construction — `RedactionReport` counts are all ≥ 1 and a category
      with none redacted is absent rather than zero; `is_empty` and `total` behave; `ImportRecord.error`
      is present only for `failed`; `OriginalPayload.media_type` is non-empty; `RecallResult.score`
      is optional (data-model.md)
- [x] T010 [P] [US1] Create `src/hermes_memory/ingestion/source.py`: `ConversationSource` protocol
      (`source: Source`, `read() -> Iterator[SourceConversation]`), `SourceFormatError` (permanent) and
      `SourceUnavailable` (transient), documented against §8 and §18
- [x] T011 [P] [US1] Create `src/hermes_memory/sanitization/sanitizer.py`: `SecretSanitizer`
      protocol (`sanitize(conversation) -> tuple[Conversation, RedactionReport]`), `RedactionReport`,
      `RedactionCategory` seeded with §13's minimum list — `api-key`, `bearer-token`, `jwt`,
      `github-token`, `gitlab-token`, `anthropic-key`, `openai-key`, `aws-access-key`,
      `private-key`, `password`, `connection-string`, `dotenv-value`, `kubernetes-secret` — and
      `SanitizationError` (permanent). The report carries counts only, never a value or an offset
      (research R6, Principle V)
- [x] T012 [P] [US1] Create `src/hermes_memory/classification/classifier.py`: `ProjectClassifier`
      protocol (`classify(conversation) -> ProjectTag`) and `UNKNOWN_PROJECT`. No error type is
      declared, and the docstring says why (E8, §15, research R7)
- [x] T013 [P] [US1] Create `src/hermes_memory/archive/interface.py`: `RawArchive` protocol
      (`store(enriched, original)`, `load(document_id)`, `load_original(document_id)`),
      `OriginalPayload` (`content: bytes`, `media_type`), `ArchiveDocumentNotFound` and
      `ArchiveRejected` (permanent), `ArchiveUnavailable` (transient) (research R8, Principle I)
- [x] T014 [P] [US1] Create `src/hermes_memory/memory/interface/store.py`: `MemoryStore` protocol
      (`retain(enriched)`, `recall(query, tags=(), limit=None)`), `RecallResult`
      (`content`, `provenance`, `score: float | None`), `MemoryStoreRejected` (permanent) and
      `MemoryStoreUnavailable` (transient). No name in the module is a Hindsight term (FR-009,
      research R9)
- [x] T015 [P] [US1] Create `src/hermes_memory/ingestion/state.py`: `ImportState` protocol
      (`record(record)`, `find(source, source_id) -> ImportRecord | None`), `ImportRecord`,
      `ImportStatus` (`imported`/`skipped`/`failed`), `may_skip`, `ImportStateCorrupt` (permanent)
      and `ImportStateUnavailable` (transient), making T008 pass (research R10)
- [x] T016 [US1] Export each boundary's public names from its module's `__init__.py`
      (`ingestion`, `sanitization`, `classification`, `archive`, `memory/interface`) with `__all__`,
      keeping each docstring's statement of which §8 row it is

**Checkpoint**: all six interfaces exist and import cleanly; `uv run pytest tests/unit -q` is green.

---

## Phase 4: User Story 2 — An implementation is proved by a suite it did not write (Priority: P1)

**Goal**: the six reusable contract suites of
[contracts/contract-suites.md](./contracts/contract-suites.md), the six in-memory fakes that pass
them, and the six breakages that prove the suites bite.

**Independent Test**: point a suite at its fake and watch it pass; point it at the matching broken
fake and watch it fail on exactly the rule named in the table.

### The suites (written before the fakes)

- [x] T017 [P] [US2] Write `tests/contracts/source.py` — `ConversationSourceContract` with one test
      per rule CS-1…CS-7 and an abstract factory `make_source(conversations)`, plus optional hooks
      for the unreadable-conversation and unreachable-export cases
- [x] T018 [P] [US2] Write `tests/contracts/sanitizer.py` — `SecretSanitizerContract`, rules
      SS-1…SS-8, factory `make_sanitizer()`
- [x] T019 [P] [US2] Write `tests/contracts/classifier.py` — `ProjectClassifierContract`, rules
      PC-1…PC-5, factory `make_classifier()`
- [x] T020 [P] [US2] Write `tests/contracts/archive.py` — `RawArchiveContract`, rules RA-1…RA-9,
      factory `make_archive()`
- [x] T021 [P] [US2] Write `tests/contracts/store.py` — `MemoryStoreContract`, rules MS-1…MS-11,
      factory `make_store()`
- [x] T022 [P] [US2] Write `tests/contracts/state.py` — `ImportStateContract`, rules IS-1…IS-8,
      factory `make_state()`
- [x] T023 [US2] Add `tests/contracts/conversations.py`: the synthesized conversations every suite
      builds on — one minimal, one exercising every optional field of #8's model, one carrying a
      recognizable fake secret. Never real history (CLAUDE.md)

> **Observe the suites fail here.** With no fake to run them against, add a temporary empty
> implementation per boundary, watch every rule fail, and delete it. Record the failure counts in
> the implementation notes — this is the red state Principle III requires and it is invisible later.

### The fakes

- [x] T024 [P] [US2] `tests/fakes/source.py` — `InMemoryConversationSource` over a tuple, with a
      constructor option that makes one conversation unreadable (CS-5) and one that makes the export
      unreachable (CS-6)
- [x] T025 [P] [US2] `tests/fakes/sanitizer.py` — `InMemorySecretSanitizer` replacing one known
      marker with `[REDACTED]` and reporting it under a §13 category, preserving surrounding text
- [x] T026 [P] [US2] `tests/fakes/classifier.py` — `InMemoryProjectClassifier` over an alias map,
      returning `UNKNOWN_PROJECT` for anything unmapped
- [x] T027 [P] [US2] `tests/fakes/archive.py` — `InMemoryRawArchive` keyed by document id, holding
      both forms, idempotent on re-store, with switches for the unavailable and rejected cases
- [x] T028 [P] [US2] `tests/fakes/store.py` — `InMemoryMemoryStore` with substring recall, tag
      narrowing, `limit`, replace-on-retain, and switches for the rejected and unavailable cases
- [x] T029 [P] [US2] `tests/fakes/state.py` — `InMemoryImportState` keyed by `(source, source_id)`,
      last write wins, recording failures
- [x] T030 [US2] `tests/contracts/test_fakes_pass_the_contracts.py` — six subclasses binding each
      fake to its suite; all six pass (SC-002)

### The suites are watched failing

- [x] T031 [P] [US2] `tests/fakes/broken.py` — six deliberately broken implementations, each
      violating exactly one rule: a source that stops at the first unreadable conversation (CS-5), a
      sanitizer reporting a redaction it did not make (SS-3), a classifier that raises instead of
      answering `project:unknown` (PC-2), an archive that drops message timestamps (RA-1), a store
      that appends on re-retain (MS-2), an import state that records only successes (IS-4)
- [x] T032 [US2] `tests/contracts/test_suites_bite.py` — one test per boundary, calling the rule's
      contract method directly inside `pytest.raises(AssertionError)`, asserting the suite rejects
      the breakage (FR-020, SC-003, research R13)

**Checkpoint**: `uv run pytest tests/contracts tests/fakes -q` green; every suite has been seen both
passing and failing.

---

## Phase 5: User Story 3 — The pipeline is assembled before any of its parts exists (Priority: P1)

**Goal**: §7's sequence composed from the six fakes, running end to end with the network and the
filesystem blocked.

**Independent Test**: run the harness and read the four assertions PL-1…PL-3 and PL-5.

- [x] T033 [US3] Add the I/O guard fixture to `tests/integration/conftest.py`: monkeypatch
      `socket.socket`, `builtins.open`, `pathlib.Path.open`, `Path.write_text` and
      `Path.write_bytes` to raise, and document what it does not cover — `os.open`, C extensions
      (research R14)
- [x] T034 [US3] Write `tests/integration/test_pipeline_from_fakes.py` first and observe it fail:
      PL-1 — one synthesized conversation is sanitized, classified, enriched, archived, retained and
      recorded
- [x] T035 [US3] Extend it with PL-2 and PL-3: a second run over unchanged content reaches neither
      archive nor store and the import state is what decided it; changed content reaches both under
      the same `document_id` (§17, §10, SC-005)
- [x] T036 [US3] Extend it with PL-5: the whole run performs no network call and no filesystem
      write, blocked rather than unobserved (SC-004)
- [x] T037 [US3] Implement the harness the tests compose — the smallest arrangement of the six
      boundaries in §7's order, living in the test module. It is not #19's pipeline and the
      docstring says so (FR-027)

**Checkpoint**: `uv run pytest tests/integration -q` green. The issue's own acceptance statement is
now satisfied.

---

## Phase 6: User Story 4 — One conversation fails and the run continues (Priority: P2)

**Goal**: the error semantics are not only declared but exercised — a failure that is typed,
classifiable and survivable.

**Independent Test**: make one conversation fail transiently and another permanently, and watch the
run classify both, continue, and report them with their source ids.

- [x] T038 [US4] Extend `tests/integration/test_pipeline_from_fakes.py` with PL-4: a conversation
      failing one stage does not stop the run, the others are imported, and the failure is reported
      with its source id (§18)
- [x] T039 [US4] Record the failure in the import state as `failed` in that test, and assert a
      `failed` record is distinguishable from no record on the next run (IS-4, research R10)
- [x] T040 [P] [US4] Add `tests/unit/test_error_payloads.py`: no declared error carries conversation
      content, a credential, a token or an authorization header, and the memory store's errors
      document the chained cause as unsafe to render (E5, FR-016, §19)
- [x] T041 [P] [US4] Add to `tests/structure/test_boundary_interfaces.py` the assertion that every
      error type declared by a boundary module derives from `TransientBoundaryError` or
      `PermanentBoundaryError` — a new error cannot be added outside the taxonomy (E1, E2)

**Checkpoint**: a run survives a failure, and the failure is typed rather than described.

---

## Phase 7: User Story 5 — The memory engine is replaced without touching ingestion (Priority: P2)

**Goal**: the exit strategy of ADR-001 demonstrated rather than asserted.

**Independent Test**: swap the store fake and rerun the pipeline tests unchanged.

- [x] T042 [US5] Add a second, differently-implemented memory store fake to `tests/fakes/store.py`
      (for example one that indexes by tag rather than scanning), and bind it to
      `MemoryStoreContract` in `tests/contracts/test_fakes_pass_the_contracts.py`
- [x] T043 [US5] Add PL-6 to `tests/integration/test_pipeline_from_fakes.py`: the pipeline
      parametrized over both stores, with only the composition line differing (SC-006)
- [x] T044 [US5] Write `tests/structure/test_boundary_interfaces.py` first and observe it fail: no
      interface module's transitive import graph reaches Hindsight, an HTTP client or a storage
      library, following the guard `tests/structure/test_normalization_boundary.py` already
      establishes (FR-026, SC-007)
- [x] T045 [US5] Add the vocabulary assertion to the same file: no public name in any of the six
      interface modules is a Hindsight term — bank, item, retain mission, update mode, operation id,
      endpoint (FR-009, MS-10)
- [x] T046 [US5] Prove that guard bites: a test that adds a forbidden import and a Hindsight-named
      public symbol to a synthesized module and observes both assertions fail (the repository's
      `test_the_behaviour_guard_still_bites` convention)

**Checkpoint**: Hindsight is provably confined, and replacing it is a one-line change in a test.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [x] T047 [P] Check every rule id of [contracts/contract-suites.md](./contracts/contract-suites.md)
      has exactly one test, and every test names its rule id — add the missing ones rather than
      editing the contract
- [x] T048 [P] Run `uv run ruff check .` and `uv run ruff format --check .` and fix what they report
- [x] T049 Walk [quickstart.md](./quickstart.md) end to end as a reviewer would, running each
      command and confirming its stated outcome; correct the quickstart where reality differs
- [x] T050 Re-read [plan.md](./plan.md#constitution-check) against the finished branch and confirm
      each principle's claim is still true of the code, amending the plan if the design moved

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: T005 blocks every interface task; T006 blocks every file placed in a
  recorded boundary — which is all of Phase 3
- **US1 (Phase 3)**: after Phase 2. Blocks US2, since a suite tests an interface
- **US2 (Phase 4)**: after US1. Blocks US3, since the harness composes the fakes
- **US3 (Phase 5)**: after US2
- **US4 (Phase 6)**: after US3 for PL-4; T040 and T041 need only Phase 3
- **US5 (Phase 7)**: after US2 for T042–T043; T044–T046 need only Phase 3
- **Polish (Phase 8)**: last

### Within each story

Test first, failing, then the code that makes it pass. No task is done with a test that has never
been red (Principle III).

### Parallel Opportunities

- T001–T003 together
- T010–T015: six interface modules, six files, no shared state
- T017–T022: six contract suites, six files
- T024–T029: six fakes, six files
- T040, T041 alongside T038–T039
- T044–T046 alongside T042–T043

---

## Parallel Example: User Story 1

```bash
# The six declarations, once T005 and T006 are in place:
Task: "Create src/hermes_memory/ingestion/source.py"
Task: "Create src/hermes_memory/sanitization/sanitizer.py"
Task: "Create src/hermes_memory/classification/classifier.py"
Task: "Create src/hermes_memory/archive/interface.py"
Task: "Create src/hermes_memory/memory/interface/store.py"
Task: "Create src/hermes_memory/ingestion/state.py"
```

---

## Implementation Strategy

### MVP scope

US1 plus US2 — six declared interfaces and six suites proving them, with fakes that pass. That is
what unblocks #10 through #16, and it is the smallest thing that does: an interface without a suite
is a suggestion.

US3 is the issue's stated acceptance and follows immediately; it is separated only because it cannot
be written before the fakes exist.

### Incremental delivery

1. Phases 1–2 → the taxonomy exists and the layout guard permits code in the boundaries
2. Phase 3 → six interfaces; #10–#16 could start reading them
3. Phase 4 → six suites and six fakes; #10–#16 could start writing against them
4. Phase 5 → the pipeline composes; the issue's acceptance criterion is met
5. Phases 6–7 → failures survive and the engine is provably replaceable
6. Phase 8 → the quickstart is true

### Notes

- Commit per task or per coherent group; the branch carries one pull request
- No task adds a dependency (research R16), and none implements a boundary for real (FR-027) — the
  temptation is the in-memory archive, which stays in `tests/fakes/`
