---

description: "Task list for the normalized conversation model"
---

# Tasks: Normalized conversation model

**Input**: Design documents from `/specs/006-normalized-conversation-model/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Required, and required *first*. Principle III of the constitution is non-negotiable and
NFR-002 restates it for this feature: every rule a test can assert has one, written before the
implementation and observed to fail. A task that writes implementation before its test is not done
differently — it is not done.

**Organization**: Tasks are grouped by the user stories of `spec.md`, so each can be implemented and
verified on its own.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: The user story the task serves (US1–US4)
- Every task names the exact file it touches

## Path Conventions

Single project: `src/hermes_memory/` and `tests/` at the repository root, per
[plan.md](./plan.md#project-structure).

---

## Phase 1: Setup

**Purpose**: Make room for an implementation inside a boundary the suite currently holds empty.

- [x] T001 Add `"normalization"` to `FILLED_BOUNDARIES` in `tests/structure/test_module_layout.py`,
  with a comment naming this feature alongside the existing `observability` and `cli` entries
  (research R13). Without it, the first source file added below turns
  `test_recorded_modules_carry_no_behaviour` red — and that guard is meant to be edited
  deliberately, not discovered.

**Checkpoint**: `uv run pytest` is still green, and the boundary is open for code.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The value semantics every entity shares. Nothing in Phase 3+ can be written before
this exists.

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

- [x] T002 Write the failing tests for the shared value semantics in `tests/unit/test_base.py`:
  a model is frozen (assignment raises), forbids extra fields, rejects a naive datetime
  (`AwareDatetime`, research R5), rejects an opaque identifier that is empty or contains whitespace
  or a control character (research R10), and rejects a slug outside `[a-z0-9][a-z0-9._-]*`
  (research R9). Run them and record that they fail.
- [x] T003 Implement `src/hermes_memory/normalization/base.py` — the frozen base
  (`model_config = ConfigDict(frozen=True, extra="forbid")`, research R7), the opaque-identifier
  type and the slug type — until T002 passes.
- [x] T004 Record the addition of `base.py` in [plan.md](./plan.md#source-code-repository-root) and
  in [research.md](./research.md) R14, with the reason: the frozen configuration and the two
  validated string types are shared by `conversation.py`, `provenance.py` and `tags.py`, and putting
  them in any one of those three would make the other two import it for a reason unrelated to what
  that file is about. The constitution requires a deviation from a committed plan to be justified in
  writing, so this is written where the plan is, not only in a commit message.

**Checkpoint**: The shared semantics exist and are tested. User stories can begin.

---

## Phase 3: User Story 1 — The boundary author declares six interfaces in one vocabulary (P1) 🎯 MVP

**Goal**: The entities of [data-model.md](./data-model.md) exist, validate, and are exported — so
#9 can declare the six boundaries of §8 against them without inventing a type.

**Independent Test**: Write the six signatures against the module in a scratch file. No boundary
needs a type it has to invent, and none needs a dictionary or a free-form string to carry a field
the architecture requires.

### Tests for User Story 1 ⚠️ Write first, observe failing

- [x] T005 [P] [US1] Write the failing tests for the conversation tree in
  `tests/unit/test_conversation.py`: `Source` renders `chatgpt`, `claude-chat`, `claude-code`,
  `codex`, `hermes` and rejects anything else (FR-004); `Role` is closed over `user`, `assistant`,
  `system`, `tool` (FR-005); `NonTextKind` is closed over `image`, `file`, `audio`, `other`; message
  order is the tuple's order and is never re-derived from timestamps (FR-003, research R6); a
  conversation with no messages is valid; `title` may be absent or empty; `sent_at` may be absent and
  has no default (FR-007); `last_activity_at` may be absent and, when present, is not earlier than
  `started_at`; a `ToolActivity` with no `result` is valid; every entity is immutable (research R7).
- [x] T006 [P] [US1] Write the failing tests for the §6 tag convention in `tests/unit/test_tags.py`:
  each of the four namespaces renders exactly `namespace:value`; `source` takes a `Source` and
  `type` a `ConversationType` (`conversation`, `coding-session`, `decision`, `troubleshooting`);
  `project` and `user` take a slug matching `[a-z0-9][a-z0-9._-]*`; `project:unknown` is an ordinary
  value (§15); a value that would render a malformed tag is rejected (FR-010).
- [x] T007 [P] [US1] Write the failing tests for provenance and the enrichment record in
  `tests/unit/test_provenance.py`: every §3.3 field is present and typed — `source`, `source_id`,
  `project`, `repository` (optional), `title` (optional), `imported_at`, `importer_version`
  (non-empty); `imported_at` appears here and nowhere else in the model (§11, FR-007);
  `EnrichedConversation` rejects a provenance whose `source` or `source_id` disagrees with its
  conversation, and rejects duplicate tags; its `document_id` and `content_hash()` delegate to the
  conversation.

### Implementation for User Story 1

- [x] T008 [P] [US1] Implement `src/hermes_memory/normalization/conversation.py` — `Source`, `Role`,
  `NonTextKind`, `NonTextPart`, `ToolActivity`, `Message`, `Conversation` — until T005 passes. Field
  types and rules are quoted in [data-model.md](./data-model.md); `messages` is
  `tuple[Message, ...]`, `text` may be empty, `source_id` is the opaque identifier type from T003.
- [x] T009 [P] [US1] Implement `src/hermes_memory/normalization/tags.py` — `TagNamespace`,
  `ConversationType`, `Tag` and the four concrete forms, rendering through one method — until T006
  passes.
- [x] T010 [US1] Implement `src/hermes_memory/normalization/provenance.py` — `Provenance` and
  `EnrichedConversation` — until T007 passes. Depends on T008 and T009.
- [x] T011 [US1] Fill `src/hermes_memory/normalization/__init__.py`: re-export exactly the names in
  [contracts/module-boundary.md](./contracts/module-boundary.md) and declare `__all__`. The module
  docstring states what the boundary is, citing §7 and §8.

**Checkpoint**: The vocabulary exists and is importable from the module. #9 is unblocked.

---

## Phase 4: User Story 2 — The importer skips an unchanged conversation without paying for it (P1)

**Goal**: A deterministic content hash covering exactly what ADR-006 decision 4 says it covers, and
a `document_id` that cannot be generated.

**Independent Test**: Build the same conversation in two separate processes and compare digests;
change a message, then change only the title, and observe which digest moves.

### Tests for User Story 2 ⚠️ Write first, observe failing

- [x] T012 [P] [US2] Write the failing tests for document identity in
  `tests/unit/test_conversation.py`: `document_id` is `<source>:<native id>` (§10), is identical on
  repeated derivation, and cannot be supplied — construction with a `document_id` argument fails
  under `extra="forbid"` (FR-006, Principle II). A native id containing a colon is accepted and the
  id is never split back apart (research R10).
- [x] T013 [P] [US2] Write the failing tests for the canonical form and the hash in
  `tests/unit/test_canonical.py`, one per guarantee in
  [contracts/canonical-form.md](./contracts/canonical-form.md): C1 equal hashes for structurally
  identical conversations; C2 a changed message text, role, position or timestamp moves the hash;
  C3 changed tool activity or a changed non-text part moves it; C4 a changed title does not; C5 a
  changed provenance field or tag does not; C6 one instant at two UTC offsets hashes equal; C7 a
  whole-second timestamp and one with microseconds render in the same shape; C8 a conversation with
  no messages has a defined hash; C9 the payload carries `"version": 1` and its bytes are produced
  with `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`, UTF-8. Assert C1, C6 and C9
  in a **subprocess** as well as in-process — a determinism claim checked inside one interpreter is
  not a determinism claim (plan, Principle III).
- [x] T014 [P] [US2] Write the failing test that non-ASCII text survives the canonical form as text
  rather than as escapes, in `tests/unit/test_canonical.py` (research R2). The corpus is
  substantially non-ASCII, and the fixture is a synthesized conversation, never real history
  (CLAUDE.md).

### Implementation for User Story 2

- [x] T015 [US2] Implement `src/hermes_memory/normalization/canonical.py` — `canonical_form` and
  `content_hash` — until T013 and T014 pass. The included fields are written out by name, never
  derived from a model dump (research R1); timestamps convert with `astimezone(UTC)` and render
  `%Y-%m-%dT%H:%M:%S.%fZ`, an absent one as `null` (research R4); the digest is
  `hashlib.sha256(...).hexdigest()` (research R3).
- [x] T016 [US2] Wire `Conversation.document_id`, `Conversation.canonical_form()` and
  `Conversation.content_hash()` in `src/hermes_memory/normalization/conversation.py` until T012
  passes, and export `canonical_form` and `content_hash` from
  `src/hermes_memory/normalization/__init__.py`.

**Checkpoint**: The §17 skip has the value it depends on, and it is stable across processes.

---

## Phase 5: User Story 3 — The archive round-trips a conversation years later (P2)

**Goal**: The normalized form survives serialization and re-parsing unchanged, and a malformed
record fails loudly instead of parsing into a partial object.

**Independent Test**: Serialize a conversation exercising every field, re-parse it, compare.

### Tests for User Story 3 ⚠️ Write first, observe failing

- [x] T017 [P] [US3] Write the failing tests in `tests/unit/test_serialization.py`: a conversation
  using every field — tool activity, a message with no timestamp, an empty title, a non-text part,
  non-ASCII text — serializes and re-parses equal to the original with an equal content hash (B3,
  FR-014, SC-002); the same holds for `Provenance` and `EnrichedConversation`.
- [x] T018 [P] [US3] Write the failing tests for parse failures in
  `tests/unit/test_serialization.py`: a record missing a required field, carrying a value outside a
  closed vocabulary, carrying a naive timestamp, or carrying an unknown field, raises an error whose
  message names the field (B4, FR-015).

### Implementation for User Story 3

- [x] T019 [US3] Make T017 and T018 pass. Where a test passes against the implementation already
  written in Phase 3 — Pydantic supplies much of this — say so in the test's docstring: what the
  test pins is then recorded as a guarantee this module owes rather than as an accident of the
  library, which is the difference between a test and a coincidence.

**Checkpoint**: Principle I's promise — re-runnable from the archive alone — is mechanically true.

---

## Phase 6: User Story 4 — The reviewer rejects a Hindsight leak by pointing at a test (P2)

**Goal**: Principle IV's boundary fails a test rather than an argument.

**Independent Test**: Add `import httpx` to a file under `src/hermes_memory/normalization/` and
watch both guards fail; remove it again.

### Tests for User Story 4 ⚠️ Write first, observe failing

- [x] T020 [US4] Write the static import guard in
  `tests/structure/test_normalization_boundary.py`: parse every `.py` under
  `src/hermes_memory/normalization/` with `ast`, collect the root of every import, and assert the
  set falls inside the allowlist of
  [contracts/module-boundary.md](./contracts/module-boundary.md) — the standard library, `pydantic`,
  and the module itself. The failure message names the file and the offending import.
- [x] T021 [US4] Write the runtime import guard in the same file: import
  `hermes_memory.normalization` in a subprocess and assert no forbidden name appears in that
  process's `sys.modules` — `hermes_memory.memory.*`, `httpx`, `requests`, `urllib.request`,
  `aiohttp`, `sqlalchemy`, `sqlite3`, `boto3`, `hermes_memory.settings` (FR-016, FR-018,
  research R12).
- [x] T022 [US4] Write the test that proves both guards bite, in the same file, following the
  precedent of `test_the_behaviour_guard_still_bites` in
  `tests/structure/test_module_layout.py`: build a source tree holding a forbidden import and
  assert the static guard reports it. A guard nobody has watched fail is a guard nobody knows is
  working (plan, Principle III).
- [x] T023 [US4] Write the test that `__all__` and the module's actual public attributes agree, in
  the same file, so a name added without being exported — or exported without existing — fails
  rather than drifting (contracts/module-boundary.md).
- [x] T024 [US4] Write the test that no public name is a Hindsight term, in the same file: assert
  no exported name matches `bank`, `retain`, `recall`, `hindsight`, `update_mode` or `item`
  (FR-017, ADR-001 exit strategy).

### Implementation for User Story 4

- [x] T025 [US4] Make T020–T024 pass. If a guard passes the moment it is written because the module
  is already clean, T022 is what supplies the observed failure — record in the commit which of the
  two it was, rather than claiming a red-green cycle that did not happen.

**Checkpoint**: The boundary of ADR-001's exit strategy is enforced by the suite.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [x] T026 [P] Write the module and class docstrings required by NFR-001 across
  `src/hermes_memory/normalization/*.py`, each citing the architecture section its rule comes from
  (§3.3, §6, §7, §8, §10, §11, §17, ADR-006), so a later reader changing a field sees what it was
  holding up.
- [x] T027 Run `uv run ruff check .` and `uv run ruff format --check .` and fix what they report.
- [x] T028 Run the full suite: `uv run pytest`. Every pre-existing test stays green — this feature
  changes exactly one line of an existing test file, in T001.
- [x] T029 Walk [quickstart.md](./quickstart.md) end to end, including step 5, where the Principle
  IV guard is made to fail on purpose and then restored, and step 6, which proves the module is
  usable with no configuration and no service.
- [x] T030 Confirm `git diff --stat origin/main...HEAD` is confined to
  `src/hermes_memory/normalization/`, `tests/`, `specs/006-normalized-conversation-model/` and the
  single deliberate line in `tests/structure/test_module_layout.py` (SC-007). In particular
  `pyproject.toml` is untouched: this feature adds no dependency.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (T001)**: no dependencies; must come first, or the first source file turns the suite red.
- **Foundational (T002–T004)**: depends on Setup. **Blocks every user story.**
- **US1 (T005–T011)**: depends on Foundational. Blocks US2, US3 and US4 — there is nothing to hash,
  serialize or guard until the entities exist.
- **US2 (T012–T016)**: depends on US1.
- **US3 (T017–T019)**: depends on US1. Independent of US2, except that the round-trip also asserts
  hash equality, so it is verified in full once US2 lands.
- **US4 (T020–T025)**: depends on US1 for there to be a module to guard.
- **Polish (T026–T030)**: depends on everything above.

### Within each story

Tests are written and observed failing before the implementation that satisfies them. Vocabularies
before the entities that use them; entities before the canonical form over them.

### Parallel Opportunities

- T005, T006, T007 — three test files, no shared state.
- T008 and T009 — `conversation.py` and `tags.py` are independent; `provenance.py` (T010) needs both.
- T013 and T014 — the same file, so in practice one after the other; listed [P] because neither
  depends on the other's outcome.
- T017 and T018 — likewise.
- US3 and US4 can proceed in parallel once US1 is complete.

## Parallel Example: User Story 1

```bash
# The three failing test files, written together:
Task: "Failing tests for the conversation tree in tests/unit/test_conversation.py"
Task: "Failing tests for the §6 tag convention in tests/unit/test_tags.py"
Task: "Failing tests for provenance in tests/unit/test_provenance.py"

# Then the two independent implementations:
Task: "Implement src/hermes_memory/normalization/conversation.py"
Task: "Implement src/hermes_memory/normalization/tags.py"
```

## Implementation Strategy

### MVP scope

**US1 alone is the MVP** — the vocabulary exists and is exported, which is what unblocks #9 and
through it the rest of Phase 1. It is worth stopping there to validate, because a shape wrong at
that point is a shape six issues inherit.

US2 is marked P1 alongside it because the hash is what Principle II's no-duplicate-extraction
guarantee rests on, and nothing downstream can be written against a hash that does not exist.

### Incremental delivery

1. Setup + Foundational → the shared semantics are tested.
2. US1 → **stop and validate**: the six signatures of #9 can be written. MVP.
3. US2 → the §17 skip has its value.
4. US3 and US4 → the archive's guarantee and the boundary's guard, in either order.
5. Polish → documentation, lint, quickstart, diff confinement.

---

## Phase 8: After code review

A review of the finished branch raised five issues worth acting on before a human reads it. All
five are done; what they changed is recorded here rather than only in commit messages, because
three of them changed a written decision rather than code.

- [x] T031 Record why the conversation's own timestamps are outside the content hash, in
  [contracts/canonical-form.md](./contracts/canonical-form.md), [research.md](./research.md) R11 and
  `canonical.py`. ADR-006 decision 4 names the *messages'* timestamps and excludes the title and
  importer-produced metadata; `started_at` is none of those, so the exclusion was this feature's
  decision being passed off as the ADR's. The rationale first given — "the key the hash is filed
  under" — is true of the source and native id and false of a start time. The exclusion stands, the
  consequence is now stated, and changing the trade is named as an amendment to ADR-006.
- [x] T032 Make `FrozenModel.model_copy(update=...)` revalidate, in
  `src/hermes_memory/normalization/base.py`, with tests in `tests/unit/test_base.py`. `frozen=True`
  stops assignment but not that call, which skipped every validator — and §7's sanitizer (#12)
  returns a rewritten conversation, so it is exactly the door the next feature would have walked
  through, into the archive Principle I makes the source of truth.
- [x] T033 Refuse text that cannot be encoded, via the new `Text` type used by every text field.
  An unpaired surrogate survives `json.loads`, constructs happily, and then breaks the content hash
  mid-import with a codec error naming neither the conversation nor the field.
- [x] T034 Validate the tags against what they scope, in
  `src/hermes_memory/normalization/provenance.py`: a `source:` tag must match the conversation's
  source and a `project:` tag the provenance's project. The same argument the provenance check
  already made, one field over — a wrong tag files a conversation where nobody will look for it.
- [x] T035 Add `AnyTag` to [contracts/module-boundary.md](./contracts/module-boundary.md), which
  claims to list the public surface exactly and did not have it.
- [x] T036 Harden the minor findings: `socket`, `http.client`, `shelve` and `dbm` added to the
  boundary guard's forbidden list; the year formatted without `strftime`, whose `%Y` padding is
  platform-dependent; two assertions that passed trivially replaced (`document_id` stability is now
  derived in a subprocess, and a chained `!=` split into real comparisons); an explicit UTC-offset
  assertion added to the round trip, which equality alone cannot see.
- [x] T037 Make SC-001 real instead of asserted, in `tests/unit/test_boundary_vocabulary.py`: the
  six boundaries of §8 declared against this model and run as a pipeline of in-memory fakes,
  including the §17 skip on a second run. Its wording in [spec.md](./spec.md) is corrected too — as
  written it forbade "any additional type", which the sanitizer's report and the import state's
  record would breach on the day they are built.

## Notes

- Commit per task or per logical group; the message says what was tested before what was written.
- Every fixture is a synthesized conversation. No real history, no credential, no token reaches a
  test file, an issue or a commit message (CLAUDE.md).
- No task adds a dependency. If one appears to need one, that is a plan change requiring a written
  justification, not a quiet line in `pyproject.toml` (constitution, Technology Stack).
