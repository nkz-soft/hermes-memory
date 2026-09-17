# Tasks: ChatGPT export source

**Input**: Design documents from `/specs/008-chatgpt-export-source/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/chatgpt-source.md](./contracts/chatgpt-source.md)

**Tests**: Required. Principle III is non-negotiable and names "unit tests for the source parser"
specifically. Every task that adds behaviour is preceded by a task that writes its test. That test
must be run and **observed failing** before the implementation task starts.

**Organization**: by user story, in the priority order of [spec.md](./spec.md). The I/O layer
(locating files, streaming records) is foundational because every story reads an export through it.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel — different files, no dependency on an incomplete task
- **[Story]**: US1–US5 from [spec.md](./spec.md)

## Path Conventions

Single project: `src/hermes_memory/ingestion/chatgpt/`, `tests/` at repository root, per
[plan.md](./plan.md#source-code-repository-root).

---

## Phase 1: Setup

**Purpose**: the test package the synthesized export writer lives in, and the static guard for the
new package.

- [X] T001 [P] Create `tests/synthetic/__init__.py` with a docstring stating that it builds
      synthesized inputs, never real history (CLAUDE.md), and is neither a fake nor a contract
- [X] T002 [P] Write `tests/structure/test_chatgpt_source_imports.py`: every `.py` under
      `src/hermes_memory/ingestion/chatgpt/` imports only the standard library, `pydantic`,
      `hermes_memory.errors`, `hermes_memory.normalization`, `hermes_memory.archive.interface`,
      `hermes_memory.ingestion.source`, `hermes_memory.ingestion.chatgpt.*` and
      `hermes_memory.observability`. Nothing on `FORBIDDEN_AT_RUNTIME` of
      `tests/structure/test_boundary_interfaces.py` is allowed; reuse that list by import. Also
      assert that `hermes_memory/ingestion/__init__.py` does not import `chatgpt`, so that importing
      the interface loads no implementation. It passes vacuously on the empty package; include a
      "still bites" test against a `tmp_path` package holding `import httpx`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the synthesized export writer, locating conversation files, and the streaming scanner.
No story can read an export without these.

- [X] T003 Create `tests/synthetic/chatgpt_export.py`, the test-only writer (research R11). It has:
      builders `node(id, parent, children, message=None)`,
      `message(role, parts=..., content_type="text", create_time=None, recipient="all",
      author_name=None, hidden=False, attachments=(), **content)` and
      `record(conversation_id, mapping, current_node, title=..., create_time=..., update_time=...)`;
      `linear_record(conversation_id, turns)`, which builds root → turns with `current_node` set;
      `from_conversation(Conversation) -> dict`, which renders #8's model as a linear record,
      folding `ToolActivity` into call + tool nodes per research R6; and
      `write_directory(path, records, *, split=False)` and `write_zip(path, records, *, split=False)`,
      which write `conversations.json`, or `conversations-000.json`…, with `json.dumps(...,
      ensure_ascii=False)`. All text is invented
- [X] T004 [P] Write `tests/unit/test_chatgpt_export.py` first and observe it fail. Opening yields
      text streams for `conversations.json` from a directory, a `.zip` and the file path itself.
      A split export yields `conversations-000.json`, `-001`, `-010` in numeric order. A missing
      path raises `SourceUnavailable`. A path that is neither zip, directory nor JSON file, a
      corrupt zip, no conversation file, or both single and split forms raise `SourceFormatError`
      with `subject is None`. Every raised error chains its cause (research R2, R10)
- [X] T005 Implement `src/hermes_memory/ingestion/chatgpt/export.py`: `conversation_files(path)`
      resolves and orders the files, and `open_text(...)` opens each as a UTF-8 text stream
      (`zipfile.ZipFile.open` wrapped in `io.TextIOWrapper` for archives), translating `OSError`
      to `SourceUnavailable` and `BadZipFile` / layout problems to `SourceFormatError`. Makes T004
      pass
- [X] T006 [P] Write `tests/unit/test_chatgpt_records.py` first and observe it fail. The scanner
      yields each array element's decoded value and its **exact raw text slice**, including
      non-ASCII and escaped text. It gives the same results with a chunk size of 1, 7 and 64 KiB,
      proving boundaries mid-string and mid-escape are handled. A leading `﻿` is tolerated,
      `[]` and whitespace-only arrays yield nothing, and a record containing `]`, `,` and braces
      inside strings is parsed correctly. A top level that is not an array, or truncated or invalid
      JSON, raises `SourceFormatError` without subject after yielding every earlier record. Two
      records of 1 MiB with a 64 KiB chunk decode with a number of `raw_decode` calls logarithmic
      in the record size (research R3; count calls through an injectable decoder)
- [X] T007 Implement `src/hermes_memory/ingestion/chatgpt/records.py`: frozen `ExportRecord(raw:
      str, value: object)` and a resumable `RecordScanner` iterator over a text stream, with a
      configurable chunk size and a buffer that at least doubles between decode attempts (research
      R3, data-model `ExportRecord`). Makes T006 pass

**Checkpoint**: an export can be opened and streamed record by record.

---

## Phase 3: User Story 1 - A conversation comes out as the thread the person actually saw (Priority: P1) 🎯 MVP

**Goal**: the graph becomes the displayed thread of turns with role and text.

**Independent Test**: read a synthesized export holding a linear conversation and one with an
edited message and a regenerated answer; each result equals the synthesized visible thread.

- [X] T008 [P] [US1] Write `tests/unit/test_chatgpt_thread.py` first and observe it fail. A linear
      graph gives every message node in root order. A branched graph (edit + regeneration) gives
      exactly root → `current_node`. A missing or unknown `current_node` follows the last-listed
      child at every fork and sets `fallback_branch`. Two roots, a dangling parent or child, a
      parent/children disagreement and a cycle each raise a thread error naming the rule, with no
      node content. Order follows the graph even when message times run backwards (FR-007). Walking
      is iterative, so a 10,000-node linear graph does not hit the recursion limit
- [X] T009 [US1] Implement `src/hermes_memory/ingestion/chatgpt/thread.py`: `validate_graph(mapping)`,
      `choose_leaf(mapping, current_node) -> (leaf, fallback)`, `walk(mapping, leaf) -> tuple[node
      id, ...]` (research R4). Makes T008 pass
- [X] T010 [P] [US1] Write `tests/unit/test_chatgpt_content.py`, part 1, first and observe it fail:
      the `text` type joins string parts with `\n`; the author roles `user`, `assistant`, `system`
      and `tool` map to `Role` (FR-012, FR-013); an empty-text message is kept
- [X] T011 [US1] Implement `src/hermes_memory/ingestion/chatgpt/content.py`, part 1: `turn_of(message)
      -> Message` for the `text` type and role mapping. Makes T010 pass
- [X] T012 [US1] Write `tests/unit/test_chatgpt_conversation.py`, part 1, first and observe it fail.
      `parse_record(value)` on a linear record and on a branched record returns a `Conversation`
      whose messages equal the visible thread (SC-001). Structural nodes, such as the root with
      `message: null`, contribute no turn
- [X] T013 [US1] Implement `src/hermes_memory/ingestion/chatgpt/conversation.py`, part 1:
      `parse_record(value) -> ReadConversation` composing `thread` and `content`, with
      `source=Source.CHATGPT`. Makes T012 pass
- [X] T014 [US1] Write `tests/unit/test_chatgpt_source.py`, part 1, first and observe it fail.
      `ChatGPTExportSource(path)` does no I/O in its constructor. `read()` over a synthesized
      directory and zip yields `SourceConversation`s in export order, across split files. Reading
      twice yields equal results (CS-4, CG-1)
- [X] T015 [US1] Implement `src/hermes_memory/ingestion/chatgpt/source.py`: `ChatGPTExportSource` with
      `source = Source.CHATGPT` and a class-based iterator (not a generator) chaining files →
      `RecordScanner` → `parse_record` (data-model state diagram). Export only
      `ChatGPTExportSource` from `src/hermes_memory/ingestion/chatgpt/__init__.py`, keeping its
      docstring. Makes T014 pass

**Checkpoint**: US1 is demonstrable. A real reading of a synthesized export gives the displayed
threads.

---

## Phase 4: User Story 2 - Identity and time survive the parse (Priority: P1)

**Goal**: native id → `document_id`, real times, title as given, originals exact.

**Independent Test**: a synthesized conversation with known id, title, times and one untimed
message maps exactly, and no time equals the controlled clock.

- [X] T016 [P] [US2] Extend `tests/unit/test_chatgpt_conversation.py` first and observe it fail. The
      identifier is `conversation_id`, falling back to `id`, and `document_id == "chatgpt:" + id`
      (CG-4). `create_time`/`update_time` floats become UTC-aware datetimes. A message with
      `create_time: null` keeps `sent_at is None` in place. A missing or null title gives `title is
      None` (CG-6). No `create_time` → `started_at` = earliest thread message time, with
      `start_from_messages` set. No time anywhere, a NaN, infinite or out-of-range time → error.
      `update_time < create_time` → `last_activity_at is None` with `inconsistent_times` set
      (research R7). With `datetime` patched in the module to a sentinel clock, no yielded time
      equals it (SC-006). An empty conversation (only a root node) is yielded with `messages == ()`
- [X] T017 [US2] Implement identity and time mapping in
      `src/hermes_memory/ingestion/chatgpt/conversation.py`, using
      `datetime.fromtimestamp(value, UTC)` and never reading a clock (research R7). Makes T016 pass
- [X] T018 [P] [US2] Extend `tests/unit/test_chatgpt_source.py` first and observe it fail. Each
      `original.content` equals the record's exact bytes in the written file, encoded as UTF-8, and
      `media_type == "application/json"`. Parsing `original.content` alone through `parse_record`
      yields an equal conversation for every fixture in this file (CG-10, research R8)
- [X] T019 [US2] Build `OriginalPayload` from `ExportRecord.raw` in
      `src/hermes_memory/ingestion/chatgpt/source.py`. Makes T018 pass

**Checkpoint**: US1 + US2 give correct turns with correct identity and time.

---

## Phase 5: User Story 3 - Nothing is dropped without a record (Priority: P1)

**Goal**: every content type has an outcome; every node is accounted for; the account is logged
without content.

**Independent Test**: a conversation with a hidden node, an abandoned branch, a tool call with its
result, an image and an unknown type produces the expected turns, markers and counts.

- [X] T020 [P] [US3] Extend `tests/unit/test_chatgpt_content.py` first and observe it fail: one test
      per row of the research R5 table. `multimodal_text` with string, image, audio,
      audio-transcription and unknown parts. `code`. `execution_output`. `tether_quote`.
      `tether_browsing_display`. `system_error`. `user_editable_context` visible and hidden.
      `thoughts` and `reasoning_recap` omitted as `hidden_reasoning`. An unknown `content_type`
      keeps the message with empty text plus `NonTextPart(kind=OTHER, name=<type>)` and does not
      raise. `metadata.attachments` adds `FILE` markers with names. `is_visually_hidden_from_conversation`
      omits the node as `hidden`, whatever its type
- [X] T021 [US3] Implement the R5 table in `src/hermes_memory/ingestion/chatgpt/content.py`. Makes
      T020 pass
- [X] T022 [P] [US3] Extend `tests/unit/test_chatgpt_content.py` with tool folding first and observe
      it fail (research R6). An assistant message with `recipient="python"` followed by a `tool`
      message named `python` gives one assistant turn with `ToolActivity(name="python",
      request=<code>, result=<output>)` and no separate tool turn. A call with no following tool
      node keeps `result is None`. A call followed by a tool node of a different name keeps
      `result is None`, and that tool node stays a `TOOL` turn. A lone tool node stays a `TOOL` turn
- [X] T023 [US3] Implement `fold_turns(thread_messages) -> (tuple[Message, ...], folded_count)` in
      `src/hermes_memory/ingestion/chatgpt/content.py`. Makes T022 pass
- [X] T024 [P] [US3] Write the `ThreadAccount` tests in `tests/unit/test_chatgpt_conversation.py`
      first and observe them fail. Constructing one whose counts do not sum to the mapping size
      raises. For each fixture in the file, `turns + folded_tool_results + structural + hidden +
      hidden_reasoning + abandoned_branch == len(mapping)` (SC-005).
      `unrecognized_content_types` is sorted and distinct. A conversation with nothing omitted has
      every omission count at zero and every flag false (FR-017)
- [X] T025 [US3] Implement `ThreadAccount` (frozen, fields exactly as data-model.md: `source_id`;
      `turns`, `folded_tool_results`, `structural`, `hidden`, `hidden_reasoning`,
      `abandoned_branch` as "`int` ≥ 0"; `fallback_branch`, `start_from_messages`,
      `inconsistent_times` as `bool`; `unrecognized_content_types: tuple[str, ...]` "sorted,
      distinct"; the sum invariant) and `ReadConversation(conversation, account)` in
      `src/hermes_memory/ingestion/chatgpt/conversation.py`, and have `parse_record` fill them.
      Makes T024 pass
- [X] T026 [P] [US3] Extend `tests/unit/test_chatgpt_source.py` first and observe it fail. Reading
      emits exactly one `chatgpt.conversation.read` event per yielded conversation, carrying the
      fields of contracts/chatgpt-source.md, with `unrecognized_content_types` omitted when empty.
      Capture events with `structlog.testing.capture_logs`. Over a fixture whose title and texts
      contain a unique marker string, no captured event contains that marker anywhere (CG-9,
      Principle V)
- [X] T027 [US3] Emit the event via `hermes_memory.observability.get_logger` in
      `src/hermes_memory/ingestion/chatgpt/source.py` (research R9). Makes T026 pass

**Checkpoint**: every node is accounted for, and the log is content-free.

---

## Phase 6: User Story 4 - One bad conversation does not stop the import (Priority: P2)

**Goal**: per-conversation failures continue; export failures are classified; nothing leaks.

**Independent Test**: an export of three with the second malformed yields two and raises one;
unreachable and non-export paths raise the right kind.

- [X] T028 [P] [US4] Extend `tests/unit/test_chatgpt_source.py` first and observe it fail. Three
      records with the second each of: not an object; no identifier; dangling parent; no time
      anywhere; a text part with an unpaired surrogate escape (a model `ValidationError`). Each
      case yields the first and third and raises exactly one `SourceFormatError` for the second,
      with `subject` set to its id where it has one, and `retryable is False` (SC-004, CG-11).
      A duplicate `conversation_id` yields the first and fails the second, naming the id.
      Invalid JSON after the first record yields the first, then raises `SourceFormatError` with no
      subject, then `StopIteration`. A missing path raises `SourceUnavailable` with `retryable is
      True`. For every raised error, the unique marker string placed in the record's title and
      text appears in neither `str(error)` nor `error.message` (CG-13), and the error is a
      `BoundaryError` (CS-7)
- [X] T029 [US4] Implement failure translation per the research R10 table in
      `src/hermes_memory/ingestion/chatgpt/conversation.py` and
      `src/hermes_memory/ingestion/chatgpt/source.py`: a seen-id set per `read()`; `ValidationError`
      rendered from `error["type"]` and `error["loc"]` only; every cause chained with `from`; after
      an export-level failure the iterator is exhausted. Makes T028 pass

**Checkpoint**: §18 holds at this boundary.

---

## Phase 7: User Story 5 - The source is proved by the contract it implements (Priority: P2)

**Goal**: #9's suite passes against the real parser with nothing skipped.

**Independent Test**: `uv run pytest tests/contracts/test_chatgpt_source_passes_the_contract.py -rs`
reports 7 passed and 0 skipped.

- [X] T030 [US5] Write `tests/contracts/test_chatgpt_source_passes_the_contract.py` and run it:
      `class TestChatGPTExportSource(ConversationSourceContract)`, with an autouse fixture storing
      `tmp_path` on the instance. `make_source` writes `from_conversation(...)` records with
      `write_directory`. `make_source_with_one_unreadable` gives the second record a dangling
      parent. `make_unreachable_source` points at `tmp_path / "missing.zip"`. Add a test that
      fails if any contract test in the class is skipped, by checking the three hooks return non-`None`
      (SC-002). If any rule fails, fix the source in the relevant module rather than the harness,
      each fix preceded by a unit test reproducing it

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T031 Write `tests/unit/test_chatgpt_streaming.py` and observe it pass only with streaming in
      place (research R3, SC-007, CG-14). With `tracemalloc`, the peak while fully iterating a
      synthesized export of 200 conversations and of 2,000 conversations, each of comparable size,
      differs by less than a factor of 3. Mark nothing as slow unless the whole unit suite exceeds
      its current duration by more than 10 seconds. To confirm the test bites, temporarily swap the
      scanner for `json.load` and observe it fail; do not commit that swap
- [X] T032 [P] Add `ingestion.chatgpt` to the `FILLED_BOUNDARIES` docstring in
      `tests/structure/test_module_layout.py`, naming 008-chatgpt-export-source and stating that
      `ingestion` already covers it by prefix. No code change to the set
- [X] T033 [P] Update `src/hermes_memory/ingestion/__init__.py` docstring: #10's ChatGPT
      implementation lives in `ingestion.chatgpt` and is deliberately not re-exported here (T002)
- [X] T034 Run the whole [quickstart.md](./quickstart.md) sections 1–4
      (`uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`), and record the
      commands and results for the pull request

---

## Dependencies & Execution Order

- **Setup (T001–T002)** → **Foundational (T003–T007)** → user stories.
- **US1 (T008–T015)** is required by all later stories: they extend its modules.
- **US2 (T016–T019)** and **US3 (T020–T027)** depend on US1 only. They touch the same files, so do
  them sequentially: US2, then US3.
- **US4 (T028–T029)** depends on US1–US3, because its fixtures use times and accounting.
- **US5 (T030)** depends on US1–US4, because CS-5 needs US4's failure handling.
- **Polish (T031–T034)** last.

Within a phase, every test task precedes its implementation task, and the test is observed failing
before the implementation starts.

## Parallel Opportunities

- T001 and T002.
- T004 and T006: different modules, both depending only on T003's writer for their fixtures, if
  they use it.
- T008 and T010: `thread` and `content` are independent pure modules.
- T032 and T033.

```text
# After T003:
T004 test_chatgpt_export.py   ║  T006 test_chatgpt_records.py
T005 export.py                ║  T007 records.py

# After T007:
T008 test_chatgpt_thread.py   ║  T010 test_chatgpt_content.py
T009 thread.py                ║  T011 content.py
```

## Implementation Strategy

**MVP = Phases 1–3 (US1).** Real threads come out of a real export. Stop and validate there.
Then add US2 for identity and time, which makes it safe to retain. Then US3, so nothing is silently
lost. Then US4 for robustness, and US5 to prove the contract. Commit after each checkpoint, with
tests green and `ruff` clean.
